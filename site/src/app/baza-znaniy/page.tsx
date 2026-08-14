import type { Metadata } from "next";

import { buildBreadcrumbJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "База знаний и руководства по закупкам | TenderLex",
  description:
    "Инструкции и руководства по подбору поставщиков, разбору ТЗ и анализу закупок для коммерческого снабжения и тендерных отделов.",
  openGraph: {
    type: "website",
    url: "/baza-znaniy",
    title: "База знаний и руководства по закупкам | TenderLex",
    description:
      "Инструкции и руководства по подбору поставщиков, разбору ТЗ и анализу закупок для коммерческого снабжения и тендерных отделов.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

const articles = [
  {
    slug: "/baza-znaniy/kak-naiti-postavshchika-po-tz",
    title: "Как найти поставщика по техническому заданию и спецификации",
    description:
      "Пошаговый алгоритм для отдела снабжения: разбор требований ТЗ, проверка сайтов, контактов, отбор дилеров и подготовка единого запроса коммерческого предложения.",
    tag: "Снабжение и закупки",
  },
  {
    slug: "/baza-znaniy/analiz-riskov-zakupki-44-fz-223-fz",
    title: "Анализ рисков закупки по 44-ФЗ и 223-ФЗ до подачи заявки",
    description:
      "Практическое руководство для поставщиков и тендерных специалистов: скрытые штрафы, короткие сроки, жесткая приемка и требования нацрежима Минпромторга.",
    tag: "Поставщикам и тендерам",
  },
  {
    slug: "/baza-znaniy/reestr-minpromtorga-postanovleniya-616-617",
    title: "Реестр Минпромторга и Постановления № 616 и 617 в закупках",
    description:
      "Разбор правил применения национального режима, проверки реестровых записей ГИСП и подтверждения отечественного производства.",
    tag: "Нацрежим и допуски",
  },
  {
    slug: "/baza-znaniy/kak-sostavit-zapros-kp-postavshchiku",
    title: "Как правильно составить запрос коммерческого предложения (КП)",
    description:
      "Структура идеального обращения закупщика к заводам и дилерам: номенклатура, ГОСТы, объемы и документы качества.",
    tag: "Практика снабжения",
  },
  {
    slug: "/baza-znaniy/proverka-dilerskih-sertifikatov-b2b",
    title: "Проверка дилерских сертификатов и полномочий поставщика",
    description:
      "Инструкция по проверке юридических бланков дилеров и предотвращению поставок контрафакта.",
    tag: "Безопасность закупок",
  },
];

export default function KnowledgeBaseHub() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "База знаний", path: "/baza-znaniy" },
  ]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 font-sans py-12 px-4 sm:px-6 lg:px-8">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      <div className="max-w-5xl mx-auto mb-10">
        <a href="/" className="text-xs font-semibold text-teal-700 font-bold hover:underline">
          ← На главную TenderLex
        </a>
        <h1 className="text-3xl font-extrabold text-slate-900 mt-4 mb-2">
          База знаний по закупкам и подбору поставщиков
        </h1>
        <p className="text-base text-slate-700 font-medium">
          Экспертные руководства и разборы рабочих процессов для коммерческого снабжения, тендерных отделов и поставщиков по всей России.
        </p>
      </div>

      <div className="max-w-5xl mx-auto grid gap-6 md:grid-cols-2">
        {articles.map((article) => (
          <article
            key={article.slug}
            className="p-6 bg-white rounded-2xl border border-slate-200 hover:border-teal-500/40 transition-all flex flex-col justify-between"
          >
            <div>
              <span className="inline-block px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-teal-950 font-extrabold bg-teal-100 border border-teal-300 rounded mb-3">
                {article.tag}
              </span>
              <h2 className="text-lg font-bold text-slate-900 mb-2">
                <a href={article.slug} className="hover:text-teal-700 font-bold transition-colors">
                  {article.title}
                </a>
              </h2>
              <p className="text-xs text-slate-700 font-medium leading-relaxed mb-4">{article.description}</p>
            </div>
            <a
              href={article.slug}
              className="text-xs font-bold text-teal-700 font-bold hover:text-teal-950 font-extrabold flex items-center gap-1 mt-2"
            >
              Читать руководство →
            </a>
          </article>
        ))}
      </div>
    </main>
  );
}
