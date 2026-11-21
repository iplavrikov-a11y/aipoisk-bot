const SESSION_ID_RE = /^[A-Za-z0-9_-]{4,64}$/;
const SAFE_IP_RE = /^[0-9a-fA-F:.]{2,64}$/;

const PROTECTED_PROXY_IPS = new Set([
  "127.0.0.1",
  "::1",
  "79.133.182.215",
  "202.71.13.57",
]);

function normalizeCandidateIp(raw: string): string {
  let candidate = raw.trim();
  if (!candidate) return "";
  if (candidate.startsWith("[") && candidate.includes("]")) {
    candidate = candidate.slice(1, candidate.indexOf("]"));
  } else if (/^\d{1,3}(?:\.\d{1,3}){3}:\d+$/.test(candidate)) {
    candidate = candidate.slice(0, candidate.lastIndexOf(":"));
  }
  if (candidate.toLowerCase().startsWith("::ffff:")) {
    const v4 = candidate.slice(7);
    if (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(v4)) {
      candidate = v4;
    }
  }
  if (!SAFE_IP_RE.test(candidate)) return "";
  return candidate;
}

function isTrustedOrPrivateHop(ip: string): boolean {
  const lower = ip.toLowerCase();
  if (PROTECTED_PROXY_IPS.has(lower)) return true;

  const extraTrusted = (process.env.AIPOISK_TRUSTED_PROXY_IPS || "")
    .split(",")
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean);
  if (extraTrusted.includes(lower)) return true;

  if (
    lower === "0.0.0.0" ||
    lower.startsWith("127.") ||
    lower.startsWith("10.") ||
    lower.startsWith("192.168.") ||
    lower.startsWith("169.254.")
  ) {
    return true;
  }
  const octets = lower.split(".");
  if (octets.length === 4 && octets[0] === "172") {
    const second = Number(octets[1]);
    if (Number.isInteger(second) && second >= 16 && second <= 31) {
      return true;
    }
  }
  if (lower.includes(":")) {
    if (
      lower === "::" ||
      lower === "::1" ||
      lower.startsWith("fc") ||
      lower.startsWith("fd") ||
      lower.startsWith("fe80:")
    ) {
      return true;
    }
  }
  return false;
}

export function extractVisitorIp(headers: Headers): string {
  const forwardedFor = headers.get("x-forwarded-for") || "";
  if (forwardedFor) {
    const hops = forwardedFor.split(",");
    for (let i = hops.length - 1; i >= 0; i -= 1) {
      const candidate = normalizeCandidateIp(hops[i]);
      if (candidate && !isTrustedOrPrivateHop(candidate)) {
        return candidate;
      }
    }
  }

  const realIp = normalizeCandidateIp(headers.get("x-real-ip") || "");
  if (realIp && !isTrustedOrPrivateHop(realIp)) {
    return realIp;
  }

  return "";
}

export function getInternalApiBaseUrl(): string {
  return (
    process.env.TENDERLEX_SITE_API_BASE_URL ||
    process.env.AIPOISK_SITE_API_BASE_URL ||
    "http://127.0.0.1:8088"
  ).replace(/\/+$/, "");
}

export function isValidGuestSessionId(raw: unknown): raw is string {
  if (typeof raw !== "string") return false;
  const trimmed = raw.trim();
  if (trimmed.toLowerCase().startsWith("tg_")) return false;
  return SESSION_ID_RE.test(trimmed);
}
