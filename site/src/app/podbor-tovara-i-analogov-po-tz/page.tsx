import { getSiteData } from "@/lib/site-data";
import type { Metadata } from "next";
import Link from "next/link";
import {
  Sparkles,
  CheckCircle2,
  FileText,
  Search,
  ArrowRight,
  ShieldCheck,
  Building2,
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

export const metadata: Metadata = {
  title: { absolute: "Подбор товара и аналогов по ТЗ | TenderLex" },
  description:
    "Подбор товара и аналогов по ТЗ: сопоставьте характеристики с документами изготовителя и получите рабочий отчёт в DOCX для проверки.",
  keywords: [
    "подбор аналогов по тз",
    "поиск товаров по тз",
    "подбор эквивалента товара 44 фз",
    "конкретные показатели товара",
    "подбор российских аналогов оборудования",
    "реестр минпромторга аналоги",
    "сопоставление характеристик тз",
    "выявление скрытой модели по тз",
    "TenderLex",
  ],
  alternates: {
    canonical: "/podbor-tovara-i-analogov-po-tz",
  },
  openGraph: {
    type: "website",
    url: "/podbor-tovara-i-analogov-po-tz",
    title: "Подбор товара и аналогов по ТЗ | TenderLex",
    description:
      "Сопоставление требований ТЗ с характеристиками товара и кандидатов на замену. Рабочий отчет в DOCX с данными для проверки.",
    siteName: "TenderLex",
    images: [
      {
        url: "/tenderlex-product-preview.png",
        width: 1200,
        height: 630,
        alt: "TenderLex — Подбор товара и аналогов по ТЗ",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Подбор товара и аналогов по ТЗ | TenderLex",
    description:
      "ИИ-подбор товаров и отечественных аналогов по техническому заданию (44-ФЗ, 223-ФЗ). Сверка параметров и отчет в Word.",
    images: ["/tenderlex-product-preview.png"],
  },
};

const pagePath = "/podbor-tovara-i-analogov-po-tz";

const faqItems: FaqItem[] = [
  {
    question: "Как TenderLex определяет скрытого производителя и модель по ТЗ?",
    answer:
      "Заказчики по 44-ФЗ и 223-ФЗ могут описывать товар через характеристики. Модуль сопоставляет совокупность параметров со спецификациями, опросными листами и техническими паспортами производителей. Результат — гипотеза о модели-первоисточнике, которую нужно проверить по первичному документу производителя.",
  },
  {
    question: "Почему данные берутся из заводских паспортов, а не подгоняются под ТЗ?",
    answer:
      "Характеристики предлагаемой модели должны подтверждаться документами изготовителя. Совпадение с диапазоном ТЗ не дает права придумывать значение. В отчете проверяйте источник каждого показателя; отсутствующие или неоднозначные данные нужно уточнять перед подачей заявки.",
  },
  {
    question: "Как формируется таблица конкретных показателей?",
    answer:
      "Рабочий отчет сопоставляет требование ТЗ, сведения о предлагаемом товаре и доступные подтверждения. Проверьте расхождения и недостающие данные по документам изготовителя. Результат модуля предоставляется в Word (DOCX); это не официальная форма заявки и не гарантия допуска.",
  },
  {
    question: "Проверяются ли аналоги на включение в Реестр Минпромторга (ГИСП)?",
    answer:
      "Если к закупке применяется национальный режим, участник должен сверить конкретную модель и действующую запись в предусмотренном реестре. Проверьте применимую редакцию ПП РФ № 1875, позицию приложения и условия извещения. Результат подбора не заменяет подтверждение происхождения товара.",
  },
  {
    question: "Можно ли сразу после подбора аналогов запросить КП и найти поставщиков?",
    answer:
      "После проверки модели можно использовать модуль поиска поставщиков по ТЗ. Сверьте контакты найденных компаний и самостоятельно направьте запрос КП с нужной комплектацией, объемом и сроком. Цены и готовность к поставке подтверждает компания, а не отчет подбора.",
  },
];

const sampleSpecRows = [
  {
    param: "Глубина погружной части резервуара",
    tz: "не менее 4.0 м и не более 4.5 м",
    fact: "4.2 м (номинал заводской серии)",
    status: "match",
    source: "Условный паспорт, таблица размеров",
    analog: "Кандидат: 4.25 м, источник нужно проверить",
  },
  {
    param: "Материал проточной части",
    tz: "Коррозионностойкая сталь марки 12Х18Н10Т",
    fact: "Сталь 12Х18Н10Т",
    status: "match",
    source: "Условный документ о материале",
    analog: "Кандидат: 12Х18Н10Т, нужен документ о материале",
  },
  {
    param: "Масса агрегата в сборе",
    tz: "не более 12 100 кг",
    fact: "11 850 кг",
    status: "match",
    source: "Условный каталог оборудования",
    analog: "Кандидат: 11 600 кг, комплектацию нужно проверить",
  },
  {
    param: "Мощность приводного электродвигателя",
    tz: "не менее 2х0.55 кВт",
    fact: "2х0.55 кВт",
    status: "match",
    source: "Условный паспорт двигателя",
    analog: "Кандидат: 2х0.75 кВт, условия применения нужно проверить",
  },
  {
    param: "Наличие в Реестре Минпромторга РФ",
    tz: "Проверьте применимую меру по ПП РФ № 1875",
    fact: "Требуется проверить применимый реестр и запись",
    status: "review",
    source: "Официальный реестр для конкретной категории товара",
    analog: "Требуется подтверждение происхождения кандидата",
  },
];

export default async function PodborTovaraPage() {
  const data = await getSiteData();
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Подбор товара и аналогов по ТЗ", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Подбор товара и аналогов по ТЗ — Реестр Минпромторга",
    description:
      "Подбор товара и кандидатов на замену по техническому заданию: рабочее сравнение характеристик и источников в DOCX для последующей проверки.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как подобрать товар и аналоги по ТЗ за 4 шага",
    description: "Процесс сопоставления спецификации, выявления модели и подбора эквивалентов.",
    steps: [
      { name: "Загрузка спецификации", text: "Загрузите файл ТЗ (Word, Excel, PDF) или вставьте текст требований." },
      { name: "Сопоставление характеристик", text: "Сопоставьте требования с данными товара и доступными документами изготовителя." },
      { name: "Проверка кандидатов", text: "Проверьте найденные варианты, расхождения и недостающие подтверждения. Число подходящих аналогов зависит от требований и доступных данных." },
      { name: "Выгрузка отчета и поиск поставщиков", text: "Скачайте рабочий отчет в DOCX, проверьте его и используйте отдельный модуль поиска поставщиков для подготовки запроса КП." },
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
            {/* Visual Breadcrumb Navigation */}
            <nav aria-label="Breadcrumb" className="flex items-center justify-center gap-2 text-xs text-slate-500 mb-1">
              <Link href="/" className="hover:text-teal-700 transition-colors">Главная</Link>
              <span>/</span>
              <span className="text-slate-800 font-medium">Подбор товара и аналогов по ТЗ</span>
            </nav>

            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-bold shadow-2xs">
              <Sparkles size={14} className="text-teal-600 animate-pulse" />
              <span>Сопоставление требований и вариантов по ТЗ</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Подбор товара и аналогов по ТЗ
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-3xl mx-auto font-normal leading-relaxed">
              Загрузите спецификацию или проект контракта. TenderLex сопоставит параметры с доступными паспортами производителей, предложит варианты аналогов и сформирует подробный отчет в Word (DOCX). Перед подачей заявки проверьте применимость аналога и требования закупки по первоисточникам.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet?scenario=exact_product"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-extrabold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Подобрать товар и аналоги</span>
              </a>
              <a
                href={data.bot.telegram_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-extrabold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
              >
                <FileText size={16} className="text-teal-600" />
                <span>Запустить в Telegram</span>
              </a>
            </div>

            {/* Quick check interactive card */}
            <div className="max-w-2xl mx-auto mt-4 p-4 sm:p-5 rounded-2xl bg-white border border-slate-200 shadow-sm text-left">
              <div className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Search size={14} className="text-teal-600" />
                <span>Экспресс-подбор товара или аналога по марке:</span>
              </div>
              <form action="/cabinet" method="GET" className="flex flex-col sm:flex-row gap-2">
                <input type="hidden" name="scenario" value="exact_product" />
                <input
                  type="text"
                  name="text"
                  placeholder="Например: Кран шаровый 11с67п или ВВГнг-LS 3х2.5..."
                  className="flex-1 px-4 py-2.5 rounded-xl border border-slate-300 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
                />
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm transition-all shadow-xs"
                >
                  <Sparkles size={15} />
                  <span>Подобрать</span>
                </button>
              </form>
              <div className="flex flex-wrap items-center gap-2 mt-3 text-xs text-slate-500">
                <span className="text-slate-400">Примеры:</span>
                <a
                  href="/cabinet?scenario=exact_product&text=Кран шаровый 11с67п ДУ50 Ру16"
                  className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-teal-50 hover:text-teal-700 transition-colors"
                >
                  Кран 11с67п ДУ50
                </a>
                <a
                  href="/cabinet?scenario=exact_product&text=Кабель ВВГнг-LS 3х2.5 ГОСТ"
                  className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-teal-50 hover:text-teal-700 transition-colors"
                >
                  ВВГнг-LS 3х2.5
                </a>
                <a
                  href="/cabinet?scenario=exact_product&text=Насос К 80-50-200"
                  className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-teal-50 hover:text-teal-700 transition-colors"
                >
                  Насос К 80-50-200
                </a>
              </div>
            </div>

            {/* Conversion trust badges */}
            <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-slate-500 font-medium pt-2">
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-teal-600" />
                Без искусственной подгонки под ТЗ
              </span>
              <span className="hidden sm:inline text-slate-300">•</span>
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-teal-600" />
                Источники для проверки характеристик
              </span>
              <span className="hidden sm:inline text-slate-300">•</span>
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-teal-600" />
                Выгрузка отчета в Word (DOCX)
              </span>
            </div>
          </div>
        </section>

        {/* 3 CORE PILLARS OF EXACT PRODUCT ENGINE */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
                Технология сопоставления
              </span>
              <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
                Что проверить в результате подбора TenderLex
              </h2>
              <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
                Сведения о товаре должны подтверждаться документами изготовителя и соответствовать инструкции закупки. Диапазоны и конкретные показатели проверяют по каждому параметру; отчет помогает подготовить такое сравнение.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              {/* Card 1 */}
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200 space-y-4 shadow-sm hover:border-teal-500 transition-all">
                <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center font-bold">
                  <Search className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-extrabold text-slate-900">Поиск возможной модели по характеристикам</h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Когда бренд не указан, сочетание габаритов, материалов и ТУ помогает найти возможные модели. Совпадение нужно подтвердить по паспорту; оно само по себе не доказывает ограничение конкуренции.
                </p>
                <div className="pt-2 text-xs font-semibold text-teal-700 flex items-center gap-1.5">
                  <CheckCircle2 size={14} />
                  <span>Гипотеза о модели требует проверки</span>
                </div>
              </div>

              {/* Card 2 */}
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200 space-y-4 shadow-sm hover:border-teal-500 transition-all">
                <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center font-bold">
                  <FileText className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-extrabold text-slate-900">Сравнение требований и подтвержденных данных</h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Сопоставьте строку ТЗ с фактическим показателем и его источником. Недостающие сведения уточняйте у изготовителя; диапазон сохраняйте или заменяйте конкретным значением в соответствии с инструкцией закупки.
                </p>
                <div className="pt-2 text-xs font-semibold text-teal-700 flex items-center gap-1.5">
                  <CheckCircle2 size={14} />
                  <span>Рабочая основа для проверки заявки</span>
                </div>
              </div>

              {/* Card 3 */}
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200 space-y-4 shadow-sm hover:border-teal-500 transition-all">
                <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center font-bold">
                  <Building2 className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-extrabold text-slate-900">Кандидаты на замену и проверка происхождения</h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Число подходящих вариантов зависит от требований и доступных подтверждений. Если закупка предусматривает национальный режим, проверьте применимую редакцию ПП № 1875 и запись на конкретную модель. Цену и срок поставки уточняйте у поставщика.
                </p>
                <div className="pt-2 text-xs font-semibold text-teal-700 flex items-center gap-1.5">
                  <CheckCircle2 size={14} />
                  <span>Актуальность записи проверяют перед подачей</span>
                </div>
              </div>
            </div>
            <p className="mt-8 text-xs text-slate-600 leading-relaxed">
              Для проверки национального режима используйте {" "}
              <a href="https://publication.pravo.gov.ru/document/0001202412250018" target="_blank" rel="noopener noreferrer" className="text-teal-700 underline underline-offset-4">официальную публикацию ПП № 1875</a>
              {" "}с учетом последующих изменений и дат их применения. {" "}
              <Link href="/baza-znaniy/reestr-minpromtorga-postanovleniya-616-617" className="text-teal-700 underline underline-offset-4">Порядок проверки и ссылки на изменения</Link>.
            </p>
          </div>
        </section>

        {/* INTERACTIVE TABLE SAMPLE: REAL SPECIFICATION PREVIEW */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-slate-50">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-3xl mx-auto mb-12 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
                Пример сформированного отчета
              </span>
              <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
                Как выглядит результат сопоставления в отчете
              </h2>
              <p className="text-slate-600 text-sm sm:text-base">
                Условный пример структуры DOCX: требования, показатели товара и источники. Названия модели и производителя ниже приведены для иллюстрации. В рабочем отчете сведения проверяют по документам изготовителя.
              </p>
            </div>

            <div className="bg-white rounded-3xl border-2 border-slate-200 shadow-sm overflow-hidden">
              <div className="p-6 bg-slate-900 text-white flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                  <span className="text-xs text-teal-400 font-bold uppercase tracking-wider">Позиция № 1 в ТЗ</span>
                  <h4 className="text-lg font-bold text-white">
                    Илосос поворотный для радиальных отстойников Ø40 м (условная модель: ИПР-40, условный изготовитель: «ГидроПром»)
                  </h4>
                </div>
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-teal-500/20 border border-teal-400/40 text-teal-300 text-xs font-bold shrink-0">
                  <ShieldCheck size={14} />
                  <span>Пример проверки параметров</span>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-100 border-b border-slate-200 text-slate-700 font-bold">
                      <th className="p-4 w-[28%]">Требуемый параметр (ТЗ)</th>
                      <th className="p-4 w-[24%]">Фактический показатель товара</th>
                      <th className="p-4 w-[16%]">Статус</th>
                      <th className="p-4 w-[32%]">Кандидат на замену</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {sampleSpecRows.map((row, idx) => (
                      <tr key={idx} className="hover:bg-teal-50/30 transition-colors">
                        <td className="p-4 font-semibold text-slate-900">
                          <div>{row.param}</div>
                          <div className="text-[11px] text-slate-500 font-normal mt-0.5">Требование: {row.tz}</div>
                        </td>
                        <td className="p-4 text-slate-800 font-bold">
                          <span className="text-teal-900 bg-teal-50 px-2 py-1 rounded border border-teal-200 block">
                            {row.fact}
                          </span>
                          <span className="text-[10px] text-slate-400 font-normal block mt-1">{row.source}</span>
                        </td>
                        <td className="p-4">
                          <span className={`inline-flex items-center gap-1 text-[11px] font-bold px-2.5 py-1 rounded-full border ${row.status === "review" ? "text-amber-800 bg-amber-50 border-amber-200" : "text-emerald-700 bg-emerald-50 border-emerald-200"}`}>
                            <CheckCircle2 size={12} />
                            {row.status === "review" ? "Нужна проверка" : "Совпадение в примере"}
                          </span>
                        </td>
                        <td className="p-4 text-slate-700">
                          <div className="font-semibold text-slate-900">{row.analog}</div>
                          <div className="text-[11px] text-slate-500">Пригодность и источники нужно проверить</div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row justify-between items-center gap-4 text-xs text-slate-600">
                <span className="flex items-center gap-2">
                  <FileText size={16} className="text-teal-600" />
                  <span>Отчет выгружается в фирменном оформлении Word (DOCX).</span>
                </span>
                <a
                  href="/cabinet?scenario=exact_product"
                  className="font-bold text-teal-700 hover:text-teal-800 flex items-center gap-1"
                >
                  <span>Загрузить свое ТЗ на проверку</span>
                  <ArrowRight size={13} />
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* 1-CLICK PIPELINE: ANALOGS TO SUPPLIERS */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="bg-gradient-to-br from-teal-900 via-slate-900 to-teal-950 text-white rounded-3xl p-8 sm:p-12 shadow-xl relative overflow-hidden">
              <div className="max-w-2xl space-y-4 relative z-10">
                <span className="text-xs font-bold uppercase tracking-wider text-teal-300 bg-teal-400/20 px-3 py-1 rounded-full border border-teal-400/30 inline-block">
                  Сквозной процесс снабжения
                </span>
                <h3 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
                  После проверки товара найдите поставщиков для запроса КП
                </h3>
                <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
                  Используйте проверенную спецификацию в модуле поиска поставщиков. Подтвердите контакты найденных компаний и направьте запрос с характеристиками, объемом и сроком поставки. Коммерческие условия и готовность отгрузить товар подтверждает поставщик.
                </p>
                <div className="pt-4 flex flex-wrap gap-4">
                  <a
                    href="/cabinet?scenario=exact_product"
                    className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 font-black text-xs shadow-lg transition-all"
                  >
                    <span>Попробовать в веб-кабинете</span>
                    <ArrowRight size={14} />
                  </a>
                  <Link
                    href="/poisk-postavshchikov-po-tz"
                    className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-white/10 hover:bg-white/20 text-white font-bold text-xs border border-white/20 transition-all"
                  >
                    <span>Подробнее о поиске поставщиков</span>
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* CURRENT TERMS */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-slate-50">
          <div className="container max-w-3xl mx-auto px-4 sm:px-6 text-center">
            <div className="space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
                Условия запуска
              </span>
              <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
                Выберите доступный пакет в личном кабинете
              </h2>
              <p className="text-slate-600 text-sm leading-relaxed">
                Актуальные пакеты и условия отображаются перед запуском задачи в кабинете. Они управляются в системе, поэтому страница не фиксирует цену, объём или срок результата.
              </p>
            </div>
            <a href="/cabinet?scenario=exact_product" className="inline-flex mt-7 px-6 py-3 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm transition-colors">Посмотреть условия в кабинете</a>
            <div className="mt-8 flex flex-wrap justify-center gap-x-5 gap-y-3 text-sm">
              <Link className="text-teal-700 underline underline-offset-4" href="/baza-znaniy/podbor-analogov-i-ekvivalentov-oborudovaniya-44-fz">Как проверить аналог по ТЗ</Link>
              <Link className="text-teal-700 underline underline-offset-4" href="/baza-znaniy/kak-opredelit-skrytogo-proizvoditelya-po-tz-44-fz">Как проверять гипотезу о модели</Link>
              <Link className="text-teal-700 underline underline-offset-4" href="/baza-znaniy/kak-zapolnit-formu-2-dlya-zayavki-44-fz-konkretnye-pokazateli">Как работать с конкретными показателями</Link>
            </div>
          </div>
        </section>

        {/* FAQ SECTION */}
        <section id="faq" className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6">
            <div className="text-center mb-12 space-y-3">
              <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
                Часто задаваемые вопросы по подбору аналогов
              </h2>
              <p className="text-slate-600 text-sm">
                Юридические и технические нюансы подбора эквивалентов по 44-ФЗ и 223-ФЗ.
              </p>
            </div>

            <div className="space-y-4">
              {faqItems.map((faq, idx) => (
                <details key={idx} className="group bg-slate-50 p-6 rounded-2xl border-2 border-slate-200 text-left shadow-2xs">
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
