import copy
import io
import json
import os
import tempfile
import unittest
from dataclasses import replace
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from scripts.collect import collect, load_api_key, refresh
from scripts.derive import derive
from scripts.normalize import content_hash, normalize
from scripts.policies import POLICIES, REQUEST_TRANSFORMS
from scripts.providers.fred import CollectionError, FredClient
from scripts.registry import ROOT, load_registry


def points(*values):
    return [{'date': f'2026-11-{day:02d}', 'value': value} for day, value in values]


class Transport:
    """Small FRED-shaped replies, generated independently of collector code."""
    def __init__(self, rows=None, metadata=None, mutate=None):
        self.rows = rows or [('2026-11-12', '4.1'), ('2026-11-13', '.'), ('2026-11-16', '0')]
        self.metadata = metadata or {}
        self.mutate = mutate or (lambda response, params: None)
        self.calls = []

    def __call__(self, url, timeout):
        params = {key: value[0] for key, value in parse_qs(urlsplit(url).query).items()}
        self.calls.append(params)
        if urlsplit(url).path.endswith('/observations'):
            offset, limit = int(params['offset']), int(params['limit'])
            response = {'count': len(self.rows), 'offset': offset, 'limit': limit,
                        'units': params['units'], 'sort_order': 'asc',
                        'realtime_start': '2026-11-17', 'realtime_end': '2026-11-17',
                        'observations': [{'date': day, 'value': value}
                                         for day, value in self.rows[offset:offset + limit]]}
        else:
            response = {'seriess': [{'id': params['series_id'], 'units': 'Percent',
                         'frequency_short': 'D', 'seasonal_adjustment_short': 'NSA',
                         'observation_start': self.rows[0][0], 'observation_end': self.rows[-1][0],
                         **self.metadata}]}
        self.mutate(response, params)
        return io.BytesIO(json.dumps(response).encode())


class FredTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()
        self.entry = self.registry['series']['sofr']

    def fetch(self, transport, entry=None, policy=None):
        return FredClient('secret-test-key', opener=transport, page_size=2).fetch(
            entry or self.entry, policy or POLICIES['sofr'])

    def test_full_history_pagination_missing_zero_and_sanitized_provenance(self):
        transport = Transport()
        result = self.fetch(transport)
        self.assertEqual(result['observations'], points((12, 4.1), (13, None), (16, 0)))
        self.assertEqual([call.get('offset') for call in transport.calls], [None, '0', '2'])
        self.assertEqual(result['requestParameters']['observation_start'], '1776-07-04')
        self.assertNotIn('secret-test-key', json.dumps(result))
        self.assertFalse(any('vintage_dates' in call or 'realtime_start' in call for call in transport.calls))

    def test_incomplete_or_invalid_responses_are_rejected(self):
        def mutate(field, value):
            def change(response, params):
                if 'observations' in response:
                    response[field] = value
            return change
        cases = [('count', 0), ('observations', []), ('offset', 99), ('units', 'pch'),
                 ('observations', [{'date': '2026-11-12', 'value': 'NaN'},
                                   {'date': '2026-11-13', 'value': '0'}])]
        for field, value in cases:
            with self.subTest(field=field), self.assertRaises(CollectionError):
                self.fetch(Transport(mutate=mutate(field, value)))
        for rows in [ [('2026-11-12', '1'), ('2026-11-12', '2')],
                      [('2026-11-13', '1'), ('2026-11-12', '2')],
                      [('bad-date', '1')], [('2026-11-13', 'arbitrary secret text')] ]:
            with self.subTest(rows=rows), self.assertRaises(CollectionError):
                self.fetch(Transport(rows=rows))

    def test_cross_page_changes_and_metadata_truncation_fail(self):
        for field, value in [('count', 4), ('realtime_end', '2026-11-18')]:
            def change(response, params):
                if params.get('offset') == '2':
                    response[field] = value
            with self.subTest(field=field), self.assertRaises(CollectionError):
                self.fetch(Transport(mutate=change))
        with self.assertRaisesRegex(CollectionError, 'metadata bounds'):
            self.fetch(Transport(metadata={'observation_start': '2000-01-01'}))

    def test_metadata_review_and_weekly_date_rule(self):
        for metadata in [{'id': 'OTHER'}, {'units': 'Basis Points'}, {'frequency_short': 'M'},
                         {'seasonal_adjustment_short': 'SA'}]:
            with self.subTest(metadata=metadata), self.assertRaises(CollectionError):
                self.fetch(Transport(metadata=metadata))
        entry = self.registry['series']['fed-assets']
        metadata = {'units': 'Millions of U.S. Dollars', 'frequency_short': 'W',
                    'frequency': 'Weekly, As of Wednesday'}
        result = self.fetch(Transport(rows=[('2026-11-11', '3000000')], metadata=metadata),
                            entry, POLICIES['fed-assets'])
        self.assertEqual(normalize(entry, result['observations'])[0]['value'], 3000)
        with self.assertRaisesRegex(CollectionError, 'weekly observation'):
            self.fetch(Transport(rows=[('2026-11-12', '3000000')], metadata=metadata),
                       entry, POLICIES['fed-assets'])

    def test_chg_is_requested_and_scaled_to_bp_once(self):
        entry = self.registry['series']['treasury-yield-chg'] | {'provider_series_id': 'DGS10'}
        policy = replace(POLICIES['sofr'], request_units=REQUEST_TRANSFORMS['treasury-yield-chg'])
        transport = Transport(rows=[('2026-11-12', '.'), ('2026-11-13', '0.10')])
        result = self.fetch(transport, entry, policy)
        self.assertEqual(transport.calls[1]['units'], 'chg')
        self.assertEqual(normalize(entry, result['observations']), points((12, None), (13, 10)))
        self.assertEqual(result['metadata']['units'], 'Percent')

    def test_retries_are_bounded_and_errors_do_not_leak_keys(self):
        for code, expected_calls in [(429, 3), (503, 3), (400, 1), (403, 1)]:
            with self.subTest(code=code):
                calls, sleeps = [], []
                def fail(url, timeout):
                    calls.append(timeout)
                    raise HTTPError(url, code, 'secret-test-key', {}, None)
                client = FredClient('secret-test-key', opener=fail, sleep=sleeps.append)
                with self.assertRaises(CollectionError) as caught:
                    client.fetch(self.entry, POLICIES['sofr'])
                self.assertEqual(len(calls), expected_calls)
                self.assertEqual(sleeps, [1, 2] if expected_calls == 3 else [])
                self.assertNotIn('secret-test-key', str(caught.exception))
        responses = [URLError('secret-test-key'), io.BytesIO(b'{"ok": true}')]
        def retry(url, timeout):
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        self.assertEqual(FredClient('key', opener=retry, sleep=lambda _: None).request(
            'series', {'series_id': 'SOFR', 'file_type': 'json'}), {'ok': True})
        with patch('scripts.providers.fred.build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.side_effect = IncompleteRead(b'partial')
            with self.assertRaisesRegex(CollectionError, 'network request failed'):
                FredClient('key', sleep=lambda _: None).request('series', {'series_id': 'SOFR'})
            self.assertEqual(opener.return_value.open.call_count, 3)


class CandidateClient:
    def __init__(self, values=None, failures=()):
        self.values = values or {'SOFR': points((12, 4.1), (13, 4.2)),
                                 'EFFR': points((12, 4.0), (13, 4.0))}
        self.failures = failures

    def fetch(self, entry, policy):
        identifier = entry['provider_series_id']
        if identifier in self.failures:
            raise CollectionError('FRED network request failed')
        data = self.values[identifier]
        return {'observations': data,
                'metadata': {'id': identifier, 'units': 'Percent', 'frequency_short': 'D',
                             'seasonal_adjustment_short': 'NSA',
                             'observation_start': data[0]['date'], 'observation_end': data[-1]['date']},
                'requestParameters': {'series_id': identifier, 'units': policy.request_units, 'file_type': 'json'}}


class CollectionTests(unittest.TestCase):
    selected = {'sofr', 'effr', 'sofr-effr-spread'}
    first_time = '2026-11-17T00:00:00Z'
    next_time = '2026-11-18T00:00:00Z'

    def setUp(self):
        self.registry = load_registry()

    def run_collect(self, client=None, **kwargs):
        return collect(self.registry, client or CandidateClient(), selected=self.selected,
                       now=kwargs.pop('now', self.first_time), **kwargs)

    def test_full_replacement_propagates_revisions_and_removals(self):
        first = self.run_collect()
        next_client = CandidateClient({'SOFR': points((12, 4.3), (16, 0)),
                                      'EFFR': points((12, 4.0), (13, 4.0))})
        second = self.run_collect(next_client, previous=first['automatic'], now=self.next_time)
        self.assertEqual(second['automatic']['sofr']['observations'], points((12, 4.3), (16, 0)))
        self.assertEqual(second['automatic']['sofr']['revisionSummary'], {'added': 1, 'revised': 1, 'removed': 1})
        self.assertEqual(second['derived']['sofr-effr-spread']['observations'],
                         points((12, 0.3), (13, None), (16, None)))
        self.assertEqual(second['derived']['sofr-effr-spread']['inputHashes']['sofr'],
                         content_hash(second['normalized']['sofr']))
        unchanged = second['automatic']['effr']['outcome']
        self.assertEqual(unchanged['status'], 'unchanged')
        self.assertEqual(unchanged['lastSuccessfulCheck'], self.next_time)
        self.assertEqual(unchanged['lastDataChange'], self.first_time)

    def test_failure_retains_history_while_other_source_updates(self):
        first = self.run_collect()
        client = CandidateClient({'SOFR': points((12, 4.4), (13, 4.5))}, failures={'EFFR'})
        second = self.run_collect(client, previous=first['automatic'], now=self.next_time)
        retained = second['automatic']['effr']
        self.assertEqual(retained['observations'], first['automatic']['effr']['observations'])
        self.assertEqual(retained['outcome']['status'], 'retained')
        self.assertEqual(retained['outcome']['lastSuccessfulCheck'], self.first_time)
        self.assertEqual(retained['outcome']['lastAttempt'], self.next_time)
        self.assertEqual(second['derived']['sofr-effr-spread']['observations'], points((12, 0.4), (13, 0.5)))
        first_failure = self.run_collect(client)
        self.assertIsNone(first_failure['automatic']['effr']['sourceHash'])
        self.assertEqual(first_failure['derived']['sofr-effr-spread']['missingInputs'], ['effr'])
        self.assertTrue(all(point['value'] is None for point in
                            first_failure['derived']['sofr-effr-spread']['observations']))

    def test_incompatible_source_cannot_be_retained_and_corrupt_cache_fails(self):
        first = self.run_collect()
        old = copy.deepcopy(first['automatic'])
        old['effr']['sourceUnit'] = 'bp'
        with self.assertRaisesRegex(ValueError, 'incompatible stored source'):
            self.run_collect(CandidateClient(failures={'EFFR'}), previous=old, now=self.next_time)
        # A complete successful refetch can replace a prior source definition.
        self.assertEqual(self.run_collect(previous=old, now=self.next_time)['automatic']['effr']['outcome']['status'], 'updated')
        old = copy.deepcopy(first['automatic'])
        old['effr']['observations'][0]['value'] = 100
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.run_collect(previous=old, now=self.next_time)
        old = copy.deepcopy(first['automatic'])
        old['effr']['outcome']['status'] = 'retained'
        with self.assertRaisesRegex(ValueError, 'check transition'):
            self.run_collect(previous=old, now=self.next_time)

    def test_freshness_is_a_diagnostic_and_no_dates_are_filled(self):
        result = self.run_collect(now='2026-12-01T00:00:00Z')
        self.assertEqual(result['automatic']['sofr']['freshness']['status'], 'stale')
        self.assertEqual(len(result['normalized']['sofr']), 2)
        self.assertEqual(result['automatic']['sofr']['outcome']['status'], 'updated')

    def test_only_automatic_paths_written_and_invalid_candidate_not_promoted(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / 'data').mkdir()
            (repo / 'data/registry.csv').write_bytes((ROOT / 'data/registry.csv').read_bytes())
            (repo / 'data/manual').mkdir()
            manual = repo / 'data/manual/bond-issuance.csv'
            manual.write_text('date,value\n2026-10-31,1\n')
            refresh(repo, CandidateClient(), selected=self.selected, now=self.first_time)
            saved = {path.name: path.read_bytes() for path in (repo / 'data/automatic').iterdir()}
            self.assertEqual(set(saved), {'sofr.json', 'effr.json'})
            self.assertEqual(manual.read_text(), 'date,value\n2026-10-31,1\n')
            with self.assertRaises(ValueError):
                refresh(repo, CandidateClient(), selected={'bond-issuance'}, now=self.next_time)
            self.assertEqual(saved, {path.name: path.read_bytes() for path in (repo / 'data/automatic').iterdir()})

    def test_local_key_is_parsed_without_executing_shell(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True):
            path = Path(temporary) / '.env'
            path.write_text('FRED="local-key" # local alias\nUNRELATED=$(false)\n')
            self.assertEqual(load_api_key(path), 'local-key')
            path.write_text('FRED_API_KEY="$(false)"\n')
            self.assertEqual(load_api_key(path), '$(false)')
            with patch.dict(os.environ, {'FRED_API_KEY': 'environment-key'}):
                self.assertEqual(load_api_key(path), 'environment-key')

    def test_normalized_ratio_nulls_zero_and_formula_gate(self):
        inputs = {'reserve-balances': normalize(self.registry['series']['reserve-balances'],
                                               points((12, 3000000), (13, 1000000), (16, None))),
                  'bank-total-assets': normalize(self.registry['series']['bank-total-assets'],
                                                points((12, 25000), (13, 0), (16, 500)))}
        result = derive(self.registry, inputs, {'reserve-assets-ratio'})
        self.assertEqual(result['reserve-assets-ratio']['observations'], points((12, 12), (13, None), (16, None)))
        self.registry['series']['reserve-assets-ratio']['formula'] = 'eval(anything)'
        with self.assertRaisesRegex(ValueError, 'calculation'):
            derive(self.registry, inputs, {'reserve-assets-ratio'})


if __name__ == '__main__':
    unittest.main()
