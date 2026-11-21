#!/usr/bin/env python3
"""Safe PostgreSQL backup utility for TenderLex (supports remote SSH compressed dump & tunnel fallback)."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url


def resolve_database_url(root_dir: Path) -> str:
    env_url = os.environ.get("AIPOISK_DATABASE_URL", "").strip()
    if env_url:
        return env_url
    env_file = root_dir / ".env"
    if env_file.is_file():
        values = dotenv_values(env_file)
        file_url = str(values.get("AIPOISK_DATABASE_URL") or "").strip()
        if file_url:
            return file_url
    return ""


def _dump_via_ssh_host(ssh_host: str, db_name: str, tmp_path: Path) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", db_name):
        return False
    remote_cmd = f"su - postgres -c 'pg_dump -Fc -Z 6 --no-owner --no-privileges -d {db_name}'"
    ssh_cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=10",
        "-o",
        "ServerAliveCountMax=3",
        ssh_host,
        remote_cmd,
    ]
    with tmp_path.open("wb") as out_fh:
        res = subprocess.run(
            ssh_cmd,
            stdout=out_fh,
            stderr=subprocess.PIPE,
            timeout=300,
            check=False,
        )
    return res.returncode == 0 and tmp_path.is_file() and tmp_path.stat().st_size >= 1024


def run_backup(
    *,
    db_url_raw: str,
    backup_dir: Path,
    prefix: str,
    keep_count: int,
    keep_days: int,
    ssh_host: str = "russian-server",
) -> Path | None:
    if not db_url_raw:
        print("[pg-backup] AIPOISK_DATABASE_URL is not set; skipping PostgreSQL backup.")
        return None
    url = make_url(db_url_raw)
    if not url.drivername.startswith("postgresql"):
        print(f"[pg-backup] Database dialect is {url.drivername}; skipping PostgreSQL backup.")
        return None
    if not url.database:
        raise RuntimeError("PostgreSQL URL is missing database name")

    pg_dump = shutil.which("pg_dump")
    pg_restore = shutil.which("pg_restore")
    if not pg_dump or not pg_restore:
        raise RuntimeError("pg_dump and pg_restore must be installed for PostgreSQL backups")

    backup_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_dir, 0o700)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    final_name = f"{prefix}-{stamp}.dump" if not prefix.endswith(stamp) else f"{prefix}.dump"
    final_path = backup_dir / final_name
    tmp_path = backup_dir / f".{final_name}.{os.getpid()}.tmp"

    try:
        dumped_ok = False
        # When connected via Moscow SSH tunnel (127.0.0.1:5433), compress on the DB host first
        # so raw 55+ MB COPY streams neither saturate nor drop over the live app tunnel.
        if str(url.host or "") == "127.0.0.1" and int(url.port or 5432) == 5433 and ssh_host:
            dumped_ok = _dump_via_ssh_host(ssh_host, str(url.database), tmp_path)

        if not dumped_ok:
            tmp_path.unlink(missing_ok=True)
            cmd = [
                pg_dump,
                "-Fc",
                "-Z",
                "6",
                "--no-owner",
                "--no-privileges",
            ]
            if url.host:
                cmd.extend(["-h", str(url.host)])
            if url.port:
                cmd.extend(["-p", str(url.port)])
            if url.username:
                cmd.extend(["-U", str(url.username)])
            cmd.extend(["-d", str(url.database), "-f", str(tmp_path)])

            child_env = os.environ.copy()
            if url.password is not None:
                child_env["PGPASSWORD"] = str(url.password)
            if str(url.host or "") in {"127.0.0.1", "localhost"}:
                child_env.setdefault("PGSSLMODE", "disable")
            child_env.setdefault("PGCONNECT_TIMEOUT", "15")

            res = subprocess.run(cmd, env=child_env, capture_output=True, text=True, timeout=300, check=False)
            if res.returncode != 0:
                stderr_clean = (res.stderr or "").strip()
                raise RuntimeError(f"pg_dump failed (exit {res.returncode}): {stderr_clean[:400]}")

        if not tmp_path.is_file() or tmp_path.stat().st_size < 1024:
            raise RuntimeError("pg_dump produced an empty or unexpectedly small archive")

        verify = subprocess.run(
            [pg_restore, "--list", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if verify.returncode != 0 or "TABLE DATA" not in (verify.stdout or ""):
            raise RuntimeError("pg_restore --list verification failed on backup archive")

        os.chmod(tmp_path, 0o600)
        tmp_path.replace(final_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    size_mb = final_path.stat().st_size / (1024 * 1024)
    print(f"[pg-backup] Verified PostgreSQL backup created: {final_path} ({size_mb:.2f} MiB)")

    all_dumps = sorted(backup_dir.glob("*.dump"), key=lambda p: p.stat().st_mtime, reverse=True)
    now_ts = time.time()
    for idx, old_file in enumerate(all_dumps):
        if old_file == final_path:
            continue
        too_many = keep_count > 0 and idx >= keep_count
        too_old = keep_days > 0 and (now_ts - old_file.stat().st_mtime) > (keep_days * 86400)
        if too_many or too_old:
            old_file.unlink(missing_ok=True)

    return final_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create verified PostgreSQL backup for TenderLex")
    root_default = Path(__file__).resolve().parents[1]
    parser.add_argument("--root-dir", type=Path, default=root_default)
    parser.add_argument("--backup-dir", type=Path, default=root_default / "data" / "backups" / "pg")
    parser.add_argument("--prefix", type=str, default="tenderlex-pg")
    parser.add_argument("--keep-count", type=int, default=20)
    parser.add_argument("--keep-days", type=int, default=14)
    args = parser.parse_args()

    db_url = resolve_database_url(args.root_dir)
    run_backup(
        db_url_raw=db_url,
        backup_dir=args.backup_dir,
        prefix=args.prefix,
        keep_count=args.keep_count,
        keep_days=args.keep_days,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
