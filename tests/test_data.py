import copy
import unittest
from scripts.build import validate
from scripts.catalog import build_catalog
from scripts.generate_fixtures import generate
from scripts.registry import load_registry


class DataContractTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()
        self.catalog = build_catalog(self.registry)
        self.observations = generate(self.catalog)

    def test_fixture_contract_and_reproducibility(self):
        validate(self.catalog, self.observations)
        self.assertEqual(self.observations, generate(self.catalog))
        visible = [(key, row) for key, row in self.registry['series'].items()
                   if row['category'] and row['status'] != 'unavailable']
        self.assertEqual([item['id'] for item in self.catalog['indicators']], [row['indicator_id'] for _, row in visible])
        self.assertEqual([item['name'] for item in self.catalog['indicators']], [row['name'] for _, row in visible])
        self.assertEqual([item['seriesId'] for item in self.catalog['indicators']], [key for key, _ in visible])
        self.assertEqual(set(self.observations), {item['id'] for item in self.catalog['indicators']})

    def test_reject_invalid_values_and_weekly_dates(self):
        if not self.catalog['indicators']:
            self.skipTest('No displayed numeric fixtures to corrupt')
        identifier = self.catalog['indicators'][0]['id']
        for invalid in [float('nan'), float('inf'), '0', False]:
            broken = copy.deepcopy(self.observations)
            broken[identifier][0]['value'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate(self.catalog, broken)
        broken = copy.deepcopy(self.observations)
        broken[identifier][1]['date'] = broken[identifier][0]['date']
        with self.assertRaises(ValueError):
            validate(self.catalog, broken)

    def test_missing_series_and_wrong_category_rejected(self):
        if not self.catalog['indicators']:
            self.skipTest('No displayed fixtures to corrupt')
        identifier = self.catalog['indicators'][0]['id']
        del self.observations[identifier]
        with self.assertRaises(ValueError):
            validate(self.catalog, self.observations)
        self.setUp()
        self.catalog['indicators'][0]['categoryId'] = 'nonexistent'
        with self.assertRaises(ValueError):
            validate(self.catalog, self.observations)

    def test_registry_edits_control_membership_names_order_and_units(self):
        template = copy.deepcopy(next(iter(self.registry['series'].values())))
        template.update(category='货币层', status='draft', input_series_ids=[], formula=None)
        self.registry['series'] = {f'example-{index}': template | {'indicator_id':f'example-{index}', 'name':f'Example {index}'} for index in range(3)}
        original = list(self.registry['series'].items())
        displayed = [key for key, row in original if row['category'] and row['status'] != 'unavailable']
        removed, hidden, renamed = displayed[:3]
        del self.registry['series'][removed]
        self.registry['series'][hidden]['status'] = 'unavailable'
        entry = self.registry['series'][renamed]
        entry.update(name='修改后的指标', normalized_unit='Millions', category='信用层')
        added = copy.deepcopy(entry)
        added.update(indicator_id='new-dashboard-entry', name='新指标')
        self.registry['series'] = {'new-series': added} | self.registry['series']
        catalog = build_catalog(self.registry)
        ids = {item['id'] for item in catalog['indicators']}
        self.assertNotIn(removed, ids)
        self.assertNotIn(hidden, ids)
        self.assertEqual(catalog['indicators'][0]['id'], 'new-dashboard-entry')
        revised = next(item for item in catalog['indicators'] if item['seriesId'] == renamed)
        self.assertEqual((revised['name'], revised['categoryId'], revised['unit']['label']), ('修改后的指标', 'category-3', '百万美元'))
        validate(catalog, generate(catalog))

    def test_empty_categories_and_all_hidden_catalog_are_valid(self):
        for row in self.registry['series'].values():
            row['status'] = 'unavailable'
        catalog = build_catalog(self.registry)
        self.assertEqual(catalog['indicators'], [])
        self.assertEqual(generate(catalog), {})
        validate(catalog, {})

    def test_fixture_shapes_survive_registry_reordering(self):
        self.registry['series'] = dict(reversed(list(self.registry['series'].items())))
        self.assertEqual(self.observations, generate(build_catalog(self.registry)))

    def test_unquantified_and_missing_unit_entries_are_explicit(self):
        entry = copy.deepcopy(next(iter(self.registry['series'].values())))
        entry.update(category='货币层', indicator_id='unquantified-example', name='未量化示例', status='draft')
        self.registry['series']['unquantified-example'] = entry
        identifier = entry['indicator_id']
        entry.update(normalized_unit=None)
        item = next(item for item in build_catalog(self.registry)['indicators'] if item['id'] == identifier)
        self.assertEqual(item['unit']['label'], '待确认')
        entry['status'] = 'unquantified'
        catalog = build_catalog(self.registry)
        observations = generate(catalog)
        self.assertTrue(all(point['value'] is None for point in observations[identifier]))
        validate(catalog, observations)
        observations[identifier][0]['value'] = 42
        with self.assertRaises(ValueError):
            validate(catalog, observations)


if __name__ == '__main__':
    unittest.main()
