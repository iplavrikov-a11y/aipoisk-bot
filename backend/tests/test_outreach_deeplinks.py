from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.bot as bot_mod
from app.db import Base
from app.legal import LEGAL_VERSION
from app.main import customer_register_api
from app.models import UserJourneyEvent
from app.schemas import WebRegisterRequest
from app.security_shield import create_human_challenge


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_telegram_start_contract_and_source_deeplinks():
    Session = _make_session()
    with patch.object(bot_mod, "SessionLocal", Session):
        msg_contract = SimpleNamespace(
            from_user=SimpleNamespace(id=770011, username="eis_winner", full_name="ООО Вектор"),
            chat=SimpleNamespace(id=770011, type="private"),
            answer=AsyncMock(),
        )
        cmd_contract = SimpleNamespace(args="c_2143300936526000289")
        asyncio.run(bot_mod.start(msg_contract, command=cmd_contract))

        assert bot_mod.PENDING_MODES.get(770011) == bot_mod.SCENARIO_SUPPLIERS
        answered_text = msg_contract.answer.call_args[0][0]
        assert "2143300936526000289" in answered_text

        msg_hh = SimpleNamespace(
            from_user=SimpleNamespace(id=770022, username="hr_buyer", full_name="Мария Снаб"),
            chat=SimpleNamespace(id=770022, type="private"),
            answer=AsyncMock(),
        )
        cmd_hh = SimpleNamespace(args="src_hh")
        asyncio.run(bot_mod.start(msg_hh, command=cmd_hh))
        assert bot_mod.PENDING_MODES.get(770022) == bot_mod.SCENARIO_SUPPLIERS

        with Session() as db:
            events = db.query(UserJourneyEvent).filter(UserJourneyEvent.event_name == "outreach_entry").all()
            outcomes = {(e.outcome, e.reason_code) for e in events}
            assert ("autoeis", "2143300936526000289") in outcomes
            assert ("hh", "src_hh") in outcomes


def test_web_register_records_outreach_utm_attribution():
    Session = _make_session()
    with Session() as db, patch("app.main._send_customer_verification_email", return_value=True):
        ch = create_human_challenge()
        # Wait tiny bit or patch verify_human_challenge so min_elapsed check passes cleanly
        with patch("app.main.verify_human_challenge", return_value=(True, "ok")):
            req = SimpleNamespace(
                headers={"user-agent": "Mozilla/5.0", "x-forwarded-for": "198.51.100.42"},
                client=SimpleNamespace(host="198.51.100.42"),
                cookies={},
            )
            resp = Response()
            payload = WebRegisterRequest(
                email="buyer@promkomplekt.ru",
                password="StrongPassword123!",
                name="Алексей Снабжение",
                terms_accepted=True,
                personal_data_consent=True,
                legal_version=LEGAL_VERSION,
                challenge_token=ch["token"],
                utm_source="suplbiz",
                utm_campaign="supl_orders",
            )
            result = customer_register_api(payload, req, resp, db=db)
            assert result["authenticated"] is True

            ev = db.query(UserJourneyEvent).filter(
                UserJourneyEvent.event_name == "outreach_entry",
                UserJourneyEvent.channel == "web",
            ).first()
            assert ev is not None
            assert ev.outcome == "suplbiz"
            assert ev.reason_code == "supl_orders"
