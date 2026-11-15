import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import bot as bot_module
from app import support_chat as sc
from app.config import config
from app.db import Base
from app.main import (
    admin_client_chat_get,
    admin_client_chat_post,
    admin_dialog_block,
    admin_dialog_unblock,
    admin_dialogs_list,
    admin_dialogs_mark_all_read,
    clients_sync_check,
    customer_chat_post_route,
    customer_job_chat_route,
    dashboard,
    public_guest_chat_messages,
    public_guest_chat_send,
)
from app.models import (
    Client,
    ClientTelegramAccount,
    Job,
    JobChatMessage,
    SupportBlockedActor,
    SupportDialogState,
    SupportGuestSession,
    SupportTelegramMessageMap,
    SupportTelegramSession,
    SystemSettings,
    WebSession,
    WebUser,
)
from app.web_auth import WebAuthContext


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    db_file = tmp_path / "test_support.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(bot_module, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(config, "storage_dir", str(tmp_path / "storage"))
    monkeypatch.setattr(config, "bot_token", "123456:TEST_TOKEN")
    monkeypatch.setattr(config, "owner_telegram_id", "900001")
    monkeypatch.setattr(config, "support_admin_ids", "")
    monkeypatch.setattr(config, "support_group_id", "")
    sc.reset_legacy_import_cache_for_tests()

    calls = []
    next_msg_id = {"val": 100}

    async def fake_tg_post(method, payload=None, **kwargs):
        next_msg_id["val"] += 1
        mid = next_msg_id["val"]
        calls.append({"method": method, "payload": payload or {}, "kwargs": kwargs, "mid": mid})
        if method == "getMe":
            return {"ok": True, "result": {"id": 888888, "username": "tenderlex_test_bot"}}
        if method == "createForumTopic":
            return {"ok": True, "result": {"message_thread_id": 700 + mid, "name": (payload or {}).get("name", "")}}
        return {"ok": True, "result": {"message_id": mid}}

    monkeypatch.setattr(sc, "_tg_api_post", fake_tg_post)

    db = TestingSessionLocal()
    try:
        db.add(
            SystemSettings(
                id=1,
                trial_enabled=True,
                support_telegram_group_id="-100777888999",
                support_admin_telegram_ids="900002",
                support_mirror_admin_replies_to_bot=True,
            )
        )
        db.commit()
        yield SimpleNamespace(
            SessionLocal=TestingSessionLocal,
            db=db,
            calls=calls,
            tmp_path=tmp_path,
        )
    finally:
        db.close()
        engine.dispose()


class FakeUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content

    async def read(self, size: int = -1):
        return self._content


class FakeBot:
    def __init__(self, payload: bytes = b"file-bytes"):
        self.payload = payload

    async def download(self, file_obj, destination: io.BytesIO):
        destination.write(self.payload)


class FakeMsg:
    def __init__(
        self,
        *,
        chat_id: int,
        user_id: int,
        text: str = "",
        caption: str = "",
        message_id: int = 500,
        chat_type: str = ChatType.PRIVATE,
        thread_id: int | None = None,
        reply_to_message=None,
        document=None,
        photo=None,
        is_bot: bool = False,
        bot=None,
        first_name: str = "Admin",
        username: str = "admin_user",
    ):
        self.chat = SimpleNamespace(id=chat_id, type=chat_type)
        self.from_user = SimpleNamespace(
            id=user_id,
            first_name=first_name,
            last_name="",
            username=username,
            is_bot=is_bot,
        )
        self.text = text
        self.caption = caption
        self.message_id = message_id
        self.message_thread_id = thread_id
        self.reply_to_message = reply_to_message
        self.document = document
        self.photo = photo
        self.bot = bot
        self.answers = []
        self.reply_markup_edits = []

    async def answer(self, text: str, **kwargs):
        self.answers.append((text, kwargs))
        return SimpleNamespace(message_id=9000 + len(self.answers))

    async def edit_reply_markup(self, **kwargs):
        self.reply_markup_edits.append(kwargs)


class FakeCallback:
    def __init__(self, *, data: str, user_id: int, chat_id: int, message: FakeMsg | None = None, first_name: str = "Admin"):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id, first_name=first_name, last_name="", username="user_cb", is_bot=False)
        self.message = message or FakeMsg(chat_id=chat_id, user_id=user_id, first_name=first_name)
        self.bot = AsyncMock()
        self.answers = []

    async def answer(self, text: str = "", **kwargs):
        self.answers.append((text, kwargs))


@pytest.mark.asyncio
async def test_web_message_syncs_to_dm_and_forum_topic_and_callback_under_64_bytes(test_env):
    db = test_env.db
    client = Client(name="ООО Ромашка", client_number=55, telegram_id="550011")
    db.add(client)
    db.flush()
    user = WebUser(client_id=client.id, email="buyer@romashka.ru", password_hash="x", is_email_verified=True)
    db.add(user)
    db.flush()
    job = Job(client_id=client.id, job_number=77, title="Поставка насосов", mode="supplier_search", status="completed")
    db.add(job)
    db.commit()

    ctx = WebAuthContext(user=user, session=WebSession(id="ws1", user_id=user.id))
    # Two rapid customer messages -> NO 60s throttle!
    await customer_chat_post_route(message="Первое сообщение", context=ctx, db=db)
    await customer_job_chat_route(job_id=job.id, message="Второе сообщение по задаче", context=ctx, db=db)

    create_topics = [c for c in test_env.calls if c["method"] == "createForumTopic"]
    assert len(create_topics) == 1  # One Forum Topic reused for both messages!
    topic_posts = [c for c in test_env.calls if c["method"] == "sendMessage" and c["payload"].get("chat_id") == "-100777888999"]
    # 1 topic header + 2 client messages
    assert len(topic_posts) == 3

    dm_posts = [c for c in test_env.calls if c["method"] == "sendMessage" and c["payload"].get("chat_id") in ("900001", "900002")]
    # 2 messages * 2 authorized admins = 4 DM cards
    assert len(dm_posts) == 4
    # Verify all inline callback_data are <= 64 bytes
    for c in dm_posts:
        kb = c["payload"].get("reply_markup", {}).get("inline_keyboard", [])
        for row in kb:
            for btn in row:
                if "callback_data" in btn:
                    assert len(btn["callback_data"].encode("utf-8")) <= 64


@pytest.mark.asyncio
async def test_option_a_dm_reply_and_session_syncs_everywhere(test_env):
    db = test_env.db
    client = Client(name="ИП Иванов", client_number=12, telegram_id="330011")
    db.add(client)
    db.flush()
    msg = JobChatMessage(client_id=client.id, job_id="", sender_role="client", channel="web", message="Нужен договор")
    db.add(msg)
    db.commit()

    await sc.notify_admins_of_incoming_message(db, client_id=client.id, text="Нужен договор", chat_message_id=msg.id, channel="web")

    # Find exact DM message_id sent to owner 900001
    owner_dm = next(c for c in test_env.calls if c["method"] == "sendMessage" and c["payload"].get("chat_id") == "900001")
    card_mid = owner_dm["mid"]

    # 1. Native Reply in DM by authorized owner
    reply_msg = FakeMsg(
        chat_id=900001,
        user_id=900001,
        text="Договор отправил!",
        reply_to_message=SimpleNamespace(message_id=card_mid),
    )
    handled = await bot_module._handle_support_private_message(reply_msg)
    assert handled is True

    # Verify DB saved reply + sent to client TG + mirrored to Forum Topic & second admin
    db.expire_all()
    msgs = db.query(JobChatMessage).filter(JobChatMessage.client_id == client.id).order_by(JobChatMessage.created_at.asc()).all()
    assert len(msgs) == 2
    assert msgs[1].sender_role == "admin"
    assert msgs[1].channel == "tg_dm"
    assert msgs[1].message == "Договор отправил!"

    client_sends = [c for c in test_env.calls if c["method"] == "sendMessage" and c["payload"].get("chat_id") == "330011"]
    assert len(client_sends) == 1
    assert "Договор отправил" in client_sends[0]["payload"]["text"]

    # Second admin 900002 received mirror, while actor 900001 did NOT get self-echo
    second_admin_echo = [c for c in test_env.calls if c["method"] == "sendMessage" and c["payload"].get("chat_id") == "900002" and "Ответ отправлен" in c["payload"].get("text", "")]
    assert len(second_admin_echo) == 1

    # Admin main menu integrates "Диалоги с клиентами" ONLY for authorized admins, NEVER for regular users
    admin_menu_labels = [btn.text for row in bot_module.main_inline_keyboard(900001).inline_keyboard for btn in row]
    second_admin_menu_labels = [btn.text for row in bot_module.main_inline_keyboard(900002).inline_keyboard for btn in row]
    client_menu_labels = [btn.text for row in bot_module.main_inline_keyboard(330011).inline_keyboard for btn in row]
    assert any("Диалоги с клиентами" in lbl for lbl in admin_menu_labels)
    assert any("Диалоги с клиентами" in lbl for lbl in second_admin_menu_labels)
    assert all("Диалоги с клиентами" not in lbl for lbl in client_menu_labels)
    assert "💬 Написать в поддержку" in client_menu_labels

    # 2. Persistent Enter Chat mode + Photo upload by admin
    state = db.query(SupportDialogState).filter(SupportDialogState.client_id == client.id).first()
    cb = FakeCallback(data=f"tg_chat:enter:{state.id}", user_id=900001, chat_id=900001)
    await bot_module.handle_admin_tg_chat_callback(cb)
    enter_kb = cb.message.answers[-1][1]["reply_markup"].inline_keyboard
    enter_labels = [btn.text for row in enter_kb for btn in row]
    assert any("Главное меню" in lbl for lbl in enter_labels)
    assert not any("Завершить диалог" in lbl for lbl in enter_labels)

    photo_msg = FakeMsg(
        chat_id=900001,
        user_id=900001,
        caption="Скан страницы 1",
        photo=[SimpleNamespace(file_id="ph_1")],
        bot=FakeBot(b"\x89PNG\r\n\x1a\nfakeimage"),
    )
    handled_photo = await bot_module._handle_support_private_message(photo_msg, photo_msg.bot)
    assert handled_photo is True
    sent_kb = photo_msg.answers[-1][1]["reply_markup"].inline_keyboard
    sent_labels = [btn.text for row in sent_kb for btn in row]
    assert sent_labels == ["💬 Все диалоги", "🏠 Главное меню"]

    # Clicking "🏠 Главное меню" exits reply session and shows main menu with admin dialogs button (no slashes)
    exit_cb = FakeCallback(data="tg_chat:exit", user_id=900001, chat_id=900001)
    await bot_module.handle_admin_tg_chat_callback(exit_cb)
    exit_text, exit_kwargs = exit_cb.message.answers[-1]
    assert "/dialogs" not in exit_text and "/exit_chat" not in exit_text
    exit_labels = [btn.text for row in exit_kwargs["reply_markup"].inline_keyboard for btn in row]
    assert any("Диалоги с клиентами" in lbl for lbl in exit_labels)
    assert sc.get_active_tg_session(db, tg_user_id=900001, role_scope="admin_reply") is None

    db.expire_all()
    msgs_after = db.query(JobChatMessage).filter(JobChatMessage.client_id == client.id).order_by(JobChatMessage.created_at.asc()).all()
    assert len(msgs_after) == 3
    atts = json.loads(msgs_after[2].attachments_json)
    assert len(atts) == 1
    assert atts[0]["name"].endswith(".jpg")

    # Unauthorized user clicking tg_chat:enter is denied
    unauth_cb = FakeCallback(data=f"tg_chat:enter:{state.id}", user_id=999999, chat_id=999999)
    await bot_module.handle_admin_tg_chat_callback(unauth_cb)
    assert unauth_cb.answers[-1][1].get("show_alert") is True


@pytest.mark.asyncio
async def test_option_b_forum_topic_sync_and_commands_and_auth(test_env):
    db = test_env.db
    client = Client(name="ООО Альфа", client_number=88, telegram_id="440022")
    db.add(client)
    db.commit()

    await sc.notify_admins_of_incoming_message(db, client_id=client.id, text="Вопрос по 44-ФЗ", channel="web")
    state = db.query(SupportDialogState).filter(SupportDialogState.client_id == client.id).first()
    assert state is not None and state.telegram_thread_id > 0

    # Non-admin typing inside the support group topic MUST be ignored (no JobChatMessage created)
    stranger_msg = FakeMsg(
        chat_id=-100777888999,
        user_id=123456,
        text="Левое сообщение",
        chat_type=ChatType.SUPERGROUP,
        thread_id=state.telegram_thread_id,
    )
    await bot_module.support_group_message_handler(stranger_msg, FakeBot())
    assert db.query(JobChatMessage).filter(JobChatMessage.client_id == client.id).count() == 0

    # Casual message in General topic (thread_id=None) is ignored
    general_msg = FakeMsg(
        chat_id=-100777888999,
        user_id=900001,
        text="Коллеги, кто на смене?",
        chat_type=ChatType.SUPERGROUP,
        thread_id=None,
    )
    await bot_module.support_group_message_handler(general_msg, FakeBot())
    assert db.query(JobChatMessage).filter(JobChatMessage.client_id == client.id).count() == 0

    # Authorized admin replies in topic with document
    topic_doc_msg = FakeMsg(
        chat_id=-100777888999,
        user_id=900002,
        caption="Заключение эксперта во вложении",
        document=SimpleNamespace(file_name="audit.pdf", file_size=200),
        chat_type=ChatType.SUPERGROUP,
        thread_id=state.telegram_thread_id,
    )
    await bot_module.support_group_message_handler(topic_doc_msg, FakeBot(b"%PDF-1.4 sample"))

    db.expire_all()
    msgs = db.query(JobChatMessage).filter(JobChatMessage.client_id == client.id).all()
    assert len(msgs) == 1
    assert msgs[0].channel == "tg_topic"
    assert msgs[0].sender_role == "admin"
    assert len(json.loads(msgs[0].attachments_json)) == 1
    assert any(c["payload"].get("chat_id") == "440022" for c in test_env.calls)

    # /info inside topic
    info_msg = FakeMsg(chat_id=-100777888999, user_id=900001, text="/info", chat_type=ChatType.SUPERGROUP, thread_id=state.telegram_thread_id)
    await bot_module.support_group_message_handler(info_msg, FakeBot())
    assert "ООО Альфа" in info_msg.answers[0][0]

    # /close inside topic
    close_msg = FakeMsg(chat_id=-100777888999, user_id=900001, text="/close", chat_type=ChatType.SUPERGROUP, thread_id=state.telegram_thread_id)
    await bot_module.support_group_message_handler(close_msg, FakeBot())
    assert any(c["method"] == "closeForumTopic" for c in test_env.calls)

    # Unrelated group falls back to group safety rejection
    other_group_msg = FakeMsg(chat_id=-100999111222, user_id=555555, text="Привет", chat_type=ChatType.SUPERGROUP)
    await bot_module.support_group_message_handler(other_group_msg, FakeBot())
    assert "только в личном чате" in other_group_msg.answers[0][0]


@pytest.mark.asyncio
async def test_client_bot_support_flow_and_topic_recovery(test_env, monkeypatch):
    db = test_env.db
    client = Client(name="Тест Клиент", telegram_id="770088", username="testcli")
    db.add(client)
    db.flush()
    db.add(ClientTelegramAccount(client_id=client.id, telegram_id="770088", username="testcli", is_active=True))
    db.commit()

    # Client clicks "Написать в поддержку" button
    cb = FakeCallback(data="client_support:start", user_id=770088, chat_id=770088, first_name="Иван")
    await bot_module.handle_client_support_callback(cb)

    cli_msg = FakeMsg(chat_id=770088, user_id=770088, text="Здравствуйте, помогите с КП!", first_name="Иван", username="testcli")
    handled = await bot_module._handle_support_private_message(cli_msg)
    assert handled is True

    db.expire_all()
    saved = db.query(JobChatMessage).filter(JobChatMessage.client_id == client.id).all()
    assert len(saved) == 1
    assert saved[0].sender_role == "client"
    assert saved[0].channel == "tg_bot"

    # Simulate deleted Forum Topic on next incoming message -> auto-recreates topic
    orig_post = sc._tg_api_post
    failed_once = {"flag": False}

    async def flaky_tg_post(method, payload=None, **kwargs):
        if method == "sendMessage" and (payload or {}).get("chat_id") == "-100777888999" and not failed_once["flag"]:
            failed_once["flag"] = True
            return {"ok": False, "description": "Bad Request: message thread not found"}
        return await orig_post(method, payload, **kwargs)

    monkeypatch.setattr(sc, "_tg_api_post", flaky_tg_post)
    state_before = db.query(SupportDialogState).filter(SupportDialogState.client_id == client.id).first()
    old_thread_id = state_before.telegram_thread_id

    await sc.notify_admins_of_incoming_message(db, client_id=client.id, text="Повторное сообщение", channel="tg_bot")
    db.expire_all()
    state_after = db.query(SupportDialogState).filter(SupportDialogState.client_id == client.id).first()
    assert state_after.telegram_thread_id != old_thread_id
    assert state_after.telegram_thread_id > 0

    # /start clears client_dm support session so subsequent messages act normally
    start_msg = FakeMsg(chat_id=770088, user_id=770088, text="/start")
    await bot_module.start(start_msg)
    assert db.query(SupportTelegramSession).filter(SupportTelegramSession.tg_user_id == "770088", SupportTelegramSession.is_active == True).count() == 0


@pytest.mark.asyncio
async def test_guest_web_chat_legacy_import_and_admin_sync(test_env):
    db = test_env.db
    legacy_file = test_env.tmp_path / "chat_sessions.json"
    legacy_file.write_text(
        json.dumps(
            {
                "sess_real_visitor_1": {
                    "sessionId": "sess_real_visitor_1",
                    "contact": "guest@company.ru",
                    "created": "2026-11-14T10:00:00Z",
                    "updated": "2026-11-14T10:01:00Z",
                    "messages": [{"id": "m1", "sender": "user", "text": "Старый вопрос гостя", "timestamp": "2026-11-14T10:00:00Z"}],
                },
                "sqli-test-1": {
                    "sessionId": "sqli-test-1",
                    "messages": [{"id": "m2", "sender": "user", "text": "' OR 1=1;", "timestamp": "2026-11-14T10:00:00Z"}],
                },
            }
        ),
        encoding="utf-8",
    )
    sc.ensure_legacy_guest_sessions_imported(db, json_path=legacy_file)
    assert db.query(SupportGuestSession).filter(SupportGuestSession.session_id == "sess_real_visitor_1").first() is not None
    assert db.query(SupportGuestSession).filter(SupportGuestSession.session_id == "sqli-test-1").first() is None

    # New guest message from public widget
    req = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    send_res = await public_guest_chat_send(
        request=req,
        payload={"sessionId": "sess_guest_sync_42", "text": "Сколько стоит анализ?", "contact": "+79990001122"},
        db=db,
    )
    assert send_res["success"] is True

    # Guest shows up in admin_dialogs_list + unread count in dashboard
    dash = dashboard(db=db)
    assert dash["unread_dialogs_count"] >= 1

    dialogs_res = admin_dialogs_list(db=db)
    guest_d = next(d for d in dialogs_res["dialogs"] if d["client_id"] == "guest:sess_guest_sync_42")
    assert guest_d["is_guest"] is True
    assert guest_d["unread_admin_count"] == 1

    # Admin replies from admin panel -> synced back to guest widget messages API
    chat_view = admin_client_chat_get(client_id="guest:sess_guest_sync_42", db=db)
    assert chat_view["client"]["is_guest"] is True
    assert len(chat_view["messages"]) == 1

    await admin_client_chat_post(client_id="guest:sess_guest_sync_42", message="Разовый анализ стоит 1490 руб.", notify_telegram=False, db=db)
    guest_msgs = public_guest_chat_messages(sessionId="sess_guest_sync_42", db=db)
    assert len(guest_msgs["messages"]) == 2
    assert guest_msgs["messages"][1]["sender"] == "admin"
    assert "1490" in guest_msgs["messages"][1]["text"]


@pytest.mark.asyncio
async def test_support_group_connection_diagnostics(test_env, monkeypatch):
    db = test_env.db

    async def mock_non_forum(method, payload=None, **kwargs):
        if method == "getMe":
            return {"ok": True, "result": {"id": 888, "username": "tenderlex_bot"}}
        if method == "getChat":
            return {"ok": True, "result": {"id": -100123456, "type": "supergroup", "is_forum": False, "title": "Test Group"}}
        return {"ok": True, "result": {}}

    monkeypatch.setattr(sc, "_tg_api_post", mock_non_forum)
    res_nf = await sc.test_support_group_connection(db, group_id_override="-100123456", allow_in_test=True)
    assert res_nf["ok"] is False
    assert "Темы" in res_nf["error"]

    async def mock_ready(method, payload=None, **kwargs):
        if method == "getMe":
            return {"ok": True, "result": {"id": 888, "username": "tenderlex_bot"}}
        if method == "getChat":
            return {"ok": True, "result": {"id": -100777, "type": "supergroup", "is_forum": True, "title": "TenderLex Поддержка"}}
        if method == "getChatMember":
            return {"ok": True, "result": {"status": "administrator", "can_manage_topics": True}}
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(sc, "_tg_api_post", mock_ready)
    res_ok = await sc.test_support_group_connection(db, group_id_override="-100777", allow_in_test=True)
    assert res_ok["ok"] is True
    assert "подтверждены" in res_ok["message"]


@pytest.mark.asyncio
async def test_guest_chat_ip_and_session_rate_limits(test_env):
    from fastapi import HTTPException

    db = test_env.db

    # 1. Malformed X-Forwarded-For tokens + loopback are ignored; valid client IP is persisted
    req_spoofed_hdr = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"x-forwarded-for": "../../../etc/passwd, 203.0.113.55, 127.0.0.1"},
    )
    for i in range(5):
        res = await public_guest_chat_send(
            request=req_spoofed_hdr,
            payload={"sessionId": f"sess_scan_{i}", "text": f"probe {i}"},
            db=db,
        )
        assert res["success"] is True

    sessions_created = db.query(SupportGuestSession).filter(SupportGuestSession.client_ip == "203.0.113.55").count()
    assert sessions_created == 5

    # 6th new session from the same IP in 10 minutes is blocked BEFORE touching DB or Telegram
    calls_before = len(test_env.calls)
    with pytest.raises(HTTPException) as exc_info:
        await public_guest_chat_send(
            request=req_spoofed_hdr,
            payload={"sessionId": "thishouldnotexistandhopefullyitwillnot", "text": "/etc/passwd"},
            db=db,
        )
    assert exc_info.value.status_code == 429
    assert (
        db.query(SupportGuestSession)
        .filter(SupportGuestSession.session_id == "thishouldnotexistandhopefullyitwillnot")
        .first()
        is None
    )
    assert len(test_env.calls) == calls_before

    # 2. Per-session (8/min) and cross-session per-IP (12/min) message burst caps
    req_ip2 = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"x-real-ip": "198.51.100.7"},
    )
    for i in range(8):
        await public_guest_chat_send(
            request=req_ip2,
            payload={"sessionId": "sess_ip2_a", "text": f"msg {i}"},
            db=db,
        )
    with pytest.raises(HTTPException) as exc_sess:
        await public_guest_chat_send(
            request=req_ip2,
            payload={"sessionId": "sess_ip2_a", "text": "msg 9"},
            db=db,
        )
    assert exc_sess.value.status_code == 429

    # Rotating to a second session allows up to 4 more messages (12 total/min per IP), then blocks
    for i in range(4):
        await public_guest_chat_send(
            request=req_ip2,
            payload={"sessionId": "sess_ip2_b", "text": f"msg_b {i}"},
            db=db,
        )
    with pytest.raises(HTTPException) as exc_ip:
        await public_guest_chat_send(
            request=req_ip2,
            payload={"sessionId": "sess_ip2_b", "text": "msg_b 5"},
            db=db,
        )
    assert exc_ip.value.status_code == 429


@pytest.mark.asyncio
async def test_mark_all_dialogs_read_and_block_unblock_guest_and_client(test_env):
    from fastapi import HTTPException
    from app.web_auth import authenticate_web_user, create_web_session, create_web_user, get_web_session_by_token

    db = test_env.db

    # Create two unread dialogs: one guest (with public IP) and one registered web+TG client
    req_guest = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"x-forwarded-for": "203.0.113.88"},
    )
    await public_guest_chat_send(
        request=req_guest,
        payload={"sessionId": "sess_spam_guest_1", "text": "spam message 1"},
        db=db,
    )

    user = create_web_user(
        db,
        email="spammer@example.com",
        password="Password123!",
        name="Spam Client",
        commit=True,
    )
    client = user.client
    client.telegram_id = "77889900"
    db.add(
        ClientTelegramAccount(
            client_id=client.id,
            telegram_id="77889900",
            username="spammer_tg",
            is_active=True,
        )
    )
    db.commit()
    token, _csrf, _sess = create_web_session(db, user, request=req_guest)

    await sc.deliver_client_telegram_message(
        db,
        tg_user_id="77889900",
        username="spammer_tg",
        full_name="Spam Client",
        text="client unread message",
        allow_in_test=False,
    )

    listed_before = admin_dialogs_list(db=db)
    assert listed_before["total_unread_admin"] == 2
    assert len(listed_before["dialogs"]) == 2
    assert all(d["is_blocked"] is False for d in listed_before["dialogs"])

    # 1. Mark all dialogs read in one click
    read_all_res = admin_dialogs_mark_all_read(db=db)
    assert read_all_res["ok"] is True
    assert read_all_res["marked_count"] == 2
    assert read_all_res["total_unread_admin"] == 0

    listed_after_read = admin_dialogs_list(db=db)
    assert listed_after_read["total_unread_admin"] == 0
    assert all(d["unread_admin_count"] == 0 for d in listed_after_read["dialogs"])
    assert clients_sync_check(db=db)["unread_dialogs_count"] == 0

    # 2. Block website guest (blocks session AND IP, even across rotated sessionId)
    block_guest_res = await admin_dialog_block("guest:sess_spam_guest_1", payload={}, db=db)
    assert block_guest_res["ok"] is True
    assert block_guest_res["is_blocked"] is True
    assert db.query(SupportBlockedActor).filter(SupportBlockedActor.actor_value == "203.0.113.88").first() is not None

    guest_poll = public_guest_chat_messages(sessionId="sess_spam_guest_1", request=req_guest, db=db)
    assert guest_poll["status"] == "blocked"
    assert guest_poll["is_blocked"] is True

    with pytest.raises(HTTPException) as exc_same_sid:
        await public_guest_chat_send(
            request=req_guest,
            payload={"sessionId": "sess_spam_guest_1", "text": "more spam"},
            db=db,
        )
    assert exc_same_sid.value.status_code == 403

    with pytest.raises(HTTPException) as exc_rotated_sid:
        await public_guest_chat_send(
            request=req_guest,
            payload={"sessionId": "sess_spam_guest_rotated_2", "text": "evade block"},
            db=db,
        )
    assert exc_rotated_sid.value.status_code == 403

    guest_chat_detail = admin_client_chat_get("guest:sess_spam_guest_1", db=db)
    assert guest_chat_detail["client"]["is_blocked"] is True

    # 3. Unblock guest -> restores access immediately
    unblock_guest_res = await admin_dialog_unblock("guest:sess_spam_guest_1", db=db)
    assert unblock_guest_res["ok"] is True
    assert unblock_guest_res["is_blocked"] is False

    ok_after_unblock = await public_guest_chat_send(
        request=req_guest,
        payload={"sessionId": "sess_spam_guest_1", "text": "sorry, legitimate question"},
        db=db,
    )
    assert ok_after_unblock["success"] is True

    # 4. Block registered client -> disables client, revokes web session, rejects login & TG support
    block_client_res = await admin_dialog_block(client.id, payload={}, db=db)
    assert block_client_res["ok"] is True
    assert block_client_res["is_blocked"] is True

    db.expire_all()
    assert get_web_session_by_token(db, token) is None
    assert authenticate_web_user(db, "spammer@example.com", "Password123!") is None
    with pytest.raises(PermissionError):
        await sc.deliver_client_telegram_message(
            db,
            tg_user_id="77889900",
            username="spammer_tg",
            full_name="Spam Client",
            text="blocked tg spam",
            allow_in_test=False,
        )

    client_chat_detail = admin_client_chat_get(client.id, db=db)
    assert client_chat_detail["client"]["is_blocked"] is True

    # 5. Unblock registered client -> restores login & TG support
    unblock_client_res = await admin_dialog_unblock(client.id, db=db)
    assert unblock_client_res["ok"] is True
    assert unblock_client_res["is_blocked"] is False
    db.expire_all()
    assert authenticate_web_user(db, "spammer@example.com", "Password123!") is not None
    tg_ok = await sc.deliver_client_telegram_message(
        db,
        tg_user_id="77889900",
        username="spammer_tg",
        full_name="Spam Client",
        text="restored tg message",
        allow_in_test=False,
    )
    assert tg_ok["client_id"] == client.id

