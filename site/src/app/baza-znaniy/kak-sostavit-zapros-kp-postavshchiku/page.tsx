import type { Metadata } from "next";

import { buildBreadcrumbJsonLd, buildHowToJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Как правильно составить запрос коммерческого предложения (КП) поставщику",
  description:
    "Образец и структура эффективного запроса коммерческих предложений (КП) для отдела снабжения: позиция, объём, условия оплаты, сертификаты и варианты замены.",
  keywords: [
    "запрос КП поставщику",
    "составить запрос коммерческого предложения",
    "образец запроса цены закупка",
    "Запрос КП снабжение",
  ],
  alternates: {
    canonical: "/baza-znaniy/kak-sostavit-zapros-kp-postavshchiku",
  },
  openGraph: {
    type: "article",
    url: "/baza-znaniy/kak-sostavit-zapros-kp-postavshchiku",
    title: "Как составить запрос коммерческого предложения поставщику | TenderLex",
    description:
      "Практическое руководство для закупщиков по составлению коммерческих запросов, экономящих время переписки.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

const steps = [
  {
    name: "Четкое описание номенклатуры и параметров",
    text: "Укажите марку, стандарты ГОСТ/ТУ, требуемые характеристики и возможные варианты аналогичных замен.",
  },
  {
    name: "Фиксация объёма и условий отгрузки",
    text: "Укажите требуемый объем партии, фасовку (барабаны, поддоны, коробки) и адрес/регион доставки.",
  },
  {
    name: "Перечень обязательных документов качества",
    text: "Запросите паспорт изделия, сертификат соответствия или выписку из реестра Минпромторга на этапе первого письма.",
  },
  {
    name: "Срок действия предложения и контактное лицо",
    text: "Укажите крайний срок приема коммерческих предложений и прямое ответственное лицо со стороны снабжения.",
  },
];

export default function GuideRfqPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "База знаний", path: "/baza-znaniy" },
    { name: "Запрос КП поставщику", path: "/baza-znaniy/kak-sostavit-zapros-kp-postavshchiku" },
  ]);

  const howToSchema = buildHowToJsonLd({
    name: "Как составить запрос коммерческого предложения (КП)",
    description:
      "Пошаговая структура первого обращения снабжения к заводам и дилерам для получения сравнимых цен.",
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
          Практика снабжения
        </span>
        <h1 className="text-3xl font-extrabold text-gray-900 mt-3 mb-4">
          Как правильно составить запрос коммерческого предложения (КП)
        </h1>
        <p className="text-lg text-gray-600">
          Чек-лист для специалиста по закупкам: как составить одно письмо, на которое менеджеры продаж поставщиков ответят в тот же день.
        </p>
      </header>

      <div className="prose prose-teal max-w-none text-gray-800 space-y-6">
        <h2>Структура правильного запроса КП</h2>
        <ol className="list-decimal pl-6 space-y-4">
          {steps.map((s, idx) => (
            <li key={idx}>
              <strong>{s.name}:</strong> {s.text}
            </li>
          ))}
        </ol>

        <h2>Автоматическое формирование запросов в TenderLex</h2>
        <p>
          Сервис <strong>TenderLex</strong> автоматически генерирует текст единого обращения для отдела продаж на основе загруженной спецификации.
        </p>

        <div className="my-8 p-6 bg-teal-50/80 rounded-2xl border border-teal-200 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-gray-900 m-0">Подготовить запрос цены в TenderLex</h3>
            <p className="text-sm text-gray-600 m-0 mt-1">
              Автоматически соберите список позиций и условий для единой рассылки.
            </p>
          </div>
          <a
            href="/zapros-kp-po-tz"
            className="px-5 py-2.5 bg-teal-600 text-white font-extrabold font-medium rounded-lg text-sm hover:bg-teal-700 transition-colors whitespace-nowrap"
          >
            Подготовить запрос КП
          </a>
        </div>
      </div>
    </article>
  );
}
