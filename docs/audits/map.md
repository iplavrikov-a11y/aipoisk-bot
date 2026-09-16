# Карта системы: TenderLex Telegram Bot

Дата: 2026-09-10
Коммит: `78a559d`
Мишень: `@tenderlex_bot` (`backend/app/bot.py`)

## 1. Входы и интерфейсы
- **Команды Telegram**: `/start`, `/help`, `/cabinet`, `/tasks`, `/create`
- **Инлайн-кнопки**:
  - `open_create_menu`
  - `scenario:suppliers`
  - `scenario:exact_product`
  - `scenario:report`
  - `scenario:analysis_and_suppliers`
  - `menu:cabinet`, `menu:tariffs`, `menu:help`, `menu:history`, `menu:contacts`, `menu:invite`
- **Текстовые сообщения**: ввод названий, характеристик ТЗ, 19-значных номеров ЕИС, ссылок
- **Файлы**: документы ТЗ (`.docx`, `.pdf`, `.xlsx`, архивы `.zip`)

## 2. Ключевые модули платформы
1. **Поиск поставщиков** (`scenario:suppliers`)
2. **Подбор товара и аналогов** (`scenario:exact_product` — исключительно DOCX)
3. **Анализ документации** (`scenario:report`)
4. **Комплексный анализ + поиск** (`scenario:analysis_and_suppliers`)

## 3. Точки наблюдения и чтения
- **Telegram-история чата**: сообщения, инлайн-кнопки, тосты callback
- **База данных**: SQLite `/root/projects/aipoisk-bot/data/aipoisk.db`
  - Таблицы: `clients`, `client_telegram_accounts`, `jobs`, `job_files`, `billing_transactions`
- **Системные логи**: `journalctl -u aipoisk-bot.service`
