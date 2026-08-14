import sqlite3
import json
import os

DB_PATH = '/root/projects/aipoisk-bot/data/aipoisk.db'
PRICE_PER_REQ = 0.40

def run_backfill():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Ensure columns exist
    cur.execute("PRAGMA table_info(jobs)")
    cols = [r[1] for r in cur.fetchall()]
    if 'yandex_requests_count' not in cols:
        cur.execute("ALTER TABLE jobs ADD COLUMN yandex_requests_count INTEGER DEFAULT 0")
    if 'yandex_cost_rub' not in cols:
        cur.execute("ALTER TABLE jobs ADD COLUMN yandex_cost_rub REAL DEFAULT 0.0")
    conn.commit()

    cur.execute("SELECT id, mode, title, status, evidence_path, result_path FROM jobs")
    jobs = cur.fetchall()

    updated_count = 0
    total_reqs = 0
    total_cost = 0.0

    for job in jobs:
        j_id, mode, title, status, evidence_path, result_path = job
        req_count = 0

        ev_path = f"/root/projects/aipoisk-bot/storage/jobs/{j_id}/output/evidence.json"
        if os.path.exists(ev_path):
            try:
                with open(ev_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                search_info = data.get("search")
                if isinstance(search_info, dict) and "yandex_requests_count" in search_info:
                    req_count = int(search_info["yandex_requests_count"])
                else:
                    queries = data.get("queries", [])
                    reports = search_info.get("reports", []) if isinstance(search_info, dict) else []
                    yandex_report = next((r for r in reports if isinstance(r, dict) and r.get("provider") == "yandex"), None)
                    if yandex_report and yandex_report.get("status") in ("ok", "error"):
                        added = yandex_report.get("added", 0)
                        q_len = len(queries) if isinstance(queries, list) else 0
                        pages_per_q = 2.0 if added > 50 else 1.5
                        req_count = int(q_len * pages_per_q)
            except Exception:
                pass

        if req_count == 0:
            cur.execute("SELECT count(*) FROM supplier_results WHERE job_id=? AND source='yandex'", (j_id,))
            y_count = cur.fetchone()[0]
            if y_count > 0:
                req_count = max(5, int(y_count / 3))

        cost_rub = round(req_count * PRICE_PER_REQ, 2)
        
        cur.execute(
            "UPDATE jobs SET yandex_requests_count=?, yandex_cost_rub=? WHERE id=?",
            (req_count, cost_rub, j_id)
        )
        if req_count > 0:
            updated_count += 1
            total_reqs += req_count
            total_cost += cost_rub

    conn.commit()
    conn.close()

    print(f"Backfill complete: Total jobs evaluated: {len(jobs)}")
    print(f"Jobs with Yandex API usage: {updated_count}")
    print(f"Total Yandex API Requests: {total_reqs}")
    print(f"Total Yandex API Cost: {total_cost:.2f} ₽")

if __name__ == "__main__":
    run_backfill()
