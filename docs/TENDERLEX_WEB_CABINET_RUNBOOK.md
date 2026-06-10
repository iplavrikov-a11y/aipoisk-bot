# TenderLex Web Cabinet Runbook

## Current Mode

- Public site: `https://tenderlex.ru`
- Customer cabinet: `https://tenderlex.ru/cabinet`
- Online payment is not enabled yet.
- Web users and Telegram users are separate. Web clients are identified in admin data as `web:<id>`.
- Web access is topped up manually from the admin panel.
- Linked Telegram and website accounts share the same customer job history.
  A Telegram-launched job can therefore appear in the website cabinet; this is
  not a duplicate job.
- The cabinet mirrors the Telegram bot scenarios:
  - `Одно ТЗ`
  - `Несколько ТЗ`
  - `Анализ закупки`
  - `Анализ + поиск`

## Customer UX Contract

- The landing page must keep both entry points visible: work on the site and work in Telegram.
- Customer-facing copy should describe the result and the task, not internal implementation details.
- Do not show customer-facing labels such as `DOCX`, `XLSX`, `web balance`, `protected session`, internal supplier target counts, raw task IDs, or exact free-run counters as marketing copy.
- Use professional procurement examples close to real work. Prefer varied construction-material examples instead of repeating one product everywhere.
- `Одно ТЗ` accepts one file or one text description and creates one supplier-search job.
- `Несколько ТЗ` accepts several files. Each file is processed as a separate supplier-search job.
- `Анализ закупки` accepts a notice number, source link, uploaded procurement materials, or archive. It must not ask the customer for a separate "what to check" field.
- `Анализ + поиск` accepts the same procurement inputs and creates the combined analysis plus supplier-search flow. It must not ask the customer for a separate "what to check" field.
- The supplier count is owner-controlled in admin/settings; customers should not choose it in the cabinet.
- Customer task history is paginated at 15 tasks per page.
- Customer-visible timestamps are shown in Moscow time. Backend storage remains UTC.
- If a supplier search underfills the target, the Telegram bot must show one
  customer-facing confirmation message only: the found count, the fact that the
  file is incomplete, and the buttons to send-and-charge or decline. It must
  not send internal task IDs, filesystem paths, evidence paths, provider details,
  or separate owner diagnostic alerts into the customer chat.
- Finished supplier-search jobs can offer `Найти ещё`; the customer must confirm
  that one supplier-search generation will be spent before an additional search
  starts.

## Manual Top-Up

1. Open the admin panel.
2. Go to `Клиенты`.
3. Find the client by website email.
4. Open the client card.
5. In `Баланс`, choose:
   - `Поставщики` for supplier search runs.
   - `Анализ документации` for procurement analysis runs.
6. Enter the number of runs or choose a tariff template.
7. Add a short note, for example `Оплата по счету от YYYY-MM-DD`.
8. Click `Начислить`.
9. Ask the customer to refresh the cabinet.

Notes:

- Use the customer's website email to find web-cabinet clients.
- Do not merge website users into Telegram customers unless the owner explicitly decides to change the billing/account model.
- Until YooKassa is enabled, payment confirmation happens outside the site and the owner grants runs manually.

## Password Recovery

Customer path:

1. Customer opens `/cabinet`.
2. Clicks `Не помню пароль`.
3. Enters the cabinet email.
4. The request appears in the admin panel.

Admin path:

1. Open `Клиенты`.
2. Check the `Восстановление доступа` block.
3. Click `Сбросить пароль`.
4. Copy the temporary password shown in the admin panel.
5. Send the temporary password to the customer through the verified support channel.
6. Ask the customer to sign in and change access later when self-service password change is added.

Security notes:

- The public reset request does not say whether an email exists.
- Old website sessions are revoked after admin password reset.
- Temporary password is shown only in the admin response and should not be stored in notes.

## Product Scenario Check

Use this checklist after deploy:

1. Open `https://tenderlex.ru/`.
2. Confirm the landing page still has both actions: website cabinet and Telegram bot.
3. Open `https://tenderlex.ru/cabinet`.
4. Register a test web account only when production data writes are acceptable.
5. In admin, find the new web client by email.
6. Manually grant one supplier search run and one procurement analysis run.
7. Sign in as the web user.
8. Confirm the cabinet shows four function cards: `Одно ТЗ`, `Несколько ТЗ`, `Анализ закупки`, and `Анализ + поиск`.
9. Confirm `Одно ТЗ` allows one dragged file or a text description.
10. Confirm `Несколько ТЗ` allows several dragged files and does not show supplier-count controls.
11. Confirm `Анализ закупки` shows only procurement input: notice number/link and optional uploaded materials.
12. Confirm `Анализ + поиск` shows only procurement input: notice number/link and optional uploaded materials.
13. Confirm no `Что особенно проверить` or `Что важно учесть` field is visible.
14. Start a supplier search from text or a test file.
15. Start a procurement analysis from a notice number, link, or document.
16. Confirm tasks appear in `Задачи`, pagination shows 15 tasks per page, progress updates, and finished results can be downloaded.
17. For a procurement where the published documents indicate an active
    prohibition, confirm the analysis says the Minpromtorg registry extract is
    required and `evidence.json` has `supplier_search.minprom_registry.required`
    set to `true`. If the registry search returns no entries, the supplier
    result must say to request registry confirmation instead of claiming that a
    supplier already satisfies the registry requirement.
18. For a partial supplier-search result in Telegram, confirm there is only one
    confirmation message with send/decline buttons and no internal paths or job
    IDs.

## Legal Pages

Current public templates:

- `/terms`
- `/privacy`
- `/personal-data`

Before paid public launch, review these texts with legal counsel and add official seller details if needed.

## YooKassa Preparation

The admin panel already has fields for:

- payment mode
- YooKassa shop id
- YooKassa return URL
- YooKassa secret key

Do not switch payment mode to `YooKassa` until checkout creation, webhook processing, idempotency, and payment history are implemented and tested.

## Deploy Check

From repo root:

```bash
./scripts/deploy_tenderlex_live.sh
```

This script is the release gate for cabinet/site/backend changes: it runs backend
tests, builds the admin panel and public site, backs up SQLite, restarts the
FastAPI API, worker, bot, and public site services when safe, then checks the
live API, site routes, and Yandex Metrika placement. Do not report a
cabinet/site change as live until this script, or the same evidence-equivalent
sequence, has passed.

Safety behavior:

- before service restarts, the script checks SQLite for `pending` jobs and fresh
  `running` jobs;
- if active jobs exist, the script skips `aipoisk-api.service`,
  `aipoisk-worker.service`, and `aipoisk-bot.service` restarts because worker and
  bot are `PartOf=aipoisk-api.service`;
- `tenderlex-site.service` can still restart during active backend jobs;
- use `AIPOISK_FORCE_JOB_SERVICE_RESTART=1` only when deliberately interrupting
  active jobs.
