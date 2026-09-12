import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { CheckCircle2, Layers, FileSpreadsheet, Building, Sparkles } from "lucide-react";
import type { FaqItem } from "@/lib/seo";

interface IndustryPageLayoutProps {
  categoryTitle: string;
  badge: string;
  headline: string;
  description: string;
  nomenclatures: string[];
  steps: { name: string; text: string }[];
  faqItems: FaqItem[];
  breadcrumbSchema: object;
  serviceSchema: object;
  faqSchema: object;
  howToSchema: object;
}

export function IndustryPageLayout({
  categoryTitle,
  badge,
  headline,
  description,
  nomenclatures,
  steps,
  faqItems,
  breadcrumbSchema,
  serviceSchema,
  faqSchema,
  howToSchema,
}: IndustryPageLayoutProps) {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(howToSchema) }} />

      <main className="bg-slate-50 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

        {/* HERO */}
        <section className="relative pt-12 pb-20 border-b border-slate-200 bg-gradient-to-b from-teal-50/50 via-slate-50 to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <div className="space-y-6">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-bold uppercase tracking-wider shadow-2xs">
                <Layers size={14} className="text-teal-600" />
                <span>{badge}</span>
              </div>

              <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight max-w-4xl leading-tight">
                {headline}
              </h1>

              <p className="text-slate-600 text-base sm:text-lg max-w-2xl font-normal leading-relaxed">
                {description}
              </p>

              <div className="flex flex-col sm:flex-row gap-4 pt-2">
                <a
                  href="/cabinet"
                  className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
                >
                  <span>Найти поставщиков</span>
                </a>
                <a
                  href="https://t.me/tenderlex_bot"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-bold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
                >
                  <span>Запустить @tenderlex_bot</span>
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* NOMENCLATURE CHECKLIST */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mb-8">
              Распознаваемая номенклатура и стандарты: {categoryTitle}
            </h2>

            <div className="grid sm:grid-cols-2 gap-4">
              {nomenclatures.map((nom, idx) => (
                <div key={idx} className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex items-start gap-3">
                  <CheckCircle2 size={18} className="text-teal-600 shrink-0 mt-0.5" />
                  <span className="text-xs text-slate-800 font-medium">{nom}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* HOW TO PIPELINE */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-slate-50">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mb-8 text-center">
              Порядок подбора поставщиков под спецификацию
            </h2>

            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {steps.map((s, idx) => (
                <div key={idx} className="p-6 rounded-3xl bg-white border-2 border-slate-200 text-center shadow-2xs">
                  <span className="text-2xl font-black text-teal-600 block mb-2">0{idx + 1}</span>
                  <h3 className="text-base font-bold text-slate-900 mb-2">{s.name}</h3>
                  <p className="text-xs text-slate-600 leading-relaxed font-normal">{s.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* FAQ ACCORDION */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6">
            <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 text-center mb-12">
              Часто задаваемые вопросы
            </h2>
            <div className="space-y-4">
              {faqItems.map((item, index) => (
                <details key={index} className="group bg-slate-50 p-6 rounded-2xl border-2 border-slate-200 text-left shadow-2xs">
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

        {/* CROSS-LINKING: ПОДБОР АНАЛОГОВ ПО ТЗ */}
        <section className="py-12 bg-slate-50 border-b border-slate-200">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <div className="p-8 rounded-3xl bg-gradient-to-br from-teal-900 to-slate-900 text-white shadow-xl flex flex-col md:flex-row items-center justify-between gap-6">
              <div className="space-y-2 max-w-xl text-left">
                <span className="text-xs font-bold text-teal-300 uppercase tracking-wider bg-teal-400/20 px-3 py-1 rounded-full border border-teal-400/30 inline-block">
                  Подбор эквивалентов
                </span>
                <h3 className="text-xl sm:text-2xl font-extrabold text-white">
                  Требуется подобрать отечественные аналоги по спецификации?
                </h3>
                <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                  ИИ TenderLex выявит скрытого производителя по параметрам номенклатуры {categoryTitle}, сопоставит рабочие диапазоны по ГОСТ и паспортам заводов РФ и подберет эквиваленты из реестра Минпромторга (ГИСП).
                </p>
              </div>
              <Link
                href="/podbor-tovara-i-analogov-po-tz"
                className="shrink-0 px-6 py-3.5 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 font-black text-xs shadow-md transition-all hover:scale-102"
              >
                Подобрать аналоги по ТЗ →
              </Link>
            </div>
          </div>
        </section>

        <ContactSection
          title={`Подбор поставщиков: ${categoryTitle}`}
          subtitle="Загрузите спецификацию в кабинет или Telegram-бот TenderLex для получения прямых контактов заводов."
        />

        <SiteFooter />
      </main>
    </>
  );
}
