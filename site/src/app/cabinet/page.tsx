import type { Metadata } from "next";

import { CabinetClient } from "./cabinet-client";

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

export default function CabinetPage() {
  return <CabinetClient />;
}
