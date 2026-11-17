"""Publish from a fresh default-branch worktree under the Actions production lock.

The caller's checkout is never reset. Only a validated fast-forward is pushed.
Builds and rollback restoration happen in temporary, disposable worktrees.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.artifacts import replace_directory
from scripts.contracts import require
from scripts.import_manual import git
from scripts.registry import ROOT
from scripts.release import GENERATED, RECORD, generated, summary


def run(repo, *command, env=None):
    subprocess.run(command, cwd=repo, env=env, check=True)


def remote_head(repo, branch):
    git(repo, 'fetch', '--no-tags', 'origin', f'+refs/heads/{branch}:refs/remotes/origin/{branch}')
    return git(repo, 'rev-parse', f'refs/remotes/origin/{branch}').strip()


def verify_candidate(repo):
    env = {key: value for key, value in os.environ.items()
           if key not in {'FRED_API_KEY', 'GITHUB_TOKEN', 'GH_TOKEN'}}
    run(repo, sys.executable, 'scripts/check.py', '--snapshot', str(repo / 'data/snapshot'), env=env)


def create_data_pr(branch, base, artifact):
    repository = os.environ.get('GITHUB_REPOSITORY', '')
    require(repository and len(repository.split('/')) == 2, 'GITHUB_REPOSITORY is required for data PRs')
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    require(bool(token), 'A workflow token is required for data PRs')
    body = {'title': 'Update validated production data', 'head': branch, 'base': base,
            'body': f'Publish validated data from artifact commit `{artifact}`.\n\n'
                    'The publication job has run offline checks and built the production artifact. '
                    'Merge this PR to publish from the default branch. Concurrent source or manual '
                    'changes cause reassembly before deployment. For rollback candidates, the '
                    'publication record identifies the restored revision.\n\n'
                    'GitHub may require approval to run checks on PRs created with GITHUB_TOKEN.'}
    request = Request(f'https://api.github.com/repos/{repository}/pulls',
                      data=json.dumps(body).encode(), method='POST',
                      headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                               'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)['html_url']
    except HTTPError as error:
        status = error.code
        error.close()
        raise ValueError(f'Creating the data PR failed (HTTP {status}); enable Actions PR creation '
                         'or open a PR from the pushed automation branch manually') from None


def publish(repo=ROOT, *, branch='main', mode='publish', rollback=None, delivery='auto',
            attempts=3, verify=verify_candidate, open_pr=create_data_pr):
    repo = Path(repo)
    require(delivery in {'auto', 'direct', 'pull-request'}, 'Unknown delivery mode')
    require(1 <= attempts <= 5, 'Use 1–5 publication attempts')
    git(repo, 'check-ref-format', '--branch', branch)
    for attempt in range(attempts):
        base = remote_head(repo, branch)
        with tempfile.TemporaryDirectory(prefix='liquidity-publish-') as temporary:
            work = Path(temporary) / 'checkout'
            git(repo, 'worktree', 'add', '--detach', str(work), base)
            try:
                # Fresh processes load the latest source and policies on every retry.
                run(work, sys.executable, 'scripts/release.py', 'prepare', '--mode', mode,
                    *(['--rollback', rollback] if rollback else []))
                record = json.loads((work / RECORD).read_text())
                verify(work)
                changed = git(work, 'diff', '--name-only').splitlines()
                untracked = git(work, 'ls-files', '--others', '--exclude-standard').splitlines()
                require(all(generated(path) for path in changed + untracked),
                        'Publication changed files outside automatic inputs and snapshots')
                git(work, 'add', '--', *GENERATED)
                if git(work, 'diff', '--cached', '--name-only').strip():
                    git(work, '-c', 'user.name=github-actions[bot]', '-c',
                        'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                        'commit', '-m', f'data: {record["mode"]} production snapshot')
                artifact = git(work, 'rev-parse', 'HEAD').strip()
                run(work, sys.executable, 'scripts/build.py', '--mode', 'production')
                run(work, sys.executable, 'scripts/release.py', 'stamp')
                if remote_head(repo, branch) != base:
                    print('Default branch advanced; discarding candidate and reassembling.', flush=True)
                    continue
                result = 'ready'
                if artifact != base:
                    if delivery != 'pull-request':
                        push = subprocess.run(['git', '-C', str(work), 'push', 'origin',
                                               f'{artifact}:refs/heads/{branch}'], capture_output=True)
                        if push.returncode:
                            if remote_head(repo, branch) != base:
                                print('Push raced with new inputs; reassembling.', flush=True)
                                continue
                            require(delivery == 'auto', 'Default-branch push rejected; use pull-request delivery')
                            result = 'pull-request'
                    else:
                        result = 'pull-request'
                    if result == 'pull-request':
                        candidate_branch = f'automation/data-{artifact[:16]}'
                        git(work, 'push', 'origin', f'{artifact}:refs/heads/{candidate_branch}')
                        print(f'Data update branch pushed: {candidate_branch}', flush=True)
                        pr = open_pr(candidate_branch, branch, artifact)
                        report = summary(work, record, artifact, f'Awaiting merge: {pr}')
                        return {'deploy': False, 'artifact': artifact, 'summary': report, 'pr': pr}
                if remote_head(repo, branch) != artifact:
                    report = summary(work, record, artifact, 'Superseded; deployment skipped')
                    return {'deploy': False, 'artifact': artifact, 'summary': report}
                with tempfile.TemporaryDirectory(prefix='.publish-output-', dir=repo) as staging:
                    stage = Path(staging) / 'dist'
                    shutil.copytree(work / 'dist', stage)
                    replace_directory(stage, repo / 'dist')
                return {'deploy': True, 'artifact': artifact,
                        'summary': summary(work, record, artifact, 'Validated artifact ready for Pages')}
            finally:
                git(repo, 'worktree', 'remove', '--force', str(work))
    raise ValueError('Default branch kept advancing; no stale artifact was published. Rerun the workflow.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--push', action='store_true', help='Explicitly authorize remote writes')
    parser.add_argument('--branch', default='main')
    parser.add_argument('--mode', choices=('publish', 'refresh', 'rollback'), default='publish')
    parser.add_argument('--rollback')
    parser.add_argument('--delivery', choices=('auto', 'direct', 'pull-request'), default='auto')
    args = parser.parse_args()
    try:
        require(args.push, 'This command writes to Git; pass --push only in an authorized publication run')
        result = publish(branch=args.branch, mode=args.mode, rollback=args.rollback, delivery=args.delivery)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                output.write(f'deploy={str(result["deploy"]).lower()}\nartifact={result["artifact"]}\n')
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
                output.write(result['summary'])
        print(result['summary'])
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        message = 'A publication subprocess failed; see the preceding step output.' if isinstance(
            error, subprocess.CalledProcessError) else str(error)
        parser.exit(1, f'Publication failed: {message}\n')
