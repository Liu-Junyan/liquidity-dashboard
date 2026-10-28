"""Validate local data and build a self-contained GitHub Pages directory."""
import json
import math
import shutil
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def validate(catalog, observations):
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    require(catalog['schemaVersion'] == 1, 'Unsupported schema version')
    dataset = catalog['dataset']
    require(dataset['isDemo'] is True, 'This prototype requires synthetic data')
    start, end = date.fromisoformat(dataset['observationStart']), date.fromisoformat(dataset['observationEnd'])
    require(start < end, 'Invalid dataset interval')
    collected = datetime.fromisoformat(dataset['collectedAt'].replace('Z', '+00:00'))
    require(collected.utcoffset() is not None, 'Collection time must include a timezone')
    categories, indicators = catalog['categories'], catalog['indicators']
    require(len(categories) == 4, 'Expected four placeholder categories')
    ids = [item['id'] for item in categories + indicators]
    require(len(set(ids)) == len(ids), 'IDs must be unique across categories and indicators')
    require(all(identifier and all(char in 'abcdefghijklmnopqrstuvwxyz0123456789-' for char in identifier) for identifier in ids), 'IDs must be stable URL-safe slugs')
    category_ids = {item['id'] for item in categories}
    require(len({item['order'] for item in categories}) == len(categories), 'Category order must be unique')
    for category in categories:
        require(category['name'] and category['description'], 'Category metadata is required')
        require(any(item['categoryId'] == category['id'] for item in indicators), 'Each category needs an indicator')
    require(set(observations) == {item['id'] for item in indicators}, 'Observation series must match indicator IDs')
    for indicator in indicators:
        require(indicator['categoryId'] in category_ids, 'Unknown category')
        require(indicator['isDemo'] is True, 'Indicator must identify synthetic data')
        require(indicator['frequency'] == 'weekly', 'Only weekly observations supported')
        require(indicator['unit']['kind'] in {'amount', 'rate'}, 'Unknown unit kind')
        require(type(indicator['unit']['precision']) is int and 0 <= indicator['unit']['precision'] <= 6, 'Invalid precision')
        require(all(indicator[field] for field in ('name', 'explanation')), 'Indicator metadata is required')
        require(indicator['unit']['label'] and indicator['source']['name'], 'Unit and source labels required')
        require(urlparse(indicator['source']['url']).scheme == 'https', 'Source URL must use HTTPS')
        points = observations[indicator['id']]
        require(len(points) > 1, 'Series needs dated observations')
        previous = None
        has_value = False
        for point in points:
            current = date.fromisoformat(point['date'])
            require(start <= current <= end, 'Observation outside dataset interval')
            require(previous is None or (current - previous).days == 7, 'Observations must be sorted on an uninterrupted weekly grid; encode gaps as null')
            value = point['value']
            require(value is None or type(value) in (float, int) and math.isfinite(value), 'Values must be finite numbers or explicit null')
            has_value |= value is not None
            previous = current
        require(has_value, 'Series needs at least one numeric value')
        require(points[0]['date'] == dataset['observationStart'] and points[-1]['date'] == dataset['observationEnd'], 'Series must span the dataset interval')


def build():
    source = ROOT / 'site'
    catalog = json.loads((source / 'data/catalog.json').read_text(encoding='utf-8'))
    observations = json.loads((source / 'data/observations.json').read_text(encoding='utf-8'))
    validate(catalog, observations)
    vendor = source / 'assets/vendor/echarts-5.6.0.min.js'
    if not vendor.is_file() or vendor.stat().st_size < 100_000:
        raise ValueError('Pinned Apache ECharts bundle is missing')
    output = ROOT / 'dist'
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(source, output)
    (output / '.nojekyll').touch()
    print(f'Built {len(catalog["categories"])} categories, {len(catalog["indicators"])} indicators to {output}')


if __name__ == '__main__':
    build()
