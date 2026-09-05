import type { Metadata } from "next";
import Link from "next/link";
import { ShieldCheck, CheckCircle2, FileText, Send, Building2, Sparkles } from "lucide-react";
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
  title: "Поиск поставщиков для тендеров и коммерческих закупок",
  description:
    "Быстрый поиск надежных поставщиков под тендеры 44-ФЗ, 223-ФЗ и коммерческие закупки, контакты дилеров и экспресс-оценка себестоимости до подачи заявки.",
  keywords: [
    "поиск поставщиков для тендера",
    "поставщики под 44-ФЗ",
    "поставщики под 223-ФЗ",
    "коммерческие закупки",
    "подбор контрагентов для закупки",
    "TenderLex",
  ],
  alternates: {
    canonical: "/poisk-postavshchikov-dlya-tendera",
  },
};

const pagePath = "/poisk-postavshchikov-dlya-tendera";

const faqItems: FaqItem[] = [
  {
    question: "Как TenderLex помогает тендерным специалистам при подготовке заявки?",
    answer:
      "Сервис быстро собирает базу официальных дилеров и заводов под извещение закупки (44-ФЗ, 223-ФЗ, коммерческие торги), извлекает контакты и готовит запрос КП для точного расчета маржинальности участия.",
  },
  {
    question: "Учитываются ли требования национального режима?",
    answer:
      "Да, система анализирует необходимость подтверждения страны происхождения по Постановлениям № 616 и № 617 и выделяет производителей из реестра Минпромторга РФ (ГИСП).",
  },
];

export default function PoiskPostavshchikovDlyaTenderaPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Поиск поставщиков для тендера", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Поиск поставщиков для тендера",
    description: "Сервис подбора поставщиков под закупки 44-ФЗ, 223-ФЗ и коммерческие торги.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как подобрать поставщиков под тендер",
    description: "Пошаговый процесс подбора контрагентов под тендерную заявку.",
    steps: [
      { name: "Загрузка извещения или ТЗ закупки", text: "Передайте файл или номер закупки." },
      { name: "Смысловой анализ требований", text: "ИИ выделяет критические параметры и стандарты." },
      { name: "Формирование пула дилеров", text: "Сбор контактов с подтвержденным опытом поставок." },
      { name: "Запрос цен для расчета заявки", text: "Готовое письмо для расчета себестоимости." },
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
              <span>Подбор поставщиков: 44-ФЗ, 223-ФЗ и коммерческие торги</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Поиск поставщиков для тендеров, госзакупок и коммерческих торгов
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Быстрый подбор прямых заводов и официальных дилеров под требования конкурсной документации для точного просчета себестоимости заявки.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Найти под тендер</span>
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
                <h3 className="text-lg font-black text-slate-900">Точный расчет НМЦК</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Сбор актуальных коммерческих предложений для формирования конкурентной цены заявки.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Соблюдение Нацрежима</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Проверка товаров по ПП 616 и ПП 617, подбор заводов с действующими реестровыми номерами ГИСП.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Сжатые сроки подготовки</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Выход на контакты лиц, принимающих решения, за 3 минуты вместо дней ручного обзвона.
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
