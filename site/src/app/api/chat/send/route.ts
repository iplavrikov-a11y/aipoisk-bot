import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const BOT_TOKEN = process.env.AIPOISK_BOT_TOKEN || "";
const OWNER_ID = process.env.AIPOISK_OWNER_TELEGRAM_ID || "";
const DATA_FILE = "/root/projects/tenderlex/data/chat_sessions.json";

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function loadSessions(): Record<string, any> {
  try {
    const dir = path.dirname(DATA_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    if (!fs.existsSync(DATA_FILE)) {
      fs.writeFileSync(DATA_FILE, "{}", "utf8");
      return {};
    }
    const raw = fs.readFileSync(DATA_FILE, "utf8").trim();
    if (!raw) return {};
    return JSON.parse(raw);
  } catch (err) {
    console.error("Error loading chat sessions:", err);
    return {};
  }
}

function saveSessions(data: Record<string, any>) {
  try {
    const dir = path.dirname(DATA_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const tmpFile = `${DATA_FILE}.tmp.${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
    fs.writeFileSync(tmpFile, JSON.stringify(data, null, 2), "utf8");
    fs.renameSync(tmpFile, DATA_FILE);
  } catch (err) {
    console.error("Error saving chat sessions:", err);
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { sessionId, text, preset, contact } = body;

    if (!sessionId || (!text && !preset)) {
      return NextResponse.json({ error: "Session ID and text are required" }, { status: 400 });
    }

    const data = loadSessions();

    if (!data[sessionId]) {
      data[sessionId] = {
        sessionId,
        created: new Date().toISOString(),
        messages: [],
        contact: contact || null,
      };
    }

    if (contact) {
      data[sessionId].contact = contact;
    }

    const newMessage = {
      id: "msg_" + Date.now() + "_" + Math.random().toString(36).substring(2, 7),
      sender: "user",
      text: text || preset,
      preset: preset || null,
      timestamp: new Date().toISOString(),
    };

    data[sessionId].messages.push(newMessage);
    data[sessionId].updated = new Date().toISOString();

    saveSessions(data);

    if (BOT_TOKEN && OWNER_ID) {
      const tgLines = [
        "📩 <b>Новое обращение с сайта TenderLex!</b>",
        "",
        `👤 <b>Сессия:</b> <code>${escapeHtml(sessionId)}</code>`,
      ];
      if (preset) tgLines.push(`📌 <b>Категория:</b> ${escapeHtml(preset)}`);
      tgLines.push(`💬 <b>Сообщение:</b> ${escapeHtml(text || preset)}`);
      if (contact) tgLines.push(`📞 <b>Контакт:</b> ${escapeHtml(contact)}`);
      tgLines.push("");
      tgLines.push("💡 <b>Как ответить клиенту:</b>");
      tgLines.push("1️⃣ Просто ответьте (<b>Reply 💬</b>) на это сообщение в Telegram");
      tgLines.push("2️⃣ Или нажмите кнопку «💬 Ответить на сайт» ниже");

      const telegramText = tgLines.join("\n");

      const replyMarkup = {
        inline_keyboard: [
          [
            { text: "💬 Ответить на сайт", callback_data: `reply:${sessionId}` },
          ],
          [
            { text: "✅ Завершить диалог", callback_data: `close:${sessionId}` },
          ],
        ],
      };

      try {
        await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: OWNER_ID,
            text: telegramText,
            parse_mode: "HTML",
            reply_markup: replyMarkup,
          }),
        });
      } catch (tgErr) {
        console.error("Telegram notification error:", tgErr);
      }
    }

    return NextResponse.json({ success: true, message: newMessage });
  } catch (err: any) {
    console.error("Chat API Error:", err);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}