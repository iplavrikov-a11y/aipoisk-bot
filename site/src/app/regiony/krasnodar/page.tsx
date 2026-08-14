import type { Metadata } from "next";
import { buildBreadcrumbJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Поиск поставщиков по ТЗ в Краснодаре и на Юге РФ",
  description: "Подбор B2B-поставщиков и заводов агропром- и стройматериалов по спецификациям в Краснодаре и ЮФО.",
  alternates: { canonical: "/regiony/krasnodar" },
};

export default function KrasnodarRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Регионы", path: "/regiony" },
    { name: "Краснодар и Юг РФ", path: "/regiony/krasnodar" },
  ]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 font-sans py-12 px-4 max-w-4xl mx-auto">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />
      <nav className="mb-6"><a href="/regiony" className="text-xs text-teal-700 font-bold hover:underline">← Все регионы</a></nav>
      <header className="mb-8 border-b border-slate-200 pb-6">
        <span className="text-xs font-bold text-teal-700 font-bold bg-teal-100 px-3 py-1 rounded border border-teal-300">Регион: Краснодар и Юг РФ</span>
        <h1 className="text-3xl font-extrabold text-slate-900 mt-3">Поиск поставщиков и заводов по ТЗ в Краснодарском крае</h1>
      </header>
      <p className="text-slate-700 font-medium text-sm">Подбор проверенных продавцов и изготовителей Южного федерального округа.</p>
    </main>
  );
}
