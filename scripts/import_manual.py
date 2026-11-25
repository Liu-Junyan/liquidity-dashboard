"""Validate source-scale manual CSVs and audit corrections in Git (no writes).

Committed mode audits first-parent history, including intermediate edits. Working
tree mode additionally checks local files against HEAD using a proposed message.
Importing a candidate does not activate its source or assemble a snapshot.
"""
import argparse
import csv
import io
import math
import re
import subprocess
from decimal import Decimal, InvalidOperation
from pathlib import Path

if __package__:
    from .contracts import iso_date, validate_reference
    from .policies import conversion_policy, specification_hash
    from .registry import SLUG, parse_registry
else:
    from contracts import iso_date, validate_reference
    from policies import conversion_policy, specification_hash
    from registry import SLUG, parse_registry

ROOT = Path(__file__).resolve().parents[1]
NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')
REASON = re.compile(
    r'Manual-Reason: ([a-z0-9]+(?:-[a-z0-9]+)*) '
    r'([0-9]{4}-[0-9]{2}-[0-9]{2})(?:\.\.([0-9]{4}-[0-9]{2}-[0-9]{2}))?: (\S.*)\Z'
)


def parse_csv(text, label='manual CSV'):
    """Return exact decimals for revision checks; blank values remain missing."""
    reader = csv.reader(io.StringIO(text.lstrip('\ufeff'), newline=''), strict=True)
    points = {}
    try:
        if next(reader, None) != ['date', 'value']:
            raise ValueError(f'{label}: header must be exactly date,value')
        previous = None
        for row in reader:
            location = f'{label}:{reader.line_num}'
            if len(row) != 2:
                raise ValueError(f'{location}: expected exactly two columns')
            day, raw = row
            try:
                iso_date(day)
            except ValueError as error:
                raise ValueError(f'{location}: {error}') from None
            if previous is not None and day <= previous:
                raise ValueError(f'{location}: dates must be sorted and unique')
            raw = raw.strip()
            value = None
            if raw:
                if not NUMBER.fullmatch(raw):
                    raise ValueError(f'{location}: value must be a finite number or blank')
                try:
                    value = Decimal(raw)
                    number = float(value)
                except (InvalidOperation, OverflowError, ValueError):
                    raise ValueError(f'{location}: value must be a finite JSON number') from None
                if not math.isfinite(number) or (value != 0 and number == 0):
                    raise ValueError(f'{location}: value cannot be represented as a finite nonzero JSON number')
            points[day] = value
            previous = day
    except csv.Error as error:
        raise ValueError(f'{label}:{reader.line_num}: invalid CSV: {error}') from None
    return points


def validate_owner(registry, identifier, method):
    """Shared input ownership gate for manual import and future collectors."""
    entry = registry['series'].get(identifier)
    if entry is None:
        raise ValueError(f'{identifier}: unknown registry series')
    if method not in {'manual', 'automatic'} or entry['update_method'] != method:
        raise ValueError(f'{identifier}: conflicting ownership; expected {method}')
    return entry


def validate_inputs(files, registry):
    result = {}
    for identifier, text in sorted(files.items()):
        entry = validate_owner(registry, identifier, 'manual')
        try:
            conversion_policy(entry)
            # Draft sources may lack a reference, but filled references must be safe.
            if entry['source_reference']:
                validate_reference(entry['source_reference'])
        except ValueError as error:
            raise ValueError(f'{identifier}: {error}') from None
        result[identifier] = parse_csv(text, f'data/manual/{identifier}.csv')
    return result


def revision_changes(previous, current):
    """Compare source values, not formatting; include whole-file deletions."""
    changes = {}
    for identifier in sorted(previous.keys() | current.keys()):
        old, new = previous.get(identifier, {}), current.get(identifier, {})
        changes[identifier] = {
            'added': sorted(new.keys() - old.keys()),
            'revised': sorted(day for day in old.keys() & new.keys() if old[day] != new[day]),
            'removed': sorted(old.keys() - new.keys()),
        }
    return changes


def require_reasons(changes, message):
    reasons = []
    for line in message.splitlines():
        if not line.startswith('Manual-Reason:'):
            continue
        match = REASON.fullmatch(line.rstrip())
        if not match:
            raise ValueError('Use Manual-Reason: <series-id> YYYY-MM-DD[..YYYY-MM-DD]: <reason>')
        identifier, start, end, _ = match.groups()
        end = end or start
        iso_date(start)
        iso_date(end)
        if start > end:
            raise ValueError('Manual-Reason date range must be ascending')
        reasons.append((identifier, start, end))
    for identifier, change in changes.items():
        uncovered = [day for day in change['revised'] + change['removed']
                     if not any(owner == identifier and start <= day <= end
                                for owner, start, end in reasons)]
        if uncovered:
            raise ValueError(f'{identifier}: corrections/removals require a Manual-Reason in the '
                             f'input commit message for: {", ".join(sorted(uncovered))}')


def git(repo, *args):
    process = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if process.returncode:
        raise ValueError(f'Git baseline/history unavailable ({" ".join(args[:2])}); '
                         'fetch full history and verify the requested commit')
    return process.stdout.decode('utf-8')


def resolve_commit(repo, revision):
    return git(repo, 'rev-parse', '--verify', '--end-of-options', f'{revision}^{{commit}}').strip()


def committed_files(repo, commit):
    files = {}
    tree = git(repo, 'ls-tree', '-rz', commit, '--', 'data/manual')
    for record in tree.split('\0'):
        if not record:
            continue
        info, name = record.split('\t', 1)
        if name == 'data/manual':
            raise ValueError('data/manual must be a regular directory')
        if not name.endswith('.csv'):
            continue
        mode, kind, blob = info.split()
        path = Path(name)
        if path.parent.as_posix() != 'data/manual' or not SLUG.fullmatch(path.stem):
            raise ValueError(f'{name}: expected data/manual/<series-id>.csv')
        if kind != 'blob' or mode not in {'100644', '100755'}:
            raise ValueError(f'{name}: manual input must be a regular file')
        files[path.stem] = git(repo, 'cat-file', 'blob', blob)
    return files


def committed_inputs(repo, commit):
    files = committed_files(repo, commit)
    registry = parse_registry(git(repo, 'show', f'{commit}:data/registry.csv')) if files else {'series': {}}
    return validate_inputs(files, registry), registry


def working_inputs(repo):
    directory = repo / 'data/manual'
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise ValueError('data/manual must be a regular directory')
    files = {}
    for path in sorted(directory.rglob('*.csv')):
        if path.parent != directory or not SLUG.fullmatch(path.stem):
            raise ValueError(f'{path}: expected data/manual/<series-id>.csv')
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'{path}: manual input must be a regular file')
        files[path.stem] = path.read_text(encoding='utf-8-sig')
    registry = parse_registry((repo / 'data/registry.csv').read_text(encoding='utf-8-sig'))
    return validate_inputs(files, registry), registry


def import_manual(repo=ROOT, *, revision='HEAD', base=None, working_tree=False, message=''):
    """Return validated candidate inputs and an audit; never mutate any inputs.

    An explicit base is a trusted, previously validated commit on the first-parent
    chain. Without one, audit full first-parent history; an empty root is the
    initial baseline. A root containing inputs needs an explicit trusted base.
    """
    repo = Path(repo).resolve()
    if git(repo, 'rev-parse', '--is-shallow-repository').strip() == 'true':
        raise ValueError('Missing Git baseline: shallow checkout; fetch full history (fetch-depth: 0)')
    commit = resolve_commit(repo, revision)
    if working_tree and commit != resolve_commit(repo, 'HEAD'):
        raise ValueError('Working-tree validation must compare against HEAD')
    history = git(repo, 'rev-list', '--first-parent', '--reverse', commit).splitlines()
    baseline = resolve_commit(repo, base) if base else history[0]
    if baseline not in history:
        raise ValueError('Baseline must be on the candidate first-parent history')
    previous, registry = committed_inputs(repo, baseline)
    if base is None and previous:
        raise ValueError('Missing previous Git baseline: root commit contains manual inputs; '
                         'select an explicitly trusted --base commit')
    revisions = f'{baseline}..{commit}'
    changed_commits = set(git(repo, 'rev-list', '--first-parent', revisions, '--',
                              'data/manual', 'data/registry.csv').splitlines())
    # Read every message, including malformed reason trailers on input-neutral commits.
    log = git(repo, 'log', '--first-parent', '--reverse', '--no-patch', '--no-notes',
              '--no-show-signature', '-z', '--format=%H%n%B', revisions)
    audits = []
    for record in log.split('\0'):
        if not record:
            continue
        current_commit, body = record.split('\n', 1)
        try:
            if current_commit not in changed_commits:
                require_reasons({}, body)
                continue
            current, registry = committed_inputs(repo, current_commit)
            changes = revision_changes(previous, current)
            require_reasons(changes, body)
        except ValueError as error:
            raise ValueError(f'{current_commit[:12]}: {error}') from None
        if any(dates for change in changes.values() for dates in change.values()):
            audits.append({'commit': current_commit, 'changes': changes})
        previous = current
    if working_tree:
        current, registry = working_inputs(repo)
        changes = revision_changes(previous, current)
        require_reasons(changes, message)
        audits.append({'commit': None, 'changes': changes})
        previous = current
    series = {}
    for identifier, points in previous.items():
        entry = registry['series'][identifier]
        conversion, factor = conversion_policy(entry)
        series[identifier] = {
            'sourceUnit': entry['source_unit'], 'normalizedUnit': entry['normalized_unit'],
            'sourceReference': entry['source_reference'], 'specHash': specification_hash(entry),
            'conversion': conversion, 'conversionFactor': factor,
            'observations': [{'date': day, 'value': None if value is None else float(value)}
                             for day, value in points.items()],
        }
    return {'sourceInputCommit': None if working_tree else commit, 'baselineCommit': baseline,
            'comparisonCommit': commit, 'series': series, 'audit': audits,
            'revisionSummary': {kind: sum(len(change[kind]) for audit in audits
                                         for change in audit['changes'].values())
                                for kind in ('added', 'revised', 'removed')}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--revision', default='HEAD', help='Committed candidate (default: HEAD)')
    parser.add_argument('--base', help='Explicitly trusted baseline commit; default audits full history')
    parser.add_argument('--working-tree', action='store_true', help='Also validate local files against HEAD')
    parser.add_argument('--message-file', type=Path, help='Proposed commit message for working-tree corrections')
    args = parser.parse_args()
    if args.message_file and not args.working_tree:
        parser.error('--message-file requires --working-tree; committed reasons come only from Git')
    try:
        message = args.message_file.read_text(encoding='utf-8') if args.message_file else ''
        result = import_manual(args.repo, revision=args.revision, base=args.base,
                               working_tree=args.working_tree, message=message)
    except (ValueError, OSError, UnicodeError) as error:
        parser.exit(1, f'Manual import failed: {error}\n')
    for identifier, entry in result['series'].items():
        print(f'{identifier}: {len(entry["observations"])} observations in {entry["sourceUnit"]}')
    print(f'Validated {len(result["series"])} manual inputs; revisions: {result["revisionSummary"]}')
    print('Source-scale candidate only; source review and production activation remain separate.')


if __name__ == '__main__':
    main()
