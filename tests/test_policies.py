import copy
import unittest
from dataclasses import replace

from scripts.policies import (ACTIVE_SERIES, PILOT_SERIES, POLICIES, SeriesPolicy, conversion_policy,
                              load_reviews, specification_hash, validate_activation,
                              validate_policies)
from scripts.registry import load_registry


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()

    def test_complete_pilot_with_incomplete_future_entries(self):
        order = validate_policies(self.registry)
        self.assertEqual(set(order), PILOT_SERIES)
        self.assertLess(order.index('sofr'), order.index('sofr-effr-spread'))
        self.assertLess(order.index('effr'), order.index('sofr-effr-spread'))
        self.assertIsNone(self.registry['series']['price-impact']['normalized_unit'])
        self.assertFalse(ACTIVE_SERIES)
        self.assertEqual(validate_activation(self.registry), [])

    def test_missing_executable_paths_cannot_activate(self):
        with self.assertRaisesRegex(ValueError, 'missing implementation'):
            validate_activation(self.registry, PILOT_SERIES)
        with self.assertRaisesRegex(ValueError, 'missing implementation'):
            validate_activation(self.registry, {'fed-assets'}, implementations={'fred-observations': 'planned'})

    def test_source_changes_require_review_but_display_renames_do_not(self):
        self.registry['series']['fed-assets']['name'] = 'Renamed'
        validate_policies(self.registry)
        for field, value in [('provider_series_id', 'OTHER'), ('source_unit', 'Billions'),
                             ('native_frequency', 'daily'), ('source_reference', 'https://example.test'),
                             ('notes', 'Changed measurement')]:
            registry = copy.deepcopy(self.registry)
            registry['series']['fed-assets'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'needs review'):
                validate_policies(registry)

    def test_missing_identity_unknown_conversion_and_wrong_formula_rejected(self):
        for identifier, field, value, message in [
            ('fed-assets', 'provider_series_id', None, 'provider_series_id'),
            ('fed-assets', 'source_unit', 'widgets', 'Unsupported conversion'),
            ('fed-repo', 'source_reference', None, 'source reference'),
            ('sofr-effr-spread', 'formula', '__import__("os")', 'calculation'),
            ('sofr-effr-spread', 'input_series_ids', ['sofr', 'sofr99'], 'calculation'),
            ('fed-repo', 'update_method', 'manual', 'conflicting ownership'),
            ('sofr', 'status', 'unavailable', 'ready specification'),
        ]:
            registry = copy.deepcopy(self.registry)
            registry['series'][identifier][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, message):
                validate_policies(registry)

    def test_missing_dependencies_and_unknown_policy_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, 'dependency must be selected'):
            validate_policies(self.registry, {'sofr-effr-spread'})
        with self.assertRaisesRegex(ValueError, 'missing registry entry or policy'):
            validate_policies(self.registry, {'vix'})
        policies = POLICIES | {'typo-id': POLICIES['sofr']}
        with self.assertRaisesRegex(ValueError, 'unknown registry ID'):
            validate_policies(self.registry, policies=policies)

    def test_explicit_transform_and_date_rules_cannot_drift(self):
        for changes, message in [({'request_units': 'pch'}, 'transform'),
                                 ({'request_units': None}, 'transform'),
                                 ({'date_rule': 'publication-date'}, 'date policy')]:
            policies = POLICIES | {'fed-assets': replace(POLICIES['fed-assets'], **changes)}
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, message):
                validate_policies(self.registry, policies=policies)

    def test_supported_scales_and_corrected_future_formula(self):
        cases = [('Millions', 'Billions', 0.001), ('Billions', 'Billions', 1),
                 ('Biliions', 'Billions', 1), ('%', '%', 1), ('%', 'bp', 100)]
        for source, target, factor in cases:
            with self.subTest(source=source, target=target):
                self.assertEqual(conversion_policy({'source_unit': source, 'normalized_unit': target})[1], factor)
        self.assertEqual(self.registry['series']['reserve-assets-ratio']['formula'],
                         '100 * reserve-balances / bank-total-assets')
        self.assertEqual(self.registry['series']['bank-total-assets']['source_unit'], 'Billions')
        self.assertEqual(self.registry['series']['reverse-repo']['native_frequency'], 'daily')

    def test_missing_review_details_rejected(self):
        reviews = load_reviews()
        reviews['sofr']['redistribution'] = ''
        with self.assertRaisesRegex(ValueError, 'incomplete source review'):
            validate_policies(self.registry, reviews=reviews)
        self.assertEqual(load_reviews()['fed-repo']['specHash'],
                         specification_hash(self.registry['series']['fed-repo']))

    def test_manual_source_is_reviewed_once_in_registry(self):
        # Illustrative metadata only: this does not certify or activate SIFMA data.
        identifier = 'bond-issuance'
        entry = self.registry['series'][identifier]
        entry.update(provider='Test publication', provider_series_id=None,
                     source_reference='Illustrative issuance workbook, monthly sheet, total column',
                     notes='Monthly amounts dated at calendar month-end; illustrative test source.')
        policies = POLICIES | {identifier: SeriesPolicy('manual', 'manual-csv', 'month-end')}
        reviews = load_reviews() | {identifier: {
            'specHash': specification_hash(entry), 'reviewedOn': '2026-11-16',
            'reference': 'Illustrative test review', 'explanation': 'Test monthly issuance',
            'dateRule': 'month-end', 'redistribution': 'Illustrative test data only',
        }}
        self.assertEqual(validate_policies(self.registry, {identifier}, policies=policies,
                                           reviews=reviews), [identifier])
        entry['source_reference'] = None
        with self.assertRaisesRegex(ValueError, 'source reference'):
            validate_policies(self.registry, {identifier}, policies=policies, reviews=reviews)
        entry['source_reference'] = 'Different workbook or table'
        with self.assertRaisesRegex(ValueError, 'needs review'):
            validate_policies(self.registry, {identifier}, policies=policies, reviews=reviews)


if __name__ == '__main__':
    unittest.main()
