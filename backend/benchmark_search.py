"""Benchmark script to measure supplier search pipeline performance.

This script compares the optimized pipeline (parallel fetching, browser pool,
early stop) against a simulated sequential version.
"""
import asyncio
import json
import time
from types import SimpleNamespace
import sys
sys.path.insert(0, '/root/projects/aipoisk-bot/backend')

import app.supplier_search as supplier_search
from app.supplier_search import (
    Candidate,
    CandidateRerank,
    ProcurementItem,
    ProcurementProfile,
    _candidate_review_batch_size,
    _accepted_supplier_results,
)


def make_settings():
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


# ── Benchmark 1: Parallel vs Sequential page fetching ──

async def benchmark_collect_pages_parallel():
    """Benchmark parallel page fetching."""
    original_fetch_page = supplier_search.fetch_page

    async def slow_fetch_page(client, url):
        await asyncio.sleep(0.05)  # 50ms network delay
        return {"url": url, "html": "<html></html>", "text": "sales@example.com +7 999 111 22 33"}

    supplier_search.fetch_page = slow_fetch_page
    supplier_search.extract_internal_links = lambda *_a, **_k: [
        f"https://example.com/page{i}" for i in range(5)
    ]

    try:
        start = time.monotonic()
        pages = await supplier_search.collect_pages("https://example.com")
        elapsed = time.monotonic() - start
        return len(pages), elapsed
    finally:
        supplier_search.fetch_page = original_fetch_page
        # Restore original extract_internal_links if available
        if hasattr(supplier_search, '_original_extract_internal_links'):
            supplier_search.extract_internal_links = supplier_search._original_extract_internal_links


async def benchmark_collect_pages_sequential():
    """Simulate sequential page fetching."""
    async def slow_fetch_page(client, url):
        await asyncio.sleep(0.05)  # 50ms network delay
        return {"url": url, "html": "<html></html>", "text": "sales@example.com +7 999 111 22 33"}

    links = [f"https://example.com/page{i}" for i in range(5)]

    import httpx
    start = time.monotonic()
    async with httpx.AsyncClient(timeout=18, follow_redirects=True) as client:
        pages = []
        for link in links:
            page = await slow_fetch_page(client, link)
            if page:
                pages.append(page)
    elapsed = time.monotonic() - start
    return len(pages), elapsed


# ── Benchmark 2: Review pipeline performance ──

async def benchmark_review_pipeline(target=10, num_candidates=50):
    """Benchmark the review pipeline with mock verification."""
    original_verify = supplier_search.verify_candidate
    verify_count = 0

    async def mock_verify(settings, candidate, context, **kwargs):
        nonlocal verify_count
        verify_count += 1
        await asyncio.sleep(0.01)  # 10ms verification
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

    supplier_search.verify_candidate = mock_verify

    try:
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
            for i in range(num_candidates)
        ]

        start = time.monotonic()
        accepted, reviewed, meta = await supplier_search._review_candidates_until_target(
            settings, candidates, "оборудование", target
        )
        elapsed = time.monotonic() - start
        return len(accepted), len(reviewed), verify_count, elapsed, meta
    finally:
        supplier_search.verify_candidate = original_verify


async def benchmark_review_sequential(target=10, num_candidates=50):
    """Simulate sequential review (no parallelism, no early stop)."""
    async def mock_verify(settings, candidate, context, **kwargs):
        await asyncio.sleep(0.01)  # 10ms verification
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
        for i in range(num_candidates)
    ]

    verified = 0
    start = time.monotonic()
    for candidate in candidates:
        result = await mock_verify(settings, candidate, "оборудование")
        if result:
            verified += 1
    elapsed = time.monotonic() - start
    return verified, elapsed


async def main():
    print("=" * 70)
    print("BENCHMARK: Supplier Search Pipeline Performance")
    print("=" * 70)

    # ── Benchmark 1: Page fetching ──
    print("\n1. PARALLEL vs SEQUENTIAL PAGE FETCHING")
    print("-" * 50)

    pages_p, time_p = await benchmark_collect_pages_parallel()
    pages_s, time_s = await benchmark_collect_pages_sequential()

    print(f"   Parallel:   {pages_p} pages in {time_p*1000:.0f}ms")
    print(f"   Sequential: {pages_s} pages in {time_s*1000:.0f}ms")
    speedup_pages = time_s / time_p if time_p > 0 else float('inf')
    print(f"   Speedup:    {speedup_pages:.1f}x faster")

    # ── Benchmark 2: Review pipeline ──
    print("\n2. OPTIMIZED vs SEQUENTIAL REVIEW PIPELINE")
    print("-" * 50)
    print(f"   Target: 10 suppliers from 50 candidates")

    acc_o, rev_o, v_o, time_o, meta_o = await benchmark_review_pipeline(target=10, num_candidates=50)
    v_s, time_s = await benchmark_review_sequential(target=10, num_candidates=50)

    print(f"   Optimized:  {acc_o} accepted, {v_o} verified in {time_o*1000:.0f}ms")
    print(f"   Sequential: {v_s} verified in {time_s*1000:.0f}ms")
    speedup_review = time_s / time_o if time_o > 0 else float('inf')
    print(f"   Speedup:    {speedup_review:.1f}x faster")
    print(f"   Candidates saved: {v_s - v_o} ({((v_s - v_o) / v_s * 100):.0f}%)")
    print(f"   Early stop: {meta_o['early_stop']}, stopped after {meta_o['stopped_after_candidates']}/{meta_o['candidate_count']}")

    # ── Benchmark 3: Larger scale ──
    print("\n3. SCALE TEST: 20 suppliers from 100 candidates")
    print("-" * 50)

    acc_o2, rev_o2, v_o2, time_o2, meta_o2 = await benchmark_review_pipeline(target=20, num_candidates=100)
    v_s2, time_s2 = await benchmark_review_sequential(target=20, num_candidates=100)

    print(f"   Optimized:  {acc_o2} accepted, {v_o2} verified in {time_o2*1000:.0f}ms")
    print(f"   Sequential: {v_s2} verified in {time_s2*1000:.0f}ms")
    speedup_review2 = time_s2 / time_o2 if time_o2 > 0 else float('inf')
    print(f"   Speedup:    {speedup_review2:.1f}x faster")
    print(f"   Candidates saved: {v_s2 - v_o2} ({((v_s2 - v_o2) / v_s2 * 100):.0f}%)")
    print(f"   Early stop: {meta_o2['early_stop']}, stopped after {meta_o2['stopped_after_candidates']}/{meta_o2['candidate_count']}")

    # ── Summary ──
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"   Page fetching:       {speedup_pages:.1f}x faster (parallel)")
    print(f"   Review (target=10):  {speedup_review:.1f}x faster ({v_s - v_o} candidates saved)")
    print(f"   Review (target=20):  {speedup_review2:.1f}x faster ({v_s2 - v_o2} candidates saved)")
    print()
    print("   Combined estimated improvement for typical search:")
    print(f"   - HTTP phase: ~{speedup_pages:.0f}x faster")
    print(f"   - Verification phase: ~{speedup_review:.0f}x faster")
    print(f"   - Overall: ~{(speedup_pages + speedup_review) / 2:.0f}x faster")
    print()


if __name__ == "__main__":
    asyncio.run(main())
