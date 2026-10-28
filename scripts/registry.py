"""Validate the editable CSV source registry and optionally export keyed JSON.

This registers specifications only: no collection, formula execution, or site writes.
"""
import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / 'data/registry.csv'
FIELDS = (
    'series_id', 'indicator_id', 'category', 'name', 'status', 'update_method',
    'provider', 'source_reference', 'provider_series_id', 'native_frequency',
    'source_unit', 'normalized_unit', 'comparison_rules',
    'input_series_ids', 'formula', 'notes',
)
STATUSES = {'draft', 'ready', 'unquantified', 'unavailable'}
METHODS = {'automatic', 'manual', 'derived'}
FREQUENCIES = {'daily', 'weekly', 'monthly', 'quarterly', 'annual', 'irregular'}
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')


def load_registry(path=DEFAULT_REGISTRY):
    """Allow incomplete drafts; reject invalid filled fields and dependency graphs."""
    mapped = set()
    series = {}
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or set(headers) != set(FIELDS):
            raise ValueError('CSV headers must contain each documented field exactly once')
        for line, raw in enumerate(reader, 2):
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError(f'Row {line}: wrong column count; quote text containing commas')
            row = {key: value.strip() for key, value in raw.items()}
            if not any(row.values()):
                continue
            row['status'] = row['status'] or 'draft'
            identifier = row['series_id']

            def require(condition, message):
                if not condition:
                    raise ValueError(f'Row {line} ({identifier or "no series_id"}): {message}')

            require(bool(SLUG.fullmatch(identifier)), 'series_id must be a stable lowercase ASCII slug')
            require(identifier not in series, 'duplicate series_id / conflicting ownership')
            require(bool(row['name']), 'name is required')
            require(row['status'] in STATUSES, 'status must be draft, ready, unquantified, or unavailable')
            require(not row['update_method'] or row['update_method'] in METHODS, 'choose exactly one update_method: automatic, manual, or derived')
            require(not row['native_frequency'] or row['native_frequency'] in FREQUENCIES, 'unknown native_frequency')
            indicator_id = row['indicator_id']
            if indicator_id:
                require(bool(SLUG.fullmatch(indicator_id)), 'indicator_id must be a stable lowercase ASCII slug')
                if row['category']:
                    require(indicator_id not in mapped, 'dashboard indicator mapped by more than one series')
                    mapped.add(indicator_id)
            require(not row['category'] or indicator_id, 'a categorized dashboard row needs an indicator_id')
            inputs = [value.strip() for value in row['input_series_ids'].split(';') if value.strip()]
            require(len(inputs) == len(set(inputs)), 'input_series_ids contains duplicates')
            require(all(SLUG.fullmatch(value) for value in inputs), 'input_series_ids must be semicolon-separated stable IDs')
            if row['update_method'] in {'automatic', 'manual'}:
                require(not inputs and not row['formula'], 'only derived series may own inputs/formulas')
            if row['status'] == 'unquantified':
                require(not row['update_method'] and not inputs and not row['formula'], 'unquantified patterns cannot own a numeric update method or formula')
            if row['status'] == 'ready':
                required = ['update_method', 'native_frequency']
                if row['update_method'] == 'derived':
                    required += ['input_series_ids', 'formula']
                else:
                    required += ['provider']
                missing = [field for field in required if not row[field]]
                require(not missing, 'ready specification missing: ' + ', '.join(missing))
            row['input_series_ids'] = inputs
            series[identifier] = {key: (value if value != '' else None) for key, value in row.items() if key != 'series_id'}

    if not series:
        raise ValueError('Registry must contain at least one series')
    for identifier, entry in series.items():
        for input_id in entry['input_series_ids']:
            if input_id not in series:
                raise ValueError(f'{identifier}: unknown input series {input_id}; add a source-only row')
            if entry['status'] == 'ready' and series[input_id]['status'] != 'ready':
                raise ValueError(f'{identifier}: input {input_id} must have a ready specification')

    visiting, visited = set(), set()

    def visit(identifier):
        if identifier in visiting:
            raise ValueError(f'Cyclic derivation involving {identifier}')
        if identifier in visited:
            return
        visiting.add(identifier)
        for input_id in series[identifier]['input_series_ids']:
            visit(input_id)
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in series:
        visit(identifier)
    return {'schemaVersion': 1, 'series': series}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument('--output', type=Path, help='Optional generated JSON path; never edit the generated file')
    args = parser.parse_args()
    try:
        registry = load_registry(args.input)
        if args.output:
            if args.output.resolve() == args.input.resolve():
                raise ValueError('Output must not overwrite the editable CSV')
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except (ValueError, OSError) as error:
        parser.exit(1, f'Registry validation failed: {error}\n')
    counts = {status: sum(entry['status'] == status for entry in registry['series'].values()) for status in sorted(STATUSES)}
    print(f'Validated {len(registry["series"])} series specifications: ' + ', '.join(f'{status}={count}' for status, count in counts.items()))
    if args.output:
        print(f'Exported registry to {args.output}')


if __name__ == '__main__':
    main()
