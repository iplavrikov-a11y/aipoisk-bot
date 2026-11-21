import crypto from "crypto";
import { NextResponse } from "next/server";
import { getInternalApiBaseUrl, isValidGuestSessionId } from "@/lib/guest-chat-proxy";

const ADMIN_TOKEN = process.env.AIPOISK_ADMIN_TOKEN || "";

function safeTokenEqual(a: string, b: string): boolean {
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const sessionId = typeof body?.sessionId === "string" ? body.sessionId.trim() : "";
    const text = typeof body?.text === "string" ? body.text.trim() : "";
    const token = typeof body?.token === "string" ? body.token : "";

    if (!ADMIN_TOKEN || !token || !safeTokenEqual(token, ADMIN_TOKEN)) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    if (!isValidGuestSessionId(sessionId) || !text) {
      return NextResponse.json({ error: "Valid sessionId and text required" }, { status: 400 });
    }

    const form = new FormData();
    form.append("message", text);
    form.append("notify_telegram", "true");

    const upstream = await fetch(
      `${getInternalApiBaseUrl()}/api/admin/clients/${encodeURIComponent(`guest:${sessionId}`)}/chat`,
      {
        method: "POST",
        headers: {
          "X-Admin-Token": ADMIN_TOKEN,
        },
        body: form,
        cache: "no-store",
      }
    );

    const data = await upstream.json().catch(() => ({ error: "Backend error" }));
    if (!upstream.ok) {
      return NextResponse.json(data, { status: upstream.status });
    }
    const msgs = Array.isArray(data?.messages) ? data.messages : [];
    const last = msgs[msgs.length - 1] || null;
    return NextResponse.json({
      success: true,
      message: last
        ? {
            id: last.id,
            sender: "admin",
            text: last.message,
            timestamp: last.created_at,
          }
        : null,
    });
  } catch (err) {
    console.error("Guest chat reply proxy error:", err);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
