import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from app import bot
from app.bot import _exact_selection_view
from app.models import Job
from app.position_selection import build_selection_snapshot


def test_telegram_selection_pages_keep_original_ids_and_bound_callback_lengths():
    selection = json.loads(build_selection_snapshot([{"position_no": i, "name": f"Товар {i}"} for i in range(1, 13)], price_kopeks=9900))
    selection["selected_ids"] = [selection["items"][8]["id"]]
    job = Job(id="a" * 32, mode="exact_product", status="awaiting_exact_selection", position_selection_json=json.dumps(selection))
    text, keyboard = _exact_selection_view(job, page=1)
    assert "99.00" in text
    assert "1 из 12" in text
    buttons = [b for row in keyboard.inline_keyboard for b in row]
    assert any("9" in b.text and "☑" in b.text for b in buttons)
    assert any(b.callback_data == f"exact_toggle:{job.id}:8" for b in buttons)
    assert all(len(b.callback_data.encode()) <= 64 for b in buttons)


def test_telegram_monitoring_selection_explains_unit_price_and_maximum_without_word_claim():
    selection = json.loads(build_selection_snapshot(
        [{"position_no": i, "name": f"Товар {i}"} for i in range(1, 4)],
        price_kopeks=5_000,
        mode="price_monitoring",
    ))
    selection["selected_ids"] = [selection["items"][0]["id"]]
    job = Job(
        id="b" * 32,
        mode="price_monitoring",
        status="awaiting_position_selection",
        position_selection_json=json.dumps(selection),
    )

    text, keyboard = _exact_selection_view(job)

    assert "1 из 3" in text
    assert "50.00 ₽ за позицию с подтверждённой ценой" in text
    assert "150.00 ₽" in text
    assert "только за найденные цены" in text
    assert "Word" not in text
    assert any(button.callback_data == f"exact_confirm:{job.id}"
               for row in keyboard.inline_keyboard for button in row)


@pytest.mark.parametrize('mode', ['exact_product', 'price_monitoring'])
@pytest.mark.parametrize('result_status', ['completed', 'cancelled', None])
def test_confirm_positions_watches_existing_progress_and_only_delivers_completed(
    monkeypatch, mode, result_status,
):
    selection = json.loads(build_selection_snapshot([{'position_no': 1, 'name': 'Товар'}], price_kopeks=100, mode=mode))
    selection['selected_ids'] = [selection['items'][0]['id']]
    job = Job(id='c' * 32, mode=mode, status='pending', position_selection_json=json.dumps(selection))
    db = Mock()
    db.get.return_value = job
    message = SimpleNamespace(edit_text=AsyncMock())
    callback = SimpleNamespace(data=f'exact_confirm:{job.id}', message=message, answer=AsyncMock())
    snapshot = SimpleNamespace(status=result_status) if result_status else None
    watch = AsyncMock(return_value=snapshot)
    deliver = AsyncMock()
    enqueue = Mock()
    monkeypatch.setattr(bot, 'SessionLocal', lambda: db)
    monkeypatch.setattr(bot, '_callback_job_allowed', lambda *args: True)
    monkeypatch.setattr(bot, 'confirm_position_selection', lambda *args: True)
    monkeypatch.setattr(bot, 'enqueue_job', enqueue)
    monkeypatch.setattr(bot, 'watch_job_progress', watch)
    monkeypatch.setattr(bot, '_send_job_outputs', deliver)

    asyncio.run(bot.exact_selection_callback(callback))

    enqueue.assert_called_once_with(job.id)
    watch.assert_awaited_once_with(message, job.id, status_message=message)
    if result_status == 'completed':
        deliver.assert_awaited_once_with(message, job.id, snapshot)
    else:
        deliver.assert_not_awaited()
    db.close.assert_called_once()


@pytest.mark.parametrize('mode', ['exact_product', 'price_monitoring'])
def test_repeated_position_confirmation_does_not_start_another_progress_watcher(monkeypatch, mode):
    job = Job(id='d' * 32, mode=mode, status='pending', position_selection_json=build_selection_snapshot([{'name': 'Товар'}], price_kopeks=100, mode=mode))
    db = Mock()
    db.get.return_value = job
    callback = SimpleNamespace(data=f'exact_confirm:{job.id}', message=SimpleNamespace(edit_text=AsyncMock()), answer=AsyncMock())
    watch = AsyncMock()
    enqueue = Mock()
    monkeypatch.setattr(bot, 'SessionLocal', lambda: db)
    monkeypatch.setattr(bot, '_callback_job_allowed', lambda *args: True)
    monkeypatch.setattr(bot, 'confirm_position_selection', lambda *args: False)
    monkeypatch.setattr(bot, 'enqueue_job', enqueue)
    monkeypatch.setattr(bot, 'watch_job_progress', watch)

    asyncio.run(bot.exact_selection_callback(callback))

    enqueue.assert_not_called()
    watch.assert_not_awaited()
    callback.message.edit_text.assert_awaited_once()
