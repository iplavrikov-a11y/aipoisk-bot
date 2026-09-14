import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const DATA_FILE = "/root/projects/tenderlex/data/chat_sessions.json";
const ADMIN_TOKEN = process.env.AIPOISK_ADMIN_TOKEN || "";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { sessionId, text, token } = body;

    if (!ADMIN_TOKEN || token !== ADMIN_TOKEN) {
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

    const dir = path.dirname(DATA_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const tmpFile = `${DATA_FILE}.tmp.${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
    fs.writeFileSync(tmpFile, JSON.stringify(data, null, 2), "utf8");
    fs.renameSync(tmpFile, DATA_FILE);

    return NextResponse.json({ success: true, message: replyMsg });
  } catch (err) {
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}