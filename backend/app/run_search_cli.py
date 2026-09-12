import asyncio
import sys
import logging
from app.db import SessionLocal
from app.models import SystemSettings
from app.outreach_models import OutreachSearchTask, now_utc
from app.outreach_search import run_outreach_search_task

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def main():
    task_name = "Участники тендеров и исполнители госконтрактов 44-ФЗ/223-ФЗ"
    prompt = (
        "Компании занимающиеся участием в тендерах и исполнением госконтрактов 44-ФЗ и 223-ФЗ, "
        "поставщики и подрядчики, торговые дома, посредники между заводами и государственными заказчиками, "
        "тендерные отделы компаний, комплексное снабжение по госзакупкам "
        "(исключить банковские гарантии, займы, факторинг, обучающие курсы и школы госзакупок)"
    )
    target_count = 1000
    task_id = f"task-tender-1000"

    db = SessionLocal()
    sys_settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not sys_settings:
        sys_settings = SystemSettings(id=1)

    # Register task
    task = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
    if not task:
        task = OutreachSearchTask(
            id=task_id,
            name=task_name,
            prompt=prompt,
            target_count=target_count,
            status="running",
            started_at=now_utc(),
            message="Генерация поисковых запросов и запуск сбора...",
        )
        db.add(task)
    else:
        task.name = task_name
        task.prompt = prompt
        task.target_count = target_count
        task.status = "running"
        task.started_at = now_utc()
        task.completed_at = None
        task.message = "Запуск сбора контактов..."
    db.commit()
    db.close()

    print(f"Starting search task '{task_name}' (ID: {task_id}, Target: {target_count})...")
    await run_outreach_search_task(
        task_id=task_id,
        name=task_name,
        prompt=prompt,
        target_count=target_count,
        session_factory=SessionLocal,
        settings=sys_settings,
    )
    print(f"Task {task_id} execution finished.")

if __name__ == "__main__":
    asyncio.run(main())
