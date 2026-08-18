import type { Metadata } from "next";
import Link from "next/link";
import { Award, CheckCircle2, FileText, Send, Building2, ArrowRight, Sparkles } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildHowToJsonLd,
  buildServiceJsonLd,
  type FaqItem,
} from "@/lib/seo";

export const metadata: Metadata = {
  title: "Реестр Минпромторга в закупках — проверка ПП 616 и 617 — TenderLex",
  description:
    "Проверка товаров и производителей на включение в Реестр российской промышленной продукции Минпромторга (ГИСП), применение нацрежима по 44-ФЗ и 223-ФЗ.",
  keywords: [
    "реестр Минпромторга в закупках",
    "постановление 616 закупки",
    "постановление 617 закупки",
    "проверка реестра ГИСП",
    "TenderLex",
  ],
  alternates: {
    canonical: "/reestr-minpromtorga-v-zakupkah",
  },
};

const pagePath = "/reestr-minpromtorga-v-zakupkah";

const faqItems: FaqItem[] = [
  {
    question: "Как TenderLex проверяет требования Минпромторга?",
    answer:
      "Сервис сопоставляет код ОКПД2 и характеристики товара из ТЗ с перечнями Постановлений Правительства № 616 (запрет) и № 617 (ограничения), выявляя необходимость предоставления реестровых номеров ГИСП.",
  },
  {
    question: "Помогает ли сервис найти российских производителей с реестровыми записями?",
    answer:
      "Да, TenderLex выделяет отечественные заводы, чья продукция официально внесена в реестр Минпромторга РФ и реестр ЕАЭС.",
  },
];

export default function ReestrMinpromtorgaPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Реестр Минпромторга в закупках", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Проверка Реестра Минпромторга в закупках",
    description: "Сервис экспресс-аудита требований национального режима (ПП 616/617) по ТЗ.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как проверить требования Минпромторга по ТЗ",
    description: "Пошаговый процесс проверки национального режима в госзакупках.",
    steps: [
      { name: "Загрузка спецификации или кода ОКПД2", text: "Передайте параметры товара." },
      { name: "Проверка наличия в перечнях ПП 616 и 617", text: "Анализ запретов и ограничений допуска." },
      { name: "Поиск производителей с реестровыми номерами ГИСП", text: "Сбор заводов с действующими выписками." },
      { name: "Формирование обоснованного запроса КП", text: "Готовое обращение с запросом реестровых номеров." },
    ],
  });

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaBreadcrumb) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaService) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaFaq) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaHowTo) }} />

      <main className="bg-slate-50/60 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

        {/* HERO */}
        <section className="relative overflow-hidden pt-12 pb-20 border-b border-slate-200/90 bg-gradient-to-b from-teal-50/60 via-slate-50 to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-black uppercase tracking-wider shadow-2xs">
              <Award size={14} className="text-teal-600" />
              <span>Национальный режим и Реестр ГИСП</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Проверка Реестра Минпромторга и нацрежима в закупках
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Узнайте, попадает ли ваша номенклатура под Постановления № 616, № 617 и найдите российских производителей с действующими выписками из ГИСП.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Проверить по реестру</span>
                <ArrowRight size={16} />
              </a>
              <a
                href="https://t.me/tenderlex_bot"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-extrabold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
              >
                <Send size={16} className="text-teal-600" />
                <span>Запустить в Telegram</span>
              </a>
            </div>
          </div>
        </section>

        {/* BENEFITS */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Постановление № 616</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Аудит полного запрета на допуск промышленных товаров иностранного происхождения.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Постановление № 617</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Контроль применения правила «третий лишний» и подтверждения страны происхождения.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Заводы с реестровыми номерами</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Прямые контакты изготовителей, чья продукция имеет действующее заключение Минпромторга.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-slate-50">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6">
            <h2 className="text-2xl sm:text-4xl font-black text-slate-900 text-center mb-12">
              Часто задаваемые вопросы
            </h2>
            <div className="space-y-4">
              {faqItems.map((item, index) => (
                <details key={index} className="group bg-white p-6 rounded-2xl border-2 border-slate-200 text-left shadow-2xs">
                  <summary className="font-bold text-slate-900 text-base cursor-pointer flex justify-between items-center list-none">
                    <span>{item.question}</span>
                    <span className="transition group-open:rotate-180 text-teal-700">▼</span>
                  </summary>
                  <p className="mt-4 text-sm text-slate-700 font-medium leading-relaxed border-t border-slate-200 pt-4">
                    {item.answer}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <ContactSection />

        <SiteFooter />
      </main>
    </>
  );
}
