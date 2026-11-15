import { NextResponse } from "next/server";
import { getInternalApiBaseUrl, isValidGuestSessionId } from "@/lib/guest-chat-proxy";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const sessionId = typeof body?.sessionId === "string" ? body.sessionId.trim() : "";
    const text = typeof body?.text === "string" ? body.text : "";
    const preset = typeof body?.preset === "string" ? body.preset : "";
    const contact = typeof body?.contact === "string" ? body.contact : "";
    const sourceUrl = req.headers.get("referer") || "";

    if (!isValidGuestSessionId(sessionId) || (!text.trim() && !preset.trim())) {
      return NextResponse.json({ error: "Valid sessionId and message text are required" }, { status: 400 });
    }

    const forwardedFor = req.headers.get("x-forwarded-for") || "";
    const realIp = req.headers.get("x-real-ip") || "";
    const upstream = await fetch(`${getInternalApiBaseUrl()}/api/public/guest-chat/send`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(forwardedFor ? { "X-Forwarded-For": forwardedFor } : {}),
        ...(realIp ? { "X-Real-IP": realIp } : {}),
      },
      body: JSON.stringify({
        sessionId,
        text,
        preset,
        contact,
        sourceUrl,
      }),
      cache: "no-store",
    });

    const data = await upstream.json().catch(() => ({ error: "Backend error" }));
    if (!upstream.ok) {
      return NextResponse.json(data, { status: upstream.status });
    }
    return NextResponse.json(data);
  } catch (err) {
    console.error("Guest chat send proxy error:", err);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
