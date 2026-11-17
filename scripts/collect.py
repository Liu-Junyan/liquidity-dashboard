"""Refresh complete FRED pilot histories without publishing or enabling production.

Run python3 scripts/collect.py. FRED_API_KEY comes from the environment or the
ignored local .env. Only the FRED_API_KEY setting is accepted.
"""
import argparse
import copy
import json
import os
import shlex
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.contracts import iso_date, utc_time, validate_points, validate_reference, validate_request
from scripts.derive import derive
from scripts.import_manual import validate_owner
from scripts.normalize import content_hash, normalize
from scripts.policies import (FRESHNESS_DAYS, PILOT_SERIES, POLICIES, POLICY_VERSION,
                              specification_hash, validate_policies)
from scripts.providers.fred import CollectionError, FredClient
from scripts.registry import ROOT, load_registry


def load_api_key(env_file=ROOT / '.env'):
    if os.environ.get('FRED_API_KEY'):
        return os.environ['FRED_API_KEY']
    values = {}
    if Path(env_file).is_file():
        for line in Path(env_file).read_text(encoding='utf-8').splitlines():
            name, separator, raw = line.removeprefix('export ').partition('=')
            if separator and name.strip() == 'FRED_API_KEY':
                try:
                    parts = shlex.split(raw, comments=True)
                except ValueError:
                    raise ValueError('Invalid FRED key setting in local .env') from None
                if len(parts) == 1:
                    values[name.strip()] = parts[0]
    key = values.get('FRED_API_KEY')
    if not key:
        raise ValueError('Set FRED_API_KEY in the environment or local .env')
    return key


def identity(identifier, entry, policy):
    return {'seriesId': identifier, 'specHash': specification_hash(entry),
            'provider': entry['provider'], 'providerSeriesId': entry['provider_series_id'],
            'sourceUnit': entry['source_unit'], 'normalizedUnit': entry['normalized_unit'],
            'sourceReference': entry['source_reference'], 'transformation': policy.request_units}


def revision_counts(previous, current):
    old = {point['date']: point['value'] for point in previous}
    new = {point['date']: point['value'] for point in current}
    return {'added': len(new.keys() - old.keys()), 'removed': len(old.keys() - new.keys()),
            'revised': sum(old[day] != new[day] for day in old.keys() & new.keys())}


def freshness(identifier, points, now):
    latest = next((point['date'] for point in reversed(points) if point['value'] is not None), None)
    age = (utc_time(now).date() - iso_date(latest)).days if latest else None
    threshold = FRESHNESS_DAYS[identifier]
    return {'latestNumericDate': latest, 'ageDays': age, 'maxAgeDays': threshold,
            'status': 'no-numeric-data' if age is None else 'stale' if age > threshold else 'current'}


def validate_cached(record):
    """Reject corrupted local inputs before using their history or timestamps."""
    try:
        if type(record['schemaVersion']) is not int or record['schemaVersion'] != 1:
            raise ValueError('Unsupported automatic input version')
        points, outcome = record['observations'], record['outcome']
        validate_points(points)
        validate_reference(record['sourceReference'])
        validate_request(record['requestParameters'])
        attempt = utc_time(outcome['lastAttempt'])
        if outcome['status'] == 'failed':
            if points or any(record[key] is not None for key in ('sourceHash', 'metadata')) or any(
                    outcome[key] is not None for key in
                    ('lastSuccessfulCheck', 'lastDataChange', 'latestObservationDate')):
                raise ValueError('Failed automatic input cannot claim history')
        else:
            if (outcome['status'] not in {'updated', 'unchanged', 'retained'} or not points
                    or record['sourceHash'] != content_hash(points)
                    or outcome['latestObservationDate'] != points[-1]['date']
                    or not utc_time(outcome['lastDataChange']) <= utc_time(outcome['lastSuccessfulCheck']) <= attempt
                    or record['metadata']['id'] != record['providerSeriesId']
                    or record['metadata']['observation_start'] != points[0]['date']
                    or record['metadata']['observation_end'] != points[-1]['date']):
                raise ValueError('Invalid automatic input history, hash, or timestamps')
            success = utc_time(outcome['lastSuccessfulCheck'])
            if ((outcome['status'] in {'updated', 'unchanged'} and success != attempt)
                    or (outcome['status'] == 'retained' and success >= attempt)):
                raise ValueError('Invalid automatic input check transition')
        if (record['requestParameters']['series_id'] != record['providerSeriesId']
                or record['requestParameters']['units'] != record['transformation']):
            raise ValueError('Automatic request identity mismatch')
    except (KeyError, TypeError, AttributeError):
        raise ValueError('Malformed automatic input') from None


def collect(registry, client, *, previous=None, selected=PILOT_SERIES, now=None):
    """Build an in-memory candidate. Failures retain only compatible history."""
    order = validate_policies(registry, selected, require_implementations=True)
    now = now or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    utc_time(now)
    previous = previous or {}
    records, normalized = {}, {}
    for identifier in order:
        if registry['series'][identifier]['update_method'] == 'derived':
            continue
        entry = validate_owner(registry, identifier, 'automatic')
        validate_reference(entry['source_reference'])
        policy = POLICIES[identifier]
        current_identity = identity(identifier, entry, policy)
        old = previous.get(identifier)
        if old is not None:
            validate_cached(old)
            if utc_time(old['outcome']['lastAttempt']) >= utc_time(now):
                raise ValueError(f'{identifier}: collection time must follow the previous attempt')
        compatible = old is not None and all(old.get(key) == value for key, value in current_identity.items())
        retained = old if compatible and old['outcome']['status'] != 'failed' else None
        record = {'schemaVersion': 1, 'policyVersion': POLICY_VERSION, **current_identity}
        try:
            fetched = client.fetch(entry, policy)
            points = fetched['observations']
            validate_points(points)
            if not points:
                raise CollectionError('FRED returned an empty history')
            changes = revision_counts(retained['observations'] if retained else [], points)
            changed = retained is None or any(changes.values())
            record.update(fetched, sourceHash=content_hash(points), revisionSummary=changes,
                          error=None, outcome={
                              'status': 'updated' if changed else 'unchanged',
                              'latestObservationDate': points[-1]['date'], 'lastAttempt': now,
                              'lastSuccessfulCheck': now,
                              'lastDataChange': now if changed else retained['outcome']['lastDataChange']})
        except CollectionError as error:
            if old is not None and not compatible:
                raise ValueError(f'{identifier}: incompatible stored source; full refetch must succeed before reuse') from None
            if retained:
                record = copy.deepcopy(retained)
                record['outcome'].update(status='retained', lastAttempt=now)
            else:
                record.update(observations=[], metadata=None, sourceHash=None,
                              requestParameters={'series_id': entry['provider_series_id'],
                                                 'file_type': 'json', 'units': policy.request_units},
                              outcome={'status': 'failed', 'latestObservationDate': None,
                                       'lastAttempt': now, 'lastSuccessfulCheck': None, 'lastDataChange': None})
            record.update(error=str(error), revisionSummary=dict.fromkeys(('added', 'revised', 'removed'), 0))
        record['freshness'] = freshness(identifier, record['observations'], now)
        validate_cached(record)
        records[identifier] = record
        if record['sourceHash'] is not None:
            normalized[identifier] = normalize(entry, record['observations'])
    derived = derive(registry, normalized, {key for key in order if POLICIES[key].method == 'derived'})
    return {'automatic': records, 'normalized': normalized, 'derived': derived}


def refresh(repo, client, *, selected=PILOT_SERIES, now=None):
    """Stage the candidate, then atomically replace each automatic input file.

    This is not a publishable snapshot. Slice 4 assembles/promotes that as one unit.
    """
    repo = Path(repo)
    registry = load_registry(repo / 'data/registry.csv')
    order = validate_policies(registry, selected, require_implementations=True)
    directory = repo / 'data/automatic'
    if directory.is_symlink():
        raise ValueError('Automatic input directory cannot be a symlink')
    previous = {}
    for identifier in order:
        if POLICIES[identifier].method == 'automatic':
            validate_owner(registry, identifier, 'automatic')
            path = directory / f'{identifier}.json'
            if path.is_symlink():
                raise ValueError('Automatic input files cannot be symlinks')
            if path.exists():
                previous[identifier] = json.loads(path.read_text(encoding='utf-8'))
    result = collect(registry, client, previous=previous, selected=selected, now=now)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.collect-', dir=directory) as staging:
        for identifier, record in result['automatic'].items():
            (Path(staging) / f'{identifier}.json').write_text(
                json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
        for identifier in result['automatic']:
            name = f'{identifier}.json'
            os.replace(Path(staging) / name, directory / name)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--series', nargs='+', choices=sorted(PILOT_SERIES), default=sorted(PILOT_SERIES),
                        help='Candidate series; derived series require their inputs explicitly')
    args = parser.parse_args()
    try:
        result = refresh(ROOT, FredClient(load_api_key()), selected=args.series)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Collection failed: {error}\n')
    for identifier, record in result['automatic'].items():
        print(f'{identifier}: {record["outcome"]["status"]}, {len(record["observations"])} observations; '
              f'changes={record["revisionSummary"]}; freshness={record["freshness"]["status"]}'
              + (f'; {record["error"]}' if record['error'] else ''))
    for identifier, record in result['derived'].items():
        print(f'{identifier}: recomputed {len(record["observations"])} observations')
    print('Automatic candidate inputs saved; production activation and publication remain disabled.')
    if any(record['outcome']['status'] in {'failed', 'retained'} for record in result['automatic'].values()):
        parser.exit(1, 'One or more FRED requests failed; compatible previous history retained where available.\n')


if __name__ == '__main__':
    main()
