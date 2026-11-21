# TenderLex — Правила для OpenCode и AI-агентов

## ⚠️ КРИТИЧЕСКИЕ ПРАВИЛА РАЗРАБОТКИ И ДЕПЛОЯ

1. **Бэкенд НЕ обновляется автоматически:**
   - Бэкенд работает как системный демон: `systemd: tenderlex-api.service` (uvicorn на `127.0.0.1:8088`).
   - При любых изменениях файлов в `backend/app/*.py` **ОБЯЗАТЕЛЬНО** выполни:
     ```bash
     systemctl restart tenderlex-api.service
     ```
   - Без перезапуска службы работающий процесс uvicorn в памяти НЕ увидит новые эндпоинты, и браузер получит `404 Not Found`.

2. **Запрещено гадать по ошибкам 404 / 500:**
   - Если при вызове API в браузере или кабинете возникает `404 Not Found` или `500 Internal Server Error`, **ЗАПРЕЩЕНО** переписывать фронтенд (`cabinet-client.tsx`, FormData, headers, CSRF).
   - Сначала проверь реальный бэкенд:
     ```bash
     curl -I http://127.0.0.1:8088/api/...
     journalctl -u tenderlex-api -n 50 --no-pager
     ```
   - Если curl возвращает 404 — роут отсутствует в работающем uvicorn! Перезапусти `tenderlex-api.service`.

3. **Обновление фронтенда (Next.js):**
   - Сайт и кабинет работают как служба `tenderlex-site.service` на `127.0.0.1:3093` (Next.js standalone).
   - После изменения `site/src/app/...`:
     ```bash
     cd site && npm run build
     systemctl restart tenderlex-site.service
     ```

4. **Обновление Telegram-бота:**
   - Бот работает как служба `tenderlex-bot.service`.
   - После правок в `backend/app/bot.py`:
     ```bash
     systemctl restart tenderlex-bot.service
     ```

5. **Комплексный деплой:**
   - Для безопасного выката всех сервисов с бекапом SQLite и проверкой очередей:
     ```bash
     ./scripts/deploy_tenderlex_live.sh
     ```

## Архитектура портов и прокси
- `https://tenderlex.ru/api/*` → Nginx → `http://127.0.0.1:8088` (`tenderlex-api.service`)
- `https://tenderlex.ru/*` → Nginx → `http://127.0.0.1:3093` (`tenderlex-site.service`)
