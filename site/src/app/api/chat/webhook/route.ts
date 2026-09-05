import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const BOT_TOKEN = process.env.AIPOISK_BOT_TOKEN || "8812193491:AAF-NXMKXB1bVyB9JX5RM_CEvohLq8NtENo";
const DATA_FILE = "/root/projects/aipoisk-bot/data/chat_sessions.json";

const BOT_MAIN_KEYBOARD = {
  keyboard: [
    [{ text: "🚀 Запустить работу" }, { text: "📋 Мои задачи" }],
    [{ text: "💳 Баланс" }, { text: "💎 Тарифы" }],
    [{ text: "❓ Инструкция" }, { text: "📞 Поддержка" }],
  ],
  resize_keyboard: true,
  input_field_placeholder: "Выберите действие",
};

function loadSessions(): Record<string, any> {
  try {
    if (!fs.existsSync(DATA_FILE)) return {};
    const raw = fs.readFileSync(DATA_FILE, "utf8").trim();
    if (!raw) return {};
    return JSON.parse(raw);
  } catch (err) {
    return {};
  }
}

function saveSessions(data: Record<string, any>) {
  try {
    const dir = path.dirname(DATA_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2), "utf8");
  } catch (err) {
    console.error("Error saving sessions:", err);
  }
}

async function sendTg(method: string, payload: any) {
  try {
    await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    console.error("Telegram Webhook send error:", err);
  }
}

export async function POST(req: Request) {
  try {
    const update = await req.json();

    // 1. Handle Inline Button Callback Queries
    if (update.callback_query) {
      const cb = update.callback_query;
      const dataStr = cb.data || "";
      const chatId = cb.message?.chat?.id;
      const messageId = cb.message?.message_id;

      if (dataStr.startsWith("reply:")) {
        const sessionId = dataStr.substring(6);
        await sendTg("answerCallbackQuery", { callback_query_id: cb.id });
        await sendTg("sendMessage", {
          chat_id: chatId,
          text: `✍️ Введите ответ для клиента \`${sessionId}\` (просто отправьте текст сообщением ниже):`,
          parse_mode: "Markdown",
          reply_markup: {
            force_reply: true,
            input_field_placeholder: `Ответ для ${sessionId}...`,
          },
        });
        return NextResponse.json({ ok: true });
      }

      if (dataStr === "cancel_reply") {
        await sendTg("answerCallbackQuery", { callback_query_id: cb.id, text: "Режим ответа отменён" });
        if (chatId) {
          await sendTg("sendMessage", {
            chat_id: chatId,
            text: "🔄 *Ввод ответа отменён.* Клавиатура бота восстановлена:",
            parse_mode: "Markdown",
            reply_markup: BOT_MAIN_KEYBOARD,
          });
        }
        return NextResponse.json({ ok: true });
      }

      if (dataStr.startsWith("close:")) {
        const sessionId = dataStr.substring(6);
        const data = loadSessions();
        if (data[sessionId]) {
          data[sessionId].messages.push({
            id: "sys_" + Date.now(),
            sender: "system",
            text: "Диалог завершен администратором. Спасибо за обращение!",
            timestamp: new Date().toISOString(),
          });
          saveSessions(data);
        }
        await sendTg("answerCallbackQuery", { callback_query_id: cb.id, text: "Диалог закрыт" });
        if (chatId && messageId) {
          await sendTg("editMessageReplyMarkup", {
            chat_id: chatId,
            message_id: messageId,
            reply_markup: {
              inline_keyboard: [
                [{ text: "🔒 Диалог закрыт", callback_data: "none" }],
              ],
            },
          });
          // Restore full bot main menu keyboard so operator/user never loses bot controls!
          await sendTg("sendMessage", {
            chat_id: chatId,
            text: `🔒 *Диалог по сессии \`${sessionId}\` закрыт.*

Клавиатура бота снова активна:`,
            parse_mode: "Markdown",
            reply_markup: BOT_MAIN_KEYBOARD,
          });
        }
        return NextResponse.json({ ok: true });
      }
    }

    // 2. Handle Text Messages & Native Replies
    if (update.message && update.message.text) {
      const msg = update.message;
      const text = msg.text.trim();
      const chatId = msg.chat.id;

      let sessionId: string | null = null;

      // Check Native Telegram Reply (Reply to bot message)
      if (msg.reply_to_message && msg.reply_to_message.text) {
        const origText = msg.reply_to_message.text;
        const match = origText.match(/sess_[a-z0-9_]+/i);
        if (match) {
          sessionId = match[0];
        }
      }

      // Check Slash Command /reply sess_123 text
      if (!sessionId && text.startsWith("/reply ")) {
        const parts = text.substring(7).trim().split(" ");
        sessionId = parts[0];
      }

      if (sessionId) {
        let replyText = text;
        if (text.startsWith("/reply ")) {
          replyText = text.substring(7).trim().split(" ").slice(1).join(" ");
        }

        if (replyText) {
          const sessions = loadSessions();
          if (sessions[sessionId]) {
            const adminMsg = {
              id: "admin_" + Date.now(),
              sender: "admin",
              text: replyText,
              timestamp: new Date().toISOString(),
            };
            sessions[sessionId].messages.push(adminMsg);
            saveSessions(sessions);

            await sendTg("sendMessage", {
              chat_id: chatId,
              reply_to_message_id: msg.message_id,
              text: `✅ *Ответ успешно доставлен клиенту на сайт!*

💬 *Текст:* ${replyText}`,
              parse_mode: "Markdown",
              reply_markup: BOT_MAIN_KEYBOARD,
            });
          } else {
            await sendTg("sendMessage", {
              chat_id: chatId,
              reply_to_message_id: msg.message_id,
              text: `⚠️ *Сессия \`${sessionId}\` не найдена в базе.*`,
              parse_mode: "Markdown",
              reply_markup: BOT_MAIN_KEYBOARD,
            });
          }
        }
      }
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    console.error("Webhook processing error:", err);
    return NextResponse.json({ ok: true });
  }
}
