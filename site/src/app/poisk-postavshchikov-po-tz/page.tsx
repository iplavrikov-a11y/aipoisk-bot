import type { Metadata } from "next";
import Link from "next/link";
import { Search, CheckCircle2, FileText, Send, Building2, Sparkles } from "lucide-react";
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
  title: "Поиск поставщиков и заводов-производителей по ТЗ онлайн",
  description:
    "Поиск поставщиков и производителей по ТЗ, ГОСТ и спецификациям онлайн. Готовый реестр прямых контактов отделов сбыта заводов с проверкой ИНН и запрос КП в 1 клик. Попробуйте бесплатно!",
  keywords: [
    "поиск поставщиков по ТЗ",
    "подбор поставщиков по спецификации",
    "поиск производителей по ТЗ",
    "контакты отделов продаж заводов",
    "запрос коммерческого предложения",
    "производители по ГОСТ",
    "проверка ИНН поставщика",
    "TenderLex",
  ],
  alternates: {
    canonical: "/poisk-postavshchikov-po-tz",
  },
};

const pagePath = "/poisk-postavshchikov-po-tz";

const faqItems: FaqItem[] = [
  {
    question: "Как работает автоматический поиск товаров и подбор аналогов по ТЗ?",
    answer:
      "TenderLex анализирует технические требования спецификации (ГОСТ, ТУ, маркоразмеры, ключевые параметры) и сопоставляет их с реальной номенклатурой предприятий по всей России. Алгоритм находит прямых производителей и подбирает эквиваленты (аналоги), соответствующие требованиям 44-ФЗ и 223-ФЗ.",
  },
  {
    question: "Как TenderLex находит поставщиков под сложное техническое задание?",
    answer:
      "ИИ-сервис парсит спецификацию, определяет технические стандарты и сопоставляет их с каталогами предприятий, отбирая прямые контакты отделов сбыта и официальных дистрибьюторов без лишней цепочки перекупщиков.",
  },
  {
    question: "В каком формате выгружаются контакты и данные поставщиков?",
    answer:
      "Вы получаете структурированный отчет: наименования компаний, их роль (завод-изготовитель / дилер), прямые e-mail адреса, телефоны, регион склада и готовый текст запроса КП для быстрой рассылки.",
  },
  {
    question: "Можно ли подобрать аналоги снятой с производства или импортной продукции?",
    answer:
      "Да. ИИ сопоставляет функциональные параметры и помогает найти российские аналоги из реестра Минпромторга (ПП 719) или альтернативные позиции с идентичными характеристиками.",
  },
  {
    question: "Можно ли попробовать сервис бесплатно?",
    answer:
      "Да. При входе в личный кабинет предоставляется бесплатный пробный доступ, позволяющий протестировать поиск и подбор аналогов на реальном ТЗ.",
  },
];

export default function PoiskPostavshchikovPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Поиск поставщиков по ТЗ", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ",
    description: "Сервис подбора поставщиков и извлечения прямых контактов по техническому заданию.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как подобрать поставщиков по ТЗ",
    description: "Пошаговый процесс подбора контрагентов под спецификацию.",
    steps: [
      { name: "Загрузка файла ТЗ", text: "Загрузите файл Excel, Word или PDF." },
      { name: "Распознавание позиций", text: "Алгоритм извлекает ключевые параметры и стандарты." },
      { name: "Формирование пула поставщиков", text: "Выгрузка проверенных компаний с прямыми контактами." },
      { name: "Подготовка запроса КП", text: "Единый текст обращения для сбора ценовых предложений." },
    ],
  });

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaBreadcrumb) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaService) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaFaq) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaHowTo) }} />

      <main className="bg-slate-50 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

        {/* HERO */}
        <section className="relative pt-12 pb-20 border-b border-slate-200 bg-gradient-to-b from-teal-50/50 via-slate-50 to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-bold uppercase tracking-wider shadow-2xs">
              <Search size={14} className="text-teal-600" />
              <span>Автоматический подбор поставщиков под ТЗ</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Поиск поставщиков и заводов-производителей по ТЗ
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-normal leading-relaxed">
              Загрузите файл документации или спецификации — TenderLex выделит номенклатуру, найдет прямые контакты отделов сбыта заводов РФ и подготовит единый запрос КП за 3 минуты.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-extrabold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Найти поставщиков бесплатно (без привязки карты)</span>
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
                <h3 className="text-lg font-black text-slate-900">Direct Email отделов сбыта</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Прямые адреса менеджеров по продажам вместо общих инфо-ящиков с долгой обработкой.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Распознавание ГОСТ и ТУ</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Глубокий смысловой разбор технических характеристик сложных промышленных позиций.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Готовый шаблон КП</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Автоматически скомпонованное деловое письмо для мгновенной веерной рассылки.
                </p>
              </div>
            </div>

            {/* Cross-linking Banner: Подбор аналогов по ТЗ */}
            <div className="mt-12 p-8 sm:p-10 rounded-3xl bg-gradient-to-br from-teal-900 to-slate-900 text-white shadow-xl flex flex-col md:flex-row items-center justify-between gap-6">
              <div className="space-y-2 max-w-xl text-left">
                <span className="text-xs font-bold text-teal-300 uppercase tracking-wider bg-teal-400/20 px-3 py-1 rounded-full border border-teal-400/30 inline-block">
                  Смежный сервис
                </span>
                <h3 className="text-xl sm:text-2xl font-extrabold text-white">
                  Нужно выявить скрытую модель или подобрать аналоги по ТЗ?
                </h3>
                <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                  Используйте модуль «Подбор товара и аналогов», чтобы распознать модель-первоисточник, сверить параметры по паспортам заводов РФ, найти эквиваленты из реестра ГИСП и выгрузить отчет в Word (DOCX).
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
