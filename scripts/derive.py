"""Recompute complete derived histories from normalized, same-date inputs."""
from decimal import Decimal

from .contracts import validate_points
from .normalize import content_hash
from .policies import CALCULATIONS, derived_output_factor


def difference(values):
    return values['sofr'] - values['effr']


def tail_difference(values):
    return values['sofr99'] - values['sofr']


def reserve_ratio(values):
    denominator = values['bank-total-assets']
    return 100 * values['reserve-balances'] / denominator if denominator else None


FUNCTIONS = {'sofr-effr-spread': difference, 'reserve-assets-ratio': reserve_ratio,
             'sofr-tail-spread': tail_difference}


def derive(registry, inputs, selected):
    """Return dependency-ordered outputs and hashes; never execute registry text."""
    available, result, visiting = dict(inputs), {}, set()
    selected = set(selected)

    def visit(identifier):
        if identifier in result:
            return
        if identifier in visiting:
            raise ValueError('Cyclic calculation dependencies')
        entry = registry['series'][identifier]
        expected = CALCULATIONS.get(identifier)
        actual = (frozenset(entry['input_series_ids']), ''.join((entry['formula'] or '').split()))
        if (entry['update_method'] != 'derived' or expected != actual or identifier not in FUNCTIONS):
            raise ValueError(f'{identifier}: unknown or mismatched calculation definition')
        output_factor = derived_output_factor(identifier, entry)
        visiting.add(identifier)
        for dependency in entry['input_series_ids']:
            if dependency in selected:
                visit(dependency)
        aligned, hashes, missing = {}, {}, []
        for dependency in entry['input_series_ids']:
            points = available.get(dependency)
            if points is None:
                missing.append(dependency)
                points = []
            else:
                hashes[dependency] = content_hash(points)
            validate_points(points)
            aligned[dependency] = {point['date']: point['value'] for point in points}
        points = []
        observed_dates = [{day for day, value in mapping.items() if value is not None}
                          for mapping in aligned.values()]
        shared_dates = set.intersection(*observed_dates)
        if shared_dates:
            start, end = min(shared_dates), max(shared_dates)
            dates = sorted(day for day in set().union(*aligned.values()) if start <= day <= end)
        else:
            dates = []
        for day in dates:
            values = {key: mapping.get(day) for key, mapping in aligned.items()}
            value = None if any(value is None for value in values.values()) else FUNCTIONS[identifier](
                {key: Decimal(str(value)) for key, value in values.items()})
            points.append({'date': day, 'value': None if value is None else float(value * output_factor)})
        validate_points(points)
        available[identifier] = points
        result[identifier] = {'observations': points, 'inputHashes': hashes,
                              'missingInputs': sorted(missing), 'calculation': expected[1]}
        visiting.remove(identifier)

    for identifier in sorted(selected):
        visit(identifier)
    return result
