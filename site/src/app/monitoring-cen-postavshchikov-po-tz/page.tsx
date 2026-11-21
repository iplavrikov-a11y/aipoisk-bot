import { getSiteData } from "@/lib/site-data";
import type { Metadata } from "next";
import Link from "next/link";
import {
  Coins,
  FileSpreadsheet,
  Search,
  ArrowRight,
  ShieldCheck,
  Percent,
  Sliders,
  Send,
} from "lucide-react";
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

const pageDescription = "Соберите цены поставщиков по спецификации. Сравните найденные предложения в таблице со ссылками на источники и отметками по позициям без цены.";

export const metadata: Metadata = {
  title: { absolute: "Мониторинг цен поставщиков по спецификациям (44-ФЗ, 223-ФЗ) — TenderLex" },
  description: pageDescription,
  keywords: [
    "мониторинг цен поставщиков",
    "поиск цен по спецификации",
    "пакетный сбор цен поставщиков",
    "мониторинг цен 44 фз",
    "расчет нмцк метод сопоставимых цен",
    "обоснование нмцк приказ 567",
    "коэффициент вариации цен 44 фз",
    "сбор коммерческих предложений",
    "анализ цен b2b поставщиков",
    "TenderLex",
  ],
  alternates: {
    canonical: "/monitoring-cen-postavshchikov-po-tz",
  },
  openGraph: {
    type: "website",
    url: "/monitoring-cen-postavshchikov-po-tz",
    title: "Мониторинг цен поставщиков по спецификациям (44-ФЗ, 223-ФЗ) — TenderLex",
    description: pageDescription,
    siteName: "TenderLex",
    images: [
      {
        url: "/tenderlex-product-preview.png",
        width: 1200,
        height: 630,
        alt: "TenderLex — Мониторинг цен поставщиков по спецификациям",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Мониторинг цен поставщиков по спецификациям | TenderLex",
    description: pageDescription,
  },
};

const pagePath = "/monitoring-cen-postavshchikov-po-tz";

const faqItems: FaqItem[] = [
  {
    question: "Как работает пакетный мониторинг цен по спецификации?",
    answer:
      "Вы загружаете файл спецификации (Excel, Word, PDF, скриншот PNG/JPG/WEBP) или вставляете перечень позиций. TenderLex распознает наименования и единицы измерения, выполняет поиск цен по профильным B2B-поставщикам, сайтам заводов и дистрибьюторов, кластеризует найденные предложения для отсечения выбросов и выгружает готовый расчет в Excel (.xlsx). Списание с баланса происходит только за позиции, по которым найдены цены.",
  },
  {
    question: "Как рассчитывается коэффициент вариации по Приказу Минэкономразвития № 567?",
    answer:
      "В методических рекомендациях, утверждённых Приказом № 567, порог 33% используется для оценки однородности ценовой выборки. TenderLex рассчитывает среднюю цену и коэффициент вариации по собранным данным при достаточном числе цен. Сопоставимость характеристик и условий поставки проверяется отдельно.",
  },
  {
    question: "Исключаются ли розничные маркетплейсы и зарубежные дропшипперы?",
    answer:
      "Поиск применяет фильтры розничных маркетплейсов и зарубежных площадок. Проверьте найденные страницы, условия продажи и принадлежность организации производителю или дистрибьютору.",
  },
  {
    question: "В каком формате формируется итоговый отчет?",
    answer:
      "Отчёт содержит найденные цены и ссылки на страницы источников. В таблице также могут быть реквизиты и контакты поставщиков, если они доступны. Строки, по которым цену найти не удалось, отмечены отдельно.",
  },
  {
    question: "Сколько позиций можно проверить за один раз?",
    answer:
      "Загрузите спецификацию и выберите нужные строки. Для большого файла можно запустить поиск по частям. Текущие условия и стоимость видны в кабинете перед запуском.",
  },
  {
    question: "Подходит ли результат для официального обоснования НМЦК?",
    answer:
      "Отчёт помогает собрать исходные данные. Перед расчётом НМЦК проверьте применимые правила, сопоставимость цен, комплектность, доставку и НДС. Если опубликованных данных недостаточно, запросите подтверждение у поставщика.",
  },
];

const samplePriceRows = [
  {
    item: "Труба электросварная 57х3.5 мм ГОСТ 10704-91",
    unit: "т",
    qty: 12,
    p1: "68 500 ₽",
    p2: "71 200 ₽",
    p3: "69 800 ₽",
    avg: "69 833 ₽",
    varPct: "1.9%",
    status: "Однородно (V ≤ 33%)",
  },
  {
    item: "Задвижка чугунная 30ч6бр ДУ100 РУ10",
    unit: "шт",
    qty: 24,
    p1: "7 450 ₽",
    p2: "7 900 ₽",
    p3: "8 150 ₽",
    avg: "7 833 ₽",
    varPct: "4.5%",
    status: "Однородно (V ≤ 33%)",
  },
  {
    item: "Кабель ВВГнг-LS 3х2.5 (ГОСТ 31996-2012)",
    unit: "м",
    qty: 1500,
    p1: "62.40 ₽",
    p2: "64.80 ₽",
    p3: "65.10 ₽",
    avg: "64.10 ₽",
    varPct: "2.3%",
    status: "Однородно (V ≤ 33%)",
  },
  {
    item: "Редуктор по чертежу заказчика",
    unit: "шт",
    p1: "—",
    p2: "—",
    p3: "—",
    avg: "—",
    varPct: "—",
    status: "Цены не найдены",
  },
];

export default async function MonitoringCenPostavshchikovPage() {
  const data = await getSiteData();
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Мониторинг цен поставщиков", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Мониторинг цен поставщиков по спецификациям",
    description: pageDescription,
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как запустить мониторинг цен по спецификации",
    description: "Пошаговый процесс сбора цен поставщиков и формирования отчета Excel.",
    steps: [
      { name: "Загрузка спецификации", text: "Загрузите файл Excel (.xlsx), Word или PDF со списком позиций." },
      { name: "Извлечение и выбор позиций", text: "Система распознает строки и единицы измерения, с возможностью выбрать нужные." },
      { name: "Поиск и консенсусная кластеризация", text: "Сбор цен у оптовых поставщиков, отсечение маркетплейсов и выбросов выше установленного порога." },
      { name: "Выгрузка готового Excel с формулами", text: "Скачайте таблицу с ценами, прямыми ссылками на источники, контактами и расчетом вариации." },
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

        {/* HERO SECTION */}
        <section className="relative pt-8 pb-20 border-b border-slate-200 bg-gradient-to-b from-teal-50/60 via-slate-50 to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6 text-center space-y-5">
            {/* Breadcrumb Navigation */}
            <nav aria-label="Breadcrumb" className="flex items-center justify-center gap-2 text-xs text-slate-500 mb-1">
              <Link href="/" className="hover:text-teal-700 transition-colors">Главная</Link>
              <span>/</span>
              <span className="text-slate-800 font-medium">Мониторинг цен поставщиков</span>
            </nav>

            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-bold shadow-2xs">
              <Coins size={14} className="text-teal-600 animate-pulse" />
              <span>Пакетный сбор цен по спецификациям 44-ФЗ и 223-ФЗ</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Мониторинг цен поставщиков по спецификациям
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-3xl mx-auto font-normal leading-relaxed">
              Загрузите спецификацию. TenderLex соберёт доступные цены со ссылками на источники и покажет, по каким позициям цены не найдены. Срок и полнота поиска зависят от состава спецификации и доступности данных.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet?scenario=price_monitoring"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-extrabold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Запустить мониторинг цен</span>
              </a>
              <a
                href={data.bot.telegram_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-extrabold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
              >
                <Send size={16} className="text-teal-600" />
                <span>Запустить в Telegram</span>
              </a>
            </div>

            {/* Quick launcher card */}
            <div className="max-w-2xl mx-auto mt-4 p-4 sm:p-5 rounded-2xl bg-white border border-slate-200 shadow-sm text-left">
              <div className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Search size={14} className="text-teal-600" />
                <span>Быстрый старт: вставьте позиции или откройте кабинет для загрузки Excel:</span>
              </div>
              <form action="/cabinet" method="GET" className="flex flex-col sm:flex-row gap-2">
                <input type="hidden" name="scenario" value="price_monitoring" />
                <input
                  type="text"
                  name="text"
                  placeholder="Например: Кабель ВВГнг-LS 3х2.5, Труба 57х3.5, Насос К 80-50-200..."
                  className="flex-1 px-4 py-2.5 rounded-xl border border-slate-300 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
                />
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm transition-all shadow-xs"
                >
                  <Coins size={15} />
                  <span>Найти цены</span>
                </button>
              </form>
              <div className="flex flex-wrap items-center gap-2 mt-3 text-xs text-slate-500">
                <span className="text-slate-400">Форматы:</span>
                <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-medium">Excel (.xlsx)</span>
                <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-medium">Word (.docx)</span>
                <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-medium">PDF со сметами</span>
                <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-medium">Фото и скриншоты (PNG/JPG)</span>
                <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-medium">Текст списком</span>
              </div>
            </div>
          </div>
        </section>

        {/* 4 CORE ADVANTAGES */}
        <section className="py-16 bg-white border-b border-slate-200">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-3xl mx-auto mb-12 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
                Преимущества модуля
              </span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
                Почему профессионалы выбирают TenderLex для сбора цен
              </h2>
              <p className="text-slate-600 text-sm sm:text-base">
                Соберите исходные данные для предварительного расчёта и определите, по каким позициям нужно запросить цены у поставщиков.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200/80 hover:border-teal-300 transition-all space-y-3">
                <div className="w-10 h-10 rounded-xl bg-teal-100/80 flex items-center justify-center text-teal-800">
                  <Percent size={20} />
                </div>
                <h3 className="font-extrabold text-base text-slate-900">Вариация по 44-ФЗ</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Сервис рассчитывает коэффициент вариации для оценки разброса найденных цен. Проверьте сопоставимость товаров и коммерческих условий по источникам.
                </p>
              </div>

              <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200/80 hover:border-teal-300 transition-all space-y-3">
                <div className="w-10 h-10 rounded-xl bg-amber-100/80 flex items-center justify-center text-amber-800">
                  <Sliders size={20} />
                </div>
                <h3 className="font-extrabold text-base text-slate-900">Консенсусная кластеризация</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Алгоритм группирует близкие цены и отсекает выбросы. Итоговую выборку можно сверить с исходными предложениями.
                </p>
              </div>

              <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200/80 hover:border-teal-300 transition-all space-y-3">
                <div className="w-10 h-10 rounded-xl bg-blue-100/80 flex items-center justify-center text-blue-800">
                  <ShieldCheck size={20} />
                </div>
                <h3 className="font-extrabold text-base text-slate-900">Фильтр розницы и маркетплейсов</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Фильтры помогают исключить известные розничные и зарубежные площадки. Тип поставщика и условия продажи проверяются по найденной странице.
                </p>
              </div>

              <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200/80 hover:border-teal-300 transition-all space-y-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-100/80 flex items-center justify-center text-emerald-800">
                  <FileSpreadsheet size={20} />
                </div>
                <h3 className="font-extrabold text-base text-slate-900">Excel с прямыми ссылками</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  В таблице указаны найденные цены со ссылками на источники и статус поиска по каждой позиции. Если сведений недостаточно, можно запросить КП вручную.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* SAMPLE CALCULATION TABLE */}
        <section className="py-16 bg-slate-50 border-b border-slate-200">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-2xl mx-auto mb-10 space-y-2">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
                Как выглядит таблица мониторинга
              </h2>
              <p className="text-slate-600 text-sm">
                Учебный пример с условными ценами. Последняя строка показывает позицию, для которой поиск не нашёл цены.
              </p>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-xs">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-100/80 text-slate-900 font-extrabold border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4">Позиция спецификации</th>
                    <th className="py-3 px-3">Ед.</th>
                    <th className="py-3 px-3 text-right">Поставщик 1</th>
                    <th className="py-3 px-3 text-right">Поставщик 2</th>
                    <th className="py-3 px-3 text-right">Поставщик 3</th>
                    <th className="py-3 px-3 text-right">Средняя</th>
                    <th className="py-3 px-3 text-right">Вариация (V)</th>
                    <th className="py-3 px-4">Статус однородности</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {samplePriceRows.map((row, idx) => (
                    <tr key={idx} className="hover:bg-teal-50/30 transition-colors">
                      <td className="py-3 px-4 font-semibold text-slate-900 max-w-xs">{row.item}</td>
                      <td className="py-3 px-3 text-slate-500">{row.unit}</td>
                      <td className="py-3 px-3 text-right font-mono text-slate-700">{row.p1}</td>
                      <td className="py-3 px-3 text-right font-mono text-slate-700">{row.p2}</td>
                      <td className="py-3 px-3 text-right font-mono text-slate-700">{row.p3}</td>
                      <td className="py-3 px-3 text-right font-mono font-bold text-teal-800">{row.avg}</td>
                      <td className="py-3 px-3 text-right font-mono font-bold text-emerald-700">{row.varPct}</td>
                      <td className="py-3 px-4 font-semibold">{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500 px-1">
              <span>В рабочем отчёте рядом с найденными ценами указаны ссылки на источники.</span>
              <a
                href="/cabinet?scenario=price_monitoring"
                className="text-teal-700 font-bold hover:underline inline-flex items-center gap-1"
              >
                <span>Проверить свою спецификацию в кабинете</span>
                <ArrowRight size={13} />
              </a>
            </div>
          </div>
        </section>

        {/* 4 STEPS HOW TO */}
        <section className="py-16 bg-white border-b border-slate-200">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-2xl mx-auto mb-12 space-y-2">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
                Порядок работы
              </span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
                От файла до готовой таблицы за 4 шага
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="space-y-2 p-5 rounded-2xl bg-slate-50 border border-slate-200">
                <div className="w-8 h-8 rounded-lg bg-teal-600 text-white font-extrabold flex items-center justify-center text-sm">
                  1
                </div>
                <h3 className="font-extrabold text-sm text-slate-900">Загрузка файла</h3>
                <p className="text-xs text-slate-600">
                  Загрузите спецификацию в Excel (.xlsx), смету в PDF или Word, либо передайте номенклатуру списком.
                </p>
              </div>

              <div className="space-y-2 p-5 rounded-2xl bg-slate-50 border border-slate-200">
                <div className="w-8 h-8 rounded-lg bg-teal-600 text-white font-extrabold flex items-center justify-center text-sm">
                  2
                </div>
                <h3 className="font-extrabold text-sm text-slate-900">Выбор позиций</h3>
                <p className="text-xs text-slate-600">
                  Алгоритм распознает строки и единицы измерения. Вы можете запустить все позиции или отметить приоритетные.
                </p>
              </div>

              <div className="space-y-2 p-5 rounded-2xl bg-slate-50 border border-slate-200">
                <div className="w-8 h-8 rounded-lg bg-teal-600 text-white font-extrabold flex items-center justify-center text-sm">
                  3
                </div>
                <h3 className="font-extrabold text-sm text-slate-900">Поиск и кластеризация</h3>
                <p className="text-xs text-slate-600">
                  Поиск собирает доступные цены, фильтрует известные розничные площадки и выделяет ценовые выбросы.
                </p>
              </div>

              <div className="space-y-2 p-5 rounded-2xl bg-slate-50 border border-slate-200">
                <div className="w-8 h-8 rounded-lg bg-teal-600 text-white font-extrabold flex items-center justify-center text-sm">
                  4
                </div>
                <h3 className="font-extrabold text-sm text-slate-900">Скачивание Excel</h3>
                <p className="text-xs text-slate-600">
                  Скачайте таблицу. Проверьте ссылки на источники и отдельно просмотрите позиции, по которым цена не найдена.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ SECTION */}
        <section className="py-16 bg-slate-50 border-b border-slate-200" id="faq">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-2xl mx-auto mb-10 space-y-2">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
                Часто задаваемые вопросы
              </h2>
              <p className="text-slate-600 text-sm">
                Ответы на популярные вопросы о мониторинге цен и формировании расчетов по 44-ФЗ и 223-ФЗ.
              </p>
            </div>

            <div className="space-y-4">
              {faqItems.map((item, idx) => (
                <details
                  key={idx}
                  className="group bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs open:border-teal-300 transition-all"
                >
                  <summary className="font-extrabold text-sm sm:text-base text-slate-900 cursor-pointer list-none flex items-center justify-between gap-4">
                    <span>{item.question}</span>
                    <span className="text-teal-600 font-extrabold group-open:rotate-180 transition-transform">
                      ↓
                    </span>
                  </summary>
                  <p className="mt-3 text-xs sm:text-sm text-slate-600 leading-relaxed font-normal">
                    {item.answer}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* BOTTOM CTA */}
        <section className="py-16 bg-gradient-to-b from-white to-teal-50/50">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
              Готовы рассчитать цены по вашей спецификации?
            </h2>
            <p className="text-slate-600 text-sm sm:text-base max-w-2xl mx-auto">
              Откройте мониторинг в кабинете и загрузите свою спецификацию.
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              <a
                href="/cabinet?scenario=price_monitoring"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-extrabold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Создать кабинет и протестировать</span>
              </a>
              <Link
                href="/baza-znaniy/monitoring-cen-postavshchikov-po-specifikaciyam"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-50 text-slate-800 font-extrabold border border-slate-300 text-sm shadow-2xs transition-all"
              >
                <span>Читать методику расчета НМЦК</span>
              </Link>
            </div>
          </div>
        </section>

        <ContactSection />
        <SiteFooter />
      </main>
    </>
  );
}
