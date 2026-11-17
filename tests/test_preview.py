import copy
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build, preview
from scripts.contracts import validate_snapshot
from scripts.import_manual import git, import_manual

ROOT = Path(__file__).resolve().parents[1]


class SifmaPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = preview.assemble_preview(ROOT)
        cls.imported = import_manual(ROOT)

    def test_matches_committed_csvs_and_has_no_other_observations(self):
        catalog, observations, manifest = self.documents
        self.assertEqual(catalog['dataset']['mode'], 'manual-preview')
        self.assertFalse(catalog['dataset']['isDemo'])
        self.assertEqual(manifest['sourceReview'], 'pending')
        imported_ids = set()
        for item in catalog['indicators']:
            points = observations['series'][item['id']]
            if item['seriesId'] in preview.SERIES:
                imported_ids.add(item['seriesId'])
                text = git(ROOT, 'show', f'{manifest["sourceInputCommit"]}:data/manual/{item["seriesId"]}.csv')
                expected = [{'date': row['date'], 'value': float(row['value']) if row['value'] else None}
                            for row in csv.DictReader(io.StringIO(text))]
                self.assertEqual(points, expected)
                self.assertEqual(item['frequency'], 'monthly')
                self.assertEqual(item['comparisonPolicy']['periods'], [1, 12])
                self.assertIn('待复核', item['explanation'])
                self.assertEqual(item['unit']['label'], '十亿美元')
            else:
                self.assertEqual(points, [])
                self.assertFalse(item['inputAvailable'])
            self.assertFalse(item['isDemo'])
        self.assertEqual(imported_ids, preview.SERIES)
        self.assertEqual(catalog['snapshotId'], preview.assemble_preview(ROOT)[0]['snapshotId'])

    def test_preview_cannot_pass_as_production(self):
        with self.assertRaises(ValueError):
            validate_snapshot(*self.documents)

    def test_missing_input_changed_units_or_non_month_end_fail(self):
        for kind in ('missing', 'units', 'date'):
            candidate = copy.deepcopy(self.imported)
            if kind == 'missing':
                del candidate['series']['bond-issuance']
            elif kind == 'units':
                candidate['series']['bond-issuance']['sourceUnit'] = 'Millions'
            else:
                candidate['series']['bond-issuance']['observations'][0]['date'] = '2011-01-30'
            with self.subTest(kind=kind), patch.object(preview, 'import_manual', return_value=candidate):
                with self.assertRaises(ValueError):
                    preview.assemble_preview(ROOT)

    def test_empty_single_point_zero_and_null_histories_remain_valid(self):
        candidate = copy.deepcopy(self.imported)
        candidate['series']['bond-issuance']['observations'] = []
        candidate['series']['treasury-bond-issuance']['observations'] = [{'date': '2024-02-29', 'value': 0}]
        candidate['series']['corporate-bond-issuance']['observations'] = [{'date': '2024-03-31', 'value': None}]
        with patch.object(preview, 'import_manual', return_value=candidate):
            catalog, observations, _ = preview.assemble_preview(ROOT)
        self.assertEqual(catalog['dataset']['observationStart'], '2024-02-29')
        self.assertEqual(catalog['dataset']['observationEnd'], '2024-03-31')
        self.assertEqual(observations['series']['bond-issuance'], [])
        for series in candidate['series'].values():
            series['observations'] = []
        with patch.object(preview, 'import_manual', return_value=candidate):
            catalog, _, _ = preview.assemble_preview(ROOT)
        self.assertIsNone(catalog['dataset']['observationEnd'])

    def test_rejects_mixed_snapshot_and_non_sifma_fallback(self):
        documents = copy.deepcopy(self.documents)
        documents[1]['snapshotId'] = 'other'
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            preview.validate_preview(*documents)
        documents = copy.deepcopy(self.documents)
        documents[1]['series']['fed-assets'] = [{'date': '2024-02-29', 'value': 1}]
        with self.assertRaisesRegex(ValueError, 'Only SIFMA'):
            preview.validate_preview(*documents)

    def test_build_isolated_and_failure_preserves_previous_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'site/assets/vendor').mkdir(parents=True)
            (root / 'site/assets/vendor/echarts-5.6.0.min.js').write_text('x' * 100001)
            (root / 'site/index.html').write_text('preview app')
            (root / 'site/data').mkdir()
            (root / 'site/data/catalog.json').write_text('user demo edits')
            (root / 'dist').mkdir()
            (root / 'dist/index.html').write_text('previous demo build')
            with patch.object(preview, 'assemble_preview', return_value=self.documents), patch.object(build, 'ROOT', root):
                output = build.build('preview')
                self.assertEqual(output, root / 'dist-preview')
                self.assertEqual(json.loads((output / 'data/catalog.json').read_text()), self.documents[0])
                self.assertFalse((output / 'data/manual').exists())
                self.assertEqual((root / 'site/data/catalog.json').read_text(), 'user demo edits')
                self.assertEqual((root / 'dist/index.html').read_text(), 'previous demo build')
            before = {p: p.read_bytes() for p in output.rglob('*') if p.is_file()}
            with patch.object(preview, 'assemble_preview', side_effect=ValueError('correction needs reason')):
                with self.assertRaises(ValueError):
                    preview.build_preview(root)
            self.assertEqual(before, {p: p.read_bytes() for p in output.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
