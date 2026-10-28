"""Regenerate deterministic, explicitly synthetic weekly observations (stdlib only)."""
import json
import math
import hashlib
from datetime import date, timedelta
from pathlib import Path

if __package__:
    from .catalog import build_catalog
    from .registry import load_registry
else:
    from catalog import build_catalog
    from registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
END = date(2026, 10, 28)
START = date(2021, 10, 27)


def generate(catalog=None):
    dates = [START + timedelta(weeks=i) for i in range((END - START).days // 7 + 1)]
    # Deliberately irregular, bounded signals: illustrative shapes, never market estimates.
    catalog = catalog if catalog is not None else build_catalog(load_registry())
    profiles = {
        'amount': (600, 0.8, 90), 'spread': (15, 0.02, 8),
        'ratio': (8, 0.01, 2), 'index': (100, 0.015, 4),
        'price': (30, 0.015, 3), 'count': (120, 0.2, 25),
        'multiple': (3, 0.002, 0.5), 'scalar': (1, 0.001, 0.25),
    }
    overrides = {
        'reserve-balances': (3800, -3.1, 210), 'reverse-repo': (1700, -5.4, 190),
        'treasury-account': (520, 0.5, 160), 'fed-assets': (8700, -7.5, 170),
        'discount-window': (8, 0.01, 6), 'fed-repo': (12, 0.01, 8),
        'cross-currency-basis': (-25, -0.02, 12), 'swap-line': (5, 0.005, 3),
        'fima-repo': (2, 0.002, 1), 'credit-spreads': (350, 0.3, 80),
        'cds-spreads': (75, 0.1, 20), 'bond-issuance': (30, 0.03, 8),
        'risky-debt-net-issuance': (0, 0.005, 8),
        'zero-issuance-days': (3, 0, 2), 'asset-volatility': (20, 0.01, 5),
        'bid-ask-spread': (0.5, 0.001, 0.15), 'market-depth': (0.8, -0.001, 0.2),
    }
    result = {}
    for indicator in catalog['indicators']:
        identifier = indicator['id']
        # Stable per-series shapes survive CSV reordering and adding/removing rows.
        series_index = int.from_bytes(hashlib.sha256(identifier.encode()).digest()[:2], 'big') % 30
        kind = indicator['unit']['kind']
        precision = indicator['unit']['precision']
        if kind == 'unquantified':
            result[identifier] = [{'date': observed_at.isoformat(), 'value': None} for observed_at in dates]
            continue
        profile = profiles.get(kind, (5, 0.01, 1))
        base, trend, amplitude = overrides.get(identifier, profile) if kind == 'amount' else profile
        points = []
        for i, observed_at in enumerate(dates):
            wave = (math.sin(i / 13 + series_index) * 0.55
                    + math.sin(i / 5.7 + series_index * 0.7) * 0.23
                    + math.sin(i * 1.7 + series_index) * 0.08
                    + math.cos(i / 31 + series_index) * 0.6)
            raw_value = base + trend * i + amplitude * wave
            signed = kind == 'spread' or identifier in {'positioning', 'risky-debt-net-issuance', 'lending-standards', 'bank-credit-growth'}
            value = round(raw_value if signed else max(0, raw_value), precision)
            # Include isolated and consecutive gaps, a missing 4-week comparator,
            # and a stale last observation. Nulls are never filled or interpolated.
            missing = i in {47 + series_index, 123, 124, 207 - series_index}
            missing |= identifier == 'reverse-repo' and i == len(dates) - 5
            missing |= identifier == 'positioning' and i == len(dates) - 1
            points.append({'date': observed_at.isoformat(), 'value': None if missing else value})
        result[identifier] = points
    return result


if __name__ == '__main__':
    output = ROOT / 'site/data/observations.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    catalog = build_catalog(load_registry())
    observations = generate(catalog)
    (ROOT / 'site/data/catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    output.write_text(json.dumps(observations, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Generated {len(observations)} registry-selected fixture series: {START} to {END}')
