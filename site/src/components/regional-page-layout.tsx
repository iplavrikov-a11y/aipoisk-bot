import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { Building2, CheckCircle2, ArrowRight, MapPin, Send, Sparkles, Phone } from "lucide-react";
import type { FaqItem } from "@/lib/seo";

interface RegionalPageLayoutProps {
  regionName: string;
  regionDistrict?: string;
  regionGenitive?: string;
  headline?: string;
  description: string;
  keyIndustries?: string[];
  features?: string[];
  industrialSpecialties?: { title: string; desc: string }[];
  faqItems?: FaqItem[];
  breadcrumbSchema: object;
  serviceSchema: object;
  faqSchema?: object;
  howToSchema?: object;
}

export function RegionalPageLayout({
  regionName,
  regionDistrict,
  regionGenitive = regionName,
  headline = `Поиск производителей и поставщиков по ТЗ в ${regionName}`,
  description,
  keyIndustries = [],
  features = [],
  industrialSpecialties = [],
  faqItems = [],
  breadcrumbSchema,
  serviceSchema,
  faqSchema,
  howToSchema,
}: RegionalPageLayoutProps) {
  const displayIndustries = keyIndustries.length > 0
    ? keyIndustries
    : features.length > 0
    ? features
    : industrialSpecialties.map((s) => `${s.title}: ${s.desc}`);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceSchema) }} />
      {faqSchema && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }} />
      )}
      {howToSchema && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(howToSchema) }} />
      )}

      <main className="bg-slate-50 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

        {/* HERO */}
        <section className="relative pt-12 pb-20 border-b border-slate-200 bg-gradient-to-b from-teal-50/50 via-slate-50 to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-bold uppercase tracking-wider shadow-2xs">
              <MapPin size={14} className="text-teal-600" />
              <span>Региональный подбор поставщиков: {regionDistrict || regionName}</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              {headline}
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-normal leading-relaxed">
              {description}
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Найти поставщиков</span>
                <ArrowRight size={16} />
              </a>
              <a
                href="https://t.me/tenderlex_bot"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-bold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
              >
                <Send size={16} className="text-teal-600" />
                <span>Запустить в Telegram</span>
              </a>
            </div>
          </div>
        </section>

        {/* INDUSTRIES / SPECIALTIES IN REGION */}
        {displayIndustries.length > 0 && (
          <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
            <div className="container max-w-5xl mx-auto px-4 sm:px-6">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 text-center mb-10">
                Ведущие отрасли производства и поставок: {regionName}
              </h2>

              <div className="grid sm:grid-cols-2 gap-6">
                {displayIndustries.map((ind, idx) => (
                  <div key={idx} className="p-6 rounded-3xl bg-slate-50 border-2 border-slate-200 shadow-2xs flex items-start gap-3">
                    <CheckCircle2 size={20} className="text-teal-600 shrink-0 mt-0.5" />
                    <span className="text-sm text-slate-800 font-bold">{ind}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* FAQ */}
        {faqItems.length > 0 && (
          <section className="py-16 sm:py-24 border-b border-slate-200 bg-slate-50">
            <div className="container max-w-4xl mx-auto px-4 sm:px-6">
              <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 text-center mb-12">
                Вопросы о подборе поставщиков в регионе
              </h2>
              <div className="space-y-4">
                {faqItems.map((item, index) => (
                  <details key={index} className="group bg-white p-6 rounded-2xl border-2 border-slate-200 text-left shadow-2xs">
                    <summary className="font-bold text-slate-900 text-base cursor-pointer flex justify-between items-center list-none">
                      <span>{item.question}</span>
                      <span className="transition group-open:rotate-180 text-teal-700">▼</span>
                    </summary>
                    <p className="mt-4 text-sm text-slate-700 font-normal leading-relaxed border-t border-slate-200 pt-4">
                      {item.answer}
                    </p>
                  </details>
                ))}
              </div>
            </div>
          </section>
        )}

        <ContactSection
          title={`Подбор поставщиков: ${regionName}`}
          subtitle={`Загрузите файл ТЗ или спецификации для мгновенного сбора прямых контактов заводов в ${regionGenitive}.`}
        />

        <SiteFooter />
      </main>
    </>
  );
}
