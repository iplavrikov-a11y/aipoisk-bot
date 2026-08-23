"""
TenderLex Yandex SEO & Metrika Autonomous Pipeline
Gathers analytics snapshots, tracks Metrika conversion goals, detects striking-distance queries, and sends Telegram digests.
"""
import os
import json
import time
import asyncio
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from aiogram import Bot
from aiogram.enums import ParseMode

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
SNAPSHOT_PATH = DATA_DIR / "yandex_analytics_snapshot.json"
ENV_PATH = ROOT_DIR / ".env"

def _load_env_tokens():
    tokens = {
        "webmaster": os.environ.get("YANDEX_WEBMASTER_TOKEN", ""),
        "metrika": os.environ.get("YANDEX_METRIKA_TOKEN", ""),
        "counter_id": os.environ.get("YANDEX_METRIKA_COUNTER_ID", "109753178"),
        "host_id": "https:tenderlex.ru:443",
        "bot_token": os.environ.get("AIPOISK_BOT_TOKEN", "8812193491:AAF-NXMKXB1bVyB9JX5RM_CEvohLq8NtENo"),
        "owner_telegram_id": os.environ.get("AIPOISK_OWNER_TELEGRAM_ID", "320433711")
    }
    if not tokens["webmaster"] or not tokens["metrika"]:
        if ENV_PATH.exists():
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("YANDEX_WEBMASTER_TOKEN="):
                        tokens["webmaster"] = line.split("=", 1)[1].strip().strip("\"'")
                    elif line.startswith("YANDEX_METRIKA_TOKEN="):
                        tokens["metrika"] = line.split("=", 1)[1].strip().strip("\"'")
                    elif line.startswith("YANDEX_METRIKA_COUNTER_ID="):
                        tokens["counter_id"] = line.split("=", 1)[1].strip().strip("\"'")
                    elif line.startswith("AIPOISK_BOT_TOKEN="):
                        tokens["bot_token"] = line.split("=", 1)[1].strip().strip("\"'")
                    elif line.startswith("AIPOISK_OWNER_TELEGRAM_ID="):
                        tokens["owner_telegram_id"] = line.split("=", 1)[1].strip().strip("\"'")
                        
    if not tokens["webmaster"]:
        tokens["webmaster"] = "y0__wgBELDitkEYs4BIIJaI2uIYMM7MspMI9_BpXJIpkOWGXoXGrtWkS4fQpVU"
    if not tokens["metrika"]:
        tokens["metrika"] = "y0__wgBELDitkEYsoBIIIiM2uIYMM7MspMIy0zhW9k_nL_p4xuNMOMSrw3v9o0"
    return tokens

def _http_json(url: str, headers: dict = None, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

def fetch_fresh_snapshot() -> dict:
    tokens = _load_env_tokens()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # 1. Fetch Webmaster Summary & Popular Queries
    wm_headers = {"Authorization": f"OAuth {tokens['webmaster']}"}
    user_id = 137212208
    try:
        user_res = _http_json("https://api.webmaster.yandex.net/v4/user", headers=wm_headers, timeout=10)
        if "user_id" in user_res:
            user_id = user_res["user_id"]
    except Exception:
        pass
        
    host_id = tokens["host_id"]
    wm_summary = _http_json(f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}/summary", headers=wm_headers, timeout=10)
    
    queries_url = (
        f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}/search-queries/popular"
        f"?order_by=TOTAL_SHOWS&query_indicator=TOTAL_SHOWS&query_indicator=TOTAL_CLICKS&query_indicator=AVG_SHOW_POSITION"
    )
    wm_queries = _http_json(queries_url, headers=wm_headers, timeout=10)
    
    # 2. Fetch Metrika Core Metrics
    m_headers = {"Authorization": f"OAuth {tokens['metrika']}"}
    counter_id = tokens["counter_id"]
    
    def m_query(params):
        url = f"https://api-metrika.yandex.net/stat/v1/data?ids={counter_id}&date1=30daysAgo&date2=today&" + params
        return _http_json(url, headers=m_headers, timeout=10)
        
    m_totals = m_query("metrics=ym:s:visits,ym:s:users,ym:s:pageviews,ym:s:bounceRate,ym:s:avgVisitDurationSeconds")
    m_sources = m_query("metrics=ym:s:visits,ym:s:users&dimensions=ym:s:lastSignTrafficSource&sort=-ym:s:visits")
    m_pages = m_query("metrics=ym:s:visits,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds&dimensions=ym:s:startURLPath&sort=-ym:s:visits&limit=10")
    
    # 3. Fetch Metrika Goals & Goal Reaches
    goals_res = _http_json(f"https://api-metrika.yandex.net/management/v1/counter/{counter_id}/goals", headers=m_headers, timeout=10)
    raw_goals = goals_res.get("goals", [])
    goals_clean = []
    total_reaches = 0
    
    if raw_goals:
        goal_metrics_list = []
        for g in raw_goals:
            gid = g.get("id")
            if gid:
                goal_metrics_list.append(f"ym:s:goal{gid}reaches")
        
        if goal_metrics_list:
            m_goals_stat = m_query(f"metrics={','.join(goal_metrics_list)}")
            g_totals = m_goals_stat.get("totals", [])
            for idx, g in enumerate(raw_goals):
                reaches = int(g_totals[idx]) if idx < len(g_totals) and g_totals[idx] is not None else 0
                total_reaches += reaches
                g_name = g.get("name", "Цель")
                goals_clean.append({
                    "id": g.get("id"),
                    "name": g_name,
                    "type": g.get("type"),
                    "reaches": reaches
                })
    
    # Process structured clean data
    totals_arr = m_totals.get("totals", [])
    visits = int(totals_arr[0]) if len(totals_arr) > 0 and totals_arr[0] is not None else 0
    users = int(totals_arr[1]) if len(totals_arr) > 1 and totals_arr[1] is not None else 0
    pageviews = int(totals_arr[2]) if len(totals_arr) > 2 and totals_arr[2] is not None else 0
    bounce_rate = round(float(totals_arr[3]), 1) if len(totals_arr) > 3 and totals_arr[3] is not None else 0.0
    duration_s = int(totals_arr[4]) if len(totals_arr) > 4 and totals_arr[4] is not None else 0
    total_conv_rate = round((total_reaches / visits * 100), 2) if visits > 0 else 0.0
    
    queries_clean = []
    growth_points = []
    
    for q in wm_queries.get("queries", []):
        text = q.get("query_text", "")
        indicators = q.get("indicators", {})
        shows = int(indicators.get("TOTAL_SHOWS", 0))
        clicks = int(indicators.get("TOTAL_CLICKS", 0))
        avg_pos = round(float(indicators.get("AVG_SHOW_POSITION", 0.0)), 1)
        ctr = round((clicks / shows * 100), 1) if shows > 0 else 0.0
        
        item = {
            "text": text,
            "shows": shows,
            "clicks": clicks,
            "avg_position": avg_pos,
            "ctr_percent": ctr
        }
        queries_clean.append(item)
        
        if 4.0 <= avg_pos <= 15.0 and shows >= 3:
            growth_points.append({
                **item,
                "potential": "Высокий (позиция 4–10)",
                "action": "Дожать в ТОП-3 (дает до 80% всех кликов)"
            })
            
    sources_clean = []
    for s in m_sources.get("data", []):
        sources_clean.append({
            "name": s["dimensions"][0]["name"],
            "visits": int(s["metrics"][0]),
            "users": int(s["metrics"][1]) if len(s["metrics"]) > 1 else 0
        })
        
    pages_clean = []
    for p in m_pages.get("data", []):
        pages_clean.append({
            "path": p["dimensions"][0]["name"],
            "visits": int(p["metrics"][0]),
            "users": int(p["metrics"][1]),
            "bounce_rate": round(float(p["metrics"][2]), 1),
            "avg_duration_seconds": int(p["metrics"][3])
        })
        
    snapshot = {
        "updated_at": now_iso,
        "collection_status": "active",
        "sample_size_ready": visits >= 300,
        "sample_visits": visits,
        "sample_target": 300,
        "webmaster": {
            "sqi": wm_summary.get("sqi", 10),
            "searchable_pages": wm_summary.get("searchable_pages_count", 32),
            "excluded_pages": wm_summary.get("excluded_pages_count", 1),
            "top_queries": queries_clean[:25],
            "growth_points": growth_points[:10]
        },
        "metrika": {
            "period_days": 30,
            "visits": visits,
            "users": users,
            "pageviews": pageviews,
            "bounce_rate": bounce_rate,
            "avg_duration_seconds": duration_s,
            "sources": sources_clean,
            "top_pages": pages_clean,
            "goals": goals_clean,
            "total_goal_reaches": total_reaches,
            "total_conversion_rate": total_conv_rate
        },
        "recommendations": []
    }
    
    # Save snapshot locally
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
        
    return snapshot

def get_cached_or_fresh_analytics(force_refresh: bool = False) -> dict:
    if not force_refresh and SNAPSHOT_PATH.exists():
        try:
            mtime = SNAPSHOT_PATH.stat().st_mtime
            if time.time() - mtime < 21600:
                with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
            
    return fetch_fresh_snapshot()

async def send_seo_telegram_digest() -> dict:
    tokens = _load_env_tokens()
    bot_token = tokens["bot_token"]
    owner_id = tokens["owner_telegram_id"]
    
    if not bot_token or not owner_id:
        return {"ok": False, "error": "Bot token or owner Telegram ID not configured"}
        
    data = get_cached_or_fresh_analytics()
    metrika = data.get("metrika", {})
    webmaster = data.get("webmaster", {})
    
    duration_min = metrika.get("avg_duration_seconds", 0) // 60
    duration_sec = metrika.get("avg_duration_seconds", 0) % 60
    
    growth_lines = []
    for g in webmaster.get("growth_points", [])[:4]:
        growth_lines.append(f"  • <b>«{g['text']}»</b> — {g['shows']} показов (поз. {g['avg_position']})")
        
    top_queries_lines = []
    for q in webmaster.get("top_queries", [])[:5]:
        top_queries_lines.append(f"  • {q['text']} — {q['shows']} показов (поз. {q.get('avg_position', '-')})")
        
    goals_lines = []
    for g in metrika.get("goals", []):
        if g.get("reaches", 0) > 0:
            goals_lines.append(f"  • {g['name']}: <b>{g['reaches']}</b> достижений")
            
    growth_block = "\n".join(growth_lines) if growth_lines else "  <i>Идет накопление показов...</i>"
    queries_block = "\n".join(top_queries_lines) if top_queries_lines else "  <i>Нет данных</i>"
    goals_block = "\n".join(goals_lines) if goals_lines else "  • <i>Цели отслеживаются в Метрике</i>"
    
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    message = (
        f"📊 <b>SEO-Дайджест TenderLex</b> ({now_str})\n\n"
        f"👥 <b>Посетители:</b> {metrika.get('users', 0)} чел. ({metrika.get('visits', 0)} визитов)\n"
        f"⏱ <b>Время на сайте:</b> {duration_min} мин {duration_sec} сек\n"
        f"📉 <b>Отказы:</b> {metrika.get('bounce_rate', 0)}%\n"
        f"🎯 <b>Конверсии (Цели):</b> {metrika.get('total_goal_reaches', 0)} достижений (конверсия {metrika.get('total_conversion_rate', 0)}%)\n"
        f"🔍 <b>Страниц в поиске:</b> {webmaster.get('searchable_pages', 32)} (ИКС: {webmaster.get('sqi', 10)})\n\n"
        f"🎯 <b>Ключевые конверсии:</b>\n{goals_block}\n\n"
        f"🔥 <b>Точки быстрого роста (Потенциал ТОП-3):</b>\n{growth_block}\n\n"
        f"🔎 <b>Топ запросов Яндекса:</b>\n{queries_block}\n\n"
        f"<i>Сбор данных работает автоматически. Новые рекомендации будут доступны в панели управления.</i>"
    )
    
    bot = Bot(token=bot_token)
    try:
        await bot.send_message(chat_id=int(owner_id), text=message, parse_mode=ParseMode.HTML)
        return {"ok": True, "sent_to": owner_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        await bot.session.close()
