import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.registry import DEFAULT_REGISTRY, FIELDS, load_registry


class SourceRegistryTests(unittest.TestCase):
    def setUp(self):
        common = dict(status='ready', update_method='automatic', provider='Example provider', native_frequency='daily')
        self.rows = [
            dict.fromkeys(FIELDS, '') | common | dict(series_id='input-source', name='Input source'),
            dict.fromkeys(FIELDS, '') | common | dict(series_id='dashboard-one', indicator_id='dashboard-one', category='货币层', name='Dashboard one'),
            dict.fromkeys(FIELDS, '') | dict(series_id='future-row', indicator_id='future-row', category='信用层', name='Future entry', status='unavailable'),
        ]
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'registry.csv'

    def load_rows(self, rows):
        with self.path.open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return load_registry(self.path)

    def test_registry_is_independent_of_the_generated_catalog(self):
        registry = load_registry()
        self.assertTrue(all(set(row) == set(FIELDS) - {'series_id'} for row in registry['series'].values()))
        rows = [dict.fromkeys(FIELDS, '') | dict(series_id='new-source', indicator_id='new-indicator',
                category='货币层', name='全新指标', status='draft')]
        self.assertEqual(set(self.load_rows(rows)['series']), {'new-source'})

    def test_csv_quotes_chinese_and_multiline_specs_round_trip(self):
        self.rows[0]['notes'] = '来源待确认，含中文\nA, B and "quoted text"'
        registry = self.load_rows(self.rows)
        export = json.loads(json.dumps(registry, ensure_ascii=False))
        self.assertEqual(export['series'][self.rows[0]['series_id']]['notes'], self.rows[0]['notes'])

    def test_deletions_are_allowed_and_duplicate_or_invalid_specs_rejected(self):
        cases = []
        duplicate = copy.deepcopy(self.rows)
        duplicate.append(copy.deepcopy(duplicate[0]))
        cases.append((duplicate, 'duplicate series_id'))
        # Do not delete a calculation input: an actual dependency must still exist.
        referenced = {value.strip() for row in self.rows for value in row['input_series_ids'].split(';')}
        mapped_index = next(index for index, row in enumerate(self.rows) if row['category'] and row['series_id'] not in referenced)
        removed = self.rows[mapped_index]['series_id']
        self.assertNotIn(removed, self.load_rows(self.rows[:mapped_index] + self.rows[mapped_index + 1:])['series'])
        for field, value, message in [
            ('update_method', 'automatic;manual', 'exactly one update_method'),
            ('native_frequency', 'often', 'unknown native_frequency'),
            ('status', 'bad-status', 'status must'),
        ]:
            rows = copy.deepcopy(self.rows)
            rows[0][field] = value
            cases.append((rows, message))
        for rows, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.load_rows(rows)

    def test_unknown_inputs_cycles_and_conflicting_ownership_rejected(self):
        self.rows[0].update(update_method='derived', input_series_ids='unknown-series', formula='input value')
        with self.assertRaisesRegex(ValueError, 'unknown input'):
            self.load_rows(self.rows)
        self.rows[0]['input_series_ids'] = self.rows[1]['series_id']
        self.rows[1].update(update_method='derived', input_series_ids=self.rows[0]['series_id'], formula='input value')
        with self.assertRaisesRegex(ValueError, 'Cyclic derivation'):
            self.load_rows(self.rows)
        self.rows[0]['update_method'] = 'manual'
        with self.assertRaisesRegex(ValueError, 'only derived'):
            self.load_rows(self.rows)

    def test_source_only_inputs_and_ready_derived_specs(self):
        common = dict(status='ready', native_frequency='daily', normalized_unit='percent', comparison_rules='none')
        for identifier in ['input-a', 'input-b']:
            self.rows.append(dict.fromkeys(FIELDS, '') | common | dict(
                series_id=identifier, name=identifier, update_method='manual', provider='Test publication',
                source_reference='Test table 1', source_unit='percent'))
        self.rows[0].update(common, update_method='derived', input_series_ids='input-a; input-b',
                            formula='(input-a - input-b) * 100', normalized_unit='bp')
        entry = self.load_rows(self.rows)['series'][self.rows[0]['series_id']]
        self.assertEqual(entry['input_series_ids'], ['input-a', 'input-b'])
        self.assertEqual(entry['formula'], '(input-a - input-b) * 100')
        self.rows[-1]['status'] = 'draft'
        with self.assertRaisesRegex(ValueError, 'ready specification'):
            self.load_rows(self.rows)

    def test_manual_provider_without_a_url_and_unavailable_future_rows_are_allowed(self):
        self.rows[0].update(status='ready', update_method='automatic', provider='Example provider',
                            native_frequency='daily', source_unit='%', normalized_unit='%', comparison_rules='none',
                            input_series_ids='', formula='')
        for reference, identifier in [('https://example.test/series', ''), ('', 'EXAMPLE'), ('https://example.test/series', 'EXAMPLE')]:
            self.rows[0].update(source_reference=reference, provider_series_id=identifier)
            with self.subTest(reference=reference, identifier=identifier):
                self.load_rows(self.rows)
        self.rows[0].update(source_reference='', provider_series_id='')
        self.load_rows(self.rows)
        self.rows[0]['status'] = ''
        entry = self.load_rows(self.rows)['series'][self.rows[0]['series_id']]
        self.assertEqual(entry['status'], 'draft')
        self.rows.append(dict.fromkeys(FIELDS, '') | dict(series_id='future-source', indicator_id='future-indicator',
                         category='信用层', name='未来指标', status='unavailable'))
        self.assertEqual(self.load_rows(self.rows)['series']['future-source']['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
