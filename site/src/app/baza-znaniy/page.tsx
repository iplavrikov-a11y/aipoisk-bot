import type { Metadata } from "next";
import Link from "next/link";
import { BookOpen, ArrowRight, Sparkles, FileText, ShieldCheck, CheckCircle2 } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { buildBreadcrumbJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "База знаний по закупкам и снабжению — руководства TenderLex",
  description:
    "Экспертные статьи и чек-листы для отделов снабжения и тендерных специалистов: поиск поставщиков по ТЗ, аудит рисков 44-ФЗ, проверка Минпромторга и составление запросов КП.",
  alternates: {
    canonical: "/baza-znaniy",
  },
  openGraph: {
    type: "website",
    url: "/baza-znaniy",
    title: "База знаний и руководства по закупкам | TenderLex",
    description: "Инструкции и руководства по подбору поставщиков, разбору ТЗ и анализу закупок.",
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
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "База знаний", item: "https://tenderlex.ru/baza-znaniy" },
  ]);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      <main className="bg-slate-50/60 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

        {/* HERO */}
        <section className="relative overflow-hidden pt-12 pb-20 border-b border-slate-200/90 bg-gradient-to-b from-teal-50/60 via-slate-50 to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-black uppercase tracking-wider shadow-2xs">
              <BookOpen size={14} className="text-teal-600" />
              <span>Экспертные руководства и чек-листы</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              База знаний по закупкам и подбору поставщиков
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Практические инструкции, разборы Федеральных законов № 44-ФЗ и № 223-ФЗ, методики проверки контрагентов и шаблоны запросов цен.
            </p>
          </div>
        </section>

        {/* ARTICLES LIST */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <div className="grid gap-6 md:grid-cols-2">
              {articles.map((article) => (
                <article
                  key={article.slug}
                  className="p-8 bg-slate-50 rounded-3xl border-2 border-slate-200 hover:border-teal-500 hover:shadow-xl transition-all flex flex-col justify-between group shadow-2xs"
                >
                  <div className="space-y-3">
                    <span className="inline-block px-3 py-1 text-[10px] font-black uppercase tracking-wider text-teal-900 bg-teal-100 border border-teal-300 rounded-lg">
                      {article.tag}
                    </span>
                    <h2 className="text-lg font-black text-slate-900 group-hover:text-teal-700 transition-colors">
                      <Link href={article.slug}>
                        {article.title}
                      </Link>
                    </h2>
                    <p className="text-xs text-slate-600 leading-relaxed font-medium">
                      {article.description}
                    </p>
                  </div>

                  <div className="pt-6 mt-6 border-t border-slate-200">
                    <Link
                      href={article.slug}
                      className="text-xs font-black text-teal-700 hover:text-teal-900 flex items-center gap-1.5 transition-colors"
                    >
                      <span>Читать руководство</span>
                      <ArrowRight size={14} />
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <ContactSection />

        <SiteFooter />
      </main>
    </>
  );
}
