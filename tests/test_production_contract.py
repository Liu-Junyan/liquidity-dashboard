import copy
import unittest

from scripts.contracts import validate_points, validate_snapshot
from scripts.policies import COMPARISONS, POLICY_VERSION


def example_snapshot():
    """Small illustrative contract inputs; never used by a production data path."""
    common = {'schemaVersion': 2, 'snapshotId': 'test-snapshot'}
    timestamp = '2026-11-16T07:00:00Z'
    categories = [{'id': f'category-{index}', 'name': f'Layer {index}'} for index in range(4)]
    indicators = []
    for identifier, frequency, availability in [('weekly', 'weekly', 'numeric'),
                                                ('daily', 'daily', 'numeric'),
                                                ('future', 'monthly', 'empty'),
                                                ('pattern', 'irregular', 'nonnumeric')]:
        indicators.append({'id': identifier, 'seriesId': identifier, 'categoryId': 'category-0',
                           'name': identifier, 'unit': '%', 'explanation': 'Illustrative test series',
                           'nativeFrequency': frequency, 'comparisonPolicy': copy.deepcopy(COMPARISONS[frequency]),
                           'availability': availability, 'sources': ['https://example.test/series']})
    catalog = common | {'dataset': {'mode': 'production', 'isDemo': False, 'generatedAt': timestamp,
                                    'observationStart': '2026-11-11', 'observationEnd': '2026-11-13'},
                        'categories': categories, 'indicators': indicators}
    observations = common | {'series': {
        'weekly': [{'date': '2026-11-11', 'value': 3}],
        'daily': [{'date': '2026-11-12', 'value': 0}, {'date': '2026-11-13', 'value': None}],
        'future': [], 'pattern': [],
    }}
    provenance, outcomes = {}, {}
    for identifier, latest in [('weekly', '2026-11-11'), ('daily', '2026-11-13'), ('hidden-input', '2026-11-13')]:
        provenance[identifier] = {'specHash': 'a' * 64, 'method': 'automatic', 'sourceUnit': '%',
                                 'normalizedUnit': '%', 'sourceReference': 'https://example.test/series',
                                 'providerUnits': 'Percent', 'transformation': 'lin',
                                 'requestParameters': {'series_id': 'EXAMPLE', 'units': 'lin'}}
        outcomes[identifier] = {'status': 'updated', 'latestObservationDate': latest,
                                'lastAttempt': timestamp, 'lastSuccessfulCheck': timestamp,
                                'lastDataChange': timestamp}
    manifest = common | {'generatedAt': timestamp, 'sourceInputCommit': 'b' * 40,
                         'policyVersion': POLICY_VERSION, 'inputHashes': dict.fromkeys(provenance, 'c' * 64),
                         'provenance': provenance, 'outcomes': outcomes,
                         'revisionSummary': {'added': 3, 'revised': 0, 'removed': 0}}
    return catalog, observations, manifest


class ProductionContractTests(unittest.TestCase):
    def setUp(self):
        self.catalog, self.observations, self.manifest = example_snapshot()

    def validate(self):
        validate_snapshot(self.catalog, self.observations, self.manifest)

    def test_earlier_policy_versions_remain_readable_for_rollback(self):
        for version in ('4', '5', '6'):
            with self.subTest(version=version):
                self.manifest['policyVersion'] = version
                self.validate()
        self.manifest['policyVersion'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'policy version'):
            self.validate()

    def test_mixed_frequency_short_history_null_zero_and_hidden_input(self):
        self.validate()
        self.assertNotIn('hidden-input', self.observations['series'])

    def test_empty_all_null_and_no_displayed_indicators(self):
        for item in self.catalog['indicators']:
            if item['availability'] != 'nonnumeric':
                item['availability'] = 'empty'
            for point in self.observations['series'][item['id']]:
                point['value'] = None
        self.validate()
        for points in self.observations['series'].values():
            points.clear()
        self.catalog['dataset'].update(observationStart=None, observationEnd=None)
        self.validate()
        self.catalog['indicators'] = []
        self.observations['series'] = {}
        self.validate()

    def test_version_and_snapshot_mismatch_rejected(self):
        for document_index in range(3):
            for field, value in [('schemaVersion', 1), ('schemaVersion', '2'), ('snapshotId', 'different')]:
                documents = example_snapshot()
                documents[document_index][field] = value
                with self.subTest(document=document_index, field=field), self.assertRaises(ValueError):
                    validate_snapshot(*documents)

    def test_invalid_values_and_dates_rejected(self):
        for value in [False, True, '0', float('nan'), float('inf')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_points([{'date': '2026-11-13', 'value': value}])
        for dates in [('2026-11-13', '2026-11-13'), ('2026-11-13', '2026-11-12'),
                      ('20261112', '2026-11-13'), ('2026-02-30', '2026-11-13')]:
            with self.subTest(dates=dates), self.assertRaises(ValueError):
                validate_points([{'date': value, 'value': 1} for value in dates])

    def test_wrong_bounds_units_and_missing_provenance_rejected(self):
        self.catalog['dataset']['observationStart'] = '2020-01-01'
        with self.assertRaisesRegex(ValueError, 'bounds'):
            self.validate()
        self.setUp()
        self.catalog['indicators'][0]['unit'] = 'bp'
        with self.assertRaisesRegex(ValueError, 'unit disagrees'):
            self.validate()
        self.setUp()
        for mapping in ('inputHashes', 'provenance', 'outcomes'):
            del self.manifest[mapping]['weekly']
        with self.assertRaisesRegex(ValueError, 'requires provenance'):
            self.validate()

    def test_source_only_observations_and_wrong_availability_rejected(self):
        self.observations['series']['hidden-input'] = []
        with self.assertRaisesRegex(ValueError, 'source-only inputs stay hidden'):
            self.validate()
        self.setUp()
        self.catalog['indicators'][0]['availability'] = 'empty'
        with self.assertRaisesRegex(ValueError, 'Availability'):
            self.validate()

    def test_requests_and_references_cannot_carry_credentials_or_ambiguous_transforms(self):
        for params in [{'api_key': 'fake-secret'}, {'url': 'https://example.test/?api_key=fake'},
                       {'frequency': 'w'}, {'units': 'pch'}]:
            self.setUp()
            self.manifest['provenance']['daily']['requestParameters'].update(params)
            with self.subTest(params=params), self.assertRaises(ValueError):
                self.validate()
        for reference in ['https://example.test/?api_key=fake', 'https://user:fake@example.test/']:
            self.setUp()
            self.manifest['provenance']['daily']['sourceReference'] = reference
            with self.subTest(reference=reference), self.assertRaisesRegex(ValueError, 'sanitized'):
                self.validate()

    def test_utc_and_attempt_check_change_separation(self):
        outcome = self.manifest['outcomes']['daily']
        outcome.update(status='unchanged', lastDataChange='2026-11-15T07:00:00Z')
        self.validate()
        outcome.update(status='retained', lastSuccessfulCheck='2026-11-15T07:00:00Z')
        self.validate()
        outcome['lastSuccessfulCheck'] = outcome['lastAttempt']
        with self.assertRaisesRegex(ValueError, 'cannot advance'):
            self.validate()
        for value in ['2026-11-16T07:00:00', '2026-11-16T07:00:00+08:00', '2026-11-17T07:00:00Z']:
            self.setUp()
            self.manifest['outcomes']['daily']['lastAttempt'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.validate()

    def test_derived_hashes_must_identify_exact_inputs(self):
        record = self.manifest['provenance']['daily']
        record.update(method='derived', calculation='illustrative-difference',
                      inputHashes={'hidden-input': 'c' * 64}, missingInputs=[])
        del self.manifest['inputHashes']['daily']
        self.manifest['outcomes']['daily']['status'] = 'derived'
        self.validate()
        record['inputHashes']['hidden-input'] = 'd' * 64
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.validate()
        record['inputHashes'] = {'unknown-input': None}
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.validate()

    def test_first_time_failure_leaves_derived_output_empty(self):
        self.manifest['outcomes']['hidden-input'].update(
            status='failed', latestObservationDate=None, lastSuccessfulCheck=None, lastDataChange=None)
        del self.manifest['inputHashes']['hidden-input']
        self.manifest['provenance']['daily'].update(method='derived', calculation='illustrative-difference',
                                                   inputHashes={}, missingInputs=['hidden-input'])
        del self.manifest['inputHashes']['daily']
        self.manifest['outcomes']['daily'].update(status='derived', latestObservationDate=None)
        self.observations['series']['daily'] = []
        self.catalog['indicators'][1]['availability'] = 'empty'
        self.catalog['dataset']['observationEnd'] = '2026-11-11'
        self.validate()
        self.manifest['provenance']['daily']['missingInputs'] = ['unknown-input']
        with self.assertRaisesRegex(ValueError, 'failed sources'):
            self.validate()

    def test_unconnected_definition_can_have_unknown_frequency(self):
        self.catalog['indicators'][2].update(nativeFrequency=None, comparisonPolicy=COMPARISONS['irregular'])
        self.validate()
        self.catalog['indicators'][0].update(nativeFrequency=None, comparisonPolicy=COMPARISONS['irregular'])
        with self.assertRaisesRegex(ValueError, 'Unknown native frequency'):
            self.validate()

    def test_manual_inputs_cannot_own_automatic_requests(self):
        record = self.manifest['provenance']['daily']
        record['method'] = 'manual'
        self.manifest['outcomes']['daily']['status'] = 'imported'
        with self.assertRaisesRegex(ValueError, 'Manual inputs'):
            self.validate()
        record['requestParameters'] = {}
        self.validate()

    def test_manual_date_value_points_use_series_level_provenance(self):
        self.manifest['provenance']['daily'] = {
            'specHash': 'a' * 64, 'method': 'manual',
            'sourceUnit': '%', 'normalizedUnit': '%',
            'sourceReference': 'Illustrative workbook, daily sheet, value column',
            'requestParameters': {}, 'transformation': 'lin',
        }
        self.manifest['outcomes']['daily'] = {
            'status': 'imported', 'latestObservationDate': '2026-11-13',
            'lastAttempt': None, 'lastSuccessfulCheck': None, 'lastDataChange': None,
        }
        # Candidate points after CSV parsing: no per-row references, release dates,
        # or correction notes. CSV parsing and commit comparisons arrive in Slice 2.
        self.observations['series']['daily'] = [
            {'date': '2026-11-12', 'value': 0},
            {'date': '2026-11-13', 'value': None},
        ]
        self.validate()
        self.manifest['provenance']['daily']['sourceReference'] = ''
        with self.assertRaisesRegex(ValueError, 'reference'):
            self.validate()

    def test_comparison_policy_mismatch_and_malformed_payloads(self):
        self.catalog['indicators'][1]['comparisonPolicy']['maxAgeDays'] = 8
        with self.assertRaisesRegex(ValueError, 'Comparison policy'):
            self.validate()
        for value in (None, {}, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_snapshot(value, self.observations, self.manifest)


if __name__ == '__main__':
    unittest.main()
