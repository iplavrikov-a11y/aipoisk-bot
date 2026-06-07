import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";
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

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "TenderLex - анализ закупок и поиск поставщиков",
    template: "%s | TenderLex",
  },
  description:
    "TenderLex анализирует закупочную документацию, показывает риски и подбирает поставщиков для запроса КП. Работать можно на сайте или в Telegram.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    url: siteUrl,
    title: "TenderLex - анализ закупок и поиск поставщиков",
    description:
      "Отправьте номер извещения, документы или ТЗ. TenderLex подготовит анализ закупки или подбор поставщиков на сайте и в Telegram.",
    siteName: "TenderLex",
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
      <body>{children}</body>
    </html>
  );
}
