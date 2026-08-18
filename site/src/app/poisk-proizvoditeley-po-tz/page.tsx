import type { Metadata } from "next";
import Link from "next/link";
import { Building2, CheckCircle2, FileText, Send, ArrowRight, Sparkles, Factory } from "lucide-react";
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
  title: "Поиск заводов-производителей по ТЗ — база изготовителей РФ — TenderLex",
  description:
    "Прямой выход на российские заводы и официальных дилеров по спецификации закупки. Извлечение direct email, контактов отделов сбыта без посредников.",
  keywords: [
    "поиск производителей по ТЗ",
    "база заводов изготовителей",
    "найти завод по спецификации",
    "прямые контакты производителей",
    "TenderLex",
  ],
  alternates: {
    canonical: "/poisk-proizvoditeley-po-tz",
  },
};

const pagePath = "/poisk-proizvoditeley-po-tz";

const faqItems: FaqItem[] = [
  {
    question: "Как TenderLex отличает завод-изготовитель от перекупщика?",
    answer:
      "Алгоритм анализирует производственные мощности, сертификаты соответствия ГОСТ/ТУ, каталоги готовой продукции и структуру предприятия, фильтруя посредников и оставляя реальных изготовителей.",
  },
  {
    question: "Какие контактные данные заводов предоставляет сервис?",
    answer:
      "Вы получаете прямые email-адреса отделов оптовых продаж, телефоны специалистов по сбыту, официальный сайт предприятия и юридические реквизиты.",
  },
  {
    question: "Сколько времени занимает поиск производителей по ТЗ?",
    answer:
      "Обработка спецификации и формирование выборки занимает от 1 до 3 минут в личном кабинете или в Telegram-боте.",
  },
];

export default function PoiskProizvoditeleyPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Поиск заводов-производителей", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Поиск заводов-производителей по ТЗ",
    description: "Сервис поиска прямых контактов заводов-изготовителей по спецификации.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как найти производителей по ТЗ",
    description: "Пошаговый процесс поиска заводов-изготовителей.",
    steps: [
      { name: "Загрузка спецификации", text: "Загрузите файл ТЗ или описание номенклатуры." },
      { name: "ИИ-анализ стандартов", text: "Система выделяет марки, ГОСТы и технические параметры." },
      { name: "Подбор заводов", text: "Формирование реестра прямых изготовителей по РФ." },
      { name: "Генерация запроса КП", text: "Готовое письмо для отправки на заводы." },
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
              <Factory size={14} className="text-teal-600" />
              <span>Прямой выход на производственные предприятия РФ</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Поиск заводов-производителей по ТЗ и спецификациям
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Мгновенный сбор прямых e-mail адресов и телефонов отделов сбыта отечественных заводов без переплат посредникам и трейдерам.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Найти заводы</span>
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
                <h3 className="text-lg font-black text-slate-900">Без посредников</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Экономия до 30% бюджета за счет прямых отпускных цен производственных площадок.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Проверка сертификации</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Сопоставление номенклатуры с действующими паспортами качества, ГОСТами и ТР ТС.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Единый запрос цен</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Автоматическая генерация официального письма RFQ с таблицей позиций и дедлайном.
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
