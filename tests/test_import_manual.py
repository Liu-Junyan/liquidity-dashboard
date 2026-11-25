import csv
import subprocess
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from scripts.import_manual import import_manual, parse_csv, validate_owner
from scripts.registry import FIELDS, load_registry


class ManualCSVTests(unittest.TestCase):
    def test_native_dates_missing_zero_and_exact_decimal_comparison(self):
        points = parse_csv('\ufeffdate,value\n2024-02-29,0\n2024-04-15, \n2024-12-31,1.234567890123456789\n')
        self.assertEqual(list(points), ['2024-02-29', '2024-04-15', '2024-12-31'])
        self.assertEqual(list(points.values()), [0, None, Decimal('1.234567890123456789')])
        self.assertEqual(parse_csv('date,value\n'), {})
        self.assertEqual(parse_csv('date,value\n2024-01-01,\n'), {'2024-01-01': None})

    def test_reject_bad_headers_shape_dates_and_numbers(self):
        invalid = [
            '', 'value,date\n', 'date,value,note\n', 'date,date\n',
            'date,value\n\n', 'date,value\n2024-01-01\n', 'date,value\n2024-01-01,1,2\n',
            'date,value\n2024-01-01,"1\n',
        ]
        invalid += [f'date,value\n{day},1\n' for day in
                    ['20240101', '2024-1-01', '2023-02-29', '2024-01-01T00:00:00', ' 2024-01-01']]
        invalid += [f'date,value\n2024-01-01,{value}\n' for value in
                    ['NaN', 'Infinity', '-inf', '1e999', '1e-999', 'true', 'null', 'NA', '$1', '1_000', '"1,000"']]
        invalid += ['date,value\n2024-01-02,1\n2024-01-01,2\n',
                    'date,value\n2024-01-01,1\n2024-01-01,2\n']
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_csv(text)


class ManualGitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Offline Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'core.hooksPath', '/dev/null')
        (self.repo / 'data/manual').mkdir(parents=True)
        self.entry = dict.fromkeys(FIELDS, '') | {
            'series_id': 'sample', 'name': 'Sample', 'status': 'draft',
            'update_method': 'manual', 'source_unit': 'Millions', 'normalized_unit': 'Billions',
            'native_frequency': 'irregular',
        }
        self.write_registry()
        self.empty = self.commit('Initial registry')
        self.write('date,value\n2024-01-01,1000\n2024-02-29,0\n2024-04-30,\n')
        self.baseline = self.commit('Add initial input')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def write_registry(self):
        with (self.repo / 'data/registry.csv').open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, FIELDS)
            writer.writeheader()
            writer.writerow(self.entry)

    def write(self, text):
        (self.repo / 'data/manual/sample.csv').write_text(text, encoding='utf-8')

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-q', '-m', message)
        return self.git('rev-parse', 'HEAD')

    def test_initial_addition_and_metadata_remain_source_scale_without_activation(self):
        result = import_manual(self.repo)
        self.assertEqual(result['sourceInputCommit'], self.baseline)
        self.assertEqual(result['revisionSummary'], {'added': 3, 'revised': 0, 'removed': 0})
        sample = result['series']['sample']
        self.assertEqual(sample['observations'][0]['value'], 1000)  # not normalized to 1
        self.assertIsNone(sample['observations'][-1]['value'])
        self.assertIsNone(sample['sourceReference'])  # incomplete draft can be checked offline
        self.assertEqual(sample['conversionFactor'], 0.001)
        self.assertEqual(sample['sourceUnit'], 'Millions')
        self.assertEqual(sample['normalizedUnit'], 'Billions')

    def test_new_dates_need_no_reason_and_formatting_is_not_a_correction(self):
        self.write('date,value\n2024-01-01,1e3\n2024-02-29,0.00\n2024-04-30,\n2024-12-31,8\n')
        self.commit('Append new observation')
        result = import_manual(self.repo, base=self.baseline)
        self.assertEqual(result['revisionSummary'], {'added': 1, 'revised': 0, 'removed': 0})

    def test_automatic_commit_adds_no_csv_parse_but_still_checks_its_message(self):
        automatic = self.repo / 'data/automatic'
        automatic.mkdir()
        (automatic / 'sample.json').write_text('{}')
        commit = self.commit('Automatic refresh')
        with patch('scripts.import_manual.parse_csv', wraps=parse_csv) as parse:
            result = import_manual(self.repo)
        parse.assert_called_once()  # The initial manual input.
        self.assertEqual(result['sourceInputCommit'], commit)
        self.assertEqual([entry['commit'] for entry in result['audit']], [self.baseline])
        self.git('commit', '--amend', '-m', 'Automatic refresh\n\nManual-Reason: malformed')
        with self.assertRaisesRegex(ValueError, 'Use Manual-Reason'):
            import_manual(self.repo)

    def test_registry_only_commit_revalidates_manual_ownership(self):
        self.entry['update_method'] = 'automatic'
        self.write_registry()
        commit = self.commit('Transfer ownership')
        with self.assertRaisesRegex(ValueError, commit[:12] + '.*conflicting ownership'):
            import_manual(self.repo)

    def test_committed_correction_nulling_and_removal_require_exact_coverage(self):
        self.write('date,value\n2024-01-01,\n2024-04-30,3\n')
        for message in [
            'Correct sample for 2024-01-01',
            'Manual-Reason: other 2024-01-01..2024-04-30: corrected publication',
            'Manual-Reason: sample 2024-01-01: corrected publication',
            'Manual-Reason: sample 2024-01-01..2024-04-30: ',
            'Manual-Reason: sample 2024-04-30..2024-01-01: corrected publication',
            'Manual-Reason: sample 2024-02-30: corrected publication',
        ]:
            with self.subTest(message=message), self.assertRaises(ValueError):
                import_manual(self.repo, working_tree=True, message=message)
        self.commit('Correct publication\n\nManual-Reason: sample 2024-01-01..2024-04-30: '
                    'publisher replaced provisional values and withdrew February')
        result = import_manual(self.repo, base=self.baseline)
        self.assertEqual(result['revisionSummary'], {'added': 0, 'revised': 2, 'removed': 1})

    def test_undocumented_intermediate_revision_cannot_be_hidden_or_overridden(self):
        self.write('date,value\n2024-01-01,2\n2024-02-29,0\n2024-04-30,\n')
        self.commit('No correction reason')
        self.write('date,value\n2024-01-01,1000\n2024-02-29,0\n2024-04-30,\n')
        self.commit('Manual-Reason: sample 2024-01-01: restore previous value')
        with self.assertRaisesRegex(ValueError, 'corrections/removals'):
            import_manual(self.repo, message='Manual-Reason: sample 2024-01-01: cannot override Git')

    def test_whole_file_removal_including_missing_rows_needs_reason(self):
        (self.repo / 'data/manual/sample.csv').unlink()
        with self.assertRaisesRegex(ValueError, '2024-04-30'):
            import_manual(self.repo, working_tree=True)
        self.commit('Remove input\n\nManual-Reason: sample 2024-01-01..2024-04-30: withdrawn source')
        result = import_manual(self.repo, base=self.baseline)
        self.assertEqual(result['series'], {})
        self.assertEqual(result['revisionSummary']['removed'], 3)

    def test_working_candidate_is_read_only_and_not_a_committed_source(self):
        self.write('date,value\n2024-01-01,5\n2024-02-29,0\n2024-04-30,\n')
        before = self.git('status', '--porcelain')
        contents = (self.repo / 'data/manual/sample.csv').read_bytes()
        result = import_manual(self.repo, working_tree=True,
                               message='Manual-Reason: sample 2024-01-01: fix transcription')
        self.assertIsNone(result['sourceInputCommit'])
        self.assertEqual(result['comparisonCommit'], self.baseline)
        self.assertEqual(before, self.git('status', '--porcelain'))
        self.assertEqual(contents, (self.repo / 'data/manual/sample.csv').read_bytes())
        self.assertEqual(import_manual(self.repo)['series']['sample']['observations'][0]['value'], 1000)

    def test_sub_float_precision_changes_still_need_reasons(self):
        self.write('date,value\n2024-01-01,1000.00000000000000001\n2024-02-29,0\n2024-04-30,\n')
        with self.assertRaisesRegex(ValueError, 'corrections/removals'):
            import_manual(self.repo, working_tree=True)

    def test_merge_message_must_cover_changes_against_first_parent(self):
        original_branch = self.git('branch', '--show-current')
        self.git('checkout', '-b', 'correction')
        self.write('date,value\n2024-01-01,2\n2024-02-29,0\n2024-04-30,\n')
        reason = 'Manual-Reason: sample 2024-01-01: publisher correction'
        self.commit(reason)
        import_manual(self.repo)  # PR head can be validated independently.
        self.git('checkout', original_branch)
        self.git('merge', '--no-ff', 'correction', '-m', 'Merge correction')
        with self.assertRaisesRegex(ValueError, 'corrections/removals'):
            import_manual(self.repo)
        self.git('commit', '--amend', '-m', 'Merge correction\n\n' + reason)
        self.assertEqual(import_manual(self.repo)['revisionSummary']['revised'], 1)

    def test_unknown_ids_ownership_units_and_unsafe_references_fail(self):
        original = self.entry.copy()
        for field, value in [('series_id', 'other'), ('update_method', 'automatic'),
                             ('update_method', 'derived'), ('source_unit', ''),
                             ('normalized_unit', 'bananas'), ('source_unit', 'Trillions'),
                             ('source_reference', 'https://example.test/?api_key=secret')]:
            self.entry = original | {field: value}
            self.write_registry()
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                import_manual(self.repo, working_tree=True)
        self.entry = original
        self.write_registry()
        with self.assertRaisesRegex(ValueError, 'ownership'):
            validate_owner(load_registry(self.repo / 'data/registry.csv'), 'sample', 'automatic')

    def test_missing_history_shallow_checkout_and_unrelated_baseline_fail(self):
        with self.assertRaisesRegex(ValueError, 'baseline/history'):
            import_manual(self.repo, base='missing-commit')
        clone = self.root / 'shallow'
        self.git('clone', '-q', '--depth=1', self.repo.as_uri(), str(clone))
        with self.assertRaisesRegex(ValueError, 'shallow'):
            import_manual(clone)
        self.git('checkout', '--orphan', 'unrelated')
        self.git('rm', '-rf', '.')
        (self.repo / 'other').touch()
        unrelated = self.commit('Unrelated root')
        with self.assertRaisesRegex(ValueError, 'first-parent'):
            import_manual(self.repo, revision=self.baseline, base=unrelated)

    def test_root_with_inputs_requires_explicit_trusted_baseline(self):
        self.git('checkout', '--orphan', 'root-inputs')
        root = self.commit('Initial input without prior Git baseline')
        with self.assertRaisesRegex(ValueError, 'root commit'):
            import_manual(self.repo)
        self.assertIn('sample', import_manual(self.repo, base=root)['series'])

    def test_utf8_path_and_symlink_validation(self):
        path = self.repo / 'data/manual/sample.csv'
        path.write_bytes(b'date,value\n2024-01-01,\xff\n')
        with self.assertRaises(UnicodeError):
            import_manual(self.repo, working_tree=True)
        path.unlink()
        path.symlink_to(self.repo / 'data/registry.csv')
        with self.assertRaisesRegex(ValueError, 'regular file'):
            import_manual(self.repo, working_tree=True)
        self.commit('Symlink input')
        with self.assertRaisesRegex(ValueError, 'regular file'):
            import_manual(self.repo)


if __name__ == '__main__':
    unittest.main()
