import type { Metadata } from "next";

import { getSiteData } from "@/lib/site-data";
import { CabinetClient } from "./cabinet-client";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Личный кабинет",
  robots: {
    index: false,
    follow: false,
  },
  alternates: {
    canonical: "/cabinet",
  },
  openGraph: {
    type: "website",
    url: "/cabinet",
    title: "Личный кабинет | TenderLex",
    description: "Личный кабинет TenderLex для анализа закупок и поиска поставщиков.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Личный кабинет | TenderLex",
    description: "Личный кабинет TenderLex для анализа закупок и поиска поставщиков.",
    images: ["/tenderlex-product-preview.png"],
  },
};

export default async function CabinetPage() {
  const siteData = await getSiteData();
  const initialTrialBalanceRub = Math.max(0, siteData.trial?.balance_rub ?? 495);
  return <CabinetClient initialTrialBalanceRub={initialTrialBalanceRub} />;
}
