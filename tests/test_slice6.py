"""Coverage expansion regressions: real conventions, gates and provenance."""
import unittest
from dataclasses import replace

from scripts.assemble import validate_source_dates
from scripts.collect import freshness
from scripts.derive import derive
from scripts.normalize import normalize
from scripts.notices import notices_for
from scripts.policies import ACTIVE_SERIES, POLICIES, validate_activation
from scripts.providers.fred import CollectionError, FredClient, validate_metadata
from scripts.registry import load_registry
from test_collect import Transport


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()

    def fetch(self, key, rows, metadata):
        transport = Transport(rows=rows, metadata=metadata)
        result = FredClient('offline-key', opener=transport).fetch(
            self.registry['series'][key], POLICIES[key])
        return result, transport

    def test_seasonally_adjusted_bank_inputs_do_not_inherit_pilot_conventions(self):
        metadata = {'frequency_short': 'W', 'frequency': 'Weekly, Ending Wednesday',
                    'units': 'Billions of U.S. Dollars', 'seasonal_adjustment_short': 'SA'}
        for key in ('bank-total-assets', 'bank-loans'):
            record, _ = self.fetch(key, [('2026-11-04', '25000')], metadata)
            self.assertEqual(normalize(self.registry['series'][key], record['observations'])[0]['value'], 25000)
            validate_metadata(record['metadata'], self.registry['series'][key], POLICIES[key], cached=True)
            for changed in ({'seasonal_adjustment_short': 'NSA'}, {'frequency': 'Weekly, As of Wednesday'}):
                with self.subTest(key=key, changed=changed), self.assertRaises(CollectionError):
                    self.fetch(key, [('2026-11-04', '25000')], metadata | changed)
            with self.assertRaises(CollectionError):
                self.fetch(key, [('2026-11-05', '25000')], metadata)
        with self.assertRaisesRegex(ValueError, 'weekly observation'):
            validate_source_dates([{'date': '2026-11-05', 'value': 0}], 'wednesday-ending')
        with self.assertRaisesRegex(ValueError, 'seasonal adjustment'):
            validate_activation(self.registry, policies=POLICIES | {
                'bank-loans': replace(POLICIES['bank-loans'], seasonal_adjustment='NSA')})

    def test_quarter_start_negative_zero_missing_and_lag(self):
        metadata = {'frequency_short': 'Q', 'frequency': 'Quarterly'}
        record, _ = self.fetch('lending-standards',
                              [('2026-04-01', '-5.5'), ('2026-07-01', '.'), ('2026-10-01', '0')], metadata)
        self.assertEqual([p['value'] for p in record['observations']], [-5.5, None, 0])
        self.assertEqual(freshness('lending-standards', record['observations'],
                                  '2027-02-01T00:00:00Z')['status'], 'current')
        for day in ('2026-10-02', '2026-11-01'):
            with self.assertRaisesRegex(CollectionError, 'quarterly observation'):
                self.fetch('lending-standards', [(day, '1')], metadata)

    def test_active_yield_transform_scales_once_and_retains_missing_periods(self):
        record, transport = self.fetch('treasury-yield-chg',
                                      [('2026-11-11', '.'), ('2026-11-12', '.'), ('2026-11-13', '0.05')], {})
        self.assertEqual(transport.calls[-1]['units'], 'chg')
        self.assertEqual(record['metadata']['units'], 'Percent')
        self.assertEqual([p['value'] for p in normalize(self.registry['series']['treasury-yield-chg'],
                                                      record['observations'])], [None, None, 5])

    def test_tail_difference_never_fills_dates_or_multiplies_percentage_points(self):
        inputs = {'sofr99': [{'date': '2026-11-12', 'value': 4.3}, {'date': '2026-11-13', 'value': None}],
                  'sofr': [{'date': '2026-11-12', 'value': 4.1}, {'date': '2026-11-16', 'value': 4}]}
        result = derive(self.registry, inputs, {'sofr-tail-spread'})['sofr-tail-spread']
        self.assertEqual([p['value'] for p in result['observations']], [0.2, None, None])
        self.assertEqual(set(result['inputHashes']), {'sofr99', 'sofr'})

    def test_ice_credit_spreads_preserve_weekend_month_ends_and_rolling_window(self):
        metadata = {'frequency_short': 'D', 'frequency': 'Daily, Close',
                    'units': 'Percent', 'seasonal_adjustment_short': 'NSA'}
        rows = [('2023-11-20', '1.10'), ('2024-03-31', '1.20'), ('2026-11-16', '0.86')]
        for key in ('credit-spreads-ig', 'credit-spreads-hy'):
            with self.subTest(key=key):
                record, transport = self.fetch(key, rows, metadata)
                self.assertEqual(transport.calls[-1]['units'], 'lin')
                self.assertEqual([point['date'] for point in record['observations']],
                                 [day for day, _ in rows])
                validate_source_dates(record['observations'], POLICIES[key].date_rule)
                normalized = normalize(self.registry['series'][key], record['observations'])
                self.assertEqual([point['value'] for point in normalized], [1.1, 1.2, 0.86])
                self.assertTrue(any('ICE Data Indices' in notice['text']
                                    for notice in notices_for(key, '2026')))
                with self.assertRaises(CollectionError):
                    self.fetch(key, rows, metadata | {'seasonal_adjustment_short': 'SA'})
                with self.assertRaises(CollectionError):
                    self.fetch(key, [('2023-11-01', '1.0'), ('2026-11-16', '0.8')],
                               {'observation_start': '2023-11-20', 'observation_end': '2026-11-16'})

    def test_credit_spreads_activate_with_reviewed_permission(self):
        keys = {'credit-spreads-ig', 'credit-spreads-hy'}
        self.assertTrue(keys <= ACTIVE_SERIES)
        self.assertEqual(set(validate_activation(self.registry, keys)), keys)

    def test_vix_index_levels_preserve_missing_markers(self):
        metadata = {'frequency_short': 'D', 'frequency': 'Daily, Close', 'units': 'Index',
                    'seasonal_adjustment_short': 'NSA',
                    'observation_start': '1990-01-02', 'observation_end': '2026-11-16'}
        rows = [('2010-01-01', '.'), ('2010-01-04', '19.5'), ('2026-11-16', '22.91')]
        record, transport = self.fetch('vix', rows, metadata)
        self.assertEqual(transport.calls[-1]['units'], 'lin')
        self.assertEqual([point['value'] for point in record['observations']], [None, 19.5, 22.91])
        normalized = normalize(self.registry['series']['vix'], record['observations'])
        self.assertEqual([point['value'] for point in normalized], [None, 19.5, 22.91])
        self.assertTrue(any('Cboe' in notice['text'] for notice in notices_for('vix', '2026')))
        with self.assertRaises(CollectionError):
            self.fetch('vix', rows, metadata | {'units': 'Percent'})
        with self.assertRaises(CollectionError):
            self.fetch('vix', [('2009-12-31', '20'), ('2026-11-16', '22.91')], metadata)

    def test_vix_activates_with_reviewed_permission(self):
        self.assertIn('vix', ACTIVE_SERIES)
        self.assertEqual(validate_activation(self.registry, {'vix'}), ['vix'])

    def test_deferred_sources_cannot_activate(self):
        for key in ('bid-ask-spread', 'price-impact', 'dollar-index', 'move'):
            self.assertNotIn(key, ACTIVE_SERIES)
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_activation(self.registry, {key})

