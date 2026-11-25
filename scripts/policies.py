"""Reviewed production specifications and fail-closed activation gates.

Run this file to check active specifications offline. Implementations are registered
only when their executable paths exist; production activation remains separate.
"""
import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __package__:
    from .registry import DEFAULT_REGISTRY, load_registry
else:
    from registry import DEFAULT_REGISTRY, load_registry

ROOT = Path(__file__).resolve().parents[1]
POLICY_VERSION = '8'
FRED_OBSERVATION_START = '2010-01-01'
PILOT_SERIES = frozenset({'fed-assets', 'sofr', 'effr', 'sofr-effr-spread', 'fed-repo'})
ACTIVE_SERIES = PILOT_SERIES | frozenset({
    'sofr99', 'sofr-tail-spread', 'reserve-balances', 'bank-total-assets',
    'reserve-assets-ratio', 'treasury-account', 'reverse-repo', 'discount-window',
    'swap-line', 'fima-repo', 'bank-loans', 'lending-standards', 'treasury-yield-chg',
    'bond-issuance', 'treasury-bond-issuance', 'corporate-bond-issuance',
    'credit-spreads-ig', 'credit-spreads-hy', 'vix', 'move', 'dollar-index',
})
# Conservative calendar-day diagnostics, not release-time guarantees or rejection
# rules. These tolerate weekends, holidays and ordinary provider ingestion lag.
FRESHNESS_DAYS = {'fed-assets': 14, 'sofr': 7, 'effr': 7, 'fed-repo': 7}
FRESHNESS_DAYS.update({
    'sofr99': 7, 'reverse-repo': 7, 'treasury-yield-chg': 7,
    'credit-spreads-ig': 7, 'credit-spreads-hy': 7, 'vix': 7,
    'reserve-balances': 14, 'treasury-account': 14, 'discount-window': 14,
    'swap-line': 14, 'fima-repo': 14, 'bank-total-assets': 21, 'bank-loans': 21,
    # Quarter-start labels predate publication; allow a full quarter plus lag.
    'lending-standards': 150,
})


def executable_implementations():
    # Lazy imports keep policies and the shared validators independently usable.
    from scripts.derive import difference, reserve_ratio, tail_difference
    from scripts.normalize import normalize
    from scripts.providers.fred import FredClient
    from scripts.import_manual import import_manual
    return {'fred-observations': FredClient.fetch, 'same-date-difference': difference,
            'same-date-reserve-ratio': reserve_ratio, 'same-date-tail-difference': tail_difference,
            'manual-csv': import_manual,
            **{f'normalize:{name}': normalize for name in
               ('identity', 'millions-to-billions', 'percentage-points-to-bp')}}


@dataclass(frozen=True)
class SeriesPolicy:
    method: str
    implementation: str
    date_rule: str
    request_units: str | None = None
    calculation: str | None = None
    seasonal_adjustment: str = 'NSA'


POLICIES = {
    'fed-assets': SeriesPolicy('automatic', 'fred-observations', 'wednesday-level', 'lin'),
    'sofr': SeriesPolicy('automatic', 'fred-observations', 'source-business-date', 'lin'),
    'effr': SeriesPolicy('automatic', 'fred-observations', 'source-business-date', 'lin'),
    'fed-repo': SeriesPolicy('automatic', 'fred-observations', 'source-business-date', 'lin'),
    'sofr-effr-spread': SeriesPolicy('derived', 'same-date-difference', 'exact-date-union',
                                     calculation='sofr-effr'),
    'sofr99': SeriesPolicy('automatic', 'fred-observations', 'source-business-date', 'lin'),
    'sofr-tail-spread': SeriesPolicy('derived', 'same-date-tail-difference', 'exact-date-union',
                                   calculation='sofr99-sofr'),
    'reserve-balances': SeriesPolicy('automatic', 'fred-observations', 'wednesday-level', 'lin'),
    'bank-total-assets': SeriesPolicy('automatic', 'fred-observations', 'wednesday-ending', 'lin',
                                     seasonal_adjustment='SA'),
    'reserve-assets-ratio': SeriesPolicy('derived', 'same-date-reserve-ratio', 'exact-date-union',
                                       calculation='100*reserve-balances/bank-total-assets'),
    'treasury-account': SeriesPolicy('automatic', 'fred-observations', 'wednesday-level', 'lin'),
    'reverse-repo': SeriesPolicy('automatic', 'fred-observations', 'source-business-date', 'lin'),
    'discount-window': SeriesPolicy('automatic', 'fred-observations', 'wednesday-level', 'lin'),
    'swap-line': SeriesPolicy('automatic', 'fred-observations', 'wednesday-level', 'lin'),
    'fima-repo': SeriesPolicy('automatic', 'fred-observations', 'wednesday-ending', 'lin'),
    'bank-loans': SeriesPolicy('automatic', 'fred-observations', 'wednesday-ending', 'lin',
                              seasonal_adjustment='SA'),
    'lending-standards': SeriesPolicy('automatic', 'fred-observations', 'quarter-start', 'lin'),
    'treasury-yield-chg': SeriesPolicy('automatic', 'fred-observations', 'source-business-date', 'chg'),
    'bond-issuance': SeriesPolicy('manual', 'manual-csv', 'month-end'),
    'treasury-bond-issuance': SeriesPolicy('manual', 'manual-csv', 'month-end'),
    'credit-spreads-ig': SeriesPolicy('automatic', 'fred-observations', 'source-daily-close', 'lin'),
    'credit-spreads-hy': SeriesPolicy('automatic', 'fred-observations', 'source-daily-close', 'lin'),
    'corporate-bond-issuance': SeriesPolicy('manual', 'manual-csv', 'month-end'),
    'move': SeriesPolicy('manual', 'manual-csv', 'source-daily-level'),
    'dollar-index': SeriesPolicy('manual', 'manual-csv', 'source-daily-level'),
    'vix': SeriesPolicy('automatic', 'fred-observations', 'source-daily-close', 'lin'),
}
COLLECTION_SERIES = frozenset(key for key in ACTIVE_SERIES if POLICIES[key].method != 'manual')

# No arbitrary registry notes or formulas are executed. Yield collection
# must explicitly use this chg policy, never infer a transform from notes.
REQUEST_TRANSFORMS = {'treasury-yield-chg': 'chg'}
CALCULATIONS = {
    'sofr-tail-spread': (frozenset({'sofr99', 'sofr'}), 'sofr99-sofr'),
    'sofr-effr-spread': (frozenset({'sofr', 'effr'}), 'sofr-effr'),
    'reserve-assets-ratio': (frozenset({'reserve-balances', 'bank-total-assets'}),
                             '100*reserve-balances/bank-total-assets'),
}
UNIT_ALIASES = {'percent': '%', 'bps': 'bp', 'biliions': 'billions', 'trillion': 'trillions'}
CONVERSIONS = {
    ('millions', 'billions'): ('millions-to-billions', 0.001),
    ('%', 'bp'): ('percentage-points-to-bp', 100),
}
KNOWN_UNITS = {'millions', 'billions', 'trillions', '%', 'bp', 'none'}
COMPARISONS = {
    'daily': {'periods': [4, 13], 'periodUnit': 'week', 'match': 'on-or-before',
              'maxAgeDays': 7, 'explicitMissing': 'null', 'valueScale': 1},
    'weekly': {'periods': [4, 13], 'periodUnit': 'week', 'match': 'exact-date', 'valueScale': 1},
    'monthly': {'periods': [1, 12], 'periodUnit': 'month', 'match': 'source-period-date', 'valueScale': 1},
    'quarterly': {'periods': [1, 4], 'periodUnit': 'quarter', 'match': 'source-period-date', 'valueScale': 1},
    'annual': {'periods': [], 'match': 'none', 'valueScale': 1},
    'irregular': {'periods': [], 'match': 'none', 'valueScale': 1},
}
SPEC_FIELDS = ('update_method', 'provider', 'provider_series_id', 'source_reference',
               'source_unit', 'normalized_unit', 'native_frequency', 'input_series_ids', 'formula', 'notes')


def canonical_unit(value):
    value = (value or '').strip().lower()
    return UNIT_ALIASES.get(value, value)


def conversion_policy(entry):
    """Return a named conversion and factor; labels never convert observations."""
    source, target = (canonical_unit(entry[key]) for key in ('source_unit', 'normalized_unit'))
    if source == target and source in KNOWN_UNITS:
        return ('identity', 1)
    if (source, target) in CONVERSIONS:
        return CONVERSIONS[source, target]
    raise ValueError(f'Unsupported conversion: {source!r} -> {target!r}')


def derived_output_factor(identifier, entry):
    conversion, factor = conversion_policy(entry)
    if conversion == 'identity':
        return factor
    if identifier in {'sofr-effr-spread', 'sofr-tail-spread'} and conversion == 'percentage-points-to-bp':
        return factor
    raise ValueError(f'{identifier}: unsupported derived output conversion')


def specification_hash(entry):
    """Bind a source review to measurement semantics, independently of display edits."""
    encoded = json.dumps({key: entry[key] for key in SPEC_FIELDS}, sort_keys=True,
                         ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def load_reviews():
    return json.loads((ROOT / 'data/source-reviews.json').read_text(encoding='utf-8'))


def validate_policies(registry, selected=PILOT_SERIES, *, policies=None, reviews=None,
                      require_implementations=False, implementations=None):
    """Check definitions separately from activation; return dependency-first IDs."""
    policies = POLICIES if policies is None else policies
    reviews = load_reviews() if reviews is None else reviews
    if implementations is None:
        implementations = executable_implementations() if require_implementations else {}
    series, selected = registry['series'], set(selected)
    for identifier, policy in policies.items():
        if identifier not in series:
            raise ValueError(f'{identifier}: policy references an unknown registry ID')
        if policy.method != series[identifier]['update_method']:
            raise ValueError(f'{identifier}: conflicting ownership in policy and registry')
    for identifier in REQUEST_TRANSFORMS:
        if identifier not in series or series[identifier]['update_method'] != 'automatic':
            raise ValueError(f'{identifier}: request transform requires automatic ownership')
    order, visiting = [], set()

    def visit(identifier):
        if identifier in order:
            return
        if identifier in visiting:
            raise ValueError(f'{identifier}: cyclic dependency')
        if identifier not in selected:
            raise ValueError(f'{identifier}: dependency must be selected explicitly')
        if identifier not in series or identifier not in policies:
            raise ValueError(f'{identifier}: missing registry entry or policy')
        entry, policy = series[identifier], policies[identifier]
        if entry['status'] != 'ready':
            raise ValueError(f'{identifier}: activation requires a ready specification')
        if entry['native_frequency'] not in COMPARISONS:
            raise ValueError(f'{identifier}: unsupported native frequency')
        calendar_rules = {'monthly': {'month-start', 'month-end', 'day-of-month'},
                          'quarterly': {'quarter-start', 'quarter-end', 'day-of-month'}}
        if (entry['native_frequency'] in calendar_rules
                and policy.date_rule not in calendar_rules[entry['native_frequency']]):
            raise ValueError(f'{identifier}: reviewed source period date convention required')
        conversion, _ = conversion_policy(entry)
        if policy.method == 'derived':
            expected = CALCULATIONS.get(identifier)
            actual = (frozenset(entry['input_series_ids']), ''.join((entry['formula'] or '').split()))
            if actual != expected or policy.calculation != actual[1]:
                raise ValueError(f'{identifier}: unknown or mismatched calculation definition')
            derived_output_factor(identifier, entry)
            if policy.request_units is not None:
                raise ValueError(f'{identifier}: formulas consume normalized inputs; no second conversion')
        else:
            if entry['input_series_ids'] or entry['formula']:
                raise ValueError(f'{identifier}: conflicting input ownership')
            if not entry['provider'] or not entry['source_reference']:
                raise ValueError(f'{identifier}: source reference and provider required')
            if policy.method == 'automatic':
                if not entry['provider_series_id']:
                    raise ValueError(f'{identifier}: explicit provider_series_id required')
                expected_transform = REQUEST_TRANSFORMS.get(identifier, 'lin')
                if policy.request_units != expected_transform:
                    raise ValueError(f'{identifier}: ambiguous or unsupported request transform')
            elif policy.method != 'manual' or policy.request_units is not None:
                raise ValueError(f'{identifier}: invalid manual ownership/transform')
        review = reviews.get(identifier, {})
        if review.get('specHash') != specification_hash(entry):
            raise ValueError(f'{identifier}: source specification needs review')
        for field in ('reviewedOn', 'reference', 'explanation', 'dateRule', 'redistribution'):
            if not review.get(field):
                raise ValueError(f'{identifier}: incomplete source review: {field}')
        if review['dateRule'] != policy.date_rule:
            raise ValueError(f'{identifier}: date policy needs review')
        if policy.method == 'automatic' and (
                policy.seasonal_adjustment not in {'NSA', 'SA'}
                or review.get('seasonalAdjustment', 'NSA') != policy.seasonal_adjustment):
            raise ValueError(f'{identifier}: seasonal adjustment policy needs review')
        if require_implementations:
            for capability in (policy.implementation, f'normalize:{conversion}'):
                if not callable(implementations.get(capability)):
                    raise ValueError(f'{identifier}: missing implementation: {capability}')
        visiting.add(identifier)
        for dependency in entry['input_series_ids']:
            visit(dependency)
        visiting.remove(identifier)
        order.append(identifier)

    for identifier in sorted(selected):
        visit(identifier)
    return order


def validate_activation(registry, selected=ACTIVE_SERIES, **kwargs):
    return validate_policies(registry, selected, require_implementations=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument('--check-activation', action='store_true', help='Require active executable paths; does not publish')
    args = parser.parse_args()
    try:
        registry = load_registry(args.input)
        order = validate_policies(registry, ACTIVE_SERIES, require_implementations=args.check_activation)
        validate_activation(registry)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Policy validation failed: {error}\n')
    print(f'Validated {len(order)} production specifications; {len(ACTIVE_SERIES)} activated series. No data collected.')


if __name__ == '__main__':
    main()
