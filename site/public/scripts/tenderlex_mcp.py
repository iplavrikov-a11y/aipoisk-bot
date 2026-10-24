#!/usr/bin/env python3
"""
TenderLex MCP (Model Context Protocol) Server.
Standard JSON-RPC 2.0 stdio server compatible with:
- Claude Desktop
- Cursor / VS Code
- ChatGPT Desktop / Codex
- Zed / Windsurf / LibreChat
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

# Configure logging to stderr so stdout remains clean for JSON-RPC
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("tenderlex_mcp")

DEFAULT_API_URL = os.getenv("TENDERLEX_API_URL", "https://tenderlex.ru").rstrip("/")
API_KEY = os.getenv("TENDERLEX_API_KEY", "").strip()


TOOLS_DEFINITIONS = [
    {
        "name": "tenderlex_find_suppliers",
        "description": (
            "Поиск прямых производителей, официальных дистрибьюторов, заводов и оптовых поставщиков РФ "
            "по тексту технического задания или наименованию продукции. "
            "Возвращает проверенные контакты (email отделов продаж, прямые телефоны, сайты, ИНН, регионы) "
            "и готовый шаблон коммерческого запроса (КП)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "specification": {
                    "type": "string",
                    "description": "Текст технического задания, перечень параметров, наименование товаров или закупаемая номенклатура",
                },
                "target_count": {
                    "type": "integer",
                    "description": "Желаемое количество поставщиков для подбора (от 1 до 50, по умолчанию 5)",
                    "default": 5,
                },
                "city": {
                    "type": "string",
                    "description": "Город или регион поставки (опционально, например 'Москва' или 'Екатеринбург')",
                    "default": "",
                },
                "geo_radius_km": {
                    "type": "integer",
                    "description": "Радиус приоритета поставщиков от города доставки в км. Указывается вместе с city.",
                    "minimum": 10,
                    "maximum": 5000,
                },
                "include_quote_request": {
                    "type": "boolean",
                    "description": "Сформировать готовый текст официального запроса КП для рассылки поставщикам",
                    "default": True,
                },
                "search_policy": {
                    "type": "string",
                    "description": (
                        "Режим поиска поставщиков: "
                        "'normal' — обычный открытый поиск по рынку РФ (заводы, дилеры, дистрибьюторы); "
                        "'minprom_registry_priority' — приоритет Реестра Минпромторга РФ (ГИСП) с добором с рынка; "
                        "'minprom_registry_only' — СТРОГО только подтвержденные производители из Реестра Минпромторга (для нацрежима ПП 616 / 719)"
                    ),
                    "enum": ["normal", "minprom_registry_priority", "minprom_registry_only"],
                    "default": "normal",
                },
            },
            "required": ["specification"],
        },
    },
    {
        "name": "tenderlex_find_exact_and_analogs",
        "description": (
            "Глубокий анализ спецификации по 44-ФЗ и 223-ФЗ: выявление скрытой оригинальной модели производителя, "
            "построение таблицы конкретных показателей и характеристик под ТЗ (сверка параметров 'не менее', 'не более', ГОСТ) и подбор 2–4 проверенных эквивалентных аналогов "
            "со ссылкой на официальный DOCX отчет."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "specification": {
                    "type": "string",
                    "description": "Текст характеристик закупки, выдержка из ТЗ или параметры оборудования",
                },
                "procurement_title": {
                    "type": "string",
                    "description": "Наименование предмета закупки (опционально)",
                    "default": "",
                },
            },
            "required": ["specification"],
        },
    },
    {
        "name": "tenderlex_analyze_procurement",
        "description": (
            "Экспресс-аудит закупочной документации и проекта контракта: проверка скрытых штрафов, нереальных сроков, "
            "национального режима (ПП 616, ПП 617, ПП 878, 1875, реестр Минпромторга), обеспечения заявки и контракта, "
            "выявление стоп-факторов и ловушек заказчика."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_text": {
                    "type": "string",
                    "description": "Текст проекта контракта, извещения или закупочной документации",
                },
            },
            "required": ["document_text"],
        },
    },
    {
        "name": "tenderlex_check_balance",
        "description": "Проверка доступных квот, лимитов и статуса авторизации API-ключа TenderLex.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "tenderlex_start_queued_job",
        "description": "Запускает задачу TenderLex в очереди. Подходит для файлов, мониторинга цен, радиуса доставки и задач с последующим выбором позиций.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["supplier_search", "procurement_report", "analysis_and_suppliers", "exact_product", "price_monitoring"]},
                "text": {"type": "string", "description": "Текст ТЗ или документации", "default": ""},
                "source_urls": {"type": "string", "description": "Номера извещений или URL, по одному в строке", "default": ""},
                "city": {"type": "string", "default": ""},
                "geo_radius_km": {"type": "integer", "minimum": 10, "maximum": 5000},
                "supplier_search_policy": {"type": "string", "enum": ["normal", "minprom_registry_priority", "minprom_registry_only"], "default": "normal"},
                "multi_item_mode": {"type": "string", "enum": ["balanced", "per_item"], "default": "balanced"},
                "file_path": {"type": "string", "description": "Необязательный путь к файлу внутри TENDERLEX_MCP_UPLOAD_DIR. Путь передаётся только по явному указанию пользователя."},
                "idempotency_key": {"type": "string", "description": "Уникальный ключ повтора; повтор с ним не создаёт вторую задачу."},
            },
            "required": ["mode"],
        },
    },
    {
        "name": "tenderlex_get_queued_job",
        "description": "Показывает статус, прогресс, выбор позиций, предложение неполного результата и файлы одной очередной задачи.",
        "inputSchema": {"type": "object", "properties": {"job_id": {"type": "string"}}, "required": ["job_id"]},
    },
    {
        "name": "tenderlex_choose_job_positions",
        "description": "Подтверждает выбранные позиции после разбора ТЗ. Используйте revision и ID из position_selection задачи.",
        "inputSchema": {"type": "object", "properties": {"job_id": {"type": "string"}, "revision": {"type": "string"}, "selected_item_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["job_id", "revision", "selected_item_ids"]},
    },
    {
        "name": "tenderlex_cancel_queued_job",
        "description": "Отменяет собственную ещё не завершённую очередь TenderLex. Резерв средств возвращается по правилам соответствующего режима.",
        "inputSchema": {"type": "object", "properties": {"job_id": {"type": "string"}}, "required": ["job_id"]},
    },
    {
        "name": "tenderlex_update_queued_job",
        "description": "Подтверждает стратегию поиска поставщиков либо решение клиента принять/отклонить неполный результат. Применяйте только после явного выбора пользователя.",
        "inputSchema": {"type": "object", "properties": {
            "job_id": {"type": "string"},
            "action": {"type": "string", "enum": ["strategy", "accept", "decline"]},
            "multi_item_mode": {"type": "string", "enum": ["balanced", "per_item"]},
            "selected_item_ids": {"type": "array", "items": {"type": "string"}},
        }, "required": ["job_id", "action"]},
    },
]


for _tool in TOOLS_DEFINITIONS:
    if _tool["name"] in {"tenderlex_find_suppliers", "tenderlex_find_exact_and_analogs", "tenderlex_analyze_procurement"}:
        _tool["inputSchema"]["properties"]["idempotency_key"] = {
            "type": "string",
            "description": "Уникальный ID операции. При повторе после таймаута сохраняйте этот ID и тело запроса.",
        }


def _http_request(endpoint: str, method: str = "GET", payload: Optional[dict] = None, *, idempotency_key: str = "") -> dict:
    """Executes authenticated HTTP request to TenderLex API."""
    url = f"{DEFAULT_API_URL}{endpoint}"
    headers = {
        "User-Agent": "TenderLex-MCP/1.0",
        "Accept": "application/json",
    }
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
        headers["X-API-Key"] = API_KEY

    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    data_bytes = None
    if payload is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as err:
        error_body = ""
        try:
            error_body = err.read().decode("utf-8")
            parsed_err = json.loads(error_body)
            detail = parsed_err.get("detail", error_body)
        except Exception:
            detail = error_body or str(err)
        raise RuntimeError(f"TenderLex API Error ({err.code}): {detail}")
    except urllib.error.URLError as err:
        raise RuntimeError(f"Failed to connect to TenderLex API at {url}: {err.reason}")


def _http_multipart(endpoint: str, fields: dict[str, Any], *, file_path: str = "", idempotency_key: str = "") -> dict:
    """Submit an explicitly user-selected file without exposing arbitrary paths."""
    boundary = f"----TenderLexMcp{os.urandom(12).hex()}"
    chunks: list[bytes] = []
    for key, value in fields.items():
        if value is None or value == "":
            continue
        chunks.extend((
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
            str(value).encode("utf-8"),
            b"\r\n",
        ))
    if file_path:
        root_raw = os.getenv("TENDERLEX_MCP_UPLOAD_DIR", "").strip()
        if not root_raw:
            raise RuntimeError("Для file_path задайте TENDERLEX_MCP_UPLOAD_DIR; это защищает от чтения произвольных файлов.")
        root = Path(root_raw).expanduser().resolve()
        path = Path(file_path).expanduser().resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise RuntimeError("file_path должен находиться внутри TENDERLEX_MCP_UPLOAD_DIR.") from exc
        if not path.is_file() or path.stat().st_size > 50 * 1024 * 1024:
            raise RuntimeError("Файл не найден, не является обычным файлом или превышает 50 МБ.")
        chunks.extend((
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="files"; filename="{path.name}"\r\n'.encode(),
            b"Content-Type: application/octet-stream\r\n\r\n",
            path.read_bytes(),
            b"\r\n",
        ))
    chunks.append(f"--{boundary}--\r\n".encode())
    headers = {"User-Agent": "TenderLex-MCP/1.0", "Accept": "application/json", "Content-Type": f"multipart/form-data; boundary={boundary}"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    req = urllib.request.Request(f"{DEFAULT_API_URL}{endpoint}", data=b"".join(chunks), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(body).get("detail", body)
        except Exception:
            pass
        raise RuntimeError(f"TenderLex API Error ({err.code}): {body}") from err


def handle_tool_call(name: str, arguments: dict) -> list[dict]:
    """Dispatches tool call to appropriate TenderLex endpoint."""
    if not API_KEY:
        return [
            {
                "type": "text",
                "text": (
                    "⚠️ Ошибка: Переменная окружения TENDERLEX_API_KEY не задана.\n"
                    "Пожалуйста, укажите ваш API-ключ TenderLex в конфигурации MCP сервера."
                ),
                "_tenderlex_error": True,
            }
        ]

    try:
        if name == "tenderlex_find_suppliers":
            res = _http_request(
                "/api/v1/mcp/suppliers/search",
                method="POST",
                idempotency_key=str(arguments.get("idempotency_key") or ""),
                payload={
                    "specification": str(arguments.get("specification") or ""),
                    "target_count": int(arguments.get("target_count") or 5),
                    "city": str(arguments.get("city") or ""),
                    "geo_radius_km": arguments.get("geo_radius_km"),
                    "include_quote_request": bool(arguments.get("include_quote_request", True)),
                    "search_policy": str(arguments.get("search_policy") or "normal"),
                },
            )
            suppliers = res.get("suppliers", [])
            lines = [
                f"🎯 **Найдено поставщиков**: {res.get('total_found', len(suppliers))} (запрошено: {res.get('target_requested')})",
                f"🏷️ **Предмет**: {res.get('source_title', 'По спецификации')}",
                "",
                "### Список проверенных компаний и прямых контактов:",
            ]
            for idx, s in enumerate(suppliers, 1):
                company = s.get("company_name", "Компания")
                inn = f" (ИНН: {s.get('inn')})" if s.get("inn") else ""
                region = f" · {s.get('region')}" if s.get("region") else ""
                status_str = f" · [{s.get('status', 'поставщик')}]" if s.get("status") else ""
                site = s.get("site", "")
                email = s.get("email", "не указан")
                phone = s.get("phone", "не указан")
                product = s.get("product", "")
                comments = s.get("comments", "")

                lines.append(f"**{idx}. {company}{inn}{region}{status_str}**")
                if site:
                    lines.append(f"- 🌐 Сайт: {site}")
                lines.append(f"- ✉️ Email отдела продаж: {email}")
                lines.append(f"- 📞 Телефон: {phone}")
                if product:
                    lines.append(f"- 📦 Продукция / совпадение: {product}")
                if comments:
                    lines.append(f"- 💬 Аудит: {comments}")
                lines.append("")

            if res.get("quote_request_markdown"):
                lines.append("---")
                lines.append("### 📝 Шаблон запроса коммерческого предложения (КП):")
                lines.append(res["quote_request_markdown"])

            remaining = res.get("quota_remaining", -1)
            rem_str = "безлимитно" if remaining == -1 else f"{remaining} запросов"
            lines.append(f"\n_Остаток квоты поиска поставщиков: {rem_str}_")
            return [{"type": "text", "text": "\n".join(lines)}]

        elif name == "tenderlex_find_exact_and_analogs":
            res = _http_request(
                "/api/v1/mcp/products/exact-analogs",
                method="POST",
                idempotency_key=str(arguments.get("idempotency_key") or ""),
                payload={
                    "specification": str(arguments.get("specification") or ""),
                    "procurement_title": str(arguments.get("procurement_title") or ""),
                },
            )
            positions = res.get("positions", [])
            lines = [
                "🔬 **Отчёт о подборе товара и аналогов**",
                f"**Резюме**: {res.get('summary', '')}",
                "",
            ]
            for pos in positions:
                p_no = pos.get("position_no", 1)
                name_tz = pos.get("name_in_tz", "")
                brand = pos.get("identified_brand", "")
                model = pos.get("identified_model", "")
                mfr = pos.get("manufacturer", "")
                conf = int(float(pos.get("confidence", 0.9)) * 100)
                reasoning = pos.get("reasoning", "")

                lines.append(f"### Позиция #{p_no}: {name_tz}")
                lines.append(f"- **Выявленная модель**: `{brand} {model}`")
                if mfr:
                    lines.append(f"- **Производитель / Завод**: {mfr}")
                lines.append(f"- **Соответствие ТЗ**: {conf}%")
                if reasoning:
                    lines.append(f"- **Обоснование**: {reasoning}")

                specs = pos.get("specs_breakdown", [])
                if specs:
                    lines.append("\n**Сверка ключевых параметров под ТЗ:**")
                    for sp in specs[:6]:
                        st_icon = "✅" if sp.get("status") == "match" else "⚠️"
                        lines.append(f"- {st_icon} `{sp.get('param_name')}`: ТЗ: *{sp.get('tz_requirement')}* → Факт: *{sp.get('product_fact')}*")

                alts = pos.get("alternatives", [])
                if alts:
                    lines.append("\n**Рекомендованные эквивалентные аналоги:**")
                    for a_idx, alt in enumerate(alts, 1):
                        a_brand = alt.get("brand", "")
                        a_model = alt.get("model", "")
                        a_mfr = alt.get("manufacturer", "")
                        a_conf = int(float(alt.get("confidence", 0.85)) * 100)
                        lines.append(f"  {a_idx}. **{a_brand} {a_model}** ({a_mfr}) — соответствие {a_conf}%")

                lines.append("")

            docx_url = res.get("docx_download_url")
            if docx_url:
                lines.append(f"📄 **Скачать полный официальный отчет в Word (.docx)**: {docx_url}")

            remaining = res.get("quota_remaining", -1)
            rem_str = "безлимитно" if remaining == -1 else f"{remaining} запросов"
            lines.append(f"\n_Остаток квоты подбора аналогов: {rem_str}_")
            return [{"type": "text", "text": "\n".join(lines)}]

        elif name == "tenderlex_analyze_procurement":
            res = _http_request(
                "/api/v1/mcp/procurements/analyze",
                method="POST",
                idempotency_key=str(arguments.get("idempotency_key") or ""),
                payload={
                    "document_text": str(arguments.get("document_text") or ""),
                },
            )
            report = res.get("report_markdown", "Отчет не сформирован")
            ai_model = res.get("ai_model", "")
            remaining = res.get("quota_remaining", -1)
            rem_str = "безлимитно" if remaining == -1 else f"{remaining} запросов"

            output_text = f"{report}\n\n---\n_ИИ-модель: {ai_model} | Остаток квоты анализа: {rem_str}_"
            return [{"type": "text", "text": output_text}]

        elif name == "tenderlex_check_balance":
            res = _http_request("/api/v1/mcp/balance", method="GET")
            is_adm = res.get("is_admin", False)
            status_badge = "👑 Master Admin" if is_adm else "🔑 Клиентский ключ"
            lines = [
                f"### Статус API-ключа: {res.get('key_name')} ({status_badge})",
                f"- **Префикс ключа**: `{res.get('key_prefix')}`",
                f"- **Лимит запросов в минуту**: {res.get('rate_limit_per_minute')} req/min",
                "",
                "**Доступные модули и остатки:**",
            ]
            for svc_key, label in [
                ("supplier_search", "Поиск поставщиков"),
                ("exact_product", "Подбор товара и аналогов"),
                ("procurement_report", "Анализ документации"),
                ("price_monitoring", "Мониторинг цен"),
            ]:
                data = res.get(svc_key, {})
                allowed = data.get("allowed", False)
                rem = data.get("remaining", 0)
                spent = data.get("spent", 0)
                if not allowed:
                    lines.append(f"- ❌ {label}: *Отключено*")
                else:
                    lines.append(f"- ✅ {label}: Остаток: **{rem}** (Использовано: {spent})")

            return [{"type": "text", "text": "\n".join(lines)}]

        elif name == "tenderlex_start_queued_job":
            res = _http_multipart(
                "/api/v1/mcp/jobs",
                {
                    "mode": str(arguments.get("mode") or ""),
                    "text": str(arguments.get("text") or ""),
                    "source_urls": str(arguments.get("source_urls") or ""),
                    "delivery_city": str(arguments.get("city") or ""),
                    "geo_radius_km": arguments.get("geo_radius_km"),
                    "supplier_search_policy": str(arguments.get("supplier_search_policy") or "normal"),
                    "multi_item_mode": str(arguments.get("multi_item_mode") or "balanced"),
                },
                file_path=str(arguments.get("file_path") or ""),
                idempotency_key=str(arguments.get("idempotency_key") or ""),
            )
            job = res.get("job") or {}
            return [{"type": "text", "text": f"Задача принята: `{job.get('id')}`. Статус: {job.get('status', 'pending')}. Используйте tenderlex_get_queued_job для прогресса и последующих действий."}]

        elif name == "tenderlex_get_queued_job":
            job_id = str(arguments.get("job_id") or "")
            res = _http_request(f"/api/v1/mcp/jobs/{job_id}", method="GET")
            job = res.get("job") or {}
            selection = job.get("position_selection") or {}
            lines = [
                f"### Задача {job.get('job_number') or job.get('id')}",
                f"- Статус: **{job.get('status_label') or job.get('status')}**",
                f"- Прогресс: {job.get('progress', 0)}%",
                f"- Сообщение: {job.get('message', '')}",
            ]
            if selection and not selection.get("confirmed"):
                lines.append(f"- Ожидается выбор позиций: revision `{selection.get('revision')}`, доступно {len(selection.get('items') or [])}.")
                lines.append(json.dumps(selection, ensure_ascii=False))
            if job.get("multi_item_details"):
                lines.append(json.dumps(job["multi_item_details"], ensure_ascii=False))
            if job.get("awaiting_customer_confirmation"):
                lines.append("- Ожидается решение по неполному результату: используйте API POST /accept или /decline.")
            for item in job.get("result_files") or []:
                lines.append(f"- Файл: {item.get('label') or item.get('kind')} (`{item.get('kind')}`), скачивание: GET /api/v1/mcp/jobs/{job_id}/files/{item.get('kind')}")
            return [{"type": "text", "text": "\n".join(lines)}]

        elif name == "tenderlex_choose_job_positions":
            job_id = str(arguments.get("job_id") or "")
            res = _http_request(
                f"/api/v1/mcp/jobs/{job_id}/position-selection",
                method="POST",
                payload={"revision": str(arguments.get("revision") or ""), "selected_item_ids": list(arguments.get("selected_item_ids") or [])},
            )
            return [{"type": "text", "text": f"Выбор сохранён. Новый статус: {res.get('job', {}).get('status', '')}."}]

        elif name == "tenderlex_update_queued_job":
            job_id = str(arguments.get("job_id") or "")
            action = str(arguments.get("action") or "")
            if action not in {"strategy", "accept", "decline"}:
                raise ValueError("Неизвестное действие задачи")
            payload = {}
            endpoint = action
            if action == "strategy":
                endpoint = "choose-strategy"
                mode = str(arguments.get("multi_item_mode") or "")
                if mode not in {"balanced", "per_item"}:
                    raise ValueError("Укажите balanced или per_item")
                payload = {"multi_item_mode": mode}
                if "selected_item_ids" in arguments:
                    payload["selected_item_ids"] = list(arguments["selected_item_ids"])
            res = _http_request(f"/api/v1/mcp/jobs/{job_id}/{endpoint}", method="POST", payload=payload)
            return [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]

        elif name == "tenderlex_cancel_queued_job":
            job_id = str(arguments.get("job_id") or "")
            res = _http_request(f"/api/v1/mcp/jobs/{job_id}/cancel", method="POST", payload={})
            return [{"type": "text", "text": f"Задача отменена. Статус: {res.get('job', {}).get('status', '')}."}]

        else:
            return [{"type": "text", "text": f"Неизвестный инструмент: '{name}'", "_tenderlex_error": True}]

    except Exception as exc:
        logger.error("tool_execution_failed: %s", exc, exc_info=True)
        return [{"type": "text", "text": f"❌ Ошибка выполнения инструмента TenderLex: {str(exc)}", "_tenderlex_error": True}]


def run_stdio_server():
    """Main JSON-RPC stdio event loop."""
    logger.info("TenderLex MCP Server running on stdio (API URL: %s)", DEFAULT_API_URL)

    for line in sys.stdin:
        line_clean = line.strip()
        if not line_clean:
            continue

        try:
            req = json.loads(line_clean)
        except Exception as exc:
            logger.error("json_parse_error: %s", exc)
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        response: Optional[dict] = None

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "tenderlex-mcp",
                        "version": "1.0.0",
                    },
                    "capabilities": {
                        "tools": {},
                    },
                },
            }

        elif method == "notifications/initialized":
            # Client notification, no response required
            continue

        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": TOOLS_DEFINITIONS,
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            content = handle_tool_call(tool_name, tool_args)
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": content,
                    "isError": any(bool(item.pop("_tenderlex_error", False)) for item in content),
                },
            }

        elif method == "ping":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {},
            }

        else:
            if req_id is not None:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method '{method}' not found",
                    },
                }

        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def main():
    global DEFAULT_API_URL, API_KEY
    parser = argparse.ArgumentParser(description="TenderLex MCP Server")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="TenderLex backend API base URL")
    parser.add_argument("--api-key", default=API_KEY, help="TenderLex API Key")
    args = parser.parse_args()

    DEFAULT_API_URL = args.api_url.rstrip("/")
    if args.api_key:
        API_KEY = args.api_key

    run_stdio_server()


if __name__ == "__main__":
    main()
