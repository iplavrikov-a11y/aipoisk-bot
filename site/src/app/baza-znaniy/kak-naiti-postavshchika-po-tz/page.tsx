import type { Metadata } from "next";

import { buildBreadcrumbJsonLd, buildHowToJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Как найти поставщика по ТЗ и спецификации — Руководство",
  description:
    "Пошаговое руководство по поиску и подбору поставщиков под техническое задание: выявление ключевых характеристик, проверка контактов и подготовка запроса КП.",
  keywords: [
    "как найти поставщика по ТЗ",
    "подбор поставщиков по техническому заданию",
    "поиск производителей для закупки",
    "запрос коммерческого предложения КП",
    "проверка контактов поставщика",
  ],
  alternates: {
    canonical: "/baza-znaniy/kak-naiti-postavshchika-po-tz",
  },
  openGraph: {
    type: "article",
    url: "/baza-znaniy/kak-naiti-postavshchika-po-tz",
    title: "Как найти поставщика по техническому заданию — Инструкция | TenderLex",
    description:
      "Алгоритм поиска производителей, дилеров и дистрибьюторов под техническое задание или спецификацию закупки.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

const steps = [
  {
    name: "Выделение ключевых критериев из ТЗ",
    text: "Определите наименование позиции, ГОСТ/ТУ, требуемые характеристики, объём, сроки и регион поставки. Отделите критические параметры от желательных.",
  },
  {
    name: "Сбор первичного пула потенциальных контрагентов",
    text: "Используйте автоматизированный поиск TenderLex для сбора компаний, чей профиль и номенклатура на сайте соответствуют вашему запросу.",
  },
  {
    name: "Проверка сайтов и рабочих контактов",
    text: "Отсейте недействительные сайты и агрегаторы. Убедитесь в наличии прямых контактных данных: отдел продаж, email, телефон, адрес компании.",
  },
  {
    name: "Формирование единого запроса коммерческого предложения (КП)",
    text: "Составьте единый текст обращения с четким списком позиций, объёмом, требованиями по доставке и документам качества.",
  },
];

export default function GuideSupplierSearchPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "База знаний", path: "/baza-znaniy" },
    { name: "Поиск поставщиков по ТЗ", path: "/baza-znaniy/kak-naiti-postavshchika-po-tz" },
  ]);

  const howToSchema = buildHowToJsonLd({
    name: "Как найти поставщика по техническому заданию",
    description:
      "Пошаговый процесс подбора релевантных производителей и дилеров по спецификации и техническому заданию.",
    steps,
  });

  return (
    <article className="min-h-screen py-12 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(howToSchema) }}
      />

      <nav className="mb-6">
        <a href="/baza-znaniy" className="text-sm font-medium text-teal-700 font-bold hover:underline">
          ← Назад в базу знаний
        </a>
      </nav>

      <header className="mb-8 border-b pb-6 border-gray-200">
        <span className="text-xs font-semibold text-teal-900 font-extrabold bg-teal-50/80 px-3 py-1 rounded-full uppercase">
          Инструкция для снабжения
        </span>
        <h1 className="text-3xl font-extrabold text-gray-900 mt-3 mb-4">
          Как найти поставщика по техническому заданию и спецификации
        </h1>
        <p className="text-lg text-gray-600">
          Практический порядок действий для специалиста по закупкам: от разбора документации до получения первых коммерческих предложений.
        </p>
      </header>

      <div className="prose prose-teal max-w-none text-gray-800 space-y-6">
        <h2>1. Почему поиск поставщиков по ТЗ отличается от обычного поиска в сети</h2>
        <p>
          При поиске в обычных поисковиках первые места часто занимают рекламные агрегаторы, посредники и информационные каталоги. Закупщику же требуется выйти напрямую на завод-изготовитель, официального дилера или складского дистрибьютора, работающего с нужным ГОСТ и номенклатурой.
        </p>

        <h2>2. Этапы эффективного подбора</h2>
        <ol className="list-decimal pl-6 space-y-4">
          {steps.map((s, idx) => (
            <li key={idx}>
              <strong>{s.name}:</strong> {s.text}
            </li>
          ))}
        </ol>

        <h2>3. Как автоматизировать поиск с помощью TenderLex</h2>
        <p>
          Вместо ручного просмотра десятков страниц ИИ-сервис <strong>TenderLex</strong> анализирует загруженный файл спецификации или извещения, сопоставляет требования с сайтами компаний по всей России и выдает готовый реестр адресатов с контактами и рекомендациями по первому обращению.
        </p>

        <div className="my-8 p-6 bg-teal-50/80 rounded-2xl border border-teal-200 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-gray-900 m-0">Нужно быстро найти поставщиков?</h3>
            <p className="text-sm text-gray-600 m-0 mt-1">
              Загрузите ТЗ в TenderLex и получите рабочий список контрагентов с контактами.
            </p>
          </div>
          <a
            href="/poisk-postavshchikov-po-tz"
            className="px-5 py-2.5 bg-teal-600 text-white font-extrabold font-medium rounded-lg text-sm hover:bg-teal-700 transition-colors whitespace-nowrap"
          >
            Подобрать поставщиков
          </a>
        </div>
      </div>
    </article>
  );
}
