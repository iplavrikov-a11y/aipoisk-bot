import type { Metadata } from "next";

import { buildBreadcrumbJsonLd, buildHowToJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Проверка дилерских сертификатов и номенклатуры поставщика B2B",
  description:
    "Как закупщику и тендерному специалисту проверить оригинальность дилерского письма, статус официального представительства и прямые складские запасы.",
  keywords: [
    "проверка дилерского сертификата",
    "официальный дилер проверка",
    "проверка поставщика B2B",
    "статус дистрибьютора закупки",
  ],
  alternates: {
    canonical: "/baza-znaniy/proverka-dilerskih-sertifikatov-b2b",
  },
  openGraph: {
    type: "article",
    url: "/baza-znaniy/proverka-dilerskih-sertifikatov-b2b",
    title: "Проверка дилерских сертификатов B2B | TenderLex",
    description:
      "Инструкция по проверке статуса дилеров и предотвращению поставок контрафакта.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

const steps = [
  {
    name: "Сверка наименования завода и номера сертификата",
    text: "Проверьте срок действия дилерского письма и совпадение юридического лица поставщика с указанным на бланке.",
  },
  {
    name: "Проверка статуса в реестре дилеров на официальном сайте завода",
    text: "Перейдите на официальный сайт изготовителя и сверьте юридическое лицо в разделе 'Где купить' или 'Авторизованные партнеры'.",
  },
  {
    name: "Запрос информационного письма от производителя",
    text: "При крупных объёмах затребуйте прямую гарантию отгрузки завода под вашу конкретную закупку.",
  },
];

export default function GuideDealerCheckPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "База знаний", path: "/baza-znaniy" },
    { name: "Проверка дилерских сертификатов", path: "/baza-znaniy/proverka-dilerskih-sertifikatov-b2b" },
  ]);

  const howToSchema = buildHowToJsonLd({
    name: "Как проверить статус официального дилера",
    description:
      "Порядок действий закупщика по сверке дилерских полномочий и предупреждению контрафакта.",
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
          Безопасность закупок
        </span>
        <h1 className="text-3xl font-extrabold text-gray-900 mt-3 mb-4">
          Проверка дилерских сертификатов и полномочий поставщика
        </h1>
        <p className="text-lg text-gray-600">
          Инструкция по снижению рисков при закупке сложного промышленного оборудования и материалов.
        </p>
      </header>

      <div className="prose prose-teal max-w-none text-gray-800 space-y-6">
        <h2>Порядок проверки дилера</h2>
        <ol className="list-decimal pl-6 space-y-4">
          {steps.map((s, idx) => (
            <li key={idx}>
              <strong>{s.name}:</strong> {s.text}
            </li>
          ))}
        </ol>

        <div className="my-8 p-6 bg-teal-50/80 rounded-2xl border border-teal-200 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-gray-900 m-0">Найти проверенных дилеров в TenderLex</h3>
            <p className="text-sm text-gray-600 m-0 mt-1">
              Получите список авторизованных поставщиков по вашей номенклатуре.
            </p>
          </div>
          <a
            href="/poisk-proizvoditeley-po-tz"
            className="px-5 py-2.5 bg-teal-600 text-white font-extrabold font-medium rounded-lg text-sm hover:bg-teal-700 transition-colors whitespace-nowrap"
          >
            Найти производителя
          </a>
        </div>
      </div>
    </article>
  );
}
