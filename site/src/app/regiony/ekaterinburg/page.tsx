import type { Metadata } from "next";

import { buildBreadcrumbJsonLd, buildServiceJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Поиск поставщиков по ТЗ в Екатеринбурге и на Урале",
  description:
    "Подбор B2B-поставщиков, заводов металлообработки, арматуры и кабеля по спецификациям в Екатеринбурге и УрФО.",
  keywords: [
    "поиск поставщиков Екатеринбург",
    "заводы Урала закупки",
    "арматура металлопрокат Екатеринбург",
    "дилеры УрФО",
  ],
  alternates: {
    canonical: "/regiony/ekaterinburg",
  },
  openGraph: {
    type: "website",
    url: "/regiony/ekaterinburg",
    title: "Поиск поставщиков по ТЗ в Екатеринбурге и на Урале | TenderLex",
    description:
      "Автоматизированный подбор контрагентов под спецификации закупки в Екатеринбурге и Уральском округе.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

export default function EkbRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Регионы", path: "/regiony" },
    { name: "Екатеринбург и Урал", path: "/regiony/ekaterinburg" },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ в Екатеринбурге",
    description:
      "TenderLex подбирает производителей, дилеров и дистрибьюторов в Екатеринбурге и УрФО под технические задания.",
    path: "/regiony/ekaterinburg",
    serviceType: "B2B Supplier Search Ekaterinburg",
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
          Регион: Екатеринбург и Урал (УрФО)
        </span>
        <h1 className="text-3xl font-extrabold text-gray-900 mt-3 mb-4">
          Поиск поставщиков и металлообрабатывающих заводов на Урале
        </h1>
        <p className="text-lg text-gray-600">
          Подбор промышленных предприятий, заводов трубопроводной арматуры и складских комплексов Уральского региона.
        </p>
      </header>

      <div className="prose prose-teal max-w-none text-gray-800 space-y-6">
        <h2>Промышленные заводы и дистрибьюторы Урала</h2>
        <p>
          TenderLex проводит подбор с выделением прямых изготовителей, официальных представительств и складов в Екатеринбурге, Челябинске и Перми.
        </p>

        <div className="my-8 p-6 bg-white text-slate-900 rounded-2xl shadow-xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-teal-950 font-extrabold m-0">Нужно найти поставщиков на Урале?</h3>
            <p className="text-sm text-slate-700 font-medium m-0 mt-1">
              Загрузите спецификацию в TenderLex и получите список компаний.
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
