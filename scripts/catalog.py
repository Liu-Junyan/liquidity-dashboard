"""Compile demo dashboard metadata from the editable source registry.

The CSV controls membership, names, ordering, grouping and source specifications.
This does not collect data, normalize observations, or execute registered formulas.
"""
import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def display_unit(entry):
    value = (entry['normalized_unit'] or '').strip()
    if entry['status'] == 'unquantified':
        return {'kind': 'unquantified', 'label': '待定义', 'precision': 0}
    aliases = {
        '%': ('ratio', '%', 2), 'percent': ('ratio', '%', 2),
        'bp': ('spread', 'bp', 2), 'bps': ('spread', 'bp', 2),
        'millions': ('amount', '百万美元', 1),
        'billions': ('amount', '十亿美元', 1), 'biliions': ('amount', '十亿美元', 1),
        'trillion': ('amount', '万亿美元', 2), 'trillions': ('amount', '万亿美元', 2),
        'none': ('index', '点', 2),
    }
    kind, label, precision = aliases.get(value.lower(), ('scalar', value or '待确认', 2))
    return {'kind': kind, 'label': label, 'precision': precision}


def build_catalog(registry, categories=None):
    categories = deepcopy(categories if categories is not None else json.loads((ROOT / 'data/categories.json').read_text(encoding='utf-8')))
    category_ids = {item['name']: item['id'] for item in categories}
    indicators = []
    for series_id, entry in registry['series'].items():
        # A category is an explicit display opt-in. Input rows can retain their
        # indicator_id for editing convenience without appearing as chart cards.
        if entry['status'] == 'unavailable' or not entry['category']:
            continue
        if entry['category'] not in category_ids:
            raise ValueError(f'{series_id}: unknown dashboard category {entry["category"]}')
        unit = display_unit(entry)
        explanation = [f'{entry["name"]}的合成示例，尚未接入登记的数据源。']
        if entry['formula']:
            explanation.append(f'登记计算式：{entry["formula"]}。当前演示数值不执行此公式。')
        if entry['notes']:
            explanation.append(entry['notes'])
        if not entry['normalized_unit'] and entry['status'] != 'unquantified':
            explanation.append('展示单位尚待确认，数值仅用于界面演示。')
        reference = entry['source_reference']
        url = reference if reference and urlparse(reference).scheme == 'https' else None
        provider = entry['provider'] or ('登记派生指标' if entry['update_method'] == 'derived' else '数据源待确认')
        source_name = provider
        if entry['provider_series_id']:
            source_name += f' · {entry["provider_series_id"]}'
        if reference and not url:
            source_name += f' · {reference}'
        indicators.append({
            'id': entry['indicator_id'], 'seriesId': series_id,
            'categoryId': category_ids[entry['category']], 'name': entry['name'],
            'role': '', 'explanation': ' '.join(explanation), 'unit': unit,
            'frequency': 'weekly', 'nativeFrequency': entry['native_frequency'],
            'source': {'name': source_name, 'url': url, 'status': 'configured' if url else 'pending'},
            'comparisonRule': entry['comparison_rules'], 'isDemo': True,
        })
    return {
        'schemaVersion': 1,
        'dataset': {
            'id': 'synthetic-registry-v1', 'isDemo': True,
            'observationStart': '2021-10-27', 'observationEnd': '2026-10-28',
            'collectedAt': '2026-10-28T00:00:00Z',
        },
        'categories': categories, 'indicators': indicators,
    }
