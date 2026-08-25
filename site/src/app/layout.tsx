import { ChatWidget } from '@/components/chat-widget';
import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import type { ReactNode } from "react";

import {
  buildOrganizationJsonLd,
  buildSoftwareApplicationJsonLd,
  normalizedSiteUrl,
} from "@/lib/seo";

import "./globals.css";
import { YandexMetrika } from "./yandex-metrika";

const inter = Inter({
  subsets: ["cyrillic", "latin"],
  variable: "--font-body",
  display: "swap",
});

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-heading",
  display: "swap",
});

const siteUrl = normalizedSiteUrl();
const defaultTitle = "TenderLex — поиск поставщиков и анализ любых закупок";
const defaultDescription =
  "TenderLex — онлайн-сервис поиска поставщиков и производителей по ТЗ, ГОСТ и спецификациям. Готовый реестр прямых контактов с проверкой ИНН, оценка рисков закупок и проектов контрактов 44-ФЗ и 223-ФЗ за 2 минуты.";
const defaultOgImage = "/tenderlex-product-preview.png";
const yandexMetrikaId = process.env.TENDERLEX_YANDEX_METRIKA_ID?.trim();
const googleSiteVerification = process.env.TENDERLEX_GOOGLE_SITE_VERIFICATION?.trim();
const yandexVerification = process.env.TENDERLEX_YANDEX_VERIFICATION?.trim();
const verification = {
  ...(googleSiteVerification ? { google: googleSiteVerification } : {}),
  ...(yandexVerification ? { yandex: yandexVerification } : {}),
};

const orgSchema = buildOrganizationJsonLd();
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

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ru" className={`${inter.variable} ${plusJakartaSans.variable}`}>
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
      <body>
        {children}
        <div className="global-legal-link">
          <a href="/legal">Правовая информация</a>
        </div>
        <YandexMetrika counterId={yandexMetrikaId} />
        <ChatWidget />
      </body>
    </html>
  );
}
