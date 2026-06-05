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
    "TenderLex анализирует закупочную документацию и находит поставщиков с email, телефонами и сайтами. Можно попробовать бесплатно в Telegram.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    url: siteUrl,
    title: "TenderLex - анализ закупок и поиск поставщиков",
    description:
      "Отправьте документы для анализа или ТЗ для поиска поставщиков. Можно бесплатно попробовать оба сценария в Telegram.",
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
