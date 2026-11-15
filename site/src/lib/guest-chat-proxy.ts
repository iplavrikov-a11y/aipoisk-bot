const SESSION_ID_RE = /^[A-Za-z0-9_-]{4,64}$/;

export function getInternalApiBaseUrl(): string {
  return (
    process.env.TENDERLEX_SITE_API_BASE_URL ||
    process.env.AIPOISK_SITE_API_BASE_URL ||
    "http://127.0.0.1:8088"
  ).replace(/\/+$/, "");
}

export function isValidGuestSessionId(raw: unknown): raw is string {
  return typeof raw === "string" && SESSION_ID_RE.test(raw.trim());
}
