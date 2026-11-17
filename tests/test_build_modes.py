import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build
from test_production_contract import example_snapshot


class BuildModeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ('site/data/catalog.json', 'site/data/observations.json', 'dist/index.html'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('untouched', encoding='utf-8')
        self.before = self.contents()
        self.snapshot = self.root / 'data/snapshot'

    def contents(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def write_snapshot(self, documents):
        self.snapshot.mkdir(parents=True)
        for name, document in zip(('catalog', 'observations', 'manifest'), documents):
            (self.snapshot / f'{name}.json').write_text(json.dumps(document), encoding='utf-8')
        self.before = self.contents()

    def test_missing_snapshot_never_calls_demo_or_changes_outputs(self):
        with patch.object(build, 'ROOT', self.root), patch.object(build, 'build_demo') as demo:
            with self.assertRaisesRegex(ValueError, 'Production snapshot missing'):
                build.build('production')
            demo.assert_not_called()
        self.assertEqual(self.before, self.contents())

    def test_invalid_snapshot_fails_contract_before_any_writes(self):
        documents = example_snapshot()
        documents[1]['snapshotId'] = 'mixed-snapshot'
        self.write_snapshot(documents)
        with patch.object(build, 'ROOT', self.root), patch.object(build, 'build_demo') as demo:
            with self.assertRaisesRegex(ValueError, 'Snapshot ID mismatch'):
                build.build('production')
            demo.assert_not_called()
        self.assertEqual(self.before, self.contents())

    def test_schema_only_snapshot_without_assembly_integrity_is_rejected(self):
        self.write_snapshot(example_snapshot())
        with patch.object(build, 'ROOT', self.root), patch.object(build, 'build_demo') as demo:
            with self.assertRaisesRegex(ValueError, 'content digest'):
                build.build('production', self.snapshot)
            demo.assert_not_called()
        self.assertEqual(self.before, self.contents())

    def test_demo_default_compatibility_and_invalid_options(self):
        with patch.object(build, 'build_demo') as demo:
            build.build()
            build.build('demo')
            self.assertEqual(demo.call_count, 2)
            for mode, snapshot in [('other', None), ('demo', self.snapshot)]:
                with self.assertRaises(ValueError):
                    build.build(mode, snapshot)
            self.assertEqual(demo.call_count, 2)

    def test_cli_missing_snapshot_is_clear_without_traceback(self):
        result = subprocess.run([sys.executable, str(Path(build.__file__)), '--mode', 'production',
                                 '--snapshot', str(self.snapshot)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Production snapshot missing', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(self.before, self.contents())


if __name__ == '__main__':
    unittest.main()
