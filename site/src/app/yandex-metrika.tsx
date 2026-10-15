"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ANALYTICS_CONSENT_KEY, configureAnalytics, safeAnalyticsUrl, trackGoal } from "@/lib/analytics";

type Consent = "unknown" | "granted" | "denied";

export function YandexMetrika({ counterId }: { counterId?: string }) {
  const pathname = usePathname();
  const [consent, setConsent] = useState<Consent>("unknown");
  const initialized = useRef(false);
  const lastPage = useRef("");
  const allowed = Boolean(counterId && /^\d+$/.test(counterId) && pathname && !/^\/api(?:\/|$)/.test(pathname));

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(ANALYTICS_CONSENT_KEY);
      setConsent(stored === "granted" || stored === "denied" ? stored : "unknown");
    } catch { setConsent("unknown"); }
    function sync(event: StorageEvent) {
      if (event.key !== ANALYTICS_CONSENT_KEY) return;
      const next = event.newValue === "granted" || event.newValue === "denied" ? event.newValue : "unknown";
      configureAnalytics(counterId, next === "granted");
      setConsent(next);
    }
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, [counterId]);

  useEffect(() => {
    const enabled = allowed && consent === "granted";
    configureAnalytics(counterId, enabled);
    if (!enabled || !counterId) {
      if (initialized.current && window.ym && counterId) {
        try { window.ym(Number(counterId), "destruct"); } catch { /* SDK may be blocked. */ }
      }
      initialized.current = false;
      lastPage.current = "";
      return;
    }
    if (!window.ym) {
      const stub: NonNullable<Window["ym"]> = (...args: unknown[]) => { (stub.a ??= []).push(args); };
      stub.l = Date.now();
      window.ym = stub;
    }
    try {
      if (!initialized.current) {
        window.ym(Number(counterId), "init", {
          defer: true, ssr: true, accurateTrackBounce: true,
          webvisor: false, clickmap: false, trackLinks: false, ecommerce: false, sendTitle: false,
          url: safeAnalyticsUrl(window.location.href), referrer: safeAnalyticsUrl(document.referrer),
        });
        initialized.current = true;
      }
      const page = safeAnalyticsUrl(window.location.origin + pathname);
      if (page && lastPage.current !== page) {
        window.ym(Number(counterId), "hit", page, {
          title: pathname?.startsWith("/cabinet") ? "Личный кабинет TenderLex" : "TenderLex",
          referer: lastPage.current || safeAnalyticsUrl(document.referrer),
        });
        lastPage.current = page;
      }
    } catch { /* Analytics failure must not affect the page. */ }
    function click(event: MouseEvent) {
      const target = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null;
      if (!target) return;
      let url: URL;
      try { url = new URL(target.href, window.location.origin); } catch { return; }
      if (url.origin === window.location.origin && /^\/cabinet(?:\/|$)/.test(url.pathname)) trackGoal("cabinet_click");
      else if (url.hostname === "t.me") trackGoal("telegram_click");
      else if (url.hostname === "wa.me") trackGoal("whatsapp_click");
      else if (url.hostname === "max.ru") trackGoal("max_click");
      else if (url.protocol === "tel:") trackGoal("phone_click");
      else if (url.protocol === "mailto:") trackGoal("email_click");
    }
    document.addEventListener("click", click);
    return () => document.removeEventListener("click", click);
  }, [allowed, consent, counterId, pathname]);

  if (!allowed || !counterId) return null;
  function choose(next: Exclude<Consent, "unknown">) {
    try { window.localStorage.setItem(ANALYTICS_CONSENT_KEY, next); } catch { /* Choice remains valid for this page. */ }
    configureAnalytics(counterId, next === "granted");
    setConsent(next);
  }

  return <>
    {consent === "unknown" ? (
      <aside className="cookie-consent" aria-label="Настройки аналитики">
        <p>TenderLex использует необходимые данные для работы сайта. С вашего разрешения Яндекс Метрика учитывает посещения и действия, чтобы улучшать сервис. <a href="/privacy#cookies">Подробнее</a></p>
        <div>
          <button type="button" className="cookie-secondary" onClick={() => choose("denied")}>Только необходимые</button>
          <button type="button" className="cookie-primary" onClick={() => choose("granted")}>Разрешить аналитику</button>
        </div>
      </aside>
    ) : null}
    {consent === "granted" ? <Script id="tenderlex-metrika-sdk" src="https://mc.yandex.ru/metrika/tag.js" strategy="afterInteractive" /> : null}
    {consent !== "unknown" ? <button type="button" className="cookie-settings" onClick={() => { configureAnalytics(counterId, false); setConsent("unknown"); }}>Настройки аналитики</button> : null}
  </>;
}
