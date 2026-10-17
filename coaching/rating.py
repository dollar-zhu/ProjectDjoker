"""Djokovic match score: rate(metrics, reference_row, config) -> dict. Deterministic and fully itemized."""

BANDS = {'p10_p90': ('p10', 'p90'), 'p25_p75': ('p25', 'p75')}

def metric_score(value, band, zero_at, kind='p10_p90'):
    """100 inside the reference band; linear decay to 0 at zero_at beyond the nearer bound."""
    lo, hi = (band[k] for k in BANDS[kind])
    distance = lo - value if value < lo else value - hi if value > hi else 0.0
    return max(0.0, 100.0 * (1 - distance / zero_at)), distance

def rate(metrics, row, config):
    items, total, weight_sum, possible = [], 0.0, 0.0, 0.0
    for name, spec in config['metrics'].items():
        possible += spec['weight']; value = metrics.get(name); band = row.get(name) if row else None
        if value is None or band is None:
            items.append({'metric': name, 'label': spec['label'], 'score': None, 'reason': 'unavailable'}); continue
        kind = spec.get('band', 'p10_p90'); lo_key, hi_key = BANDS[kind]
        score, distance = metric_score(value, band, spec['zero_at'], kind)
        direction = None if distance == 0 else ('above' if value > band[hi_key] else 'below')
        items.append({'metric': name, 'label': spec['label'], 'score': round(score, 1), 'value': round(value, 3),
                      'band': [band[lo_key], band[hi_key]], 'band_kind': kind, 'distance_outside': round(distance, 3), 'direction': direction,
                      'units': spec['units'], 'weight': spec['weight']})
        total += spec['weight'] * score; weight_sum += spec['weight']
    coverage = weight_sum / possible if possible else 0.0
    score = round(total / weight_sum) if weight_sum and coverage >= config['min_coverage'] else None
    return {'name': config['name'], 'version': config['version'], 'status': config['status'], 'score': score,
            'scale': '0-100, 100 = every measured metric inside Djokovic\'s typical range',
            'coverage': round(coverage, 2), 'items': items, 'not_measured': sorted(config.get('not_measured', {})),
            'reason': None if score is not None else 'insufficient_metric_coverage'}

def rate_with_view_sensitivity(metrics, table, yaw, config):
    """Score at the matched view, plus the range over +/- view_sensitivity_deg of camera-angle error."""
    pick = lambda y: min(table, key=lambda r: abs(r['yaw_deg'] - y))
    result = rate(metrics, pick(yaw), config); d = config.get('view_sensitivity_deg', 10)
    scores = [rate(metrics, pick(yaw + k), config)['score'] for k in (-d, 0, d)]
    if result['score'] is not None and None not in scores:
        result['score_range_view_uncertainty'] = [min(scores), max(scores)]
    return result

def not_rated(reason, config):
    return {'name': config['name'], 'version': config['version'], 'status': config['status'], 'score': None, 'reason': reason}
