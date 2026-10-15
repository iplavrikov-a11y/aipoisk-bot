#!/usr/bin/env python3
"""
Migrate legacy '/root/projects/aipoisk-bot' paths to '/root/projects/tenderlex'
in SQLite database and evidence.json files.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "aipoisk.db"
STORAGE_JOBS_DIR = REPO_ROOT / "storage" / "jobs"
OLD_PREFIX = "/root/projects/aipoisk-bot"
NEW_PREFIX = "/root/projects/tenderlex"


def backup_database(db_path: Path) -> Path:
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"aipoisk.db.backup-before-path-migration-20260914.db"
    print(f"Creating safe online backup to {backup_path}...")
    src = sqlite3.connect(str(db_path), timeout=30.0)
    dst = sqlite3.connect(str(backup_path))
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    print(f"Backup created successfully ({backup_path.stat().st_size} bytes)")
    return backup_path


def migrate_database(db_path: Path) -> dict[str, int]:
    con = sqlite3.connect(str(db_path), timeout=30.0)
    cur = con.cursor()
    cur.execute("PRAGMA busy_timeout = 30000;")
    stats = {}

    with con:
        # jobs.result_path
        cur.execute(
            f"UPDATE jobs SET result_path = replace(result_path, ?, ?) WHERE result_path LIKE ?;",
            (OLD_PREFIX, NEW_PREFIX, f"%{OLD_PREFIX}%"),
        )
        stats["jobs.result_path"] = cur.rowcount

        # jobs.evidence_path
        cur.execute(
            f"UPDATE jobs SET evidence_path = replace(evidence_path, ?, ?) WHERE evidence_path LIKE ?;",
            (OLD_PREFIX, NEW_PREFIX, f"%{OLD_PREFIX}%"),
        )
        stats["jobs.evidence_path"] = cur.rowcount

        # jobs.admin_supplement_path
        cur.execute(
            f"UPDATE jobs SET admin_supplement_path = replace(admin_supplement_path, ?, ?) WHERE admin_supplement_path LIKE ?;",
            (OLD_PREFIX, NEW_PREFIX, f"%{OLD_PREFIX}%"),
        )
        stats["jobs.admin_supplement_path"] = cur.rowcount

        # job_files.stored_path
        cur.execute(
            f"UPDATE job_files SET stored_path = replace(stored_path, ?, ?) WHERE stored_path LIKE ?;",
            (OLD_PREFIX, NEW_PREFIX, f"%{OLD_PREFIX}%"),
        )
        stats["job_files.stored_path"] = cur.rowcount

        # job_sources.context_path
        cur.execute(
            f"UPDATE job_sources SET context_path = replace(context_path, ?, ?) WHERE context_path LIKE ?;",
            (OLD_PREFIX, NEW_PREFIX, f"%{OLD_PREFIX}%"),
        )
        stats["job_sources.context_path"] = cur.rowcount

    con.close()
    return stats


def migrate_evidence_files(storage_jobs: Path) -> int:
    migrated_count = 0
    if not storage_jobs.exists():
        print(f"Storage jobs dir {storage_jobs} does not exist, skipping.")
        return 0

    for ev_path in storage_jobs.glob("*/output/evidence.json"):
        try:
            content = ev_path.read_text(encoding="utf-8")
            if OLD_PREFIX in content:
                new_content = content.replace(OLD_PREFIX, NEW_PREFIX)
                ev_path.write_text(new_content, encoding="utf-8")
                migrated_count += 1
        except Exception as e:
            print(f"Error processing {ev_path}: {e}")
    return migrated_count


def main():
    print(f"Starting path migration from '{OLD_PREFIX}' to '{NEW_PREFIX}'...")
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)

    backup_database(DB_PATH)
    db_stats = migrate_database(DB_PATH)
    print("Database updates:")
    for col, count in db_stats.items():
        print(f"  {col}: {count} rows updated")

    ev_count = migrate_evidence_files(STORAGE_JOBS_DIR)
    print(f"Evidence files updated: {ev_count} files")
    print("Migration completed successfully!")


if __name__ == "__main__":
    main()
