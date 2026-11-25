"""Prepare and validate production artifacts in a disposable publication checkout."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.artifacts import promote_snapshot
from scripts.assemble import assemble, validate_assembled_snapshot
from scripts.collect import refresh, load_api_key
from scripts.contracts import require
from scripts.import_manual import git, import_manual
from scripts.policies import ACTIVE_SERIES, POLICIES
from scripts.providers.fred import FredClient
from scripts.registry import ROOT

RECORD = 'data/publication.json'
GENERATED = ('data/automatic', 'data/snapshot', RECORD)
SHA = re.compile(r'[0-9a-f]{40}\Z')
PUBLIC_FILES = {
    '.nojekyll', 'index.html', 'assets/favicon.svg', 'assets/app.js', 'assets/charts.js',
    'assets/data.js', 'assets/zh-CN.js', 'assets/styles.css',
    'assets/vendor/echarts-5.6.0.min.js', 'assets/vendor/echarts-LICENSE.txt',
    'data/catalog.json', 'data/observations.json', 'data/manifest.json', 'data/release.json',
}


def generated(path):
    return any(path == name or path.startswith(name + '/') for name in GENERATED)


def read_snapshot(repo):
    documents = [json.loads((Path(repo) / f'data/snapshot/{name}.json').read_text())
                 for name in ('catalog', 'observations', 'manifest')]
    validate_assembled_snapshot(*documents)
    require(not documents[2]['modifiedSourceFiles'], 'Release snapshot contains uncommitted source changes')
    return documents


def artifact_hashes(repo):
    paths = sorted([*(Path(repo) / 'data/automatic').glob('*.json'),
                    *(Path(repo) / 'data/snapshot').glob('*.json')])
    require(all(not path.is_symlink() for path in paths), 'Release inputs cannot be symlinks')
    return {path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def is_ancestor(repo, ancestor, descendant='HEAD'):
    return subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', ancestor, descendant],
                          capture_output=True).returncode == 0


def validate_restored_artifact(repo, target, documents):
    previous = json.loads(git(repo, 'show', f'{target}:{RECORD}'))
    require(previous.get('schemaVersion') == 1, 'Rollback target needs a publication record')
    require(previous['artifactHashes'] == artifact_hashes(repo),
            'Rollback inputs differ from the historic publication record')
    require(previous['snapshotId'] == documents[0]['snapshotId'], 'Rollback snapshot identity differs')


def reusable_record(repo):
    """Recognize a merged data PR without creating a second data PR forever.

    Any intervening source/manual/UI change invalidates reuse. The next run
    assembles against that new default-branch revision instead.
    """
    path = Path(repo) / RECORD
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    base = record.get('baseCommit', '')
    require(bool(SHA.fullmatch(base)), 'Invalid publication base commit')
    require(is_ancestor(repo, base), 'Publication base is not in branch history')
    changed = git(repo, 'diff', '--name-only', base, 'HEAD').splitlines()
    if any(not generated(name) for name in changed):
        return None
    require(record.get('schemaVersion') == 1 and record.get('mode') in {'publish', 'refresh', 'rollback'},
            'Invalid publication record')
    if record['artifactHashes'] != artifact_hashes(repo):
        # A newly committed automatic input is a new source candidate. The
        # assembler validates it before any replacement snapshot can be used.
        return None
    documents = read_snapshot(repo)
    require(record['snapshotId'] == documents[0]['snapshotId'], 'Publication snapshot identity differs')
    if record['mode'] == 'rollback':
        target = record.get('restoredFrom', '')
        require(bool(SHA.fullmatch(target)) and is_ancestor(repo, target, base), 'Invalid rollback history')
        require(not git(repo, 'diff', '--name-only', target, 'HEAD', '--', *GENERATED[:2]).strip(),
                'Rollback does not match the selected committed inputs and snapshot')
        validate_restored_artifact(repo, target, documents)
    else:
        require(documents[2]['sourceInputCommit'] == base, 'Snapshot source commit differs from publication base')
        # Recompute against saved inputs, including manual audits, without changing
        # the original timestamp/base identity. This also detects forged hashes.
        expected = assemble(repo, now=documents[2]['generatedAt'])
        expected[2]['sourceInputCommit'] = base
        for actual, candidate in zip(documents, expected):
            require({key: value for key, value in actual.items() if key != 'snapshotId'} ==
                    {key: value for key, value in candidate.items() if key != 'snapshotId'},
                    'Committed artifact no longer matches current source inputs')
    return record


def prepare(repo=ROOT, *, mode='publish', client=None):
    repo = Path(repo)
    require(mode in {'publish', 'refresh'}, 'Unknown publication mode')
    require(not git(repo, 'status', '--porcelain').strip(), 'Publication requires a clean checkout')
    import_manual(repo)  # Audit even inactive manual inputs before any publication.
    base = git(repo, 'rev-parse', 'HEAD').strip()
    if mode == 'publish':
        reusable = reusable_record(repo)
        if reusable:
            return reusable
    if mode == 'refresh':
        selected = [key for key in ACTIVE_SERIES if POLICIES[key].method == 'automatic']
        refresh(repo, client or FredClient(load_api_key()), selected=selected)
    documents = assemble(repo)
    require(not documents[2]['modifiedSourceFiles'], 'Commit source changes before publication')
    promote_snapshot(repo / 'data/snapshot', documents)
    record = {'schemaVersion': 1, 'mode': mode, 'baseCommit': base,
              'snapshotId': documents[0]['snapshotId'], 'restoredFrom': None,
              'artifactHashes': artifact_hashes(repo)}
    (repo / RECORD).write_text(json.dumps(record, indent=2) + '\n')
    return record


def validate_public_tree(directory, *, stamped=True):
    directory = Path(directory)
    paths = list(directory.rglob('*'))
    require(not any(path.is_symlink() for path in paths), 'Public artifact cannot contain symlinks')
    names = {path.relative_to(directory).as_posix() for path in paths if path.is_file()}
    expected = PUBLIC_FILES if stamped else PUBLIC_FILES - {'data/release.json'}
    require(names == expected, f'Unexpected or missing public files: {sorted(names ^ expected)}')


def stamp_output(repo=ROOT):
    repo = Path(repo)
    require(not git(repo, 'status', '--porcelain').strip(), 'Build must use a clean artifact commit')
    documents = read_snapshot(repo)
    record = json.loads((repo / RECORD).read_text())
    require(record['artifactHashes'] == artifact_hashes(repo), 'Artifact changed after validation')
    for name in ('catalog', 'observations', 'manifest'):
        require((repo / f'dist/data/{name}.json').read_bytes() ==
                (repo / f'data/snapshot/{name}.json').read_bytes(), 'Build differs from committed snapshot')
    release = {'artifactCommit': git(repo, 'rev-parse', 'HEAD').strip(),
               'sourceInputCommit': documents[2]['sourceInputCommit'],
               'snapshotId': documents[0]['snapshotId'], 'restoredFrom': record['restoredFrom']}
    (repo / 'dist/data/release.json').write_text(json.dumps(release, indent=2) + '\n')
    validate_public_tree(repo / 'dist')
    return release


def summary(repo, record, artifact, delivery, *, manifest=None):
    if manifest is None:
        manifest = read_snapshot(repo)[2]
    lines = ['## Production candidate', '', f'- Result: {delivery}', f'- Artifact commit: `{artifact}`',
             f'- Snapshot: `{record["snapshotId"]}`', f'- Mode: {record["mode"]}']
    if record['restoredFrom']:
        lines.append(f'- Restored from: `{record["restoredFrom"]}` (no collection)')
    lines += ['', '| Source | Outcome | Latest observation | Freshness |', '| --- | --- | --- | --- |']
    warnings = []
    for identifier, outcome in manifest['outcomes'].items():
        diagnostic = manifest['diagnostics'].get(identifier, {})
        freshness = (diagnostic.get('freshness') or {}).get('status', 'n/a')
        lines.append(f'| {identifier} | {outcome["status"]} | {outcome["latestObservationDate"] or "—"} | {freshness} |')
        if outcome['status'] in {'retained', 'failed'}:
            warnings.append(f'Collection warning: `{identifier}` is **{outcome["status"]}**; '
                            'compatible prior history is used when available.')
    lines += ['', *warnings]
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'stamp'))
    parser.add_argument('--mode', choices=('publish', 'refresh'), default='publish')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            record = prepare(mode=args.mode)
            print(f'Prepared {record["mode"]} snapshot {record["snapshotId"]}')
        else:
            print(json.dumps(stamp_output()))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Release failed: {error}\n')
