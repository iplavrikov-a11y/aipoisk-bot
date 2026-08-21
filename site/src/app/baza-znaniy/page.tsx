import type { Metadata } from "next";
import { BookOpen, Sparkles, ShieldCheck } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { buildBreadcrumbJsonLd } from "@/lib/seo";
import { KnowledgeBaseHubClient } from "@/components/knowledge-base-hub-client";
import { KNOWLEDGE_ARTICLES } from "@/data/knowledge-base";

export const metadata: Metadata = {
  title: "База знаний по закупкам, подбору поставщиков и 44-ФЗ",
  description:
    "Экспертные руководства, практические алгоритмы и чек-листы для отделов снабжения и участников тендеров: поиск заводов по ТЗ, аудит рисков 44-ФЗ/223-ФЗ, нацрежим Минпромторга, расчет НМЦК и проверка контрагентов.",
  alternates: {
    canonical: "/baza-znaniy",
  },
  openGraph: {
    type: "website",
    url: "/baza-znaniy",
    title: "База знаний и руководства по закупкам | TenderLex",
    description:
      "Инструкции и руководства по подбору поставщиков, разбору ТЗ и анализу закупок.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

export default function KnowledgeBaseHubPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "База знаний", item: "https://tenderlex.ru/baza-znaniy" },
  ]);

  const collectionSchema = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: "База знаний TenderLex по закупкам и подбору поставщиков",
    description:
      "Коллекция экспертных материалов, чек-листов и инструкций по закупкам 44-ФЗ, 223-ФЗ и коммерческому снабжению.",
    url: "https://tenderlex.ru/baza-znaniy",
    hasPart: KNOWLEDGE_ARTICLES.map((art) => ({
      "@type": "TechArticle",
      name: art.title,
      description: art.description,
      url: `https://tenderlex.ru/baza-znaniy/${art.slug}`,
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(collectionSchema) }}
      />

      <main className="bg-[#f6f8f7] text-[#172120] min-h-screen font-sans">
        <SiteHeader />

        {/* HERO SECTION */}
        <section className="relative overflow-hidden pt-12 pb-16 sm:pt-16 sm:pb-20 border-b border-[#d8e3e1] bg-gradient-to-b from-[#e5f4f3]/60 via-[#f6f8f7] to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6 text-center space-y-5">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-[#b8c8c5] text-[#075b63] text-xs font-black uppercase tracking-wider shadow-2xs">
              <BookOpen size={14} className="text-[#075b63]" />
              <span>Экспертная база знаний закупщика</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-[#172120] tracking-tight max-w-4xl mx-auto leading-tight">
              База знаний по закупкам, подбору поставщиков и 44-ФЗ
            </h1>

            <p className="text-[#2f3f3d] text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Пошаговые алгоритмы для специалистов по снабжению и тендерам: выход на заводы-изготовители по ТЗ, расчет НМЦК, применение нацрежима Минпромторга, сопоставление номенклатуры и снижение логистических издержек.
            </p>
          </div>
        </section>

        {/* MAIN ARTICLES CATALOG */}
        <section className="py-12 sm:py-16 border-b border-[#d8e3e1] bg-white">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <KnowledgeBaseHubClient />
          </div>
        </section>

        <ContactSection />
        <SiteFooter />
      </main>
    </>
  );
}
