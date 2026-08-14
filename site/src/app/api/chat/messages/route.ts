import { NextResponse } from "next/server";
import fs from "fs";

const DATA_FILE = "/root/projects/aipoisk-bot/data/chat_sessions.json";

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const sessionId = searchParams.get("sessionId");

    if (!sessionId) {
      return NextResponse.json({ error: "sessionId required" }, { status: 400 });
    }

    if (!fs.existsSync(DATA_FILE)) {
      return NextResponse.json({ messages: [] });
    }

    let data: Record<string, any> = {};
    try {
      data = JSON.parse(fs.readFileSync(DATA_FILE, "utf8") || "{}");
    } catch {
      data = {};
    }

    const session = data[sessionId] || { messages: [] };
    return NextResponse.json({ messages: session.messages || [], contact: session.contact || null });
  } catch (err) {
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}