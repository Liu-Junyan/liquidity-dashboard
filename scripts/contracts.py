"""Offline schema-v2 snapshot validation, separate from schema-v1 demo builds.

This validates the serialized base contract. scripts.assemble additionally
validates activation, reconciles content hashes/calculations, and promotes atomically.
"""
import math
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

if __package__:
    from .policies import COMPARISONS, POLICY_VERSION
else:
    from policies import COMPARISONS, POLICY_VERSION

SCHEMA_VERSION = 2
HASH = re.compile(r'[0-9a-f]{64}\Z')
COMMIT = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def iso_date(value):
    require(isinstance(value, str), 'Observation dates must be ISO strings')
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError('Invalid ISO observation date') from None
    require(parsed.isoformat() == value, 'Dates must use YYYY-MM-DD')
    return parsed


def utc_time(value):
    require(isinstance(value, str), 'Operational timestamps must be UTC strings')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('Invalid UTC operational timestamp') from None
    require('T' in value and parsed.utcoffset() == timedelta(0), 'Operational timestamps must include UTC timezone')
    return parsed


def validate_points(points):
    require(isinstance(points, list), 'Series must be arrays')
    previous = None
    for point in points:
        require(isinstance(point, dict) and set(point) == {'date', 'value'}, 'Expected date/value observation')
        current = iso_date(point['date'])
        require(previous is None or current > previous, 'Observation dates must be sorted and unique')
        value = point['value']
        require(value is None or (type(value) in (int, float) and math.isfinite(value)),
                'Observation values must be finite numbers or null')
        previous = current


def validate_reference(value):
    require(isinstance(value, str) and bool(value.strip()), 'Source reference required')
    # Public references never carry request queries, fragments or credentials.
    if '://' in value:
        url = urlsplit(value)
        require(url.scheme == 'https' and bool(url.hostname) and not
                (url.username or url.password or url.query or url.fragment), 'Source reference must be a sanitized HTTPS URL')


def validate_request(params):
    """Only persist harmless FRED request parameters, never full request URLs."""
    require(isinstance(params, dict), 'Request parameters must be an object')
    allowed = {'series_id', 'file_type', 'units', 'observation_start', 'observation_end',
               'sort_order', 'limit', 'offset', 'realtime_start', 'realtime_end'}
    require(set(params) <= allowed, 'Unknown or credential-bearing request parameter')
    for key, value in params.items():
        if key == 'series_id':
            require(isinstance(value, str) and re.fullmatch(r'[A-Z0-9_]+', value), 'Invalid provider series ID')
        elif key == 'units':
            require(value in ('lin', 'chg'), 'Unsupported request transformation')
        elif key == 'file_type':
            require(value == 'json', 'Only JSON requests supported')
        elif key == 'sort_order':
            require(value == 'asc', 'Requests must preserve ascending history')
        elif key in ('limit', 'offset'):
            require(type(value) is int and value >= (1 if key == 'limit' else 0), 'Invalid pagination parameter')
        else:
            iso_date(value)


def validate_snapshot(catalog, observations, manifest):
    """Raise ValueError on malformed or inconsistent production artifacts."""
    try:
        _validate_snapshot(catalog, observations, manifest)
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError(f'Malformed production snapshot: {error}') from None


def _validate_snapshot(catalog, observations, manifest):
    for document in (catalog, observations, manifest):
        require(isinstance(document, dict) and type(document.get('schemaVersion')) is int
                and document['schemaVersion'] == SCHEMA_VERSION, 'Expected schema version 2')
        require(isinstance(document.get('snapshotId'), str) and
                bool(SLUG.fullmatch(document['snapshotId'])), 'Invalid snapshot ID')
    require(catalog['snapshotId'] == observations['snapshotId'] == manifest['snapshotId'], 'Snapshot ID mismatch')
    dataset = catalog['dataset']
    require(dataset['mode'] == 'production' and dataset['isDemo'] is False, 'Expected production dataset')
    generated = utc_time(dataset['generatedAt'])
    require(dataset['generatedAt'] == manifest['generatedAt'], 'Generation time mismatch')
    require(COMMIT.fullmatch(manifest['sourceInputCommit']) is not None, 'Invalid source-input commit')
    # Slice 6 only extends policies/calculations; earlier policy versions remain
    # valid for exact-byte rollback of their published snapshots.
    require(manifest['policyVersion'] in {'4', '5', '6', POLICY_VERSION}, 'Unsupported policy version')
    categories, indicators, series = catalog['categories'], catalog['indicators'], observations['series']
    require(isinstance(categories, list) and len(categories) == 4, 'Expected four research layers')
    require(isinstance(indicators, list) and isinstance(series, dict), 'Invalid catalog/series containers')
    ids = [item['id'] for item in categories + indicators]
    require(all(isinstance(identifier, str) and SLUG.fullmatch(identifier) for identifier in ids)
            and len(ids) == len(set(ids)), 'IDs must be unique slugs across categories and indicators')
    category_ids = {item['id'] for item in categories}
    for category in categories:
        require(bool(category['name']), 'Category name required')
    displayed = {item['id'] for item in indicators}
    require(set(series) == displayed, 'Observation IDs must match displayed indicators; source-only inputs stay hidden')
    source_ids = [item['seriesId'] for item in indicators]
    require(len(source_ids) == len(set(source_ids)), 'Conflicting displayed series ownership')
    dates = []
    for item in indicators:
        require(SLUG.fullmatch(item['seriesId']) is not None, 'Invalid series ID')
        require(item['categoryId'] in category_ids, 'Unknown category')
        require(bool(item['name']) and bool(item['explanation']), 'Name and reviewed explanation required')
        require(item['availability'] in {'numeric', 'empty', 'nonnumeric'}, 'Invalid availability')
        frequency = item['nativeFrequency']
        require(frequency in COMPARISONS or (frequency is None and item['availability'] != 'numeric'),
                'Unknown native frequency')
        comparison = COMPARISONS[frequency] if frequency is not None else COMPARISONS['irregular']
        require(item['comparisonPolicy'] == comparison, 'Comparison policy mismatch')
        require(isinstance(item['unit'], str) and bool(item['unit']), 'Output unit required (or pending)')
        require(isinstance(item['sources'], list), 'Sources must be an array')
        for reference in item['sources']:
            validate_reference(reference)
        points = series[item['id']]
        validate_points(points)
        numeric = any(point['value'] is not None for point in points)
        require((item['availability'] == 'numeric') == numeric, 'Availability disagrees with numeric history')
        require(item['availability'] != 'nonnumeric' or not points, 'Nonnumeric indicators cannot own observations')
        dates.extend(point['date'] for point in points)
    require(dataset['observationStart'] == (min(dates) if dates else None) and
            dataset['observationEnd'] == (max(dates) if dates else None), 'Dataset bounds must summarize actual observations')
    hashes, provenance, outcomes = manifest['inputHashes'], manifest['provenance'], manifest['outcomes']
    require(all(isinstance(mapping, dict) for mapping in (hashes, provenance, outcomes)), 'Invalid manifest maps')
    require(set(provenance) == set(outcomes), 'Each activated series needs provenance and an outcome')
    require(set(hashes) <= set(provenance), 'Input hash has no provenance')
    for identifier, digest in hashes.items():
        require(SLUG.fullmatch(identifier) and HASH.fullmatch(digest), 'Invalid input hash')
    for identifier, record in provenance.items():
        require(SLUG.fullmatch(identifier) and HASH.fullmatch(record['specHash']), 'Invalid source identity')
        require(record['method'] in ('automatic', 'manual', 'derived'), 'Invalid provenance ownership')
        require(bool(record['sourceUnit']) and bool(record['normalizedUnit']), 'Provenance units required')
        if record['method'] == 'derived':
            used, missing = record['inputHashes'], record['missingInputs']
            require(identifier not in hashes and isinstance(used, dict) and isinstance(missing, list)
                    and (used or missing), 'Derived provenance requires input hashes or explicit missing inputs')
            require(len(missing) == len(set(missing)) and not (set(used) & set(missing)), 'Conflicting derived inputs')
            require(all(key in hashes and hashes[key] == digest for key, digest in used.items()), 'Derived input hash mismatch')
            require(all(key in outcomes and outcomes[key]['status'] == 'failed' and key not in hashes for key in missing),
                    'Missing derived inputs must identify failed sources without history')
            require(bool(record['calculation']), 'Calculation policy required')
            require(outcomes[identifier]['status'] == 'derived', 'Derived outcome ownership mismatch')
        else:
            validate_reference(record['sourceReference'])
            require(record['requestParameters'] == {} or record['method'] == 'automatic', 'Manual inputs cannot own requests')
            validate_request(record['requestParameters'])
            require(record['transformation'] == record['requestParameters'].get('units', 'lin'), 'Transformation provenance mismatch')
            if record['method'] == 'automatic':
                require(bool(record['providerUnits']), 'Original provider units required')
                require({'series_id', 'units'} <= set(record['requestParameters']), 'Automatic request identity required')
                allowed = {'updated', 'unchanged', 'retained', 'failed'}
            else:
                allowed = {'imported', 'unchanged', 'failed'}
            require(outcomes[identifier]['status'] in allowed, 'Outcome ownership mismatch')
            require(identifier in hashes or outcomes[identifier]['status'] == 'failed', 'Validated input hash required')
        outcome = outcomes[identifier]
        if outcome['latestObservationDate'] is not None:
            iso_date(outcome['latestObservationDate'])
        times = {key: utc_time(outcome[key]) if outcome[key] is not None else None for key in
                 ('lastAttempt', 'lastSuccessfulCheck', 'lastDataChange')}
        require(all(time is None or time <= generated for time in times.values()), 'Operational timestamp after generation')
        if outcome['status'] == 'failed':
            require(identifier not in hashes and outcome['latestObservationDate'] is None
                    and times['lastSuccessfulCheck'] is None and times['lastDataChange'] is None,
                    'Failed first-time input cannot claim validated history')
        if record['method'] == 'automatic':
            attempt, success, change = (times[key] for key in ('lastAttempt', 'lastSuccessfulCheck', 'lastDataChange'))
            require(attempt is not None, 'Automatic input requires last attempt time')
            require(success is None or success <= attempt, 'Check time after attempt')
            require(change is None or (success is not None and change <= success), 'Change time after successful check')
            if outcome['status'] in {'updated', 'unchanged'}:
                require(success == attempt, 'Successful checks must advance check time')
            if outcome['status'] in {'retained', 'failed'}:
                require(success is None or success < attempt, 'Failed attempts cannot advance successful check')
            if outcome['status'] == 'retained':
                require(success is not None, 'Retained history requires a previous successful check')
    for item in indicators:
        if series[item['id']]:
            require(item['seriesId'] in provenance, 'Observed series requires provenance')
            record = provenance[item['seriesId']]
            if record['method'] == 'derived' and record['missingInputs']:
                require(not any(point['value'] is not None for point in series[item['id']]),
                        'Missing derived input cannot produce numeric observations')
            require(item['unit'] == record['normalizedUnit'], 'Catalog unit disagrees with normalized provenance')
            require(outcomes[item['seriesId']]['latestObservationDate'] == series[item['id']][-1]['date'],
                    'Latest observation date disagrees with history')
    summary = manifest['revisionSummary']
    require(isinstance(summary, dict) and set(summary) == {'added', 'revised', 'removed'}, 'Revision summary required')
    require(all(type(value) is int and value >= 0 for value in summary.values()), 'Invalid revision counts')
