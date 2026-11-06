#!/usr/bin/env bash
# Restarts tenderlex-pg-tunnel if a fresh PostgreSQL TCP+auth handshake through it is slow or fails.
set -u
cd /root/projects/tenderlex/backend
if ! timeout 8 python3 - <<'PY' >/dev/null 2>&1
import sys, time, psycopg2
sys.path.insert(0, ".")
from app.config import config
from sqlalchemy.engine import make_url
u = make_url(config.database_url)
if not u.drivername.startswith("postgresql"):
    sys.exit(0)
t = time.time()
c = psycopg2.connect(host=u.host, port=u.port, user=u.username, password=u.password, dbname=u.database, connect_timeout=5)
c.cursor().execute("select 1")
c.close()
sys.exit(0 if time.time() - t < 4 else 1)
PY
then
  logger -t tenderlex-pg-watchdog "PostgreSQL tunnel slow/unreachable, restarting tenderlex-pg-tunnel"
  systemctl restart tenderlex-pg-tunnel.service
fi
