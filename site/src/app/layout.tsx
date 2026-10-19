import { getSiteData } from "@/lib/site-data";
import { PublicSiteSettingsProvider } from "@/lib/public-site-settings";
import { ChatWidget } from '@/components/chat-widget';
import { PublicMotion } from "@/components/public-motion";
import type { Metadata } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";

import {
  buildOrganizationJsonLd,
  buildSoftwareApplicationJsonLd,
  normalizedSiteUrl,
} from "@/lib/seo";

import "./globals.css";
import "./brand-theme.css";
import "./public-redesign.css";
import "@/components/public-motion.css";
import { YandexMetrika } from "./yandex-metrika";

const manrope = localFont({
  src: "./fonts/Manrope.woff2",
  weight: "200 800",
  variable: "--font-body",
  display: "swap",
});

const siteUrl = normalizedSiteUrl();
const defaultTitle = "TenderLex — поиск поставщиков, подбор аналогов и анализ закупок";
const defaultDescription =
  "ИИ-поиск поставщиков по ТЗ, подбор аналогов и анализ закупок 44-ФЗ, 223-ФЗ. Кандидаты для запроса КП и рабочие отчеты с источниками для проверки.";
const defaultOgImage = "/tenderlex-og-1200x630.png";
const yandexMetrikaId = (process.env.TENDERLEX_YANDEX_METRIKA_ID || process.env.YANDEX_METRIKA_COUNTER_ID || "").trim();
const googleSiteVerification = process.env.TENDERLEX_GOOGLE_SITE_VERIFICATION?.trim();
const yandexVerification = process.env.TENDERLEX_YANDEX_VERIFICATION?.trim();
const verification = {
  ...(googleSiteVerification ? { google: googleSiteVerification } : {}),
  ...(yandexVerification ? { yandex: yandexVerification } : {}),
};

const softwareSchema = buildSoftwareApplicationJsonLd();

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: defaultTitle,
    template: "%s | TenderLex",
  },
  description: defaultDescription,
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  alternates: {
    canonical: "./",
  },
  keywords: [
    "TenderLex",
    "поиск поставщиков",
    "подбор поставщиков",
    "поиск поставщиков по ТЗ",
    "поиск поставщиков по техническому заданию",
    "поиск поставщиков под спецификацию",
    "поиск товаров по ТЗ",
    "подбор аналогов по ТЗ",
    "оценка рисков закупок",
    "минпромторг закупки",
    "анализ рисков закупок",
    "риски 44 фз",
    "запрос цены поставщику",
    "анализ закупок",
    "анализ закупочной документации",
    "тендерная документация",
    "реестр Минпромторга",
  ],
  manifest: "/manifest.webmanifest",
  verification: Object.keys(verification).length ? verification : undefined,
  openGraph: {
    type: "website",
    url: siteUrl,
    title: defaultTitle,
    description: "Передайте описание позиции, спецификацию, номер извещения или документы. TenderLex найдет компании, покажет контакты и подготовит основу для первого обращения.",
    siteName: "TenderLex",
    images: [
      {
        url: defaultOgImage,
        width: 1200,
        height: 630,
        alt: "TenderLex - поиск поставщиков под спецификацию",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: defaultTitle,
    description: "Передайте описание позиции, спецификацию, номер извещения или документы. TenderLex найдет компании, покажет контакты и подготовит основу для первого обращения.",
    images: [defaultOgImage],
  },
  icons: {
    icon: [
      { url: "/favicon.svg", sizes: "120x120", type: "image/svg+xml" },
      { url: "/favicon.ico", sizes: "120x120", type: "image/x-icon" },
      { url: "/favicon.png", sizes: "120x120", type: "image/png" },
      { url: "/icon.png", sizes: "120x120", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
};

export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  const data = await getSiteData();
  const orgSchema = buildOrganizationJsonLd({ botUrl: data.bot.telegram_url, contacts: data.contacts });
  return (
    <html lang="ru" className={manrope.variable}>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(orgSchema) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareSchema) }}
        />
        <script
          type="speculationrules"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              prerender: [
                {
                  source: "list",
                  urls: [
                    "/poisk-postavshchikov-po-tz",
                    "/baza-znaniy",
                    "/otrasli",
                    "/regiony",
                    "/analiz-zakupochnoi-dokumentacii",
                  ],
                  eagerness: "moderate",
                },
              ],
              prefetch: [
                {
                  source: "document",
                  where: {
                    and: [
                      { href_matches: "/*" },
                      { not: { href_matches: "/cabinet/*" } },
                      { not: { href_matches: "/api/*" } },
                    ],
                  },
                  eagerness: "conservative",
                },
              ],
            }),
          }}
        />
      </head>
      <body className="tl-theme">
        <PublicMotion />
        <PublicSiteSettingsProvider settings={{ contacts: data.contacts, bot: data.bot }}>
        {children}
        <div className="global-legal-link">
          <a href="/legal">Правовая информация</a>
        </div>
        <YandexMetrika counterId={yandexMetrikaId} />
        <ChatWidget />
        </PublicSiteSettingsProvider>
      </body>
    </html>
  );
}
