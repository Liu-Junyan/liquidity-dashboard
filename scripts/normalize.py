"""Convert validated source-scale observations exactly once."""
import hashlib
import json
from decimal import Decimal

from .contracts import validate_points
from .policies import conversion_policy


def content_hash(points):
    validate_points(points)
    encoded = json.dumps(points, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def normalize(entry, points):
    validate_points(points)
    _, factor = conversion_policy(entry)
    result = [{'date': point['date'], 'value': None if point['value'] is None else
               float(Decimal(str(point['value'])) * Decimal(str(factor)))} for point in points]
    validate_points(result)
    return result
