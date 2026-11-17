import { NextResponse } from "next/server";
import { extractVisitorIp, getInternalApiBaseUrl, isValidGuestSessionId } from "@/lib/guest-chat-proxy";

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const sessionId = (searchParams.get("sessionId") || "").trim();

    if (!isValidGuestSessionId(sessionId)) {
      return NextResponse.json({ error: "Invalid sessionId" }, { status: 400 });
    }

    const visitorIp = extractVisitorIp(req.headers);
    const forwardedFor = visitorIp || req.headers.get("x-forwarded-for") || "";
    const realIp = visitorIp || req.headers.get("x-real-ip") || "";
    const userAgent = req.headers.get("user-agent") || "";
    const cookieHeader = req.headers.get("cookie") || "";
    const upstream = await fetch(
      `${getInternalApiBaseUrl()}/api/public/guest-chat/messages?sessionId=${encodeURIComponent(sessionId)}`,
      {
        cache: "no-store",
        signal: AbortSignal.timeout(4000),
        headers: {
          "User-Agent": userAgent,
          ...(cookieHeader ? { Cookie: cookieHeader } : {}),
          ...(forwardedFor ? { "X-Forwarded-For": forwardedFor } : {}),
          ...(realIp ? { "X-Real-IP": realIp } : {}),
        },
      }
    );
    if (!upstream.ok && upstream.status >= 500) {
      return NextResponse.json({ messages: [], transient: true }, { status: 200 });
    }
    const data = await upstream.json().catch(() => ({ messages: [] }));
    if (!upstream.ok) {
      return NextResponse.json(data, { status: upstream.status });
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ messages: [], transient: true }, { status: 200 });
  }
}
