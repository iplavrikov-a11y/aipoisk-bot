# Universal Blueprint: Yandex SEO & Metrika Autonomous Pipeline

> **Инструкция для ИИ-агента**: Этот документ описывает готовую эталонную архитектуру автономного SEO-модуля для любого веб-проекта. Примени эти принципы, формулы и код с адаптацией под технологический стек целевого репозитория (Django, FastAPI, Next.js, Express, PHP, Laravel, Ruby on Rails и др.).

---

## 🎯 Цель модуля

Создать полностью автономную систему мониторинга, ускоренной индексации, отслеживания конверсий и поиска точек роста в Яндексе без необходимости вручную открывать кабинеты Вебмастера и Метрики.

### Основные компоненты:
1. **Фоновый сборщик**: 1 раз в сутки (в 08:00 МСК) забирает срез данных через REST API и кэширует локально в JSON/БД (чтобы интерфейсы открывались мгновенно с нулевой задержкой).
2. **Модуль быстрой индексации**: Парсит `sitemap.xml` и отправляет все URL в приоритетную очередь переобхода Яндекса (`POST /recrawl/queue`) + `IndexNow`.
3. **Детектор «Точек быстрого роста» (Striking Distance Queries)**: Находит запросы с позициями 4–10 и высоким числом показов (потенциал выхода в ТОП-3, где сосредоточено 80% поискового трафика).
4. **Сквозной трекинг конверсий и целей**: Автоматически опрашивает Management API и Data API Метрики по всем настроенным целям (переходы в бот, вход в кабинет, клики по кнопкам, формы) и вычисляет общую конверсию воронки сайта.
5. **Контур ИИ-оптимизации**: Защита от ложных правок (порог выборки ~300 визитов) + генерация понятных гипотез для человека с ручным согласованием в 1 клик.
6. **Telegram-дайджест**: Еженедельный автоматический отчет владельцу по понедельникам + кнопка отправки по требованию из админки.
7. **Панель управления (Admin View)**: Просторный, полноразмерный интерфейс с широкой таблицей запросов, сеткой 50/50 источников и целей, прогресс-барами и статусами.

---

## 🔑 1. Необходимые переменные окружения (.env)

```env
# Яндекс.Вебмастер (OAuth-токен приложения с правами webmaster:api)
YANDEX_WEBMASTER_TOKEN=y0__wg...
YANDEX_HOST_ID=https:example.com:443

# Яндекс.Метрика (OAuth-токен приложения с правами metrika:read)
YANDEX_METRIKA_TOKEN=y0__wg...
YANDEX_METRIKA_COUNTER_ID=12345678

# Telegram Уведомления (опционально)
BOT_TOKEN=123456789:ABC...
OWNER_TELEGRAM_ID=123456789
```

---

## 🛠 2. Архитектура и эндпоинты API Яндекса

### A. Яндекс.Вебмастер API (`https://api.webmaster.yandex.net/v4`)
* **Получение `user_id`**:
  `GET /user` → `{"user_id": 12345678}`
* **Сводка по хосту (ИКС, индексация)**:
  `GET /user/{user_id}/hosts/{host_id}/summary`
  * Поля: `sqi` (ИКС), `searchable_pages_count` (в поиске), `excluded_pages_count` (исключено).
* **Поисковые фразы, показы и средняя позиция**:
  `GET /user/{user_id}/hosts/{host_id}/search-queries/popular?order_by=TOTAL_SHOWS&query_indicator=TOTAL_SHOWS&query_indicator=TOTAL_CLICKS&query_indicator=AVG_SHOW_POSITION`
  * Для каждого запроса забираем: `query_text`, `TOTAL_SHOWS`, `TOTAL_CLICKS`, `AVG_SHOW_POSITION`.
* **Приоритетная переиндексация (Recrawl Queue)**:
  `POST /user/{user_id}/hosts/{host_id}/recrawl/queue`
  `{"url": "https://example.com/page"}` (до 80–100 URL в сутки).

### B. Яндекс.Метрика Management & Data API
* **Список целей счетчика (Management API)**:
  `GET https://api-metrika.yandex.net/management/v1/counter/{counter_id}/goals`
  * Возвращает список настроенных целей: `id`, `name`, `type`, `conditions`.
* **Достижения целей и конверсии в одном батч-запросе (Data API)**:
  `GET https://api-metrika.yandex.net/stat/v1/data?ids={counter_id}&date1=30daysAgo&date2=today&metrics=ym:s:goal{ID1}reaches,ym:s:goal{ID2}reaches,...`
* **Общие метрики трафика (за 30 дней)**:
  `GET https://api-metrika.yandex.net/stat/v1/data?ids={counter_id}&date1=30daysAgo&date2=today&metrics=ym:s:visits,ym:s:users,ym:s:pageviews,ym:s:bounceRate,ym:s:avgVisitDurationSeconds`
* **Источники трафика**:
  `GET https://api-metrika.yandex.net/stat/v1/data?ids={counter_id}&date1=30daysAgo&date2=today&metrics=ym:s:visits,ym:s:users&dimensions=ym:s:lastSignTrafficSource&sort=-ym:s:visits`
* **Топ входных страниц и отказы**:
  `GET https://api-metrika.yandex.net/stat/v1/data?ids={counter_id}&date1=30daysAgo&date2=today&metrics=ym:s:visits,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds&dimensions=ym:s:startURLPath&sort=-ym:s:visits&limit=10`

---

## 🧠 3. Алгоритм детектора «Точек быстрого роста» (Striking Distance)

```python
growth_points = []
for q in queries:
    text = q["text"]
    shows = q["shows"]
    clicks = q["clicks"]
    pos = q["avg_position"]
    
    # Критерий точки быстрого роста:
    # Запрос уже на 1-й странице (4.0 <= pos <= 15.0) и имеет спрос (shows >= 3)
    if 4.0 <= pos <= 15.0 and shows >= 3:
        growth_points.append({
            "text": text,
            "shows": shows,
            "clicks": clicks,
            "avg_position": pos,
            "potential": "Высокий (позиция 4–10)",
            "action": "Дожать в ТОП-3 (дает до 80% всех кликов)"
        })
```

---

## 🎯 4. Расчет сквозной конверсии сайта

```python
total_goal_reaches = sum(g["reaches"] for g in goals)
total_conversion_rate = round((total_goal_reaches / visits * 100), 2) if visits > 0 else 0.0
```

---

## 🤖 5. Защита от преждевременных правок (AI Alignment)

* Если `visits < 300` за 30 дней:
  * Статус: `⏳ Режим защиты: Идет накопление статистики`.
  * Режим: **Read-Only / No Auto Changes**. Никаких правок сайта нейросетью не производится.
* Если `visits >= 300`:
  * Нейросеть генерирует точечные гипотезы: `id`, `page_url`, `reason`, `proposal_text`.
  * Статус: `pending` (ждет подтверждения владельца в админке).
  * Сайт обновляется **только после явного клика [Согласовать]**.

---

## 📱 6. Telegram-дайджест

Формат сообщения:
```html
📊 <b>SEO-Дайджест [Имя Проекта]</b> (24.08.2026 09:00)

👥 <b>Посетители:</b> 120 чел. (340 визитов)
⏱ <b>Время на сайте:</b> 2 мин 45 сек
📉 <b>Отказы:</b> 24.1%
🎯 <b>Конверсии (Цели):</b> 28 достижений (конверсия 8.2%)
🔍 <b>Страниц в поиске Яндекса:</b> 48 (ИКС: 20)

🎯 <b>Ключевые конверсии:</b>
  • Личный кабинет: <b>14</b> достижений
  • Переход в Telegram: <b>10</b> достижений
  • Запуск калькулятора: <b>4</b> достижения

🔥 <b>Точки быстрого роста (Потенциал ТОП-3):</b>
  • <b>«купить кирпич оптом»</b> — 180 показов (поз. 6.4)
  • <b>«доставка стройматериалов»</b> — 95 показов (поз. 7.1)

🔎 <b>Топ поисковых фраз:</b>
  • кирпич москва — 210 показов (поз. 4.2)
  • стройматериалы каталог — 150 показов (поз. 8.0)
```

---

## ⏱ 7. Автоматизация в планировщике (Cron / Systemd Timers)

1. **Ежедневный сбор снимка в 08:00 МСК (05:00 UTC)**:
   ```bash
   0 5 * * * /path/to/python -c "from app.yandex_seo import fetch_fresh_snapshot; fetch_fresh_snapshot()" >> /path/to/seo_cron.log 2>&1
   ```
2. **Еженедельный дайджест в Telegram (Понедельник 09:00 МСК)**:
   ```bash
   0 6 * * 1 /path/to/python -c "import asyncio; from app.yandex_seo import send_seo_telegram_digest; asyncio.run(send_seo_telegram_digest())" >> /path/to/seo_digest_cron.log 2>&1
   ```

---

## 💻 8. Чеклист внедрения для нового проекта

- [ ] 1. Получить OAuth-токены Яндекс.Вебмастера и Яндекс.Метрики.
- [ ] 2. Добавить переменные в `.env`.
- [ ] 3. Скопировать/адаптировать бэкенд-сервис `yandex_seo` (методы сбора, кэширования, целей и переобхода).
- [ ] 4. Добавить API эндпоинты в роутер:
  - `GET /api/seo-analytics`
  - `POST /api/seo-analytics/send-digest`
- [ ] 5. Добавить вкладку «SEO и Трафик» в UI админ-панели (широкие таблицы + сетка 50/50).
- [ ] 6. Добавить 2 строчки в `crontab` для полной автономности.
- [ ] 7. Протестировать отправку в Telegram и отображение в админке.
