import copy
import csv
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import assemble, build
from scripts.artifacts import promote_snapshot
from scripts.collect import collect
from scripts.normalize import content_hash
from scripts.policies import POLICIES, SeriesPolicy, specification_hash
from scripts.providers.fred import CollectionError
from scripts.registry import ROOT, load_registry

NOW = '2026-11-17T12:00:00Z'


class SavedInputClient:
    def __init__(self, failed=()):
        self.failed = failed

    def fetch(self, entry, policy):
        identifier = entry['indicator_id']
        if identifier in self.failed:
            raise CollectionError('Illustrative offline outage')
        weekly = entry['native_frequency'] == 'weekly'
        quarterly = entry['native_frequency'] == 'quarterly'
        days = ['2026-11-04', '2026-11-11'] if weekly else ['2026-11-12', '2026-11-13', '2026-11-16']
        values = [6000000, 7000000] if weekly else [4.1, 4.0, None] if identifier == 'sofr' else [4, 4, None] if identifier == 'effr' else [0, 1, None]
        if quarterly:
            days, values = ['2026-07-01', '2026-10-01'], [-5, 0]
        units = {'Millions': 'Millions of U.S. Dollars', 'Billions': 'Billions of US Dollars',
                 '%': 'Percent', 'none': 'Index'}
        return {'observations': [dict(date=day, value=value) for day, value in zip(days, values)],
                'metadata': {'id': entry['provider_series_id'], 'units': units[entry['source_unit']],
                             'frequency_short': 'W' if weekly else 'Q' if quarterly else 'D',
                             'seasonal_adjustment_short': policy.seasonal_adjustment,
                             'observation_start': days[0], 'observation_end': days[-1]},
                'requestParameters': {'series_id': entry['provider_series_id'], 'units': policy.request_units,
                                      'observation_start': '2010-01-01'}}


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'data/automatic').mkdir(parents=True)
        for name in ('registry.csv', 'categories.json', 'source-reviews.json'):
            shutil.copy(ROOT / 'data' / name, self.root / 'data' / name)
        shutil.copytree(ROOT / 'data/manual', self.root / 'data/manual')
        self.git('init', '-q')
        self.git('config', 'user.email', 'offline@example.test')
        self.git('config', 'user.name', 'Offline test')
        self.git('commit', '--allow-empty', '-qm', 'Empty trusted baseline')
        self.git('add', 'data')
        self.git('commit', '-qm', 'Initial specifications')
        self.registry = load_registry(self.root / 'data/registry.csv')
        self.records = collect(self.registry, SavedInputClient(), now=NOW)['automatic']
        self.save_inputs()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True).stdout.decode()

    def save_inputs(self):
        for key, record in self.records.items():
            (self.root / f'data/automatic/{key}.json').write_text(json.dumps(record))

    def candidate(self, **kwargs):
        return assemble.assemble(self.root, now=NOW, **kwargs)

    def test_normalization_derived_hashes_membership_and_notices(self):
        catalog, observations, manifest = self.candidate()
        self.assertEqual(observations['series']['fed-assets'][0]['value'], 6000)
        self.assertEqual(observations['series']['sofr-effr-spread'], [
            {'date': '2026-11-12', 'value': 10}, {'date': '2026-11-13', 'value': 0},
            {'date': '2026-11-16', 'value': None}])
        self.assertNotIn('sofr', observations['series'])
        self.assertEqual(manifest['provenance']['sofr-effr-spread']['inputHashes']['sofr'],
                         content_hash(manifest['normalizedInputs']['sofr']))
        self.assertEqual(catalog['dataset']['publisher'], 'Junyan Liu')
        spread = next(item for item in catalog['indicators'] if item['id'] == 'sofr-effr-spread')
        self.assertIn('Junyan Liu', json.dumps(spread['notices']))
        self.assertEqual(spread['comparisonPolicy']['valueScale'], 1)
        self.assertEqual(catalog['dataset']['observationEnd'], '2026-11-16')
        for item in catalog['indicators']:
            self.assertNotIn('合成', item['explanation'])
            if not item['inputAvailable']:
                self.assertEqual(observations['series'][item['id']], [])
        self.assertEqual(self.records['fed-assets']['observations'][0]['value'], 6000000)

    def test_missing_input_blocks_without_inventing_history(self):
        (self.root / 'data/automatic/sofr.json').unlink()
        with self.assertRaisesRegex(ValueError, 'saved automatic input'):
            self.candidate()

    def test_first_failed_source_preserves_null_derived_history(self):
        self.records = collect(self.registry, SavedInputClient({'sofr'}), now=NOW)['automatic']
        self.save_inputs()
        catalog, observations, manifest = self.candidate()
        self.assertNotIn('sofr', manifest['inputHashes'])
        self.assertEqual(manifest['provenance']['sofr-effr-spread']['missingInputs'], ['sofr'])
        self.assertTrue(all(point['value'] is None for point in observations['series']['sofr-effr-spread']))
        self.assertEqual(observations['series']['fed-assets'][0]['value'], 6000)

    def test_retained_input_can_assemble_without_a_network_request(self):
        self.records = collect(self.registry, SavedInputClient({'sofr'}), previous=self.records,
                               now='2026-11-17T12:01:00Z')['automatic']
        self.save_inputs()
        docs = assemble.assemble(self.root, now='2026-11-17T12:02:00Z')
        self.assertEqual(docs[2]['outcomes']['sofr']['status'], 'retained')
        self.assertEqual(docs[1]['series']['sofr-effr-spread'][0]['value'], 10)

    def test_corruption_and_changed_metadata_rejected(self):
        original = copy.deepcopy(self.records['fed-assets'])
        for mutate in [lambda r: r['observations'][0].update(value=1),
                       lambda r: r['metadata'].update(units='Percent'),
                       lambda r: r.update(normalizedUnit='%'),
                       lambda r: r['requestParameters'].update(observation_start='2000-01-01')]:
            self.records['fed-assets'] = copy.deepcopy(original)
            mutate(self.records['fed-assets'])
            self.save_inputs()
            with self.assertRaises(ValueError):
                self.candidate()

    def test_snapshot_digest_rejects_mixed_and_modified_content(self):
        documents = self.candidate()
        documents[1]['series']['fed-assets'][0]['value'] += 1
        with self.assertRaisesRegex(ValueError, 'digest'):
            assemble.validate_assembled_snapshot(*documents)

    def test_rehashed_snapshot_still_requires_correct_calculation_and_source_notices(self):
        original = self.candidate()
        for kind in ('calculation', 'notice', 'hash'):
            documents = copy.deepcopy(original)
            if kind == 'calculation':
                documents[1]['series']['sofr-effr-spread'][0]['value'] = 100
            elif kind == 'notice':
                next(item for item in documents[0]['indicators'] if item['id'] == 'fed-repo')['notices'] = []
            else:
                documents[2]['normalizedInputs']['sofr'][0]['value'] = 100
            snapshot_id = assemble.snapshot_identity(documents)
            for document in documents:
                document['snapshotId'] = snapshot_id
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                assemble.validate_assembled_snapshot(*documents)

    def test_source_calendar_validation_rejects_wrong_period_conventions(self):
        for date, rule in [('2026-11-12', 'wednesday-level'), ('2026-02-27', 'month-end'),
                           ('2026-04-30', 'quarter-end'), ('2026-02-01', 'quarter-start')]:
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                assemble.validate_source_dates([{'date': date, 'value': 0}], rule)

    def test_empty_activation_has_null_bounds_and_no_fixtures(self):
        catalog, observations, manifest = self.candidate(selected=[])
        self.assertIsNone(catalog['dataset']['observationStart'])
        self.assertIsNone(catalog['dataset']['observationEnd'])
        self.assertTrue(all(not value for value in observations['series'].values()))
        self.assertEqual(manifest['inputHashes'], {})

    def test_atomic_replacement_and_failure_preserve_previous_snapshot(self):
        output = self.root / 'data/snapshot'
        documents = self.candidate()
        promote_snapshot(output, documents)
        before = (output / 'manifest.json').read_bytes()
        with patch('scripts.artifacts.replace_directory', side_effect=OSError('exchange failed')):
            with self.assertRaises(OSError):
                promote_snapshot(output, documents)
        self.assertEqual((output / 'manifest.json').read_bytes(), before)
        second = assemble.assemble(self.root, now='2026-11-17T12:03:00Z')
        promote_snapshot(output, second)
        self.assertEqual(json.loads((output / 'manifest.json').read_text())['snapshotId'], second[2]['snapshotId'])
        self.assertFalse(list(output.parent.glob('.snapshot-*')))

    def test_production_build_copies_only_selected_snapshot_and_preserves_demo(self):
        shutil.copytree(ROOT / 'site', self.root / 'site')
        original = (self.root / 'site/data/observations.json').read_bytes()
        output = self.root / 'data/snapshot'
        documents = self.candidate()
        promote_snapshot(output, documents)
        (self.root / 'dist').mkdir()
        (self.root / 'dist/old.txt').write_text('old')
        with patch.object(build, 'ROOT', self.root), patch.object(build, 'build_demo') as demo:
            build.build('production')
            demo.assert_not_called()
        self.assertEqual((self.root / 'site/data/observations.json').read_bytes(), original)
        self.assertFalse((self.root / 'dist/old.txt').exists())
        self.assertFalse((self.root / 'dist/data/automatic').exists())
        self.assertEqual(json.loads((self.root / 'dist/data/observations.json').read_text()), documents[1])

    def test_source_changes_are_identified_without_mislabeling_head(self):
        path = self.root / 'data/categories.json'
        path.write_text(path.read_text() + '\n')
        manifest = self.candidate()[2]
        self.assertIn('data/categories.json', manifest['modifiedSourceFiles'])
        self.assertEqual(manifest['sourceInputCommit'], self.git('rev-parse', 'HEAD').strip())

    def test_reviewed_manual_input_is_audited_and_uncommitted_correction_rejected(self):
        identifier = 'bond-issuance'
        path = self.root / 'data/registry.csv'
        with path.open(encoding='utf-8-sig') as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        for row in rows:
            if row['series_id'] == identifier:
                row['source_reference'] = 'Illustrative offline workbook, monthly totals'
        with path.open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        entry = load_registry(path)['series'][identifier]
        review_path = self.root / 'data/source-reviews.json'
        reviews = json.loads(review_path.read_text())
        reviews[identifier] = {'specHash': specification_hash(entry), 'reviewedOn': '2026-11-17',
            'reference': 'offline test', 'explanation': 'Illustrative test only',
            'dateRule': 'month-end', 'redistribution': 'Offline fixture'}
        review_path.write_text(json.dumps(reviews))
        manual_path = self.root / f'data/manual/{identifier}.csv'
        manual_path.parent.mkdir(exist_ok=True)
        self.git('rm', '-q', str(manual_path.relative_to(self.root)))
        self.git('commit', '-qm', 'Remove prior input for isolated manual fixture\n\n'
                 'Manual-Reason: bond-issuance 2011-01-01..2026-12-31: replace with offline fixture')
        manual_path.write_text('date,value\n2026-09-30,0\n2026-10-31,12\n')
        self.git('add', 'data/registry.csv', 'data/source-reviews.json', 'data/manual')
        self.git('commit', '-qm', 'Add illustrative manual input')
        with patch.dict(POLICIES, {identifier: SeriesPolicy('manual', 'manual-csv', 'month-end')}):
            documents = self.candidate(selected={identifier})
            self.assertEqual(documents[1]['series'][identifier][-1]['value'], 12)
            self.assertEqual(documents[2]['provenance'][identifier]['method'], 'manual')
            manual_path.write_text('date,value\n2026-09-30,0\n2026-10-31,13\n')
            with self.assertRaisesRegex(ValueError, 'commit and audit'):
                self.candidate(selected={identifier})


if __name__ == '__main__':
    unittest.main()
