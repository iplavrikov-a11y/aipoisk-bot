# Evidence

## 2026-06-03

- Backend tests: `cd backend && PYTHONPATH=. pytest -q`
  - Result: `129 passed, 2 warnings, 35 subtests passed`.
- Frontend build: `cd frontend && npm run build`
  - Result: Vite build completed successfully, generated `dist/assets/index-BArkB0qI.js` and `dist/assets/index-UyMd111n.css`.
- Whitespace check: `git diff --check`
  - Result: no output, exit code 0.
- Local queue stress: 100 pending supplier jobs claimed through `claim_next_job`.
  - Result: `created=100`, `claimed=100`, `duplicates=0`, `pending=0`, `running=100`, `extra=None`.
- Playwright visual audit: `TARGET_URL=http://localhost:5173 node run.js /tmp/aipoisk-visual-audit.js`
  - Result: desktop sections and mobile clients/settings had no horizontal overflow.
  - Client cards default collapsed: `clientFullCardsVisible=0`.
  - Old model aliases absent: `oldModelAliases=false`.
  - Tavily not displayed before Yandex: `tavilyBeforeYandex=false`.
- Playwright interaction check: `TARGET_URL=http://localhost:5173 node run.js /tmp/aipoisk-interaction-check.js`
  - Result: client card expands with no overflow; source settings open with Yandex before Google and Google before Tavily; Yandex and Google key fields are present.
- AI models focused check: `cd /root/shared_skills/playwright-skill && node run.js /tmp/aipoisk-ai-models-check.js`
  - Result: `forbiddenMatches=[]`; function model dropdowns display exact `modelId` text only; provider rows include `openrouter:OpenRouter`, `open-ai:OpenAI`, `gemini:Gemini`, `polza:Polza`; OpenRouter Base URL is set, Polza Base URL is set; model provider dropdowns display `provider id`; desktop and mobile have no horizontal overflow.
- UI text scan after rebuild: `rg -n "По умолчанию|по умолчанию|простых операций|Подключение|подключение|Основной ИИ|Новая модель|Настроенная модель|Быстрая модель|Сильная модель|Модели по умолчанию|Основная модель по умолчанию|Модель для простых операций" frontend/src frontend/dist`
  - Result: no matches.
- Live settings provider normalization:
  - Backups created before DB updates: `data/aipoisk.db.backup-before-ai-provider-urls-20260603T210402Z`, `data/aipoisk.db.backup-before-polza-url-fix-20260603T210910Z`.
  - Result: `openrouter` Base URL `https://openrouter.ai/api/v1`, `polza` Base URL `https://api.polza.ai/v1`, existing `open-ai` and `gemini` API keys preserved, no invented OpenRouter/Polza API keys inserted.
- Safe load simulation: `PYTHONPATH=backend python3 .agent/tasks/2026-06-03-admin-ui-10/raw/stress_100_clients_1000_jobs.py`
  - Scenario: 100 clients, 10 jobs per client, mixed modes (`supplier_search`, `procurement_report`, `analysis_and_suppliers`), 40 concurrent claim workers, isolated temporary SQLite DB.
  - Result: `created_jobs=1000`, `access_errors=0`, `mode_counts={'supplier_search': 400, 'procurement_report': 300, 'analysis_and_suppliers': 300}`, `usage_ok=True`, `per_client_ok=True`, `claimed_jobs=1000`, `duplicate_claims=0`, `statuses={'running': 1000}`, `create_seconds=6.391`, `claim_seconds=6.778`.
- Runtime process check:
  - Result: current server has `aipoisk-api`, `aipoisk-bot`, and one `aipoisk-worker` process. Queue can hold the load, but live processing throughput is limited by the single worker process plus external API rate limits.

## Screenshots

- `/tmp/aipoisk-visual-audit/сводка.png`
- `/tmp/aipoisk-visual-audit/клиенты.png`
- `/tmp/aipoisk-visual-audit/clients-expanded.png`
- `/tmp/aipoisk-visual-audit/настройки.png`
- `/tmp/aipoisk-visual-audit/settings-sources-open.png`
- `/tmp/aipoisk-visual-audit/ии-модели.png`
- `/tmp/aipoisk-visual-audit/mobile-clients.png`
- `/tmp/aipoisk-visual-audit/mobile-settings.png`
- `/tmp/aipoisk-ai-models-check/desktop-ai-models.png`
- `/tmp/aipoisk-ai-models-check/mobile-ai-models.png`
