import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";
import Script from "next/script";
import type { ReactNode } from "react";

import "./globals.css";

const manrope = Manrope({
  subsets: ["cyrillic", "latin"],
  variable: "--font-display",
  weight: ["600", "700", "800"],
  display: "swap",
});

const inter = Inter({
  subsets: ["cyrillic", "latin"],
  variable: "--font-body",
  display: "swap",
});

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://tenderlex.ru";
const defaultTitle = "TenderLex - анализ закупок и поиск поставщиков";
const defaultDescription =
  "TenderLex анализирует закупочную документацию, показывает риски и подбирает поставщиков для запроса КП. Работать можно на сайте или в Telegram.";
const defaultOgImage = "/tenderlex-product-preview.png";
const yandexMetrikaId = process.env.TENDERLEX_YANDEX_METRIKA_ID?.trim();
const googleSiteVerification = process.env.TENDERLEX_GOOGLE_SITE_VERIFICATION?.trim();
const yandexVerification = process.env.TENDERLEX_YANDEX_VERIFICATION?.trim();
const verification = {
  ...(googleSiteVerification ? { google: googleSiteVerification } : {}),
  ...(yandexVerification ? { yandex: yandexVerification } : {}),
};

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: defaultTitle,
    template: "%s | TenderLex",
  },
  description: defaultDescription,
  alternates: {
    canonical: "/",
  },
  verification: Object.keys(verification).length ? verification : undefined,
  openGraph: {
    type: "website",
    url: siteUrl,
    title: defaultTitle,
    description: "Отправьте номер извещения, документы или ТЗ. TenderLex подготовит анализ закупки или подбор поставщиков на сайте и в Telegram.",
    siteName: "TenderLex",
    images: [
      {
        url: defaultOgImage,
        width: 1200,
        height: 630,
        alt: "TenderLex - анализ закупок и поиск поставщиков",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: defaultTitle,
    description: "Отправьте номер извещения, документы или ТЗ. TenderLex подготовит анализ закупки или подбор поставщиков на сайте и в Telegram.",
    images: [defaultOgImage],
  },
  icons: {
    icon: "/tenderlex-logo.png",
    shortcut: "/tenderlex-logo.png",
    apple: "/tenderlex-logo.png",
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ru" className={`${manrope.variable} ${inter.variable}`}>
      <body>
        {children}
        <YandexMetrika counterId={yandexMetrikaId} />
      </body>
    </html>
  );
}

function YandexMetrika({ counterId }: { counterId?: string }) {
  if (!counterId) {
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
