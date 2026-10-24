import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Job
from app.position_selection import build_selection_snapshot, confirm_exact_product_selection, read_selection, selected_positions


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def make_job(db):
    snapshot = build_selection_snapshot([{"position_no": i, "name": f"Товар {i}", "requirements": []} for i in range(1, 13)], price_kopeks=9900)
    job = Job(mode="exact_product", status="awaiting_exact_selection", position_selection_json=snapshot)
    db.add(job)
    db.commit()
    return job, read_selection(job)


def test_select_second_and_ninth_not_first_five(db):
    job, selection = make_job(db)
    ids = [selection["items"][1]["id"], selection["items"][8]["id"]]
    assert confirm_exact_product_selection(db, job, selection["revision"], ids)
    assert [item["position_no"] for item in selected_positions(job)] == [2, 9]
    assert job.status == "pending"
    assert not confirm_exact_product_selection(db, job, selection["revision"], ids)


@pytest.mark.parametrize("case", ["empty", "unknown", "duplicate", "too_many", "stale"])
def test_invalid_selection_never_becomes_all(db, case):
    job, selection = make_job(db)
    ids = [selection["items"][0]["id"]]
    revision = selection["revision"]
    if case == "empty": ids = []
    if case == "unknown": ids = ["unknown"]
    if case == "duplicate": ids *= 2
    if case == "too_many": ids = [row["id"] for row in selection["items"][:6]]
    if case == "stale": revision = "stale"
    with pytest.raises(ValueError):
        confirm_exact_product_selection(db, job, revision, ids)
    db.refresh(job)
    assert job.status == "awaiting_exact_selection"
    assert not read_selection(job)["confirmed"]


def test_confirmed_choice_cannot_be_overwritten(db):
    job, selection = make_job(db)
    confirm_exact_product_selection(db, job, selection["revision"], [selection["items"][0]["id"]])
    with pytest.raises(ValueError):
        confirm_exact_product_selection(db, job, selection["revision"], [selection["items"][1]["id"]])


def test_duplicate_names_keep_distinct_source_ids():
    import json
    snapshot = json.loads(build_selection_snapshot([{"position_no": 1, "name": "Кран"}, {"position_no": 2, "name": "Кран"}], price_kopeks=9900))
    assert snapshot["items"][0]["id"] != snapshot["items"][1]["id"]
