"""Assemble a local, explicitly unreviewed SIFMA preview from committed inputs.

This is not a production snapshot: it has no activation, normalized manifest
hashes, collection outcomes, or claim that SIFMA measurement definitions are reviewed.
"""
import calendar
import hashlib
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

if __package__:
    from .assets import version_assets
    from .catalog import display_unit
    from .contracts import validate_points, require
    from .import_manual import git, import_manual
    from .registry import parse_registry
else:
    from assets import version_assets
    from catalog import display_unit
    from contracts import validate_points, require
    from import_manual import git, import_manual
    from registry import parse_registry

SERIES = frozenset({'bond-issuance', 'treasury-bond-issuance', 'corporate-bond-issuance'})
MODE = 'manual-preview'


def assemble_preview(repo):
    repo = Path(repo)
    imported = import_manual(repo)
    commit = imported['sourceInputCommit']
    registry = parse_registry(git(repo, 'show', f'{commit}:data/registry.csv'))
    categories = json.loads(git(repo, 'show', f'{commit}:data/categories.json'))
    category_ids = {item['name']: item['id'] for item in categories}
    indicators, observations = [], {}
    for identifier in SERIES:
        require(identifier in imported['series'], f'{identifier}: committed manual CSV required for preview')
        entry = registry['series'][identifier]
        require(entry['provider'] == 'SIFMA' and entry['native_frequency'] == 'monthly',
                f'{identifier}: preview requires the SIFMA monthly definition')
        require(entry['category'] and entry['status'] != 'unavailable', f'{identifier}: preview input must be visible')
        source = imported['series'][identifier]
        require(source['sourceUnit'] == source['normalizedUnit'] == 'Billions'
                and source['conversion'] == 'identity', f'{identifier}: preview requires Billions identity units')
        for point in source['observations']:
            day = date.fromisoformat(point['date'])
            require(day.day == calendar.monthrange(day.year, day.month)[1],
                    f'{identifier}: expected saved month-end dates')
    for identifier, entry in registry['series'].items():
        if not entry['category'] or entry['status'] == 'unavailable':
            continue
        require(entry['category'] in category_ids, f'{identifier}: unknown category')
        loaded = identifier in SERIES
        points = imported['series'][identifier]['observations'] if loaded else []
        reference = entry['source_reference']
        url = reference if reference and urlparse(reference).scheme == 'https' else None
        explanation = ('展示已保存的 Wind 工作簿中的 SIFMA 月度发行数据，保留原始月末日期和十亿美元数值。'
                       '来源引用、覆盖范围、发行口径及月度／年累计定义仍待复核；仅供本地预览。'
                       if loaded else '待接入：此预览尚未提供该指标的真实数据，不生成替代数值。')
        if entry['notes']:
            explanation += ' ' + entry['notes']
        indicators.append({
            'id': entry['indicator_id'], 'seriesId': identifier,
            'categoryId': category_ids[entry['category']], 'name': entry['name'],
            'unit': display_unit(entry), 'frequency': entry['native_frequency'],
            'nativeFrequency': entry['native_frequency'], 'isDemo': False,
            'inputAvailable': loaded, 'role': '', 'explanation': explanation,
            'availability': ('nonnumeric' if entry['status'] == 'unquantified' else
                             'numeric' if any(p['value'] is not None for p in points) else 'empty'),
            'comparisonPolicy': {'periods': [1, 12], 'periodUnit': 'month',
                                 'match': 'month-end', 'valueScale': 1} if loaded else None,
            'source': {'name': 'SIFMA / Wind 已保存工作簿（定义待复核）' if loaded else
                       (entry['provider'] or '数据源待确认'), 'url': url,
                       'reference': reference, 'status': 'preview' if loaded else 'pending'},
        })
        observations[entry['indicator_id']] = points
    dates = [point['date'] for points in observations.values() for point in points]
    catalog = {'schemaVersion': 2, 'dataset': {
        'mode': MODE, 'isDemo': False, 'sourceReview': 'pending', 'sourceInputCommit': commit,
        'observationStart': min(dates) if dates else None, 'observationEnd': max(dates) if dates else None,
    }, 'categories': categories, 'indicators': indicators}
    content = json.dumps([catalog, observations], ensure_ascii=False, sort_keys=True, allow_nan=False)
    snapshot_id = 'sifma-preview-' + hashlib.sha256(content.encode()).hexdigest()[:20]
    catalog['snapshotId'] = snapshot_id
    observations = {'schemaVersion': 2, 'snapshotId': snapshot_id, 'series': observations}
    manifest = {'schemaVersion': 2, 'snapshotId': snapshot_id, 'mode': MODE,
                'sourceReview': 'pending', 'sourceInputCommit': commit,
                'inputs': {identifier: {'path': f'data/manual/{identifier}.csv',
                                       'specHash': imported['series'][identifier]['specHash'],
                                       'sourceUnit': 'Billions'} for identifier in sorted(SERIES)}}
    validate_preview(catalog, observations, manifest)
    return catalog, observations, manifest


def validate_preview(catalog, observations, manifest):
    require(all(document['schemaVersion'] == 2 for document in (catalog, observations, manifest)), 'Preview schema mismatch')
    require(catalog['snapshotId'] == observations['snapshotId'] == manifest['snapshotId'], 'Preview snapshot mismatch')
    require(catalog['dataset']['mode'] == manifest['mode'] == MODE
            and catalog['dataset']['isDemo'] is False
            and catalog['dataset']['sourceReview'] == manifest['sourceReview'] == 'pending', 'Preview must remain explicitly unreviewed')
    require(set(manifest['inputs']) == SERIES, 'Unexpected preview inputs')
    require(catalog['dataset']['sourceInputCommit'] == manifest['sourceInputCommit'], 'Preview source commit mismatch')
    require(set(observations['series']) == {item['id'] for item in catalog['indicators']}, 'Preview membership mismatch')
    for indicator in catalog['indicators']:
        points = observations['series'][indicator['id']]
        validate_points(points)
        require(indicator['isDemo'] is False, 'Preview cannot contain demo indicators')
        require(indicator['seriesId'] in SERIES or not points, 'Only SIFMA inputs may contain preview observations')


def build_preview(repo):
    repo = Path(repo)
    documents = assemble_preview(repo)  # Validate everything before replacing output.
    source, output = repo / 'site', repo / 'dist-preview'
    vendor = source / 'assets/vendor/echarts-5.6.0.min.js'
    require(vendor.is_file() and vendor.stat().st_size > 100_000, 'Pinned Apache ECharts bundle is missing')
    with tempfile.TemporaryDirectory(prefix='.preview-', dir=repo) as temporary:
        stage = Path(temporary) / 'site'
        shutil.copytree(source, stage, ignore=lambda folder, names: ['data'] if Path(folder) == source else [])
        (stage / 'data').mkdir()
        for name, document in zip(('catalog', 'observations', 'manifest'), documents):
            (stage / f'data/{name}.json').write_text(
                json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        version_assets(stage)
        (stage / '.nojekyll').touch()
        previous = Path(temporary) / 'previous'
        if output.exists():
            output.rename(previous)
        try:
            stage.rename(output)
        except OSError:
            if previous.exists():
                previous.rename(output)
            raise
    print(f'Built local SIFMA preview from {documents[2]["sourceInputCommit"][:12]} to {output}')
    print('Source definitions pending review. No production activation or demo data fallback.')
    return output
