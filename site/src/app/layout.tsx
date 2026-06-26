import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";
import type { ReactNode } from "react";

import "./globals.css";
import { YandexMetrika } from "./yandex-metrika";

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
const defaultTitle = "TenderLex - поиск поставщиков под спецификацию";
const defaultDescription =
  "TenderLex находит компании под закупочную задачу, проверяет контакты, помогает подготовить запрос цены и разобрать условия закупки.";
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
  keywords: [
    "TenderLex",
    "поиск поставщиков",
    "подбор поставщиков",
    "поиск поставщиков по ТЗ",
    "поиск поставщиков по техническому заданию",
    "поиск поставщиков под спецификацию",
    "запрос цены поставщику",
    "анализ закупок",
    "анализ закупочной документации",
    "тендерная документация",
    "реестр Минпромторга",
  ],
  alternates: {
    canonical: "/",
  },
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
    <html lang="ru" className={`${manrope.variable} ${inter.variable}`}>
      <body>
        {children}
        <YandexMetrika counterId={yandexMetrikaId} />
      </body>
    </html>
  );
}
