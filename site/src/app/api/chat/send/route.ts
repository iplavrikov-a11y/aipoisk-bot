import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const BOT_TOKEN = process.env.AIPOISK_BOT_TOKEN || "8812193491:AAF-NXMKXB1bVyB9JX5RM_CEvohLq8NtENo";
const OWNER_ID = process.env.AIPOISK_OWNER_TELEGRAM_ID || "320433711";
const DATA_FILE = "/root/projects/aipoisk-bot/data/chat_sessions.json";

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
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2), "utf8");
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

    const tgLines = [
      "📩 *Новое обращение с сайта TenderLex!*",
      "",
      `👤 *Сессия:* \`${sessionId}\``,
    ];
    if (preset) tgLines.push(`📌 *Категория:* ${preset}`);
    tgLines.push(`💬 *Сообщение:* ${text || preset}`);
    if (contact) tgLines.push(`📞 *Контакт:* ${contact}`);
    tgLines.push("");
    tgLines.push("💡 *Как ответить клиенту:*");
    tgLines.push("1️⃣ Просто ответьте (*Reply 💬*) на это сообщение в Telegram");
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
          parse_mode: "Markdown",
          reply_markup: replyMarkup,
        }),
      });
    } catch (tgErr) {
      console.error("Telegram notification error:", tgErr);
    }

    return NextResponse.json({ success: true, message: newMessage });
  } catch (err: any) {
    console.error("Chat API Error:", err);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}