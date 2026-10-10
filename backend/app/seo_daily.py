"""Normalize source observations without inventing missing dates or metrics."""
import math
import re
from datetime import date


def source_date(value):
    if not isinstance(value, str) or not re.match(r'^\d{4}-\d{2}-\d{2}(?:T|$)', value):
        return None
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return None


def metric(value, position=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0 or (position and value == 0)):
        return None
    return round(value, 2) if position else value


def yandex_daily(response, today):
    indicators = response.get('indicators')
    if not isinstance(indicators, dict):
        raise ValueError('Yandex daily indicator arrays are unavailable.')
    dates = {}
    for key, field in [('TOTAL_SHOWS', 'shows'), ('TOTAL_CLICKS', 'clicks'), ('AVG_SHOW_POSITION', 'avg_position')]:
        values = indicators.get(key, [])
        if not isinstance(values, list):
            raise ValueError('Yandex daily indicator array is invalid.')
        for item in values:
            if not isinstance(item, dict):
                raise ValueError('Yandex daily indicator observation is invalid.')
            day = source_date(item.get('date'))
            if not day:
                continue
            row = dates.setdefault(day, {
                'date': day, 'shows': None, 'clicks': None, 'avg_position': None,
                'queries_count': None, 'coverage': 'All queries reported by Webmaster; not a phrase sample.',
            })
            row[field] = metric(item.get('value'), position=field == 'avg_position')
    for day, row in dates.items():
        row['data_status'] = 'preliminary' if day >= today else 'reported'
        row['ctr_percent'] = (
            round(row['clicks'] / row['shows'] * 100, 2)
            if row['shows'] and row['clicks'] is not None else None
        )
    return [dates[day] for day in sorted(dates)]
