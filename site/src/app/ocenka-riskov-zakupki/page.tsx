import type { Metadata } from "next";
import Link from "next/link";
import { ShieldCheck, CheckCircle2, FileText, Send, Building2, ShieldAlert } from "lucide-react";
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
  title: "Оценка рисков закупок: 44-ФЗ, 223-ФЗ и коммерческие торги",
  description:
    "Автоматическая оценка рисков закупок и проектов контрактов 44-ФЗ, 223-ФЗ: выявление скрытых штрафов, невыполнимых сроков поставки и условий приемки за 2 минуты.",
  keywords: [
    "оценка рисков закупок",
    "оценка рисков закупки",
    "проверка рисков 44-ФЗ",
    "риски 44 фз",
    "риск закупки 44 фз",
    "анализ рисков закупок",
    "риски 223-ФЗ",
    "коммерческие торги",
    "риски исполнения контракта",
    "TenderLex",
  ],
  alternates: {
    canonical: "/ocenka-riskov-zakupki",
  },
};

const pagePath = "/ocenka-riskov-zakupki";

const faqItems: FaqItem[] = [
  {
    question: "Как оценка рисков закупок помогает поставщикам?",
    answer:
      "Она позволяет вовремя отказаться от заведомо токсичных или неисполнимых контрактов в госзакупках и коммерческих торгах, где заказчик установил невыполнимые сроки или скрытые штрафы.",
  },
  {
    question: "Сколько времени занимает проверка?",
    answer:
      "Анализ проекта контракта и спецификации занимает от 1 до 3 минут в кабинете или Telegram-боте.",
  },
];

export default function OcenkaRisktovZakupkiPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Оценка рисков закупок", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Оценка рисков закупок",
    description: "Сервис экспресс-оценки рисков исполнения контрактов 44-ФЗ, 223-ФЗ и коммерческих закупок.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как оценить риски закупки перед подачей заявки",
    description: "Пошаговый аудит рисков проекта контракта через TenderLex.",
    steps: [
      { name: "Загрузка проекта контракта", text: "Передайте файл проекта договора или извещения." },
      { name: "Смысловой ИИ-разбор спорных пунктов", text: "Анализ условий приемки, сроков и штрафов." },
      { name: "Формирование отчета об исполнимости", text: "Выгрузка детальной сводки с рекомендациями." },
      { name: "Принятие решения об участии", text: "Обоснованный выход на торги или запрос разъяснений." },
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
              <ShieldCheck size={14} className="text-teal-600" />
              <span>Защита от риска срыва контракта и РНП</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Оценка рисков закупок, госконтрактов 44-ФЗ и коммерческих договоров
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Проверьте условия оплаты, график поставки, скрытые штрафы и ограничения нацрежима до того, как внесете обеспечение заявки.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Оценить риски</span>
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

        {/* FEATURES */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Проверка сроков приемки</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Контроль соответствия между сроком поставки товара и сроком работы приемочной комиссии заказчика.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Обеспечительные платежи</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Анализ требований к гарантийным обязательствам, независимым гарантиям и удержаниям.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Вопросы заказчику</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Готовые формулировки запросов на разъяснение положений извещения в единой информационной системе.
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
