"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const ANALYTICS_CONSENT_KEY = "tenderlex_analytics_consent";

type Consent = "unknown" | "granted" | "denied";

export function YandexMetrika({ counterId }: { counterId?: string }) {
  const pathname = usePathname();
  const [consent, setConsent] = useState<Consent>("unknown");
  const allowed = Boolean(counterId && pathname && !pathname.startsWith("/api") && !pathname.startsWith("/cabinet"));

  useEffect(() => {
    if (!allowed) return;

    // Auto-consent for crawlers and bots (e.g. Yandex Webmaster, YandexBot, Googlebot)
    if (typeof navigator !== "undefined" && navigator.userAgent) {
      const ua = navigator.userAgent.toLowerCase();
      if (
        ua.includes("yandex") ||
        ua.includes("google") ||
        ua.includes("bot") ||
        ua.includes("crawler") ||
        ua.includes("spider") ||
        ua.includes("lighthouse")
      ) {
        setConsent("granted");
        return;
      }
    }

    const stored = window.localStorage.getItem(ANALYTICS_CONSENT_KEY);
    setConsent(stored === "granted" || stored === "denied" ? stored : "unknown");
  }, [allowed]);

  if (!allowed || !counterId) return null;

  function choose(next: Exclude<Consent, "unknown">) {
    window.localStorage.setItem(ANALYTICS_CONSENT_KEY, next);
    setConsent(next);
  }

  const tagUrl = `https://mc.yandex.ru/metrika/tag.js?id=${encodeURIComponent(counterId)}`;

  return (
    <>
      {consent === "unknown" ? (
        <aside className="cookie-consent" aria-label="Настройки аналитики">
          <p>
            TenderLex использует необходимые данные для работы сайта. Яндекс Метрика включится только с вашего разрешения. {" "}
            <a href="/privacy#cookies">Подробнее</a>
          </p>
          <div>
            <button type="button" className="cookie-secondary" onClick={() => choose("denied")}>Только необходимые</button>
            <button type="button" className="cookie-primary" onClick={() => choose("granted")}>Разрешить аналитику</button>
          </div>
        </aside>
      ) : null}
      {consent === "granted" ? (
        <Script id="yandex-metrika" strategy="afterInteractive">
          {`
            (function(m,e,t,r,i,k,a){
              m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
              m[i].l=1*new Date();
              for (var j = 0; j < document.scripts.length; j++) {
                if (document.scripts[j].src === r) { return; }
              }
              k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)
            })(window, document, "script", ${JSON.stringify(tagUrl)}, "ym");
            ym(${JSON.stringify(counterId)}, "init", {
              ssr: true,
              webvisor: true,
              clickmap: true,
              ecommerce: "dataLayer",
              referrer: document.referrer,
              url: location.href,
              accurateTrackBounce: true,
              informer: false,
              trackLinks: true
            });
            document.addEventListener("click", function(event) {
              var target = event.target && event.target.closest ? event.target.closest("a[href]") : null;
              if (!target || !window.ym) { return; }
              var href = target.href || "";
              var goal = "";
              if (href.indexOf("/cabinet") !== -1) {
                goal = "cabinet_click";
              } else if (href.toLowerCase().indexOf("t.me/tenderlex_bot") !== -1 || href.toLowerCase().indexOf("t.me/lexelence") !== -1) {
                goal = "telegram_click";
              } else if (href.indexOf("tel:") === 0) {
                goal = "phone_click";
              } else if (href.indexOf("mailto:") === 0) {
                goal = "email_click";
              }
              if (goal) ym(${JSON.stringify(counterId)}, "reachGoal", goal, { page: location.pathname, href: href });
            });
          `}
        </Script>
      ) : null}
    </>
  );
}
