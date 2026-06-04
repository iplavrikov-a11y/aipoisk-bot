from __future__ import annotations

import tempfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.jobs import (
    MODE_ANALYSIS_AND_SUPPLIERS,
    MODE_PROCUREMENT_REPORT,
    MODE_SUPPLIER_SEARCH,
    claim_next_job,
)
from app.models import Client, ClientTelegramAccount, Job
from app.repository import client_access_error, current_function_usage


CLIENTS = 100
JOBS_PER_CLIENT = 10
WORKERS = 40
MODES = [
    MODE_SUPPLIER_SEARCH,
    MODE_PROCUREMENT_REPORT,
    MODE_ANALYSIS_AND_SUPPLIERS,
    MODE_SUPPLIER_SEARCH,
    MODE_PROCUREMENT_REPORT,
    MODE_ANALYSIS_AND_SUPPLIERS,
    MODE_SUPPLIER_SEARCH,
    MODE_PROCUREMENT_REPORT,
    MODE_ANALYSIS_AND_SUPPLIERS,
    MODE_SUPPLIER_SEARCH,
]


def create_client_jobs(session_factory, client_index: int) -> dict:
    db = session_factory()
    try:
        client = Client(
            id=f"stress-client-{client_index:03d}",
            telegram_id=f"900000{client_index:03d}",
            name=f"Stress Client {client_index:03d}",
            is_active=True,
            allowed_supplier_search=True,
            allowed_procurement_report=True,
            monthly_supplier_search_limit=100,
            monthly_procurement_report_limit=100,
            monthly_file_limit=100,
        )
        db.add(client)
        db.flush()
        db.add(
            ClientTelegramAccount(
                client_id=client.id,
                telegram_id=client.telegram_id,
                username=f"stress_{client_index:03d}",
                name=client.name,
            )
        )
        errors: list[str] = []
        jobs: list[Job] = []
        for job_index, mode in enumerate(MODES):
            error = client_access_error(db, client, mode, incoming_file_count=1, supplier_search_count=1)
            if error:
                errors.append(error)
                continue
            jobs.append(
                Job(
                    client_id=client.id,
                    created_by_telegram_id=client.telegram_id,
                    mode=mode,
                    title=f"stress-{client_index:03d}-{job_index:02d}-{mode}",
                    target_suppliers=15,
                    file_count=1,
                    status="pending",
                    message="stress queued",
                )
            )
        db.add_all(jobs)
        db.commit()
        return {"client": client.id, "created": len(jobs), "errors": errors}
    finally:
        db.close()


def claim_until_empty(session_factory, worker_index: int) -> list[str]:
    claimed: list[str] = []
    while True:
        db = session_factory()
        try:
            job_id = claim_next_job(db, worker_id=f"stress-worker-{worker_index:02d}")
        finally:
            db.close()
        if not job_id:
            return claimed
        claimed.append(job_id)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "stress.sqlite"
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=40) as executor:
            create_results = list(executor.map(lambda index: create_client_jobs(Session, index), range(CLIENTS)))
        create_seconds = time.perf_counter() - started

        created = sum(item["created"] for item in create_results)
        access_errors = [error for item in create_results for error in item["errors"]]

        db = Session()
        try:
            usage_by_client = {}
            mode_counts = Counter(mode for (mode,) in db.query(Job.mode).all())
            for client in db.query(Client).all():
                usage_by_client[client.id] = current_function_usage(db, client)[:2]
        finally:
            db.close()

        claim_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = [executor.submit(claim_until_empty, Session, worker_index) for worker_index in range(WORKERS)]
            claimed_by_worker = [future.result() for future in as_completed(futures)]
        claim_seconds = time.perf_counter() - claim_started

        claimed = [job_id for worker_jobs in claimed_by_worker for job_id in worker_jobs]
        claim_counts = Counter(claimed)
        duplicates = [job_id for job_id, count in claim_counts.items() if count > 1]

        db = Session()
        try:
            statuses = Counter(status for (status,) in db.query(Job.status).all())
            per_client_jobs = defaultdict(int)
            for client_id, in db.query(Job.client_id).all():
                per_client_jobs[client_id] += 1
        finally:
            db.close()

        expected_supplier_units = MODES.count(MODE_SUPPLIER_SEARCH) + MODES.count(MODE_ANALYSIS_AND_SUPPLIERS)
        expected_report_units = MODES.count(MODE_PROCUREMENT_REPORT) + MODES.count(MODE_ANALYSIS_AND_SUPPLIERS)
        usage_ok = all(value == (expected_supplier_units, expected_report_units) for value in usage_by_client.values())
        per_client_ok = all(count == JOBS_PER_CLIENT for count in per_client_jobs.values()) and len(per_client_jobs) == CLIENTS

        print(
            {
                "clients": CLIENTS,
                "jobs_per_client": JOBS_PER_CLIENT,
                "created_jobs": created,
                "access_errors": len(access_errors),
                "mode_counts": dict(mode_counts),
                "expected_supplier_units_per_client": expected_supplier_units,
                "expected_report_units_per_client": expected_report_units,
                "usage_ok": usage_ok,
                "per_client_ok": per_client_ok,
                "workers": WORKERS,
                "claimed_jobs": len(claimed),
                "duplicate_claims": len(duplicates),
                "statuses": dict(statuses),
                "create_seconds": round(create_seconds, 3),
                "claim_seconds": round(claim_seconds, 3),
            }
        )


if __name__ == "__main__":
    main()
