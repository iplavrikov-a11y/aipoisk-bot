"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";

const METRIKA_ALLOWED_PATHS = new Set([
  "/",
  "/analiz-zakupochnoi-dokumentacii",
  "/poisk-postavshchikov-po-tz",
  "/reestr-minpromtorga-v-zakupkah",
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
