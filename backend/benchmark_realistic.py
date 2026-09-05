"""Realistic benchmark with network delays."""
import asyncio
import json
import time
import sys
sys.path.insert(0, '/root/projects/aipoisk-bot/backend')

import app.supplier_search as supplier_search
from app.supplier_search import Candidate


def make_settings():
    from types import SimpleNamespace
    return SimpleNamespace(
        has_active_ai_provider=True,
        custom_ai_providers_json=json.dumps([{"id": "test"}]),
        saved_models_json=json.dumps([]),
        ai_function_models_json=json.dumps({}),
        ai_analysis_fallback_json=json.dumps([]),
        ai_supplier_fallback_json=json.dumps([]),
        primary_provider="test",
        primary_model="test-model",
        light_provider="test",
        light_model="test-model",
        supplier_ai_provider="test",
        supplier_ai_model="test-model",
    )


async def benchmark_realistic():
    """Benchmark with realistic network delays."""
    print("=" * 70)
    print("REALISTIC BENCHMARK: Simulated network delays (200ms per request)")
    print("=" * 70)

    # ── Parallel page fetching with realistic delay ──
    original_fetch_page = supplier_search.fetch_page

    async def realistic_fetch(client, url):
        await asyncio.sleep(0.2)  # 200ms network delay
        return {"url": url, "html": "<html></html>", "text": "sales@example.com +7 999 111 22 33"}

    supplier_search.fetch_page = realistic_fetch
    supplier_search.extract_internal_links = lambda *_a, **_k: [
        f"https://example.com/page{i}" for i in range(5)
    ]

    # Parallel fetch
    original_extract = supplier_search.extract_internal_links
    start = time.monotonic()
    pages = await supplier_search.collect_pages("https://example.com")
    parallel_time = time.monotonic() - start

    # Sequential fetch
    import httpx
    start = time.monotonic()
    async with httpx.AsyncClient(timeout=18, follow_redirects=True) as client:
        seq_pages = []
        for i in range(5):
            page = await realistic_fetch(client, f"https://example.com/page{i}")
            if page:
                seq_pages.append(page)
    sequential_time = time.monotonic() - start

    supplier_search.fetch_page = original_fetch_page
    supplier_search.extract_internal_links = original_extract

    print(f"\n   Page Fetching (6 pages, 200ms delay each):")
    print(f"   - Sequential: {sequential_time*1000:.0f}ms")
    print(f"   - Parallel:   {parallel_time*1000:.0f}ms")
    print(f"   - Speedup:    {sequential_time/parallel_time:.1f}x faster")

    # ── Review pipeline with realistic delay ──
    original_verify = supplier_search.verify_candidate

    async def realistic_verify(settings, candidate, context, **kwargs):
        await asyncio.sleep(0.05)  # 50ms verification
        return {
            "company_name": candidate.domain,
            "site": candidate.url,
            "evidence_url": candidate.url,
            "contact_url": candidate.url,
            "phone": "+7 999 111 22 33",
            "email": f"sales@{candidate.domain}",
            "evidence_status": "verified",
            "match_level": "exact",
            "source": candidate.source,
            "search_query": candidate.query,
        }

    supplier_search.verify_candidate = realistic_verify

    # Optimized
    settings = make_settings()
    candidates = [
        Candidate(
            url=f"https://supplier-{i}.ru",
            domain=f"supplier-{i}.ru",
            title="производитель",
            snippet="оборудование",
            source="test",
            query="оборудование поставщик",
        )
        for i in range(50)
    ]

    start = time.monotonic()
    accepted, reviewed, meta = await supplier_search._review_candidates_until_target(
        settings, candidates, "оборудование", target=10
    )
    optimized_time = time.monotonic() - start

    # Sequential (no early stop)
    start = time.monotonic()
    for candidate in candidates:
        await realistic_verify(settings, candidate, "оборудование")
    sequential_review_time = time.monotonic() - start

    supplier_search.verify_candidate = original_verify

    print(f"\n   Review Pipeline (50 candidates, target=10):")
    print(f"   - Sequential: {sequential_review_time*1000:.0f}ms (all 50 verified)")
    print(f"   - Optimized:  {optimized_time*1000:.0f}ms ({len(reviewed)} verified, {len(accepted)} accepted)")
    print(f"   - Speedup:    {sequential_review_time/optimized_time:.1f}x faster")
    print(f"   - Early stop: {meta['early_stop']}, stopped after {meta['stopped_after_candidates']}/50")

    # ── Combined estimate ──
    print(f"\n{'=' * 70}")
    print(f"COMBINED ESTIMATE FOR REAL SEARCH (target=10)")
    print(f"{'=' * 70}")
    print(f"   HTTP phase:     {sequential_time:.1f}s -> {parallel_time:.1f}s ({sequential_time/parallel_time:.1f}x)")
    print(f"   Verify phase:   {sequential_review_time:.1f}s -> {optimized_time:.1f}s ({sequential_review_time/optimized_time:.1f}x)")
    print(f"   Total:          {sequential_time + sequential_review_time:.1f}s -> {parallel_time + optimized_time:.1f}s")
    print(f"   Overall speedup: {(sequential_time + sequential_review_time)/(parallel_time + optimized_time):.1f}x faster")


if __name__ == "__main__":
    asyncio.run(benchmark_realistic())
