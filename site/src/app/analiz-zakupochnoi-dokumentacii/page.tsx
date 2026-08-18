import type { Metadata } from "next";
import Link from "next/link";
import { ShieldAlert, CheckCircle2, FileText, Send, Building2, ArrowRight, Sparkles } from "lucide-react";
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
  title: "Анализ закупочной документации 44-ФЗ и 223-ФЗ — проверка рисков ТЗ — TenderLex",
  description:
    "Автоматический экспресс-аудит проекта контракта и ТЗ: выявление скрытых штрафов, сжатых сроков, нетипичных требований к обеспечению и ограничений нацрежима.",
  keywords: [
    "анализ закупочной документации",
    "проверка проекта контракта 44-ФЗ",
    "аудит рисков закупки",
    "анализ ТЗ госконтракта",
    "TenderLex",
  ],
  alternates: {
    canonical: "/analiz-zakupochnoi-dokumentacii",
  },
};

const pagePath = "/analiz-zakupochnoi-dokumentacii";

const faqItems: FaqItem[] = [
  {
    question: "Какие риски выявляет модуль анализа документации?",
    answer:
      "Сервис анализирует несоответствие сроков поставки и приемки, кабальные штрафные санкции, отсутствие аванса, завышенные требования к банковским гарантиям и ограничения нацрежима (ПП 616/617).",
  },
  {
    question: "Помогает ли сервис составить запрос на разъяснение положений извещения?",
    answer:
      "Да. При обнаружении противоречий TenderLex готовит юридически выверенные формулировки запросов заказчику для публикации в ЕИС.",
  },
];

export default function AnalizZakupochnoiDokumentaciiPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Анализ закупочной документации", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Анализ закупочной документации",
    description: "Сервис экспресс-аудита рисков условий контрактов 44-ФЗ и 223-ФЗ.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как проверить закупочную документацию",
    description: "Пошаговый процесс экспресс-аудита рисков госконтракта.",
    steps: [
      { name: "Загрузка проекта контракта", text: "Передайте файл извещения или проект договора." },
      { name: "Смысловой ИИ-анализ условий", text: "Аудит сроков, штрафов и обеспечения." },
      { name: "Формирование отчета о рисках", text: "Выгрузка сводки с оценкой критичности." },
      { name: "Подготовка запроса разъяснений", text: "Готовые формулировки для обращения в ЕИС." },
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
              <ShieldAlert size={14} className="text-teal-600" />
              <span>Экспресс-аудит проекта контракта за 60 секунд</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Анализ закупочной документации и рисков 44-ФЗ / 223-ФЗ
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Выявите скрытые штрафы, невыполнимые сроки поставки и ловушки заказчика до подачи заявки на участие в торгах.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Проверить документацию</span>
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
                <h3 className="text-lg font-black text-slate-900">Защита от РНП</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Отказ от заведомо неисполнимых контрактов до блокировки средств обеспечения заявки.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Контроль штрафов</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Проверка соответствия санкций Постановлению № 1042 и выявление незаконных удержаний.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Запросы заказчику</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Автоматическая подготовка текста запроса на разъяснение положений извещения.
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
