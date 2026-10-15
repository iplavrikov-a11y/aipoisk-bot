import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  KNOWLEDGE_ARTICLES,
  getKnowledgeArticleBySlug,
  getRelatedArticles,
} from "@/data/knowledge-base";
import { KnowledgeArticleLayout } from "@/components/knowledge-article-layout";
import {
  buildBreadcrumbJsonLd,
  buildHowToJsonLd,
  buildArticleJsonLd,
  buildFaqJsonLd,
  formatSeoTitle,
} from "@/lib/seo";
import {
  CheckCircle2,
  AlertTriangle,
  Info,
  Sparkles,
  ShieldCheck,
  FileCheck,
} from "lucide-react";

interface Props {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return KNOWLEDGE_ARTICLES.map((article) => ({
    slug: article.slug,
  }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const article = getKnowledgeArticleBySlug(slug);

  if (!article) {
    return {
      title: "Статья не найдена",
      description: "Запрошенная статья базы знаний не найдена.",
    };
  }

  const seoTitle = formatSeoTitle(article.title, article.seoTitle);

  return {
    title: seoTitle,
    description: article.description,
    keywords: article.keywords,
    alternates: {
      canonical: `/baza-znaniy/${article.slug}`,
    },
    openGraph: {
      title: article.title,
      description: article.description,
      type: "article",
      url: `/baza-znaniy/${article.slug}`,
      siteName: "TenderLex",
      images: [
        {
          url: "/tenderlex-product-preview.png",
          width: 1200,
          height: 630,
          alt: `${article.title} — TenderLex`,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: article.title,
      description: article.description,
      images: ["/tenderlex-product-preview.png"],
    },
  };
}

export default async function KnowledgeArticleDynamicPage({ params }: Props) {
  const { slug } = await params;
  const article = getKnowledgeArticleBySlug(slug);

  if (!article) {
    notFound();
  }

  const related = getRelatedArticles(article.slug, 3);

  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "База знаний", item: "https://tenderlex.ru/baza-znaniy" },
    {
      name: article.title,
      item: `https://tenderlex.ru/baza-znaniy/${article.slug}`,
    },
  ]);

  const articleSchema = buildArticleJsonLd({
    title: article.title,
    description: article.description,
    path: `/baza-znaniy/${article.slug}`,
    datePublished: article.publishedDate,
    dateModified: article.updatedDate,
    category: article.categoryLabel,
  });

  const howToSchema = article.steps
    ? buildHowToJsonLd({
        name: article.title,
        description: article.description,
        steps: article.steps,
      })
    : undefined;

  const faqSchema = article.faq ? buildFaqJsonLd(article.faq) : undefined;

  return (
    <KnowledgeArticleLayout
      tag={article.tag}
      category={article.categoryLabel}
      title={article.title}
      subtitle={article.subtitle}
      readTime={article.readTime}
      publishedDate={article.publishedDate}
      updatedDate={article.updatedDate ? new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(article.updatedDate)) : undefined}
      steps={article.steps}
      faq={article.faq}
      toc={article.toc}
      relatedArticles={related}
      breadcrumbSchema={breadcrumbSchema}
      articleSchema={articleSchema}
      howToSchema={howToSchema}
      faqSchema={faqSchema}
    >
      <div className="space-y-10 text-[#172120]">
        {/* LEAD SUBTITLE */}
        <p className="text-base sm:text-lg leading-relaxed text-[#2f3f3d] font-medium border-l-4 border-[#075b63] pl-4 bg-[#e5f4f3]/50 py-3 rounded-r-xl">
          {article.subtitle}
        </p>

        {/* CONTENT SECTIONS */}
        {article.contentSections.map((section, idx) => (
          <section key={section.id} id={section.id} className="space-y-4 pt-4">
            <h2 className="text-2xl sm:text-3xl font-black text-[#172120] tracking-tight flex items-center gap-3">
              <span className="w-8 h-8 rounded-lg bg-[#e5f4f3] text-[#075b63] flex items-center justify-center text-sm font-bold shrink-0 border border-[#b8c8c5]">
                {idx + 1}
              </span>
              <span>{section.title.replace(/^\d+\.\s*/, "")}</span>
            </h2>

            <div className="space-y-4 text-base leading-relaxed text-[#2f3f3d]">
              {section.paragraphs.map((p, pIdx) => (
                <p key={pIdx}>{p}</p>
              ))}
            </div>

            {section.callout && (
              <div
                className={`p-4 sm:p-5 rounded-2xl border text-xs sm:text-sm space-y-1.5 ${
                  section.callout.type === "warning"
                    ? "bg-amber-50/80 border-amber-200 text-amber-950"
                    : section.callout.type === "tip"
                    ? "bg-[#edf7df] border-[#b8c8c5] text-[#172120]"
                    : "bg-[#eef3f2] border-[#d8e3e1] text-[#172120]"
                }`}
              >
                <div className="flex items-center gap-2 font-bold">
                  {section.callout.type === "warning" ? (
                    <AlertTriangle size={16} className="text-amber-700 shrink-0" />
                  ) : (
                    <ShieldCheck size={16} className="text-[#075b63] shrink-0" />
                  )}
                  <span>{section.callout.title}</span>
                </div>
                <p className="leading-relaxed">{section.callout.text}</p>
              </div>
            )}

            {section.list && section.list.length > 0 && (
              <ul className="space-y-2 list-disc pl-5 text-[#2f3f3d] text-sm sm:text-base">
                {section.list.map((item, lIdx) => (
                  <li key={lIdx}>{item}</li>
                ))}
              </ul>
            )}
          </section>
        ))}
        {article.sources && article.sources.length > 0 && (
          <section id="sources" className="space-y-4 pt-6 border-t border-[#d8e3e1]">
            <h2 className="text-xl font-black text-[#172120]">Источники и документы для проверки</h2>
            <ul className="space-y-3 text-sm leading-relaxed">
              {article.sources.map((source) => (
                <li key={source.url}>
                  <a href={source.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-[#075b63] underline underline-offset-4">{source.title}</a>
                  {source.note && <p className="mt-1 text-[#697a77]">{source.note}</p>}
                </li>
              ))}
            </ul>
          </section>
        )}
        {article.moduleLink && (
          <aside className="rounded-2xl border border-[#b8c8c5] bg-[#e5f4f3]/60 p-5 sm:p-6">
            <h2 className="text-lg font-black text-[#172120]">Применить к своей задаче</h2>
            <p className="mt-2 text-sm leading-relaxed text-[#2f3f3d]">Сопоставьте выводы статьи с исходными документами и проверьте результат перед принятием закупочного решения.</p>
            <a className="mt-4 inline-flex rounded-xl bg-[#075b63] px-4 py-2.5 text-sm font-bold text-white hover:bg-[#06464c]" href={article.moduleLink.href}>{article.moduleLink.label}</a>
          </aside>
        )}
        {article.downloads && article.downloads.length > 0 && (
          <section className="rounded-2xl border border-[#d8e3e1] bg-white p-5 sm:p-6">
            <h2 className="text-lg font-black text-[#172120]">Рабочие материалы</h2>
            <p className="mt-2 text-sm leading-relaxed text-[#2f3f3d]">Материалы содержат учебные бланки. Перед использованием сверяйте их с вашей спецификацией и условиями закупки.</p>
            <ul className="mt-4 space-y-3">
              {article.downloads.map((item) => (
                <li key={item.href} className="rounded-xl bg-[#f6f8f7] p-4">
                  <a href={item.href} download className="font-bold text-[#075b63] underline underline-offset-4 hover:text-[#06464c]">{item.label}</a>
                  <p className="mt-1 text-sm leading-relaxed text-[#2f3f3d]">{item.description}</p>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </KnowledgeArticleLayout>
  );
}
