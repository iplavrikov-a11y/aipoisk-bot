const endpoint = "/api/customer/seo-entry";
const marker = "tenderlex_seo_entry_recorded";

type SeoEntry = { source: "google" | "yandex" | "bing"; landing: string };

let entry: SeoEntry | null | undefined;
let mayHaveEntry = false;
let recording = false;
let pending: Promise<void> = Promise.resolve();

export function rememberSeoEntry() {
  if (entry !== undefined) return;
  entry = null;
  const { pathname, search } = window.location;
  if (!document.referrer) return;
  const params = new URLSearchParams(search);
  if (params.has("utm_medium") && params.get("utm_medium")?.toLowerCase() !== "organic") return;
  if (["gclid", "yclid", "msclkid"].some((key) => params.has(key))) return;
  if (pathname !== "/" && !/^\/[a-z0-9-]+(?:\/[a-z0-9-]+)?$/.test(pathname)) return;
  try {
    const host = new URL(document.referrer).hostname.toLowerCase().replace(/^www\./, "");
    if (["google.com", "google.ru", "google.by", "google.kz", "google.com.ua", "google.co.uk", "google.de"].includes(host)) {
      entry = { source: "google", landing: pathname };
    } else if (["yandex.ru", "ya.ru", "yandex.com", "yandex.by", "yandex.kz"].includes(host)) {
      entry = { source: "yandex", landing: pathname };
    } else if (["bing.com", "cn.bing.com"].includes(host)) {
      entry = { source: "bing", landing: pathname };
    }
  } catch { /* A malformed referrer is ineligible. */ }
}

export function recordSeoLanding() {
  const landing = entry;
  if (!landing || recording) return;
  mayHaveEntry = true;
  recording = true;
  try { window.localStorage.setItem(marker, "1"); } catch { /* Optional deletion hint. */ }
  pending = pending.then(async () => {
    if (entry !== landing) return;
    const save = async () => {
      if (entry !== landing) return;
      const response = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        keepalive: true,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(landing),
      });
      if (response.ok) entry = null;
    };
    if (navigator.locks) await navigator.locks.request("tenderlex-seo-entry", save);
    else await save();
  }).catch(() => { /* Attribution must not interrupt the customer flow. */ }).finally(() => { recording = false; });
}

export function clearSeoLanding() {
  entry = null;
  try { mayHaveEntry ||= window.localStorage.getItem(marker) === "1"; } catch { /* This tab still has its hint. */ }
  if (!mayHaveEntry) return;
  pending = pending.then(async () => {
    const clear = async () => {
      const response = await fetch(endpoint, { method: "DELETE", credentials: "same-origin", keepalive: true });
      if (response.ok) {
        mayHaveEntry = false;
        try { window.localStorage.removeItem(marker); } catch { /* Optional deletion hint. */ }
      }
    };
    if (navigator.locks) await navigator.locks.request("tenderlex-seo-entry", clear);
    else await clear();
  }).catch(() => { /* The browser keeps the analytics preference regardless. */ });
}

export function pendingSeoEntry(): Promise<void> | null {
  if (!recording) return null;
  return new Promise((resolve) => {
    const timeout = window.setTimeout(resolve, 850);
    void pending.then(() => {
      window.clearTimeout(timeout);
      resolve();
    });
  });
}
