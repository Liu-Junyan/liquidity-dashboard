import copy
import json
import unittest
from pathlib import Path
from scripts.build import validate
from scripts.generate_fixtures import generate

ROOT = Path(__file__).resolve().parents[1]


class DataContractTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'site/data/catalog.json').read_text())
        self.observations = json.loads((ROOT / 'site/data/observations.json').read_text())

    def test_fixture_contract_and_reproducibility(self):
        validate(self.catalog, self.observations)
        self.assertEqual(self.observations, generate())
        self.assertEqual(len(self.catalog['indicators']), 30)
        self.assertEqual([category['name'] for category in self.catalog['categories']], ['货币层', '离岸层', '信用层', '金融市场层'])
        for category, expected in zip(self.catalog['categories'], [10, 4, 9, 7]):
            self.assertEqual(sum(item['categoryId'] == category['id'] for item in self.catalog['indicators']), expected)
        # The Markdown inventory is the source of truth: preserve exactly one indicator per row.
        brief = (ROOT / 'docs/implementation-brief.md').read_text()
        inventory = brief.split('#### Article framework:')[1].split('### 6.')[0]
        article_names = [line.split('|')[1].strip().rsplit(' / ', 1)[1] for line in inventory.splitlines() if line.startswith('| ') and ' / ' in line.split('|')[1] and not line.startswith('| Indicator')]
        self.assertEqual([item['name'] for item in self.catalog['indicators']], article_names)

    def test_reject_invalid_values_and_weekly_dates(self):
        for invalid in [float('nan'), float('inf'), '0', False]:
            broken = copy.deepcopy(self.observations)
            broken['sofr-effr-spread'][0]['value'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate(self.catalog, broken)
        broken = copy.deepcopy(self.observations)
        broken['sofr-effr-spread'][1]['date'] = broken['sofr-effr-spread'][0]['date']
        with self.assertRaises(ValueError):
            validate(self.catalog, broken)

    def test_missing_series_and_wrong_category_rejected(self):
        del self.observations['sofr-effr-spread']
        with self.assertRaises(ValueError):
            validate(self.catalog, self.observations)
        self.setUp()
        self.catalog['indicators'][0]['categoryId'] = 'nonexistent'
        with self.assertRaises(ValueError):
            validate(self.catalog, self.observations)

    def test_add_indicator_through_configuration_only(self):
        extra = copy.deepcopy(self.catalog['indicators'][0])
        extra['id'] = 'additional-indicator'
        extra['name'] = '新增指标（示例）'
        self.catalog['indicators'].append(extra)
        self.observations[extra['id']] = copy.deepcopy(self.observations['reserve-balances'])
        validate(self.catalog, self.observations)

    def test_unquantified_pattern_and_unresolved_sources_are_explicit(self):
        self.assertTrue(all(point['value'] is None for point in self.observations['cross-asset-selling']))
        broken = copy.deepcopy(self.observations)
        broken['cross-asset-selling'][0]['value'] = 42
        with self.assertRaises(ValueError):
            validate(self.catalog, broken)
        self.catalog['indicators'][0]['source'] = {'name':'Unresolved', 'url':None}
        with self.assertRaises(ValueError):
            validate(self.catalog, self.observations)


if __name__ == '__main__':
    unittest.main()
