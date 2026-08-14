import type { Metadata } from "next";

import { buildBreadcrumbJsonLd, buildHowToJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Реестр Минпромторга и Постановления № 616 и 617 в закупках — Инструкция",
  description:
    "Полный разбор применения национального режима в 44-ФЗ и 223-ФЗ: проверка реестра Минпромторга, Постановления № 616, 617 и правила подтверждения производства.",
  keywords: [
    "реестр Минпромторга закупки",
    "постановление 616 закупки",
    "постановление 617 закупки",
    "национальный режим 44-ФЗ",
    "подтверждение производства Минпромторг",
    "реестровая запись Минпромторг",
  ],
  alternates: {
    canonical: "/baza-znaniy/reestr-minpromtorga-postanovleniya-616-617",
  },
  openGraph: {
    type: "article",
    url: "/baza-znaniy/reestr-minpromtorga-postanovleniya-616-617",
    title: "Реестр Минпромторга и нацрежим в закупках: Постановления № 616 и 617 | TenderLex",
    description:
      "Практическое руководство для снабжения и поставщиков по применению национального режима и реестровых записей Минпромторга.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

const steps = [
  {
    name: "Проверка извещения на наличие требований нацрежима",
    text: "Установите, установлено ли Постановление № 616 (запрет закупки иностранной продукции) или Постановление № 617 (ограничения допуска).",
  },
  {
    name: "Поиск реестровой записи в ГИСП Минпромторга",
    text: "Найдите товар в реестре российской промышленной продукции или евразийском реестре промышленных товаров по ОКПД2 и наименованию.",
  },
  {
    name: "Выписка и проверка количества баллов локализации",
    text: "Проверьте выписку из реестра, номер реестровой записи и требуемый совокупный объем баллов за выполнение технологических операций на территории РФ.",
  },
  {
    name: "Подготовка декларирующих документов в заявке",
    text: "Укажите номер реестровой записи и декларацию о стране происхождения товара в составе заявки.",
  },
];

export default function GuideMinpromtorgPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "База знаний", path: "/baza-znaniy" },
    { name: "Реестр Минпромторга в закупках", path: "/baza-znaniy/reestr-minpromtorga-postanovleniya-616-617" },
  ]);

  const howToSchema = buildHowToJsonLd({
    name: "Как проверить реестр Минпромторга для участия в закупке",
    description:
      "Пошаговый порядок проверки национального режима и подтверждения происхождения продукции по 44-ФЗ и 223-ФЗ.",
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
          Инструкция по 44-ФЗ и 223-ФЗ
        </span>
        <h1 className="text-3xl font-extrabold text-gray-900 mt-3 mb-4">
          Реестр Минпромторга и Постановления № 616 и 617 в закупках
        </h1>
        <p className="text-lg text-gray-600">
          Практический разбор национального режима: как проверить реестровые записи, подтвердить локализацию товара и отклонить необоснованные требования.
        </p>
      </header>

      <div className="prose prose-teal max-w-none text-gray-800 space-y-6">
        <h2>1. Что такое национальный режим и Постановления № 616 / 617</h2>
        <p>
          В государственных и муниципальных закупках действуют механизмы поддержки отечественного производителя. Заказчики обязаны устанавливать:
        </p>
        <ul>
          <li><strong>Постановление № 616:</strong> Запрет на закупку промышленных товаров, происходящих из иностранных государств (за исключением государств ЕАЭС).</li>
          <li><strong>Постановление № 617:</strong> Ограничение допуска промышленных товаров, происходящих из иностранных государств (правило «третий лишний»).</li>
        </ul>

        <h2>2. Порядок проверки реестровых записей</h2>
        <ol className="list-decimal pl-6 space-y-4">
          {steps.map((s, idx) => (
            <li key={idx}>
              <strong>{s.name}:</strong> {s.text}
            </li>
          ))}
        </ol>

        <h2>3. Автоматическая проверка допусков в TenderLex</h2>
        <p>
          Сервис <strong>TenderLex</strong> проверяет номенклатуру закупки на требования Постановлений № 616/617 и при необходимости показывает проверенных российских производителей, имеющих действующие выписки из реестра Минпромторга ГИСП.
        </p>

        <div className="my-8 p-6 bg-teal-50/80 rounded-2xl border border-teal-200 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-gray-900 m-0">Нужно проверить допуск или найти производителя?</h3>
            <p className="text-sm text-gray-600 m-0 mt-1">
              Используйте модуль TenderLex для проверки реестров и поиска отечественных поставщиков.
            </p>
          </div>
          <a
            href="/reestr-minpromtorga-v-zakupkah"
            className="px-5 py-2.5 bg-teal-600 text-white font-extrabold font-medium rounded-lg text-sm hover:bg-teal-700 transition-colors whitespace-nowrap"
          >
            Проверить допуск
          </a>
        </div>
      </div>
    </article>
  );
}
