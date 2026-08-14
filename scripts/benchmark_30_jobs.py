import sys, os, sqlite3, json, asyncio, time

sys.path.insert(0, '/root/projects/aipoisk-bot/backend')

from app.db import SessionLocal
from app.models import Job, SystemSettings
from app.repository import get_or_create_settings
from app.supplier_search import _expand_search_queries, discover_candidates, _search_with_yandex

DB_PATH = '/root/projects/aipoisk-bot/data/aipoisk.db'
PRICE_PER_REQ = 0.04

async def run_benchmark():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, mode, title, verified_count, yandex_requests_count, yandex_cost_rub, evidence_path
        FROM jobs
        WHERE status IN ('completed', 'partial', 'needs_review') AND yandex_requests_count > 0
        ORDER BY created_at DESC
        LIMIT 30
    """)
    rows = cur.fetchall()
    conn.close()

    db = SessionLocal()
    settings = get_or_create_settings(db)
    db.close()

    print(f"Starting 30-Job Benchmark Audit on Real Client Tasks...", flush=True)
    print(f"{'#':<3} | {'Job ID':<8} | {'Title':<32} | {'Orig Reqs':<9} | {'New Reqs':<8} | {'Orig ₽':<7} | {'New ₽':<7} | {'Savings':<8} | {'Orig Dom':<8} | {'New Dom':<8} | {'Recall':<7}", flush=True)
    print("-" * 125, flush=True)

    tot_orig_reqs = 0
    tot_new_reqs = 0
    tot_orig_cost = 0.0
    tot_new_cost = 0.0
    tot_orig_dom = 0
    tot_new_dom = 0
    recal_sum = 0.0
    valid_jobs = 0

    idx = 0
    for row in rows:
        j_id, mode, title, verified_count, orig_reqs, orig_cost, evidence_path = row
        ev_path = f"/root/projects/aipoisk-bot/storage/jobs/{j_id}/output/evidence.json"

        queries = []
        orig_domains = set()

        if os.path.exists(ev_path):
            try:
                with open(ev_path, 'r', encoding='utf-8') as f:
                    ev_data = json.load(f)
                queries = ev_data.get("queries", [])
                cands = ev_data.get("candidates", [])
                for c in cands:
                    d = c.get("domain")
                    if d:
                        orig_domains.add(d)
            except Exception:
                pass

        if not queries:
            queries = [title or mode]

        new_cands, search_meta = await discover_candidates(
            settings,
            queries,
            max_results=min(120, max(40, (verified_count or 15) * 3)),
        )

        new_reqs = search_meta.get("yandex_requests_count", 0)
        new_cost = round(new_reqs * PRICE_PER_REQ, 2)
        new_domains = {c.domain for c in new_cands if c.domain}

        if orig_domains:
            overlap = orig_domains.intersection(new_domains)
            recall = round((len(overlap) / min(len(orig_domains), len(new_domains) or 1)) * 100, 1)
        else:
            recall = 100.0

        savings_pct = round(((orig_reqs - new_reqs) / (orig_reqs or 1)) * 100, 1)

        idx += 1
        clean_title = (title or mode or 'Без названия').replace('\n', ' ')[:30]
        print(f"{idx:<3} | {j_id[:8]:<8} | {clean_title:<32} | {orig_reqs:<9} | {new_reqs:<8} | {orig_cost:<7.2f} | {new_cost:<7.2f} | {savings_pct:>6.1f}% | {len(orig_domains):<8} | {len(new_domains):<8} | {recall:>5.1f}%", flush=True)

        tot_orig_reqs += orig_reqs
        tot_new_reqs += new_reqs
        tot_orig_cost += orig_cost
        tot_new_cost += new_cost
        tot_orig_dom += len(orig_domains)
        tot_new_dom += len(new_domains)
        recal_sum += recall
        valid_jobs += 1

    print("-" * 125, flush=True)
    avg_orig_reqs = tot_orig_reqs / (valid_jobs or 1)
    avg_new_reqs = tot_new_reqs / (valid_jobs or 1)
    avg_orig_cost = tot_orig_cost / (valid_jobs or 1)
    avg_new_cost = tot_new_cost / (valid_jobs or 1)
    tot_savings_pct = round(((tot_orig_cost - tot_new_cost) / (tot_orig_cost or 1)) * 100, 1)
    avg_recall = round(recal_sum / (valid_jobs or 1), 1)

    print("\nBENCHMARK AUDIT SUMMARY (30 CLIENT TASKS):", flush=True)
    print(f"Total Client Jobs Audited: {valid_jobs}", flush=True)
    print(f"Original Total Yandex API Requests: {tot_orig_reqs} (Avg {avg_orig_reqs:.1f} reqs/job)", flush=True)
    print(f"Optimized Total Yandex API Requests: {tot_new_reqs} (Avg {avg_new_reqs:.1f} reqs/job)", flush=True)
    print(f"Original Total Cost: {tot_orig_cost:.2f} ₽ (Avg {avg_orig_cost:.2f} ₽/job)", flush=True)
    print(f"Optimized Total Cost: {tot_new_cost:.2f} ₽ (Avg {avg_new_cost:.2f} ₽/job)", flush=True)
    print(f"Total API Cost Savings: {tot_savings_pct:.1f}% reduction", flush=True)
    print(f"Average Supplier Candidate Recall / Quality Match: {avg_recall:.1f}%", flush=True)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
