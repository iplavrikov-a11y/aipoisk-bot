import { NextResponse } from "next/server";
import { extractVisitorIp, getInternalApiBaseUrl, isValidGuestSessionId } from "@/lib/guest-chat-proxy";

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

    const visitorIp = extractVisitorIp(req.headers);
    const forwardedFor = visitorIp || req.headers.get("x-forwarded-for") || "";
    const realIp = visitorIp || req.headers.get("x-real-ip") || "";
    const userAgent = req.headers.get("user-agent") || "";
    const cookieHeader = req.headers.get("cookie") || "";
    const upstream = await fetch(`${getInternalApiBaseUrl()}/api/public/guest-chat/send`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "User-Agent": userAgent,
        ...(cookieHeader ? { Cookie: cookieHeader } : {}),
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
    const res = NextResponse.json(data, { status: upstream.ok ? 200 : upstream.status });
    const setCookies =
      typeof upstream.headers.getSetCookie === "function"
        ? upstream.headers.getSetCookie()
        : upstream.headers.get("set-cookie")
        ? [upstream.headers.get("set-cookie") as string]
        : [];
    for (const cookie of setCookies) {
      res.headers.append("Set-Cookie", cookie);
    }
    return res;
  } catch (err) {
    console.error("Guest chat send proxy error:", err);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
