import type { Metadata } from "next";
import { buildBreadcrumbJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Поиск поставщиков по ТЗ в Самаре и Поволжье",
  description: "Подбор B2B-поставщиков и заводов автопрома и оборудования в Самаре, Тольятти и Самарской области.",
  alternates: { canonical: "/regiony/samara" },
};

export default function SamaraRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Регионы", path: "/regiony" },
    { name: "Самара и Поволжье", path: "/regiony/samara" },
  ]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 font-sans py-12 px-4 max-w-4xl mx-auto">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />
      <nav className="mb-6"><a href="/regiony" className="text-xs text-teal-700 font-bold hover:underline">← Все регионы</a></nav>
      <header className="mb-8 border-b border-slate-200 pb-6">
        <span className="text-xs font-bold text-teal-700 font-bold bg-teal-100 px-3 py-1 rounded border border-teal-300">Регион: Самара и Поволжье</span>
        <h1 className="text-3xl font-extrabold text-slate-900 mt-3">Поиск поставщиков и заводов по ТЗ в Самарской области</h1>
      </header>
      <p className="text-slate-700 font-medium text-sm">Подбор промышленных контрагентов и складов Поволжского региона.</p>
    </main>
  );
}
