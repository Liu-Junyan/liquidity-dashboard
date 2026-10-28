"""Regenerate deterministic, explicitly synthetic weekly observations (stdlib only)."""
import json
import math
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
END = date(2026, 10, 28)
START = date(2021, 10, 27)


def generate():
    dates = [START + timedelta(weeks=i) for i in range((END - START).days // 7 + 1)]
    # Deliberately irregular, bounded signals: illustrative shapes, never market estimates.
    specifications = [
        ('reserve-balances', 3800, -3.1, 210, 1),
        ('reverse-repo', 1700, -5.4, 190, 1),
        ('sofr', 0.8, 0.013, 1.1, 2),
        ('effr', 0.7, 0.012, 1.0, 2),
        ('treasury-account', 520, 0.5, 160, 1),
        ('fed-assets', 8700, -7.5, 170, 1),
        ('repo-volume', 1600, 5.3, 180, 1),
        ('dealer-positions', 220, 0.4, 45, 1),
    ]
    result = {}
    for series_index, (identifier, base, trend, amplitude, precision) in enumerate(specifications):
        points = []
        for i, observed_at in enumerate(dates):
            wave = (math.sin(i / 13 + series_index) * 0.55
                    + math.sin(i / 5.7 + series_index * 0.7) * 0.23
                    + math.sin(i * 1.7 + series_index) * 0.08
                    + math.cos(i / 31 + series_index) * 0.6)
            value = round(max(0.05, base + trend * i + amplitude * wave), precision)
            # Include isolated and consecutive gaps, a missing 4-week comparator,
            # and a stale last observation. Nulls are never filled or interpolated.
            missing = i in {47 + series_index, 123, 124, 207 - series_index}
            missing |= identifier == 'reverse-repo' and i == len(dates) - 5
            missing |= identifier == 'dealer-positions' and i == len(dates) - 1
            points.append({'date': observed_at.isoformat(), 'value': None if missing else value})
        result[identifier] = points
    return result


if __name__ == '__main__':
    output = ROOT / 'site/data/observations.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(generate(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Generated eight synthetic series: {START} to {END}')
