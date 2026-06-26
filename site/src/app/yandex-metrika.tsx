"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";

const METRIKA_ALLOWED_PATHS = new Set([
  "/",
  "/analiz-zakupochnoi-dokumentacii",
  "/poisk-postavshchikov-dlya-tendera",
  "/poisk-postavshchikov-po-tz",
  "/poisk-proizvoditeley-po-tz",
  "/postavshchiki-dlya-zaprosa-kp",
  "/reestr-minpromtorga-v-zakupkah",
  "/zapros-kp-po-tz",
]);

export function YandexMetrika({ counterId }: { counterId?: string }) {
  const pathname = usePathname();
  if (!counterId || !METRIKA_ALLOWED_PATHS.has(pathname || "")) {
    return null;
  }

  const tagUrl = `https://mc.yandex.ru/metrika/tag.js?id=${encodeURIComponent(counterId)}`;

  return (
    <>
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
            } else if (href.indexOf("t.me/tenderlex_bot") !== -1 || href.indexOf("t.me/lexelence") !== -1) {
              goal = "telegram_click";
            } else if (href.indexOf("mailto:") === 0) {
              goal = "email_click";
            }
            if (goal) {
              ym(${JSON.stringify(counterId)}, "reachGoal", goal, { page: location.pathname, href: href });
            }
          });
        `}
      </Script>
      <noscript>
        <div>
          <img src={`https://mc.yandex.ru/watch/${encodeURIComponent(counterId)}`} style={{ position: "absolute", left: "-9999px" }} alt="" />
        </div>
      </noscript>
    </>
  );
}
