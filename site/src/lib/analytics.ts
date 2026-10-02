// Only coarse events are accepted. Documents, contacts, auth tokens, job IDs
// and free text must never be sent to a third party.
export const ANALYTICS_CONSENT_KEY = "tenderlex_analytics_consent";
export const ANALYTICS_GOALS = [
  "cabinet_click", "telegram_click", "whatsapp_click", "max_click", "phone_click", "email_click",
  "registration_success", "login_success", "email_verified", "task_started", "result_downloaded",
] as const;
export type AnalyticsGoal = typeof ANALYTICS_GOALS[number];
type MetrikaFunction = ((...args: unknown[]) => void) & { a?: unknown[][]; l?: number };
declare global { interface Window { ym?: MetrikaFunction } }

let counter: number | undefined;
let consentGranted = false;
const modules = new Set(["supplier_search", "exact_product", "procurement_report", "analysis_and_suppliers"]);

export function configureAnalytics(counterId: string | undefined, granted: boolean) {
  counter = counterId && /^\d+$/.test(counterId) && Number(counterId) > 0 ? Number(counterId) : undefined;
  consentGranted = granted && Boolean(counter);
}

export function safeAnalyticsUrl(value: string): string {
  if (!value) return "";
  try {
    const url = new URL(value, typeof window === "undefined" ? "https://tenderlex.ru" : window.location.origin);
    if (!/^https?:$/.test(url.protocol) || /^\/api(?:\/|$)/.test(url.pathname)) return "";
    const path = /^\/cabinet(?:\/|$)/.test(url.pathname) ? "/cabinet" : url.pathname;
    return `${url.origin}${path}`;
  } catch { return ""; }
}

export function trackGoal(goal: AnalyticsGoal, params: Record<string, unknown> = {}): void {
  if (typeof window === "undefined" || !consentGranted || !counter || !window.ym || !ANALYTICS_GOALS.includes(goal)) return;
  const safe: Record<string, string> = {};
  if (typeof params.module === "string" && modules.has(params.module)) safe.module = params.module;
  try { window.ym(counter, "reachGoal", goal, safe); } catch { /* Analytics must not interrupt a customer action. */ }
}
