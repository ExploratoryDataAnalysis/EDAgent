"""Join already linked traffic observations to an eligible site-year panel.

This does not match stations to sites or approve an exposure source.
"""
from __future__ import annotations
import math


def join_site_year_exposure(panel_rows, observations):
    by_key = {}
    for row in observations:
        key = (row['site_id'], int(row['year']))
        if key in by_key:
            raise ValueError(f'Duplicate traffic observation: {key}')
        value = float(row['aadt'])
        if not math.isfinite(value) or value <= 0 or not row.get('source_id'):
            raise ValueError(f'Invalid traffic observation: {key}')
        by_key[key] = row
    seen = set()
    result = []
    for row in panel_rows:
        key = (row['site_id'], int(row['year']))
        if key in seen:
            raise ValueError(f'Duplicate panel site-year: {key}')
        seen.add(key)
        observation = by_key.get(key)
        copy = dict(row)
        copy['traffic_exposure'] = float(observation['aadt']) if observation else None
        copy['exposure_source'] = observation['source_id'] if observation else 'UNAVAILABLE'
        copy['exposure_year'] = key[1] if observation else None
        copy['exposure_quality_status'] = 'OBSERVED_UNREVIEWED' if observation else 'MISSING_EXPOSURE'
        result.append(copy)
    return result, sorted(set(by_key) - seen)
