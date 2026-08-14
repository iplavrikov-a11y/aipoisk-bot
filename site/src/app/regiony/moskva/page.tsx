import type { Metadata } from "next";

import { buildBreadcrumbJsonLd, buildServiceJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Поиск поставщиков по ТЗ в Москве и Московской области",
  description:
    "Подбор B2B-поставщиков, заводов и официальных дилеров по спецификациям в Москве и МО. Проверка контактов и отправка запроса КП.",
  keywords: [
    "поиск поставщиков Москва",
    "подбор поставщиков по ТЗ Москва",
    "производители Москва закупки",
    "официальные дилеры Москва",
    "запрос КП Москва",
  ],
  alternates: {
    canonical: "/regiony/moskva",
  },
  openGraph: {
    type: "website",
    url: "/regiony/moskva",
    title: "Поиск поставщиков по ТЗ в Москве и МО | TenderLex",
    description:
      "Автоматизированный подбор контрагентов под спецификации закупки в Москве и Центральном федеральном округе.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

export default function MoscowRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Регионы", path: "/regiony" },
    { name: "Москва и МО", path: "/regiony/moskva" },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ в Москве и МО",
    description:
      "TenderLex подбирает производителей, дилеров и дистрибьюторов в Москве и Московской области под технические задания.",
    path: "/regiony/moskva",
    serviceType: "B2B Supplier Search Moscow",
  });

  return (
    <main className="min-h-screen py-12 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceSchema) }}
      />

      <nav className="mb-6">
        <a href="/regiony" className="text-sm font-medium text-teal-700 font-bold hover:underline">
          ← Все регионы
        </a>
      </nav>

      <header className="mb-8 border-b pb-6 border-gray-200">
        <span className="text-xs font-semibold text-teal-800 bg-teal-50 px-3 py-1 rounded-full uppercase border border-teal-200">
          Регион: Москва и МО (ЦФО)
        </span>
        <h1 className="text-3xl font-extrabold text-gray-900 mt-3 mb-4">
          Поиск поставщиков и производителей по ТЗ в Москве
        </h1>
        <p className="text-lg text-gray-600">
          Подбор проверенных контрагентов в столичном регионе: выявление прямых складов, дилеров и изготовителей под спецификации.
        </p>
      </header>

      <div className="prose prose-teal max-w-none text-gray-800 space-y-6">
        <h2>Особенности подбора поставщиков в Москве и МО</h2>
        <p>
          Московский регион обладает максимальной концентрацией дистрибьюторов и представительств. Однако при ручном поиске закупщик часто сталкивается с ценами перекупщиков. TenderLex отделяет торговых агентов от официальных дилеров и заводов.
        </p>

        <div className="my-8 p-6 bg-white text-slate-900 rounded-2xl shadow-xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-teal-950 font-extrabold m-0">Нужно найти поставщиков в Москве?</h3>
            <p className="text-sm text-slate-700 font-medium m-0 mt-1">
              Загрузите ТЗ в кабинет TenderLex и получите проверенный список контрагентов.
            </p>
          </div>
          <a
            href="/cabinet"
            className="px-5 py-2.5 bg-teal-500 text-slate-950 font-bold rounded-lg text-sm hover:bg-teal-400 transition-colors whitespace-nowrap"
          >
            Попробовать на сайте
          </a>
        </div>
      </div>
    </main>
  );
}
