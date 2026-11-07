# Карта системы: TenderLex Telegram Bot

Дата: 2026-09-10
Коммит: `78a559d`
Мишень: `@tenderlex_bot` (`backend/app/bot.py`)

> Начальная карта и дополнение 22 октября — исторические снимки. Текущее состояние описано в дополнении 23 октября и [отчёте выпуска](../API_RULE14_GEO_RELEASE_2026-10-23.md). Локальные журналы `.agent/tasks/` не публикуются в Git.

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


## Дополнение 2026-10-22: API, география и товарные позиции

Историческая карта выше сохранена. Текущий checkout: `/root/projects/tenderlex`, БД runtime — `data/aipoisk.db`. Проверена только область нового отчёта `2026-10-22-api-rule14-geo.md`.

- Клиент: Next.js `/cabinet` → `/api/customer/jobs` → исходный snapshot/подтверждение → worker `jobs.py` → supplier/exact/PM pipeline → Word/Excel → reserve/settle/release. Точка чтения — карточка, modal выбора, скачанный отчёт; содержимое платного нового отчёта не проверялось.
- Внешняя интеграция: API-ключ → `/api/v1/mcp/{balance,suppliers/search,products/exact-analogs,procurements/analyze}` → синхронный pipeline → JSON/Word-ссылка. MCP Python-скрипт — stdio JSON-RPC клиент этих маршрутов.
- Админ: React/Vite `McpApiView` → защищённые admin api-key routes; страница автоматически читает `/master`, который при отсутствии ключа может его создать. В браузерном стенде все API подменялись.
- География: cabinet city+radius → Job → supplier city queries, location annotation/ranking; PM использует city queries, числовой радиус только в отчёте. Цена дополнительно зависит от radius. Производные задания могут потерять поля.
- Товарные данные: `product_inventory` → `position_selection` → exact selected rows / PM source_positions; legacy/API exact без selection имеет иной путь. Source parsing и сохранность строк отличаются от семантического решения о модели/упаковке.
- Наблюдения и доказательства: `.agent/tasks/api-rule14-geo-audit-2026-10-22/raw/`; владельцы сценариев: root — UX/docs/интеграция, audit_api_readiness — API, audit_geo_all_modes — география, exact_selection_cabinet — правило 14.


## Дополнение 2026-10-23: опубликованные исправления

Исторические наблюдения 22 октября выше сохранены. Текущее состояние:

- Добавлена очередь `/api/v1/mcp/jobs` для пяти режимов, файлов, выбора строк/стратегии и защищённого результата. Прямые текстовые методы сохранены. MCP stdio объявляет девять инструментов.
- `GET master` возвращает только метаданные; создание/ротация только явным POST. Старые хэши действуют, открытые секреты удалены из runtime БД.
- Общая валидация города/радиуса выполняется до резерва. PM аннотирует каждую цену, supplier продолжения сохраняют пару. Интерфейс обозначает приоритет с добором и неизвестными адресами.
- Прямые API-задачи исключены из повторного рыночного запуска worker; отмена/поздняя выдача защищены общим атомарным переходом.
- Проверки и пределы: [отчёт выпуска](../API_RULE14_GEO_RELEASE_2026-10-23.md), `.agent/tasks/api-rule14-geo-fix-2026-10-22/`.
