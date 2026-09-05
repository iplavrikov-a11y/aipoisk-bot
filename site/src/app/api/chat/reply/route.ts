import { NextResponse } from "next/server";
import fs from "fs";

const DATA_FILE = "/root/projects/aipoisk-bot/data/chat_sessions.json";
const ADMIN_TOKEN = process.env.AIPOISK_ADMIN_TOKEN || "05503b2c669dce0bc6631e4a6ce9af074fb84d1b558dd88e6e66db0547ac294d";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { sessionId, text, token } = body;

    if (token !== ADMIN_TOKEN) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    if (!sessionId || !text) {
      return NextResponse.json({ error: "sessionId and text required" }, { status: 400 });
    }

    if (!fs.existsSync(DATA_FILE)) {
      return NextResponse.json({ error: "Session not found" }, { status: 404 });
    }

    let data: Record<string, any> = JSON.parse(fs.readFileSync(DATA_FILE, "utf8") || "{}");

    if (!data[sessionId]) {
      return NextResponse.json({ error: "Session not found" }, { status: 404 });
    }

    const replyMsg = {
      id: "admin_" + Date.now(),
      sender: "admin",
      text,
      timestamp: new Date().toISOString(),
    };

    data[sessionId].messages.push(replyMsg);
    data[sessionId].updated = new Date().toISOString();

    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2), "utf8");

    return NextResponse.json({ success: true, message: replyMsg });
  } catch (err) {
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}