import type { Metadata } from "next";
import Link from "next/link";
import {
  Building2,
  CheckCircle2,
  FileText,
  Mail,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users,
  Layers,
  Zap,
  TrendingUp,
  FileCheck,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatRubles, getSiteData, type PublicTariff } from "@/lib/site-data";
import {
  buildFaqJsonLd,
  buildOrganizationJsonLd,
  buildSoftwareApplicationJsonLd,
  buildWebSiteJsonLd,
  type FaqItem,
} from "@/lib/seo";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { RfqPreviewWidget } from "@/components/rfq-preview-widget";
import { ProcurementCalculator } from "@/components/procurement-calculator";
import { ComparisonSection } from "@/components/comparison-section";
import { ScrollWorldViewer } from "@/components/scroll-world/scroll-world-viewer";
import { TrustRegistryBar } from "@/components/trust-registry-bar";

export const revalidate = 300;

export const metadata: Metadata = {
  title: {
    absolute: "TenderLex — Поиск поставщиков, подбор аналогов по ТЗ и анализ закупок",
  },
  description:
    "Поиск поставщиков по ТЗ, подбор товара и аналогов, анализ закупочной документации. Подготовьте данные для проверки и запроса КП.",
  keywords: [
    "поиск поставщиков по ТЗ",
    "подбор аналогов по ТЗ",
    "поиск товаров по ТЗ",
    "эквивалент оборудования 44 фз",
    "поиск производителей Россия",
    "запрос коммерческого предложения",
    "контакты отделов продаж заводов",
    "реестр минпромторга аналоги",
    "анализ рисков 44-ФЗ и 223-ФЗ",
    "коммерческие закупки",
    "TenderLex",
  ],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "TenderLex — Поиск поставщиков по ТЗ и анализ любых закупок",
    description:
      "ИИ-помощник для разбора ТЗ, поиска кандидатов на поставку и анализа условий закупки перед проверкой.",
    url: "https://tenderlex.ru",
    siteName: "TenderLex",
    locale: "ru_RU",
    type: "website",
    images: ["/tenderlex-product-preview.png"],
  },
};

const mainFaqItems: FaqItem[] = [
  {
    question: "Как TenderLex находит поставщиков по всей России?",
    answer:
      "TenderLex помогает разобрать ТЗ или спецификацию, выделить маркоразмеры, ГОСТы и технические требования, затем сформировать список кандидатов и проект запроса КП. Роль компании, контакты, наличие товара, цену и срок поставки нужно подтвердить у поставщика и по его документам.",
  },
  {
    question: "Как формируется готовый Запрос коммерческого предложения (КП)?",
    answer:
      "На основе номенклатуры ТЗ модуль готовит проект запроса с позициями и вопросами о поставке. Перед отправкой проверьте объёмы, сроки, адрес, комплектность, документы и адресата.",
  },
  {
    question: "Что проверяет модуль анализа документации 44-ФЗ и 223-ФЗ?",
    answer:
      "Модуль помогает структурировать проект контракта и извещение: сроки, приемку, оплату, обеспечение, штрафы и требования национального режима. Выводы сверяют с первичными документами процедуры и применимыми нормами.",
  },
  {
    question: "Как работает подбор товара и аналогов по ТЗ?",
    answer:
      "Модуль сопоставляет параметры спецификации с доступными документами изготовителей, помогает сформировать гипотезы о модели и кандидаты на замену, а также рабочий отчёт в Word (DOCX). Гипотезу, применимость аналога, происхождение и каждый показатель проверяют по первоисточникам и условиям закупки.",
  },
  {
    question: "Где посмотреть условия запуска и тарифы?",
    answer:
      "Доступные пакеты и условия запуска отображаются в личном кабинете. Они управляются в системе, поэтому до запуска проверьте актуальные объём, стоимость и доступность пробного доступа.",
  },
];

export default async function HomePage() {
  const data = await getSiteData();
  const botUrl = data.bot.telegram_url;
  const cabinetUrl = "/cabinet";
  const supplierTariffs = data.tariff_groups?.supplier_search || [];
  const exactProductTariffs = data.tariff_groups?.exact_product || [];
  const reportTariffs = data.tariff_groups?.procurement_report || [];

  const websiteSchema = buildWebSiteJsonLd();
  const faqSchema = buildFaqJsonLd(mainFaqItems);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
      />

      <main className="bg-slate-50 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

        {/* HERO SECTION WITH INTERACTIVE SCROLL-WORLD */}
        <section className="relative pt-10 pb-16 border-b border-slate-200 bg-gradient-to-b from-teal-50/50 via-slate-50 to-white">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            {/* Hero Top Copy */}
            <div className="max-w-3xl mx-auto text-center space-y-4 mb-8">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-bold shadow-2xs">
                <Sparkles size={14} className="text-teal-600 animate-pulse" />
                <span>ИИ-поиск поставщиков • Подбор аналогов по ТЗ • Экспресс-аудит 44-ФЗ и 223-ФЗ</span>
              </div>

              <h1 className="text-3xl sm:text-4xl lg:text-[44px] font-extrabold text-slate-900 leading-[1.2] tracking-tight">
                Поиск надежных поставщиков и подбор аналогов
              </h1>

              <p className="text-base sm:text-lg text-slate-600 font-normal leading-relaxed max-w-2xl mx-auto">
                От разбора требований ТЗ и сопоставления вариантов до подготовки запроса КП и проверки условий проекта контракта.
              </p>

              {/* Responsive Quick-Action CTAs for Mobile & Desktop CRO */}
              <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3.5 max-w-lg mx-auto">
                <Button asChild className="w-full sm:w-auto bg-teal-600 hover:bg-teal-700 text-white font-extrabold px-7 h-12 text-sm shadow-lg shadow-teal-600/25 transition-all">
                  <Link href={cabinetUrl} className="flex items-center justify-center gap-2">
                    <span>Открыть кабинет</span>
                  </Link>
                </Button>
                <Button asChild variant="secondary" className="w-full sm:w-auto border-2 border-slate-300 hover:border-teal-600 hover:text-teal-700 bg-white font-bold px-6 h-12 text-sm text-slate-800 shadow-2xs transition-all">
                  <a href={botUrl} target="_blank" rel="noreferrer" className="flex items-center justify-center gap-2">
                    <Send className="w-4 h-4 text-cyan-600" />
                    <span>Запустить в Telegram</span>
                  </a>
                </Button>
              </div>

              {/* Conversion Trust Micro-Badges */}
              <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5 text-xs text-slate-500 font-medium pt-1">
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-teal-600" />
                  Условия доступа — в кабинете
                </span>
                <span className="hidden sm:inline text-slate-300">•</span>
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-teal-600" />
                  Выберите нужный модуль
                </span>
                <span className="hidden sm:inline text-slate-300">•</span>
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-teal-600" />
                  Проверяйте результат по первоисточникам
                </span>
              </div>
            </div>

            {/* WOW SCROLL-WORLD INTERACTIVE COMPONENT */}
            <div className="mb-10">
              <ScrollWorldViewer />
            </div>

            {/* Metrics Bar */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-6 bg-white rounded-2xl border border-slate-200 shadow-sm text-center">
              <div>
                <strong className="block text-2xl font-black text-teal-700">ТЗ и спецификация</strong>
                <span className="text-xs text-slate-500">анализ номенклатуры и требований</span>
              </div>
              <div>
                <strong className="block text-2xl font-black text-teal-700">Яндекс & Google</strong>
                <span className="text-xs text-slate-500">живой поиск по сайтам РФ</span>
              </div>
              <div>
                <strong className="block text-2xl font-black text-teal-700">Сравнение вариантов</strong>
                <span className="text-xs text-slate-500">для обоснованного выбора поставщика</span>
              </div>
              <div>
                <strong className="block text-2xl font-black text-teal-700">Карта рисков</strong>
                <span className="text-xs text-slate-500">для проверки условий до подачи заявки</span>
              </div>
            </div>

            {/* OFFICIAL REGISTRIES & TRUST VERIFICATION BAR */}
            <TrustRegistryBar />
          </div>
        </section>

        {/* THREE PRIMARY MODULES (Core Platform Architecture) */}
        <section className="py-16 sm:py-24 bg-white border-b border-slate-200">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
                Возможности платформы
              </span>
              <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
                Инструменты для снабжения и участия в закупках
              </h2>
              <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
                TenderLex помогает решать три ключевые задачи снабжения: поиск поставщиков, подбор товара и аналогов и анализ закупочной документации.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-6">
              {/* Module 1: Поиск поставщиков (First as requested) */}
              <div className="p-7 bg-slate-50 rounded-3xl border-2 border-slate-200 flex flex-col justify-between space-y-6 shadow-sm hover:border-teal-500 transition-all">
                <div className="space-y-4">
                  <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center">
                    <Search className="w-6 h-6" />
                  </div>
                  <span className="text-xs font-bold text-teal-700 uppercase tracking-wider block">1. Поиск поставщиков</span>
                  <h3 className="text-xl font-extrabold text-slate-900 leading-snug">
                    Поиск поставщиков по ТЗ
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                    Разбор спецификации, список кандидатов для запроса КП и проект обращения. Роль компании и контакты подтверждаются перед заказом.
                  </p>

                  <ul className="space-y-2.5 pt-2 border-t border-slate-200">
                    <li className="flex items-start text-xs text-slate-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2 shrink-0 mt-0.5" />
                      <span>Кандидаты и контакты для проверки</span>
                    </li>
                    <li className="flex items-start text-xs text-slate-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2 shrink-0 mt-0.5" />
                      <span>Проверка роли изготовителя или дилера</span>
                    </li>
                    <li className="flex items-start text-xs text-slate-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2 shrink-0 mt-0.5" />
                      <span>Проект запроса коммерческого предложения</span>
                    </li>
                  </ul>
                </div>

                <div className="pt-2">
                  <Button asChild className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold h-10 text-xs shadow-md shadow-teal-600/20">
                    <Link href="/poisk-postavshchikov-po-tz">
                      <span>Подробнее о поставщиках</span>
                    </Link>
                  </Button>
                </div>
              </div>

              {/* Module 2: Подбор товара и аналогов (Second as requested) */}
              <div className="p-7 bg-slate-50 rounded-3xl border-2 border-slate-200 flex flex-col justify-between space-y-6 shadow-sm hover:border-teal-500 transition-all">
                <div className="space-y-4">
                  <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center">
                    <Layers className="w-6 h-6" />
                  </div>
                  <span className="text-xs font-bold text-teal-700 uppercase tracking-wider block">2. Подбор товара</span>
                  <h3 className="text-xl font-extrabold text-slate-900 leading-snug">
                    Подбор товара и аналогов по ТЗ
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                    Сопоставление параметров с доступными документами изготовителя и варианты для дальнейшей проверки эквивалентности.
                  </p>

                  <ul className="space-y-2.5 pt-2 border-t border-slate-200">
                    <li className="flex items-start text-xs text-slate-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2 shrink-0 mt-0.5" />
                      <span>Требования ТЗ и сведения для проверки</span>
                    </li>
                    <li className="flex items-start text-xs text-slate-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2 shrink-0 mt-0.5" />
                      <span>Кандидаты на замену при наличии подтверждений</span>
                    </li>
                    <li className="flex items-start text-xs text-slate-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2 shrink-0 mt-0.5" />
                      <span>Выгрузка подробного отчета в Word (DOCX)</span>
                    </li>
                  </ul>
                </div>

                <div className="pt-2">
                  <Button asChild className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold h-10 text-xs shadow-md shadow-teal-600/20">
                    <Link href="/podbor-tovara-i-analogov-po-tz">
                      <span>Подробнее о подборе аналогов</span>
                    </Link>
                  </Button>
                </div>
              </div>

              {/* Module 3: Анализ документации (Third as requested) */}
              <div className="p-7 bg-slate-50 rounded-3xl border-2 border-slate-200 flex flex-col justify-between space-y-6 shadow-sm hover:border-teal-500 transition-all">
                <div className="space-y-4">
                  <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center">
                    <ShieldAlert className="w-6 h-6" />
                  </div>
                  <span className="text-xs font-bold text-teal-700 uppercase tracking-wider block">3. Анализ документации</span>
                  <h3 className="text-xl font-extrabold text-slate-900 leading-snug">
                    Экспресс-аудит документации: 44-ФЗ, 223-ФЗ
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                    Рабочая структура условий проекта контракта: сроки, обеспечение, штрафы, приёмка и национальный режим для дальнейшей проверки.
                  </p>

                  <ul className="space-y-2.5 pt-2 border-t border-slate-200">
                    <li className="flex items-start text-xs text-slate-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2 shrink-0 mt-0.5" />
                      <span>Сверка графиков поставки и сроков приемки</span>
                    </li>
                    <li className="flex items-start text-xs text-slate-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2 shrink-0 mt-0.5" />
                      <span>Аудит штрафов по ПП РФ № 1042</span>
                    </li>
                    <li className="flex items-start text-xs text-slate-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2 shrink-0 mt-0.5" />
                      <span>Проверка требований национального режима</span>
                    </li>
                  </ul>
                </div>

                <div className="pt-2">
                  <Button asChild className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold h-10 text-xs shadow-md shadow-teal-600/20">
                    <Link href="/analiz-zakupochnoi-dokumentacii">
                      <span>Подробнее об анализе документации</span>
                    </Link>
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* COMPARISON SECTION */}
        <section className="py-16 sm:py-24 bg-slate-50 border-b border-slate-200">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-2xl mx-auto mb-12 sm:mb-16 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
                Сравнение подходов
              </span>
              <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
                Ручной поиск в поисковиках против ИИ TenderLex
              </h2>
              <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
                    Когда полезно структурировать требования и проверять кандидатов перед запросом КП.
              </p>
            </div>

            <ComparisonSection />
          </div>
        </section>

        {/* RFQ GENERATOR WIDGET */}
        <section className="py-16 sm:py-24 bg-white border-b border-slate-200">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <RfqPreviewWidget />
          </div>
        </section>

        {/* PROCUREMENT CALCULATOR */}
        <section id="calculator" className="py-16 sm:py-24 bg-slate-50 border-b border-slate-200">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <ProcurementCalculator />
          </div>
        </section>

        {/* PRICING & TARIFFS */}
        <section id="pricing" className="py-16 sm:py-24 bg-white border-b border-slate-200">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
                Тарифы сервиса
              </span>
              <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
                Прозрачная стоимость без скрытых платежей
              </h2>
              <p className="text-slate-600 text-sm sm:text-base">
                Актуальные пакеты, цены и доступность пробного доступа отображаются перед запуском в личном кабинете.
              </p>
            </div>

            {data.tariffs.length === 0 && <p role="status" className="text-center text-sm text-slate-600 mb-6">Цены временно недоступны. Проверьте действующие условия в кабинете перед оплатой.</p>}

            <div className="grid md:grid-cols-3 gap-6 max-w-6xl mx-auto">
              {/* 1. Поставщики */}
              <div className="p-6 bg-gradient-to-br from-white to-teal-50/40 rounded-3xl border-2 border-slate-200 shadow-md flex flex-col justify-between">
                <div>
                  <span className="text-xs font-bold text-teal-700 uppercase tracking-wider bg-teal-100/60 px-2.5 py-0.5 rounded-full">Контакты отделов продаж</span>
                  <h3 className="text-xl font-extrabold text-slate-900 mt-2 mb-2">Контакты поставщиков</h3>
                  <p className="text-xs text-slate-600 mb-4">Список кандидатов и контактов для запроса КП с последующей проверкой роли компании и условий поставки.</p>
                  <div className="space-y-3 border-t border-slate-200 pt-4 mb-6">
                    {supplierTariffs.map((t: PublicTariff) => (
                      <div key={t.id} className="flex justify-between items-center text-xs">
                        <span className="text-slate-800 font-bold">{t.name}</span>
                        <strong className="text-teal-700 font-extrabold">{formatRubles(t.price_kopeks)}</strong>
                      </div>
                    ))}
                  </div>
                </div>
                <Button asChild className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold h-11 text-xs shadow-md shadow-teal-600/20">
                  <a href={cabinetUrl}>Выбрать пакет поставщиков</a>
                </Button>
              </div>

              {/* 2. Подбор товара и аналогов */}
              <div className="p-6 bg-gradient-to-br from-white to-teal-50/40 rounded-3xl border-2 border-slate-200 shadow-md flex flex-col justify-between">
                <div>
                  <span className="text-xs font-bold text-teal-700 uppercase tracking-wider bg-teal-100/60 px-2.5 py-0.5 rounded-full">Подбор по спецификации</span>
                  <h3 className="text-xl font-extrabold text-slate-900 mt-2 mb-2">Подбор товара и аналогов</h3>
                  <p className="text-xs text-slate-600 mb-4">Сопоставление показателей, кандидаты на замену и данные для проверки эквивалентности по документам изготовителя.</p>
                  <div className="space-y-3 border-t border-slate-200 pt-4 mb-6">
                    {exactProductTariffs.length > 0 ? (
                      exactProductTariffs.map((t: PublicTariff) => (
                        <div key={t.id} className="flex justify-between items-center text-xs">
                          <span className="text-slate-800 font-bold">{t.name}</span>
                          <strong className="text-teal-700 font-extrabold">{formatRubles(t.price_kopeks)}</strong>
                        </div>
                      ))
                    ) : (
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-slate-800 font-bold">Условия подбора</span>
                        <strong className="text-teal-700 font-extrabold">в кабинете</strong>
                      </div>
                    )}
                  </div>
                </div>
                <Button asChild className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold h-11 text-xs shadow-md shadow-teal-600/20">
                  <a href="/cabinet?scenario=exact_product">Подобрать товар и аналоги</a>
                </Button>
              </div>

              {/* 3. Анализ документации */}
              <div className="p-6 bg-gradient-to-br from-white to-teal-50/40 rounded-3xl border-2 border-slate-200 shadow-md flex flex-col justify-between">
                <div>
                  <span className="text-xs font-bold text-teal-700 uppercase tracking-wider bg-teal-100/60 px-2.5 py-0.5 rounded-full">Аудит рисков закупки</span>
                  <h3 className="text-xl font-extrabold text-slate-900 mt-2 mb-2">Анализ документации</h3>
                  <p className="text-xs text-slate-600 mb-4">Сроки, штрафы, обеспечение, приёмка и национальный режим как список условий для проверки перед подачей заявки.</p>
                  <div className="space-y-3 border-t border-slate-200 pt-4 mb-6">
                    {reportTariffs.map((t: PublicTariff) => (
                      <div key={t.id} className="flex justify-between items-center text-xs">
                        <span className="text-slate-800 font-bold">{t.name}</span>
                        <strong className="text-teal-700 font-extrabold">{formatRubles(t.price_kopeks)}</strong>
                      </div>
                    ))}
                  </div>
                </div>
                <Button asChild className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold h-11 text-xs shadow-md shadow-teal-600/20">
                  <a href="/cabinet?scenario=procurement_report">Выбрать пакет отчетов</a>
                </Button>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ SECTION */}
        <section id="faq" className="py-16 sm:py-24 border-b border-slate-200 bg-slate-50">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6">
            <div className="text-center mb-12 space-y-3">
              <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">Часто задаваемые вопросы</h2>
              <p className="text-slate-600 text-sm">Ответы на ключевые вопросы о работе сервиса.</p>
            </div>

            <div className="space-y-4">
              {mainFaqItems.map((faq, idx) => (
                <details key={idx} className="group bg-white p-6 rounded-2xl border-2 border-slate-200 text-left shadow-2xs">
                  <summary className="font-bold text-slate-900 text-base cursor-pointer flex justify-between items-center list-none">
                    <span>{faq.question}</span>
                    <span className="transition group-open:rotate-180 text-teal-700">▼</span>
                  </summary>
                  <p className="mt-4 text-sm text-slate-700 font-normal leading-relaxed border-t border-slate-200 pt-4">
                    {faq.answer}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* CONTACT SECTION */}
        <ContactSection />

        <SiteFooter />
      </main>
    </>
  );
}
