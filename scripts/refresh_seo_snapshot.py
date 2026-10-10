#!/usr/bin/env python3
"""Refresh the admin's read-only SEO snapshot without opening the dashboard."""
from app.yandex_seo import get_cached_or_fresh_analytics


def main() -> int:
    snapshot = get_cached_or_fresh_analytics()
    # Log operational status only, never credentials or customer data.
    print(f"SEO snapshot: status={snapshot.get('collection_status', 'unknown')} collected_at={snapshot.get('updated_at', 'unknown')}")
    return 1 if snapshot.get('collection_status') == 'error' else 0


if __name__ == '__main__':
    raise SystemExit(main())
