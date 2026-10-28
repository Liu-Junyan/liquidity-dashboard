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
        self.assertEqual(len(self.catalog['indicators']), 8)
        for category in self.catalog['categories']:
            self.assertEqual(sum(item['categoryId'] == category['id'] for item in self.catalog['indicators']), 2)

    def test_reject_invalid_values_and_weekly_dates(self):
        for invalid in [float('nan'), float('inf'), '0', False]:
            broken = copy.deepcopy(self.observations)
            broken['sofr'][0]['value'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate(self.catalog, broken)
        broken = copy.deepcopy(self.observations)
        broken['sofr'][1]['date'] = broken['sofr'][0]['date']
        with self.assertRaises(ValueError):
            validate(self.catalog, broken)

    def test_missing_series_and_wrong_category_rejected(self):
        del self.observations['sofr']
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


if __name__ == '__main__':
    unittest.main()
