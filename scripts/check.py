"""Run all offline checks and builds, preserving checked-in demo data."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(repo=ROOT, *, snapshot=None):
    repo = Path(repo)
    env = {key: value for key, value in os.environ.items()
           if key not in {'FRED_API_KEY', 'GITHUB_TOKEN', 'GH_TOKEN'}}

    def run(*command):
        subprocess.run(command, cwd=repo, env=env, check=True)

    originals = {path: path.read_bytes() for path in (repo / 'site/data').glob('*.json')}
    try:
        run(sys.executable, 'scripts/registry.py')
        run(sys.executable, 'scripts/policies.py', '--check-activation')
        run(sys.executable, 'scripts/import_manual.py')
        run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py')
        run(sys.executable, 'scripts/build.py', '--mode', 'demo')
        run('node', '--test', 'tests/data.test.mjs')
        with tempfile.TemporaryDirectory(prefix='liquidity-check-') as temporary:
            if snapshot is None:
                snapshot = Path(temporary).resolve() / 'snapshot'
                run(sys.executable, 'scripts/assemble.py', '--output', str(snapshot))
            run(sys.executable, 'scripts/build.py', '--mode', 'production', '--snapshot', str(snapshot))
            run('node', '--test', 'tests/production.test.mjs')
    finally:
        for path, content in originals.items():
            path.write_bytes(content)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path)
    args = parser.parse_args()
    check(snapshot=args.snapshot)
