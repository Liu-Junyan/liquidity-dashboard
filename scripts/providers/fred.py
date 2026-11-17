"""Fetch FRED's complete current history; no vintages or incremental merges."""
import json
import math
import time
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, build_opener

from ..contracts import iso_date, validate_points, validate_request
from ..policies import canonical_unit


class CollectionError(ValueError):
    """Safe diagnostics: never include a request URL, response body, or API key."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class FredClient:
    def __init__(self, api_key, *, timeout=20, attempts=3, page_size=100000,
                 opener=None, sleep=time.sleep):
        if not api_key:
            raise ValueError('FRED_API_KEY is required')
        if not 1 <= attempts <= 5 or not 0 < timeout <= 60 or not 1 <= page_size <= 100000:
            raise ValueError('Invalid FRED request limits')
        self.api_key, self.timeout, self.attempts = api_key, timeout, attempts
        self.page_size = page_size
        self.open = opener or build_opener(NoRedirect()).open
        self.sleep = sleep

    def request(self, endpoint, params):
        if endpoint not in {'series', 'series/observations'}:
            raise ValueError('Unsupported FRED endpoint')
        validate_request(params)
        url = 'https://api.stlouisfed.org/fred/' + endpoint + '?' + urlencode(
            params | {'api_key': self.api_key})
        for attempt in range(self.attempts):
            try:
                with self.open(url, timeout=self.timeout) as response:
                    body = response.read(32 * 1024 * 1024 + 1)
                if len(body) > 32 * 1024 * 1024:
                    raise CollectionError('FRED response exceeds size limit')
                result = json.loads(body)
                if not isinstance(result, dict) or 'error_code' in result:
                    raise CollectionError('FRED returned an invalid response')
                return result
            except HTTPError as error:
                retry = error.code in {429, 500, 502, 503, 504}
                message = f'FRED HTTP {error.code}'
                error.close()
            except (URLError, TimeoutError, OSError, HTTPException):
                retry, message = True, 'FRED network request failed'
            except (UnicodeError, json.JSONDecodeError):
                raise CollectionError('FRED returned invalid JSON') from None
            if not retry or attempt + 1 == self.attempts:
                raise CollectionError(message) from None
            self.sleep(2 ** attempt)

    def fetch(self, entry, policy):
        """Review live metadata, then validate every page before returning values."""
        params = {'series_id': entry['provider_series_id'], 'file_type': 'json'}
        try:
            metadata = self.request('series', params)['seriess']
            if not isinstance(metadata, list) or len(metadata) != 1:
                raise CollectionError('FRED metadata must identify exactly one series')
            metadata = validate_metadata(metadata[0], entry, policy)
            params |= {'units': policy.request_units, 'sort_order': 'asc',
                       'observation_start': '1776-07-04', 'observation_end': '9999-12-31',
                       'limit': self.page_size, 'offset': 0}
            points, count, realtime = [], None, None
            while count is None or len(points) < count:
                page = self.request('series/observations', params | {'offset': len(points)})
                if type(page['count']) is not int or not 0 < page['count'] <= 1000000:
                    raise CollectionError('FRED returned an empty or excessive history')
                if count is None:
                    count = page['count']
                    realtime = (page['realtime_start'], page['realtime_end'])
                    for day in realtime:
                        iso_date(day)
                if (page['count'] != count or page['offset'] != len(points)
                        or page['limit'] != self.page_size or page['units'] != policy.request_units
                        or page['sort_order'] != 'asc'
                        or (page['realtime_start'], page['realtime_end']) != realtime):
                    raise CollectionError('FRED pagination or transformation mismatch')
                rows = page['observations']
                if not isinstance(rows, list) or len(rows) != min(self.page_size, count - len(points)):
                    raise CollectionError('FRED history is truncated')
                for row in rows:
                    raw = row['value']
                    if not isinstance(raw, str):
                        raise CollectionError('FRED observation value must be a string')
                    value = None if raw == '.' else float(raw)
                    if value is not None and not math.isfinite(value):
                        raise CollectionError('FRED observation is not finite')
                    points.append({'date': row['date'], 'value': value})
            validate_points(points)
            if (points[0]['date'] != metadata['observation_start']
                    or points[-1]['date'] != metadata['observation_end']):
                raise CollectionError('FRED history does not match metadata bounds; retry full refresh')
            if policy.date_rule == 'wednesday-level' and any(
                    iso_date(point['date']).weekday() != 2 for point in points):
                raise CollectionError('FRED weekly observation date changed')
            return {'observations': points, 'metadata': metadata, 'requestParameters': params}
        except CollectionError:
            raise
        except (ValueError, KeyError, TypeError, OverflowError):
            raise CollectionError('FRED metadata or observations failed validation') from None


def validate_metadata(metadata, entry, policy):
    units = {'millions': 'Millions of U.S. Dollars', 'billions': 'Billions of US Dollars',
             '%': 'Percent'}
    # FRED uses both "US" and "U.S." in otherwise identical dollar unit labels.
    def unit_label(value):
        return value.replace('U.S.', 'US')
    expected = units.get(canonical_unit(entry['source_unit']))
    frequency = {'daily': 'D', 'weekly': 'W'}.get(entry['native_frequency'])
    if (entry['provider'] != 'FRED' or metadata['id'] != entry['provider_series_id']
            or expected is None or unit_label(metadata['units']) != unit_label(expected)
            or frequency is None or metadata['frequency_short'] != frequency
            or metadata['seasonal_adjustment_short'] != 'NSA'):
        raise CollectionError('FRED source units, frequency, identity, or seasonal adjustment changed')
    if policy.date_rule == 'wednesday-level' and metadata['frequency'] != 'Weekly, As of Wednesday':
        raise CollectionError('FRED weekly date convention changed')
    if iso_date(metadata['observation_start']) > iso_date(metadata['observation_end']):
        raise CollectionError('Invalid FRED metadata history bounds')
    return {key: metadata[key] for key in ('id', 'units', 'frequency_short',
            'seasonal_adjustment_short', 'observation_start', 'observation_end')}
