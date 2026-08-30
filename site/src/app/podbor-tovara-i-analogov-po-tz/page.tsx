import type { Metadata } from "next";
import Link from "next/link";
import {
  Sparkles,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  FileText,
  Search,
  ArrowRight,
  ShieldCheck,
  Building2,
  ExternalLink,
  Layers,
  Zap,
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
  title: "Подбор аналогов и эквивалентов по ТЗ — Форма 2 и Реестр Минпромторга (ГИСП)",
  description:
    "ИИ-подбор товаров и взаимозаменяемых аналогов по техническому заданию (44-ФЗ, 223-ФЗ). Определение скрытого производителя, построчная сверка параметров по паспортам, Форма 2 в DOCX и XLSX без риска отклонения.",
  keywords: [
    "подбор аналогов по тз",
    "поиск товаров по тз",
    "подбор эквивалента товара 44 фз",
    "форма 2 госзакупки",
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
};

const pagePath = "/podbor-tovara-i-analogov-po-tz";

const faqItems: FaqItem[] = [
  {
    question: "Как TenderLex определяет скрытого производителя и модель по ТЗ?",
    answer:
      "Заказчики по 44-ФЗ и 223-ФЗ обязаны описывать товар без указания товарных знаков, но используют уникальные числовые диапазоны, габариты и ГОСТы конкретного завода. Модуль Deep Search сопоставляет совокупность параметров со спецификациями, опросными листами и техническими паспортами производителей по всей РФ, безошибочно выявляя модель-первоисточник.",
  },
  {
    question: "Почему данные берутся из заводских паспортов, а не подгоняются под ТЗ?",
    answer:
      "Искусственная подгонка характеристик под диапазон ТЗ ('не менее/не более') — главная причина отклонения заявок комиссией и штрафов ФАС за предоставление недостоверных сведений. TenderLex строго извлекает фактические заводские номиналы из каталогов и паспортов, подтверждая каждое значение ссылкой на первоисточник.",
  },
  {
    question: "Как формируется таблица Формы 2 (конкретные показатели)?",
    answer:
      "Сервис формирует структурированную таблицу: наименование параметра, требование заказчика, фактический показатель производителя, статус соответствия ('соответствует' / 'отклонение') и обоснование. Готовый документ выгружается в форматах Word (DOCX) и Excel (XLSX).",
  },
  {
    question: "Проверяются ли аналоги на включение в Реестр Минпромторга (ГИСП)?",
    answer:
      "Да. Каждый подобранный эквивалент сверяется с официальным Реестром промышленной продукции Минпромторга РФ (ПП № 616, № 617, ПП № 719) с указанием реестрового номера записи и наименования завода-изготовителя.",
  },
  {
    question: "Можно ли сразу после подбора аналогов запросить КП и найти поставщиков?",
    answer:
      "Да, в веб-кабинете и Telegram-боте реализован бесшовный переход в 1 клик: на основе найденных аналогов автоматически формируется контекст для модуля поиска прямых поставщиков и генератора Запроса КП.",
  },
];

const sampleSpecRows = [
  {
    param: "Глубина погружной части резервуара",
    tz: "не менее 4.0 м и не более 4.5 м",
    fact: "4.2 м (номинал заводской серии)",
    status: "match",
    source: "Паспорт изделия зав. № 14, табл. 2",
    analog: "4.25 м (Аналог РФ, Завод 'ГидроМаш')",
  },
  {
    param: "Материал проточной части",
    tz: "Коррозионностойкая сталь марки не ниже 12Х18Н10Т / AISI 304",
    fact: "Сталь 12Х18Н10Т (ГОСТ 5632-2014)",
    status: "match",
    source: "Сертификат качества производителя",
    analog: "AISI 304 / 08Х18Н10 (в реестре ГИСП)",
  },
  {
    param: "Масса агрегата в сборе",
    tz: "не более 12 100 кг",
    fact: "11 850 кг",
    status: "match",
    source: "Официальный каталог оборудования 2026",
    analog: "11 600 кг (соответствует ТЗ)",
  },
  {
    param: "Мощность приводного электродвигателя",
    tz: "не менее 2х0.55 кВт",
    fact: "2х0.55 кВт (IP67, взрывозащита 1Ex)",
    status: "match",
    source: "Электротехнический паспорт двигателя",
    analog: "2х0.75 кВт (улучшенные характеристики)",
  },
  {
    param: "Наличие в Реестре Минпромторга РФ",
    tz: "Требуется в соответствии с ПП РФ № 616",
    fact: "Запись № 1024\\2024 (действующая выписка ГИСП)",
    status: "match",
    source: "ГИСП Минпромторг РФ",
    analog: "Запись № 891\\2024 (АО 'ПромАрматура')",
  },
];

export default function PodborTovaraPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Подбор товара и аналогов по ТЗ", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Подбор товара и аналогов по ТЗ — Форма 2 и Реестр Минпромторга",
    description:
      "Автоматизированный подбор аналогов оборудования и материалов по техническому заданию: определение скрытого завода, Форма 2 с конкретными показателями, Реестр ГИСП.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как подобрать товар и аналоги по ТЗ за 4 шага",
    description: "Процесс сопоставления спецификации, выявления модели и подготовки Формы 2.",
    steps: [
      { name: "Загрузка спецификации", text: "Загрузите файл ТЗ (Word, Excel, PDF) или вставьте текст требований." },
      { name: "Поиск первоисточников", text: "Алгоритм Deep Search сопоставляет требования с паспортами заводов и ГОСТ." },
      { name: "Формирование Формы 2", text: "Получите таблицу конкретных параметров модели и 2–4 отечественных эквивалентов." },
      { name: "Выгрузка отчета и поиск поставщиков", text: "Скачайте готовый DOCX/XLSX и в 1 клик запустите сбор коммерческих предложений." },
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
        <section className="relative pt-12 pb-20 border-b border-slate-200 bg-gradient-to-b from-teal-50/60 via-slate-50 to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-black uppercase tracking-wider shadow-2xs">
              <Sparkles size={14} className="text-teal-600 animate-pulse" />
              <span>Форма 2 для заявок 44-ФЗ / 223-ФЗ & Реестр Минпромторга (ГИСП)</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Подбор товара и аналогов по ТЗ: выявление скрытых брендов и заполнение Формы 2
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-3xl mx-auto font-normal leading-relaxed">
              Загрузите спецификацию или проект контракта. ИИ распознает заложенную заказчиком модель, проведет построчную сверку параметров по паспортам заводов РФ, подберет эквиваленты из реестра ГИСП и сформирует готовую Форму 2 в Word и Excel.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-extrabold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Подобрать товар и аналоги (от 99 ₽)</span>
              </a>
              <a
                href="https://t.me/tenderlex_bot"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-extrabold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
              >
                <FileText size={16} className="text-teal-600" />
                <span>Запустить в Telegram</span>
              </a>
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
                100% подтверждение первоисточниками
              </span>
              <span className="hidden sm:inline text-slate-300">•</span>
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-teal-600" />
                Выгрузка в DOCX (Word) и XLSX (Excel)
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
                Почему тендерные специалисты доверяют подбору TenderLex
              </h2>
              <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
                Комиссия заказчика и ФАС отклоняют заявки, где характеристики искусственно скопированы из требований «не более/не менее». Мы находим реальные заводские паспорта.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              {/* Card 1 */}
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200 space-y-4 shadow-sm hover:border-teal-500 transition-all">
                <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center font-bold">
                  <Search className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-extrabold text-slate-900">Выявление «заточек» и скрытых моделей</h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Заказчик убрал название бренда? Алгоритм Deep Search анализирует редкие комбинации габаритов, материалов и ТУ, мгновенно определяя заложенного производителя.
                </p>
                <div className="pt-2 text-xs font-semibold text-teal-700 flex items-center gap-1.5">
                  <CheckCircle2 size={14} />
                  <span>Точность распознавания первоисточника 96%</span>
                </div>
              </div>

              {/* Card 2 */}
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200 space-y-4 shadow-sm hover:border-teal-500 transition-all">
                <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center font-bold">
                  <FileSpreadsheet className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-extrabold text-slate-900">Готовая Форма 2 без пустых ячеек</h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Построчная таблица с четким разделением: требование заказчика vs реальный показатель завода vs статус соответствия. Никаких «не более/не менее» в заявке.
                </p>
                <div className="pt-2 text-xs font-semibold text-teal-700 flex items-center gap-1.5">
                  <CheckCircle2 size={14} />
                  <span>Защита от отклонения по ч. 2 ст. 48 44-ФЗ</span>
                </div>
              </div>

              {/* Card 3 */}
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200 space-y-4 shadow-sm hover:border-teal-500 transition-all">
                <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center font-bold">
                  <Building2 className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-extrabold text-slate-900">2–4 эквивалента из Реестра Минпромторга</h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Автоматический поиск отечественных аналогов с действующими выписками ГИСП (ПП 616, 617, 719), позволяющий предложить альтернативу по меньшей цене.
                </p>
                <div className="pt-2 text-xs font-semibold text-teal-700 flex items-center gap-1.5">
                  <CheckCircle2 size={14} />
                  <span>Проверка реестровых номеров в режиме реального времени</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* INTERACTIVE TABLE SAMPLE: REAL FORM 2 PREVIEW */}
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
                Фрагмент таблицы из итогового документа DOCX/XLSX: конкретные показатели вместо диапазонных требований ТЗ.
              </p>
            </div>

            <div className="bg-white rounded-3xl border-2 border-slate-200 shadow-sm overflow-hidden">
              <div className="p-6 bg-slate-900 text-white flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                  <span className="text-xs text-teal-400 font-bold uppercase tracking-wider">Позиция № 1 в ТЗ</span>
                  <h4 className="text-lg font-bold text-white">
                    Илосос поворотный для радиальных отстойников Ø40 м (выявлена модель: ИПР-40, завод 'ГидроПром')
                  </h4>
                </div>
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-teal-500/20 border border-teal-400/40 text-teal-300 text-xs font-bold shrink-0">
                  <ShieldCheck size={14} />
                  <span>Соответствие ТЗ: 100%</span>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-100 border-b border-slate-200 text-slate-700 font-bold">
                      <th className="p-4 w-[28%]">Требуемый параметр (ТЗ)</th>
                      <th className="p-4 w-[24%]">Фактический показатель (Форма 2)</th>
                      <th className="p-4 w-[16%]">Статус</th>
                      <th className="p-4 w-[32%]">Отечественный аналог (Минпромторг)</th>
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
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                            <CheckCircle2 size={12} />
                            Соответствует
                          </span>
                        </td>
                        <td className="p-4 text-slate-700">
                          <div className="font-semibold text-slate-900">{row.analog}</div>
                          <div className="text-[11px] text-slate-500">Взаимозаменяемый эквивалент по ГОСТ</div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row justify-between items-center gap-4 text-xs text-slate-600">
                <span className="flex items-center gap-2">
                  <FileSpreadsheet size={16} className="text-teal-600" />
                  <span>Отчет выгружается в фирменном оформлении Word (DOCX) и Excel (XLSX).</span>
                </span>
                <a
                  href="/cabinet"
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
                  От подбора аналогов до сбора коммерческих предложений в 1 клик
                </h3>
                <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
                  После завершения подбора аналогов вам не нужно заново вводить позиции. Нажмите кнопку «Найти поставщиков» прямо в карточке задачи — TenderLex автоматически сформирует манифест оборудования и найдет прямые отделы сбыта заводов для получения цен.
                </p>
                <div className="pt-4 flex flex-wrap gap-4">
                  <a
                    href="/cabinet"
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

        {/* PRICING TABLE COMPACT */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-slate-50">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-2xl mx-auto mb-12 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
                Тарифы на подбор товара и аналогов
              </span>
              <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
                Прозрачная цена от 75.8 ₽ за позицию
              </h2>
              <p className="text-slate-600 text-sm">
                Включает распознавание скрытой модели, Форму 2, сверку с реестром Минпромторга и DOCX/XLSX.
              </p>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-6 bg-white rounded-2xl border-2 border-slate-200 text-center space-y-3 shadow-2xs">
                <span className="text-xs font-bold text-slate-500 uppercase">Разовый подбор</span>
                <div className="text-3xl font-black text-slate-900">99 ₽</div>
                <p className="text-xs text-slate-600">1 подбор товара и аналогов по ТЗ</p>
                <a href="/cabinet" className="block w-full py-2 bg-slate-100 hover:bg-teal-600 hover:text-white rounded-xl text-xs font-bold transition-all">
                  Выбрать
                </a>
              </div>

              <div className="p-6 bg-white rounded-2xl border-2 border-teal-500 text-center space-y-3 shadow-md relative">
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-teal-600 text-white text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full">
                  Популярный
                </div>
                <span className="text-xs font-bold text-teal-700 uppercase">Пакет 10</span>
                <div className="text-3xl font-black text-slate-900">890 ₽</div>
                <p className="text-xs text-slate-600">89 ₽ за подбор товара и аналогов</p>
                <a href="/cabinet" className="block w-full py-2 bg-teal-600 text-white hover:bg-teal-700 rounded-xl text-xs font-bold transition-all">
                  Выбрать
                </a>
              </div>

              <div className="p-6 bg-white rounded-2xl border-2 border-slate-200 text-center space-y-3 shadow-2xs">
                <span className="text-xs font-bold text-slate-500 uppercase">Пакет 25</span>
                <div className="text-3xl font-black text-slate-900">1 990 ₽</div>
                <p className="text-xs text-slate-600">79.6 ₽ за подбор товара и аналогов</p>
                <a href="/cabinet" className="block w-full py-2 bg-slate-100 hover:bg-teal-600 hover:text-white rounded-xl text-xs font-bold transition-all">
                  Выбрать
                </a>
              </div>

              <div className="p-6 bg-white rounded-2xl border-2 border-slate-200 text-center space-y-3 shadow-2xs">
                <span className="text-xs font-bold text-slate-500 uppercase">Пакет 50</span>
                <div className="text-3xl font-black text-slate-900">3 790 ₽</div>
                <p className="text-xs text-slate-600">75.8 ₽ за подбор товара и аналогов</p>
                <a href="/cabinet" className="block w-full py-2 bg-slate-100 hover:bg-teal-600 hover:text-white rounded-xl text-xs font-bold transition-all">
                  Выбрать
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ SECTION */}
        <section id="faq" className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6">
            <div className="text-center mb-12 space-y-3">
              <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
                Часто задаваемые вопросы по аналогам и Форме 2
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
