import type { Metadata } from "next";

import { buildBreadcrumbJsonLd, buildServiceJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Поиск поставщиков по ТЗ в Санкт-Петербурге и СЗФО",
  description:
    "Подбор B2B-поставщиков, заводов и официальных дилеров по спецификациям в Санкт-Петербурге и СЗФО.",
  keywords: [
    "поиск поставщиков Санкт-Петербург",
    "подбор поставщиков по ТЗ СПб",
    "производители Санкт-Петербург закупки",
    "дилеры СЗФО",
  ],
  alternates: {
    canonical: "/regiony/sankt-peterburg",
  },
  openGraph: {
    type: "website",
    url: "/regiony/sankt-peterburg",
    title: "Поиск поставщиков по ТЗ в Санкт-Петербурге | TenderLex",
    description:
      "Автоматизированный подбор контрагентов под спецификации закупки в Санкт-Петербурге и Северо-Западном округе.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

export default function SpbRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Регионы", path: "/regiony" },
    { name: "Санкт-Петербург и СЗФО", path: "/regiony/sankt-peterburg" },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ в Санкт-Петербурге",
    description:
      "TenderLex подбирает производителей, дилеров и дистрибьюторов в Санкт-Петербурге и СЗФО под технические задания.",
    path: "/regiony/sankt-peterburg",
    serviceType: "B2B Supplier Search SPb",
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
          Регион: Санкт-Петербург и СЗФО
        </span>
        <h1 className="text-3xl font-extrabold text-gray-900 mt-3 mb-4">
          Поиск поставщиков и заводов по ТЗ в Санкт-Петербурге
        </h1>
        <p className="text-lg text-gray-600">
          Подбор машиностроительных, судностроительных, химических и строительных поставщиков в Северо-Западном регионе.
        </p>
      </header>

      <div className="prose prose-teal max-w-none text-gray-800 space-y-6">
        <h2>Официальные дилеры и заводы Северо-Запада</h2>
        <p>
          TenderLex проводит глубокий поиск контрагентов с подборкой релевантных сайтов, номеров отделов продаж и предсформированных вопросов по отгрузкам со складов СЗФО.
        </p>

        <div className="my-8 p-6 bg-white text-slate-900 rounded-2xl shadow-xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-teal-950 font-extrabold m-0">Нужно найти поставщиков в СПб?</h3>
            <p className="text-sm text-slate-700 font-medium m-0 mt-1">
              Передайте спецификацию в TenderLex и получите список компаний.
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
