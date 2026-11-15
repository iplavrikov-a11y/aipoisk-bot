import { NextResponse } from "next/server";
import { getInternalApiBaseUrl, isValidGuestSessionId } from "@/lib/guest-chat-proxy";

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const sessionId = (searchParams.get("sessionId") || "").trim();

    if (!isValidGuestSessionId(sessionId)) {
      return NextResponse.json({ error: "Invalid sessionId" }, { status: 400 });
    }

    const forwardedFor = req.headers.get("x-forwarded-for") || "";
    const realIp = req.headers.get("x-real-ip") || "";
    const upstream = await fetch(
      `${getInternalApiBaseUrl()}/api/public/guest-chat/messages?sessionId=${encodeURIComponent(sessionId)}`,
      {
        cache: "no-store",
        headers: {
          ...(forwardedFor ? { "X-Forwarded-For": forwardedFor } : {}),
          ...(realIp ? { "X-Real-IP": realIp } : {}),
        },
      }
    );
    const data = await upstream.json().catch(() => ({ messages: [] }));
    if (!upstream.ok) {
      return NextResponse.json(data, { status: upstream.status });
    }
    return NextResponse.json(data);
  } catch (err) {
    console.error("Guest chat messages proxy error:", err);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
