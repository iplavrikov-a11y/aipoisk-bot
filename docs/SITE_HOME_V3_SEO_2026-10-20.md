# TenderLex — Home v3 и SEO-релиз (20.10.2026)

Дата: 20.10.2026. Production: https://tenderlex.ru

## 1. Новая главная внедрена

- Главная теперь отдаёт Home v3: интерактивный разбор ТЗ из 5 шагов, артефакты, типичные ошибки и мини-проверка.
- Используются существующие SiteHeader, SiteFooter, Метрика, чат и правовые ссылки.
- Исходники: site/src/app/page.tsx, site/src/app/home-v3-content.ts, site/src/app/home-v3.css, site/src/components/home-v3-interactions.tsx.
- Предыдущий page.tsx сохранён на VPS: site/src/app/page.tsx.bak-home-v3-20261019.
- Предыдущий .next сохранён deploy-скриптом: /root/projects/tenderlex/data/backups/tenderlex-site/.

## 2. SEO-базлайн (Google Search Console, 19.09–16.10)

- 995 показов, 20 кликов, CTR 2.01%, средняя позиция 20.96.
- 82 страницы с показами; 120 запросов в выборке.
- Главная: 7 кликов / 39 показов / средняя позиция 3.7.
- Лучшие точки входа — статьи базы знаний; коммерческие лендинги пока получают мало показов.
- Sitemap: без ошибок, последняя загрузка 17.10.
- Яндекс Вебмастер: кэш SQI 10, 57 страниц в поиске, 3 исключено; API недоступен с 30.08.
- Wordstat API не работает; данные в кэше — оценки, не фактические.
- Метрика: 7 визитов / 6 пользователей за 28 дней; основная цель — регистрация, 0 достижений.

## 3. Что изменено

| Область | Изменение |
|---|---|
| Главная | Home v3 с интерактивным разбором, новый title/description, FAQ/Service/WebSite JSON-LD |
| Sitemap | lastmod статей из updatedDate; обновлены даты изменённых лендингов и главной |
| Статьи | datePublished добавлен во все TechArticle (fallback на updatedDate, где нет даты публикации) |
| /v2 | noindex, nofollow + canonical на /; добавлен в robots.txt |
| Robots | Закрыты /v2, /test-buttons, /demo-*; sitemap указан |
| 404 | noindex + canonical на / вместо несуществующего URL |
| OG | Новый tenderlex-og-1200x630.png (1200×630) |
| Organization | Добавлены email и телефон из настроек сайта |
| Метрика | Fallback на YANDEX_METRIKA_COUNTER_ID; счётчик загружается после согласия |
| HTTP/2 | Включён на 4443 для tenderlex.ru и admin.tenderlex.ru |
| llms.txt | 91/91 URL sitemap; добавлены регионы, отрасли, сервисы |
| Лендинги | Расширены /zapros-kp-po-tz, /ocenka-riskov-zakupki, /poisk-postavshchikov-dlya-tendera, /poisk-proizvoditeley-po-tz, /postavshchiki-dlya-zaprosa-kp |
| Статьи → сервисы | В сайдбар всех статей добавлены ссылки на 4 коммерческих лендинга |
| Title | Сокращены длинные title: /api-integracii, /regiony/ekaterinburg, /reestr-minpromtorga-v-zakupkah, 4 лендинга |

## 4. Статус интеграций

- **Google Search Console — работает.** Service account, read-only, property sc-domain:tenderlex.ru. Данные используются для приоритизации.
- **Яндекс Вебмастер — заблокирован сетью.** Токен валиден, но api.webmaster.yandex.net недоступен с VPS (IPv4 timeout, IPv6 нет). Нужен IPv6/другой egress.
- **Wordstat — API недоступен.** Хост возвращает 404/чужой сертификат; автоматизация невозможна, только ручной экспорт.
- **Метрика — работает.** Счётчик выводится после согласия; проверено: mc.yandex.ru + window.ym.
- **IndexNow** — ключ и файл настроены; можно уведомлять Яндекс/Bing об изменениях.

## 5. Проверки

- Deploy pipeline: build + typecheck + isolated promotion + live routes + analytics consent gate + live deploy verified.
- Home v3: 32/32 проверки на production (scripts/test_public_refinement_browser.py).
- Public gate: 91 страница × 2 ширины = 182 проверки, 0 падений (staging и production).
- Navigation: sticky header, mobile menu, Escape, переход в кабинет — passed (production).
- IndexNow: 12 изменённых URL отправлены, HTTP 200.
- HTTP/2: подтверждён `curl --http2` → 2.
- llms.txt: 91/91 URL sitemap, пропусков нет.
- SEO: canonical/robots/OG/JSON-LD/404/v2/sitemap/llms/HTTP2 проверены на production.
- Метрика: после «Разрешить аналитику» загружается SDK, window.ym — function.
- Внешних мутаций при работе демо нет; ошибок JS нет.

## 6. Остаточные риски

- Яндекс Вебмастер не обновляется с 30.08; SQI 10 и 57 страниц — устаревший кэш. Это инфраструктурный блокер, не ошибка сайта.
- Wordstat API мёртв; спрос оценивать нечем, кроме ручного экспорта.
- GSC read-only: нельзя автоматически отправить sitemap/URL; recrawl Яндекса тоже недоступен.
- datePublished для статей без реальной даты публикации выставлен по updatedDate — лучше заменить на фактические даты.
- Кластер near-duplicate статей по нацрежиму (5 статей, Jaccard 0.44–0.50) не переписывался.
- Лендинги доведены до 776–977 слов (postavshchiki — 823); цель 900–1400 выполнена частично.
- Эффект SEO-правок оценивать через 4–8 недель; трафик пока низкий, выборка GSC покрывает ~27% показов.

## 7. Следующие шаги

1. Разблокировать Вебмастер: IPv6 на VPS или внешний egress; затем включить свежий сбор запросов/SQI.
2. Отправить изменённые URL через IndexNow; sitemap уже обновлён.
3. Через 2–4 недели снять GSC-отчёт по страницам и CTR; при необходимости усилить title/контент.
4. Добавить реальные publishedDate статьям.
5. Развести кластер нацрежима и добавить тематические блоки «ещё по теме».
6. По возможности расширить лендинги до 1000–1200 слов уникальными сценариями.
