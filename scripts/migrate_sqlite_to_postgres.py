#!/usr/bin/env python3
"""One-off migration: copy the TenderLex SQLite database into PostgreSQL (152-FZ data localisation).

Usage: migrate_sqlite_to_postgres.py <sqlite_path> <postgresql_url>
The target database must be empty. SQLite is opened read-only. Row counts and money totals are verified.
Orphaned rows (test remnants without a parent row) are dropped / nulled and reported.
"""
from __future__ import annotations

import os
import sqlite3
import sys

SQLITE_PATH, PG_URL = sys.argv[1], sys.argv[2]
os.environ["AIPOISK_DATABASE_URL"] = PG_URL
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import create_engine, text  # noqa: E402

from app import models, outreach_models  # noqa: E402,F401
from app.db import Base, init_db, engine  # noqa: E402

assert engine.dialect.name == "postgresql", "target must be PostgreSQL"
init_db()

src = create_engine(f"sqlite:///file:{SQLITE_PATH}?mode=ro&uri=true")
report: dict[str, int] = {}


def fk_rows(table):
    return list(table.foreign_keys)


with src.connect() as s, engine.begin() as d:
    # init_db() seeds default rows (e.g. tariffs); the copy must start from truly empty tables.
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    d.exec_driver_sql(f"TRUNCATE {names} RESTART IDENTITY CASCADE")
    d.exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
    for table in Base.metadata.sorted_tables:
        rows = [dict(r._mapping) for r in s.execute(table.select())]
        # normalise empty-string references and drop orphans
        for fk in fk_rows(table):
            col, parent_table, parent_col = fk.parent.name, fk.column.table, fk.column.name
            if parent_table is table:
                valid = {r[parent_col] for r in rows}
            else:
                valid = {r[0] for r in d.execute(parent_table.select().with_only_columns(parent_table.c[parent_col]))}
            for row in rows[:]:
                v = row.get(col)
                if v in (None,) or v in valid:
                    continue
                if table.c[col].nullable:
                    row[col] = None
                    report[f"{table.name}.{col} -> NULL"] = report.get(f"{table.name}.{col} -> NULL", 0) + 1
                else:
                    rows.remove(row)
                    report[f"{table.name} row dropped (orphan {col})"] = report.get(f"{table.name} row dropped (orphan {col})", 0) + 1
        if rows:
            for i in range(0, len(rows), 500):
                d.execute(table.insert(), rows[i:i + 500])
        print(f"{table.name}: {len(rows)}")
    # restart sequences / numbering triggers after bulk load
    from app.db import _ensure_postgres_number_triggers
    _ensure_postgres_number_triggers(d)

print("normalisations:", report)

# verification
lite = sqlite3.connect(f"file:{SQLITE_PATH}?mode=ro", uri=True)
ok = True
with engine.connect() as d:
    for table in Base.metadata.sorted_tables:
        a = lite.execute(f'select count(*) from "{table.name}"').fetchone()[0]
        b = d.execute(text(f'select count(*) from "{table.name}"')).scalar()
        dropped = sum(v for k, v in report.items() if k.startswith(table.name + " row dropped"))
        if a - dropped != b:
            ok = False
            print("COUNT MISMATCH", table.name, a, dropped, b)
    sums = [("clients", "money_balance_kopeks"), ("clients", "money_reserved_kopeks")]
    for t, c in sums:
        a = lite.execute(f"select coalesce(sum({c}),0) from {t}").fetchone()[0]
        b = d.execute(text(f"select coalesce(sum({c}),0) from {t}")).scalar()
        print(f"sum {t}.{c}: sqlite={a} pg={b}")
        ok &= int(a) == int(b)
print("MIGRATION OK" if ok else "MIGRATION FAILED")
sys.exit(0 if ok else 1)
