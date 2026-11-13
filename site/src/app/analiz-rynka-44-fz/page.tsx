import { PublicSiteLink } from "@/components/public-site-link";
import type { Metadata } from "next";
import Link from "next/link";
import { TrendingUp, CheckCircle2, FileText, Send, Building2, Sparkles, Calculator } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { ProcurementCalculator } from "@/components/procurement-calculator";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildHowToJsonLd,
  buildServiceJsonLd,
  type FaqItem,
} from "@/lib/seo";

export const metadata: Metadata = {
  title: "Анализ рынка 44-ФЗ и расчет НМЦК онлайн",
  description:
    "Анализ рынка для закупки по 44-ФЗ: поиск потенциальных поставщиков, проект запроса КП и калькулятор для предварительного сопоставления цен.",
  keywords: [
    "анализ рынка 44-ФЗ",
    "исследование рынка для закупки",
    "проверка цен поставщиков",
    "обоснование НМЦК",
    "калькулятор нмцк 44 фз",
    "калькулятор нмцк скачать бесплатно",
    "расчет нмцк метод сопоставимых цен",
    "TenderLex",
  ],
  alternates: {
    canonical: "/analiz-rynka-44-fz",
  },
};

const pagePath = "/analiz-rynka-44-fz";

const faqItems: FaqItem[] = [
  {
    question: "Как TenderLex помогает проанализировать рынок перед торгами?",
    answer:
      "Сервис помогает разобрать номенклатуру, найти кандидатов на поставку и подготовить проект запроса цен. Актуальность контактов, статус компании и условия предложения подтвердите отдельно.",
  },
  {
    question: "Как рассчитать НМЦК методом анализа рынка по 44-ФЗ?",
    answer:
      "При расчёте НМЦК учитывайте требования конкретной закупки и применимые методические рекомендации. TenderLex помогает подготовить перечень вопросов и проект запроса КП; достаточность и независимость ценовых предложений оценивает заказчик или профильный специалист.",
  },
  {
    question: "Как выявить закупку «под одного поставщика» по характеристикам ТЗ?",
    answer:
      "Сопоставление параметров помогает заметить узкие или необычные характеристики, которые стоит проверить. Вывод сервиса не подтверждает ограничение конкуренции и сам по себе не является основанием для обращения в контролирующий орган.",
  },
  {
    question: "Помогает ли сервис при подборе российских аналогов по ПП 719?",
    answer:
      "Сервис помогает найти кандидатов и сведения для проверки. Применимость национального режима, наличие конкретной модели в реестре и документы о происхождении проверяйте по извещению и официальному реестру.",
  },
];

export default function AnalizRynkaPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Анализ рынка 44-ФЗ", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Анализ рынка 44-ФЗ",
    description: "Сервис исследования рынка поставщиков и оценки конкуренции для госзакупок.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как провести анализ рынка по спецификации ТЗ",
    description: "Пошаговый процесс оценки конкурентной среды перед подачей заявки.",
    steps: [
      { name: "Загрузка спецификации или номенклатуры ТЗ", text: "Передайте перечень закупаемой продукции." },
      { name: "Определение списка кандидатов", text: "Поиск производителей и поставщиков, подходящих для дальнейшей проверки." },
      { name: "Сбор доступных контактов", text: "Контакты для уточнения цены, наличия и условий у компании." },
      { name: "Сопоставление предложений", text: "Сравните полученные предложения с требованиями закупки и расчётом НМЦК." },
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
              <TrendingUp size={14} className="text-teal-600" />
              <span>Оценка конкурентной среды и цен</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Анализ рынка и поставщиков для госзакупок 44-ФЗ
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Поиск потенциальных производителей и поставщиков по номенклатуре закупки, чтобы запросить цены и проверить условия до подачи заявки.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet?scenario=supplier_search"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Проанализировать рынок</span>
              </a>
              <PublicSiteLink
                channel="bot"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-extrabold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
              >
                <Send size={16} className="text-teal-600" />
                <span>Запустить в Telegram</span>
              </PublicSiteLink>
            </div>
          </div>
        </section>

        {/* BENEFITS */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Выявление монополий</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Определение закупок с «заточенным» ТЗ под единственного производителя до подачи заявки.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Пул официальных дилеров</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Сбор контактов нескольких независимых поставщиков для получения конкурентных скидок.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Сравнение аналогов</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Поиск эквивалентных решений, соответствующих ГОСТ/ТУ, для снижения себестоимости.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* CALCULATOR */}
        <section className="py-16 sm:py-20 border-b border-slate-200 bg-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-2xl mx-auto mb-10 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
                Калькулятор экономии и НМЦК
              </span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                Оценка снижения себестоимости и расчета НМЦК
              </h2>
              <p className="text-slate-600 text-sm">
                Рассчитайте потенциал экономии бюджета и окупаемость поиска прямых производителей.
              </p>
            </div>
            <ProcurementCalculator />
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
