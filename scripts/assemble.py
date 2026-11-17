"""Assemble the activated pilot from saved inputs, offline; never deploy or collect."""
import argparse
import calendar
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.artifacts import promote_snapshot
from scripts.catalog import build_production_catalog
from scripts.collect import identity, validate_cached
from scripts.contracts import require, utc_time, iso_date, validate_snapshot, validate_reference
from scripts.derive import derive
from scripts.import_manual import git, import_manual, validate_owner
from scripts.normalize import content_hash, normalize
from scripts.notices import PUBLISHER, notices_for
from scripts.policies import (ACTIVE_SERIES, POLICIES, POLICY_VERSION, FRED_OBSERVATION_START,
                              specification_hash, validate_activation)
from scripts.providers.fred import validate_metadata
from scripts.registry import ROOT, load_registry


def snapshot_identity(documents):
    payload = [{key: value for key, value in document.items() if key != 'snapshotId'} for document in documents]
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return 'production-' + hashlib.sha256(encoded.encode()).hexdigest()


def validate_assembled_snapshot(catalog, observations, manifest):
    try:
        _validate_assembled_snapshot(catalog, observations, manifest)
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError(f'Malformed assembled snapshot: {error}') from None


def _validate_assembled_snapshot(catalog, observations, manifest):
    validate_snapshot(catalog, observations, manifest)
    require(catalog['snapshotId'] == snapshot_identity((catalog, observations, manifest)),
            'Snapshot content digest mismatch')
    require(catalog['dataset']['publisher'] == PUBLISHER, 'Publisher notice identity mismatch')
    require(set(manifest['normalizedInputs']) == set(manifest['inputHashes']), 'Normalized input membership mismatch')
    for identifier, points in manifest['normalizedInputs'].items():
        require(content_hash(points) == manifest['inputHashes'][identifier], 'Normalized input hash mismatch')
    derived_registry = {'series': {key: {
        'update_method': 'derived', 'source_unit': record['sourceUnit'], 'normalized_unit': record['normalizedUnit'],
        'input_series_ids': sorted(set(record['inputHashes']) | set(record['missingInputs'])),
        'formula': record['calculation'],
    } for key, record in manifest['provenance'].items() if record['method'] == 'derived'}}
    calculated = derive(derived_registry, manifest['normalizedInputs'], derived_registry['series'])
    for item in catalog['indicators']:
        require(item['isDemo'] is False and type(item['inputAvailable']) is bool, 'Invalid production display mode')
        unit = item['displayUnit']
        require(unit['kind'] in {'amount', 'rate', 'spread', 'ratio', 'index', 'price', 'count', 'multiple', 'scalar', 'unquantified'}
                and isinstance(unit['label'], str) and bool(unit['label'])
                and type(unit['precision']) is int and 0 <= unit['precision'] <= 6, 'Invalid display unit')
        require(item['inputAvailable'] == (item['seriesId'] in manifest['provenance']), 'Activation/display mismatch')
        require(item['inputAvailable'] or not observations['series'][item['id']], 'Inactive series owns observations')
        expected = (calculated[item['seriesId']]['observations'] if item['seriesId'] in calculated else
                    manifest['normalizedInputs'].get(item['seriesId'], []))
        require(observations['series'][item['id']] == expected, 'Displayed history disagrees with normalized inputs/calculation')
        if item['source']['url'] is not None:
            validate_reference(item['source']['url'])
        for notice in item['notices']:
            require(isinstance(notice['text'], str) and bool(notice['text']), 'Source notice text required')
            validate_reference(notice['url'])
        if item['inputAvailable']:
            for notice in notices_for(item['seriesId'], catalog['dataset']['generatedAt'][:4]):
                require(notice in item['notices'], 'Required source notice missing')


def source_state(repo, commit):
    # A local implementation preview can have uncommitted code. Record exact
    # bytes and flag it, rather than claiming HEAD contains those changes.
    paths = sorted([*repo.glob('scripts/**/*.py'), repo / 'data/registry.csv',
                    repo / 'data/source-reviews.json', repo / 'data/categories.json'])
    hashes, modified = {}, []
    for path in paths:
        name = path.relative_to(repo).as_posix()
        data = path.read_bytes()
        hashes[name] = hashlib.sha256(data).hexdigest()
        try:
            committed = git(repo, 'show', f'{commit}:{name}').encode()
        except ValueError:
            committed = None
        if data != committed:
            modified.append(name)
    return hashes, modified


def validate_source_dates(points, rule):
    dates = [iso_date(point['date']) for point in points]
    if rule == 'wednesday-level':
        require(all(day.weekday() == 2 for day in dates), 'Invalid weekly observation date')
    elif rule in {'month-start', 'quarter-start'}:
        require(all(day.day == 1 and (rule != 'quarter-start' or day.month in {1, 4, 7, 10})
                    for day in dates), 'Invalid source period start date')
    elif rule in {'month-end', 'quarter-end'}:
        require(all(day.day == calendar.monthrange(day.year, day.month)[1]
                    and (rule != 'quarter-end' or day.month in {3, 6, 9, 12}) for day in dates),
                'Invalid source period end date')
    elif rule == 'day-of-month':
        require(len({day.day for day in dates}) <= 1, 'Inconsistent source day-of-month')


def assemble(repo=ROOT, *, selected=ACTIVE_SERIES, now=None):
    repo = Path(repo)
    registry = load_registry(repo / 'data/registry.csv')
    reviews = json.loads((repo / 'data/source-reviews.json').read_text(encoding='utf-8'))
    order = validate_activation(registry, selected, reviews=reviews)
    now = now or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    utc_time(now)
    commit = git(repo, 'rev-parse', 'HEAD').strip()
    normalized, histories, provenance, outcomes, diagnostics = {}, {}, {}, {}, {}
    revisions = dict.fromkeys(('added', 'revised', 'removed'), 0)
    manual_ids = [key for key in order if POLICIES[key].method == 'manual']
    manual = import_manual(repo) if manual_ids else None
    if manual:
        for audit in manual['audit']:
            for identifier in manual_ids:
                for key in revisions:
                    revisions[key] += len(audit['changes'].get(identifier, {}).get(key, []))
    for identifier in order:
        entry, policy = registry['series'][identifier], POLICIES[identifier]
        common = {'specHash': specification_hash(entry), 'method': policy.method,
                  'sourceUnit': entry['source_unit'], 'normalizedUnit': entry['normalized_unit']}
        if policy.method == 'derived':
            continue
        validate_owner(registry, identifier, policy.method)
        if policy.method == 'automatic':
            path = repo / f'data/automatic/{identifier}.json'
            require(not path.is_symlink() and not path.parent.is_symlink(), 'Automatic inputs cannot be symlinks')
            require(path.is_file(), f'{identifier}: saved automatic input required; run collect.py first')
            record = json.loads(path.read_text(encoding='utf-8'))
            validate_cached(record)
            require(all(record.get(key) == value for key, value in identity(identifier, entry, policy).items()),
                    f'{identifier}: incompatible stored source; successful refetch required')
            if record['sourceHash'] is not None:
                # Cached metadata omits the full frequency label; verify every
                # stored weekly date below instead of inventing that field.
                validate_metadata(record['metadata'], entry, policy, cached=True)
                require(record['requestParameters'].get('observation_start') == FRED_OBSERVATION_START,
                        f'{identifier}: incompatible collection window; refetch required')
                validate_source_dates(record['observations'], policy.date_rule)
                normalized[identifier] = normalize(entry, record['observations'])
            outcomes[identifier] = copy.deepcopy(record['outcome'])
            provenance[identifier] = common | {
                'sourceReference': entry['source_reference'], 'sourceHash': record['sourceHash'],
                'providerUnits': record['metadata']['units'] if record['metadata'] else entry['source_unit'],
                'requestParameters': record['requestParameters'], 'transformation': policy.request_units}
            diagnostics[identifier] = {key: record.get(key) for key in ('error', 'freshness', 'revisionSummary')}
            for key in revisions:
                count = record['revisionSummary'][key]
                require(type(count) is int and count >= 0, 'Invalid automatic revision count')
                revisions[key] += count
        else:
            require(identifier in manual['series'], f'{identifier}: committed manual input required')
            record = manual['series'][identifier]
            require(record['specHash'] == common['specHash'], f'{identifier}: manual definition differs from committed input')
            validate_source_dates(record['observations'], policy.date_rule)
            # Never silently ignore an uncommitted CSV correction.
            path = repo / f'data/manual/{identifier}.csv'
            require(not path.is_symlink() and not path.parent.is_symlink(), 'Manual input cannot be a symlink')
            require(path.read_text(encoding='utf-8') == git(repo, 'show', f'{commit}:data/manual/{identifier}.csv'),
                    f'{identifier}: commit and audit manual edits before assembly')
            normalized[identifier] = normalize(entry, record['observations'])
            provenance[identifier] = common | {'sourceReference': entry['source_reference'],
                'sourceHash': content_hash(record['observations']), 'requestParameters': {}, 'transformation': 'lin'}
            outcomes[identifier] = {'status': 'imported',
                'latestObservationDate': record['observations'][-1]['date'] if record['observations'] else None,
                'lastAttempt': None, 'lastSuccessfulCheck': None, 'lastDataChange': None}
        histories[identifier] = normalized.get(identifier, [])
    derived = derive(registry, normalized, {key for key in order if POLICIES[key].method == 'derived'})
    for identifier, record in derived.items():
        entry = registry['series'][identifier]
        histories[identifier] = record['observations']
        provenance[identifier] = {'method': 'derived', 'specHash': specification_hash(entry),
            'sourceUnit': entry['source_unit'], 'normalizedUnit': entry['normalized_unit'],
            **{key: record[key] for key in ('inputHashes', 'missingInputs', 'calculation')}}
        outcomes[identifier] = {'status': 'derived',
            'latestObservationDate': record['observations'][-1]['date'] if record['observations'] else None,
            'lastAttempt': None, 'lastSuccessfulCheck': None, 'lastDataChange': None}
    categories = json.loads((repo / 'data/categories.json').read_text(encoding='utf-8'))
    catalog, series = build_production_catalog(registry, categories, histories, reviews, now, outcomes)
    source_hashes, modified = source_state(repo, commit)
    observations = {'schemaVersion': 2, 'series': series}
    manifest = {'schemaVersion': 2, 'generatedAt': now, 'sourceInputCommit': commit,
        'sourceFileHashes': source_hashes, 'modifiedSourceFiles': modified,
        'policyVersion': POLICY_VERSION, 'inputHashes': {key: content_hash(value) for key, value in normalized.items()},
        'normalizedInputs': normalized, 'provenance': provenance, 'outcomes': outcomes,
        'revisionSummary': revisions, 'diagnostics': diagnostics}
    documents = (catalog, observations, manifest)
    snapshot_id = snapshot_identity(documents)
    for document in documents:
        document['snapshotId'] = snapshot_id
    validate_assembled_snapshot(*documents)
    return documents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/snapshot')
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        require(output == ROOT / 'data/snapshot' or not output.is_relative_to(ROOT),
                'Use data/snapshot or an external output directory; never overwrite source inputs')
        documents = assemble()
        promote_snapshot(output, documents)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Assembly failed: {error}\n')
    print(f'Assembled {documents[0]["snapshotId"]} to {output}')
    print('Local production snapshot only. Scheduling and publication remain disabled.')
    if documents[2]['modifiedSourceFiles']:
        print('Local source changes recorded in manifest; commit source before a release assembly.')


if __name__ == '__main__':
    main()
