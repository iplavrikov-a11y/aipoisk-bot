import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import {
  ArrowLeft,
  ArrowRight,
  Clock,
  Calendar,
  UserCheck,
  CheckCircle2,
  Sparkles,
  Search,
  FileCheck,
  Share2,
  Bookmark,
  ShieldCheck,
  HelpCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export interface KnowledgeArticleLayoutProps {
  tag: string;
  category?: string;
  title: string;
  subtitle: string;
  readTime?: string;
  publishedDate?: string;
  updatedDate?: string;
  steps?: { name: string; text: string }[];
  faq?: { question: string; answer: string }[];
  toc?: { id: string; title: string }[];
  relatedArticles?: {
    slug: string;
    title: string;
    description: string;
    tag: string;
  }[];
  children: React.ReactNode;
  breadcrumbSchema: object;
  howToSchema?: object;
  articleSchema?: object;
  faqSchema?: object;
}

export function KnowledgeArticleLayout({
  tag,
  category = "Закупки и снабжение",
  title,
  subtitle,
  readTime = "7 мин чтения",
  publishedDate = "15 марта 2026",
  updatedDate = "20 августа 2026",
  steps,
  faq,
  toc,
  relatedArticles,
  children,
  breadcrumbSchema,
  howToSchema,
  articleSchema,
  faqSchema,
}: KnowledgeArticleLayoutProps) {
  const botUrl = process.env.NEXT_PUBLIC_BOT_URL || "https://t.me/tenderlex_bot";

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      {articleSchema && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(articleSchema) }}
        />
      )}
      {howToSchema && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(howToSchema) }}
        />
      )}
      {faqSchema && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
        />
      )}

      <main className="bg-[#f6f8f7] text-[#172120] min-h-screen font-sans">
        <SiteHeader />

        {/* BREADCRUMB & HERO */}
        <section className="relative overflow-hidden pt-8 pb-12 sm:pt-12 sm:pb-16 border-b border-[#d8e3e1] bg-gradient-to-b from-[#e5f4f3]/60 via-[#f6f8f7] to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <nav aria-label="Breadcrumb" className="mb-6">
              <ol className="flex flex-wrap items-center gap-2 text-xs font-semibold text-[#697a77]">
                <li>
                  <Link href="/" className="hover:text-[#075b63] transition-colors">
                    Главная
                  </Link>
                </li>
                <li>/</li>
                <li>
                  <Link href="/baza-znaniy" className="hover:text-[#075b63] transition-colors">
                    База знаний
                  </Link>
                </li>
                <li>/</li>
                <li className="text-[#075b63] truncate max-w-[260px] sm:max-w-md font-bold">
                  {title}
                </li>
              </ol>
            </nav>

            <div className="space-y-4 max-w-4xl">
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="inline-block px-3 py-1 text-xs font-black uppercase tracking-wider text-[#075b63] bg-[#e5f4f3] border border-[#b8c8c5] rounded-lg">
                  {tag}
                </span>
                <span className="inline-flex items-center gap-1.5 text-xs text-[#2f3f3d] font-semibold px-2.5 py-1 bg-white border border-[#d8e3e1] rounded-lg shadow-2xs">
                  <Clock size={13} className="text-[#075b63]" />
                  {readTime}
                </span>
                <span className="inline-flex items-center gap-1.5 text-xs text-[#697a77] font-semibold px-2.5 py-1 bg-white border border-[#d8e3e1] rounded-lg shadow-2xs">
                  <Calendar size={13} className="text-[#697a77]" />
                  Обновлено: {updatedDate}
                </span>
              </div>

              <h1 className="text-3xl sm:text-4xl md:text-5xl font-black text-[#172120] tracking-tight leading-[1.15]">
                {title}
              </h1>

              <p className="text-base sm:text-xl text-[#2f3f3d] font-medium leading-relaxed max-w-3xl">
                {subtitle}
              </p>

              {/* AUTHOR / E-E-A-T BADGE */}
              <div className="pt-2 flex items-center gap-3 text-xs text-[#697a77]">
                <div className="w-8 h-8 rounded-full bg-[#075b63] text-white flex items-center justify-center font-black shadow-xs">
                  TL
                </div>
                <div>
                  <span className="font-bold text-[#172120] block">Экспертная редакция TenderLex</span>
                  <span className="text-[#697a77]">Материал проверен юристами и экспертами по закупкам 44-ФЗ / 223-ФЗ</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* MAIN CONTENT AREA */}
        <section className="py-12 sm:py-16 border-b border-[#d8e3e1] bg-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
              {/* ARTICLE BODY */}
              <article className="lg:col-span-8 space-y-8 text-[#172120] text-base leading-relaxed">
                {/* INLINE TOC IF AVAILABLE */}
                {toc && toc.length > 0 && (
                  <nav className="p-6 rounded-2xl bg-[#eef3f2] border border-[#d8e3e1] shadow-2xs">
                    <h3 className="text-xs font-black uppercase tracking-wider text-[#075b63] mb-3 flex items-center gap-2">
                      <Bookmark size={14} className="text-[#075b63]" /> Содержание статьи
                    </h3>
                    <ul className="space-y-2 text-sm">
                      {toc.map((item, idx) => (
                        <li key={idx}>
                          <a
                            href={`#${item.id}`}
                            className="text-[#075b63] hover:text-[#06464c] font-semibold hover:underline flex items-baseline gap-2"
                          >
                            <span className="text-[#697a77] text-xs font-mono">{idx + 1}.</span>
                            <span>{item.title}</span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </nav>
                )}

                {/* ACTUAL ARTICLE CONTENT */}
                <div className="article-prose space-y-6">
                  {children}
                </div>

                {/* STEP-BY-STEP CHECKLIST */}
                {steps && steps.length > 0 && (
                  <div className="my-10 p-6 sm:p-8 rounded-3xl bg-[#f6f8f7] border-2 border-[#b8c8c5] shadow-xs space-y-6">
                    <div className="flex items-center gap-2 text-[#075b63]">
                      <FileCheck size={22} className="text-[#075b63] shrink-0" />
                      <h2 className="text-xl sm:text-2xl font-black text-[#172120] tracking-tight">
                        Пошаговый регламент действий закупщика
                      </h2>
                    </div>
                    <div className="space-y-4">
                      {steps.map((s, idx) => (
                        <div key={idx} className="flex items-start gap-4 p-4 rounded-2xl bg-white border border-[#d8e3e1] shadow-2xs">
                          <span className="w-8 h-8 rounded-xl bg-[#075b63] text-white font-black flex items-center justify-center shrink-0 text-sm shadow-xs">
                            {idx + 1}
                          </span>
                          <div>
                            <strong className="text-[#172120] block text-base font-bold">{s.name}</strong>
                            <p className="text-sm text-[#2f3f3d] mt-1 leading-relaxed">{s.text}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* FAQ SECTION */}
                {faq && faq.length > 0 && (
                  <div className="my-10 p-6 sm:p-8 rounded-3xl bg-white border border-[#d8e3e1] shadow-xs space-y-6">
                    <div className="flex items-center gap-2 text-[#172120]">
                      <HelpCircle size={22} className="text-[#075b63] shrink-0" />
                      <h2 className="text-xl sm:text-2xl font-black tracking-tight">
                        Часто задаваемые вопросы (FAQ)
                      </h2>
                    </div>
                    <div className="space-y-4">
                      {faq.map((item, idx) => (
                        <div key={idx} className="p-4 sm:p-5 rounded-2xl bg-[#f6f8f7] border border-[#d8e3e1] space-y-2">
                          <h3 className="font-bold text-[#172120] text-base">
                            {item.question}
                          </h3>
                          <p className="text-sm text-[#2f3f3d] leading-relaxed">
                            {item.answer}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* RELATED ARTICLES BOTTOM GRID */}
                {relatedArticles && relatedArticles.length > 0 && (
                  <div className="my-10 pt-8 border-t border-[#d8e3e1] space-y-6">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div>
                        <h2 className="text-xl sm:text-2xl font-black tracking-tight text-[#172120]">
                          Связанные статьи по теме
                        </h2>
                        <p className="text-xs sm:text-sm text-[#697a77] mt-1">
                          Материалы по закупкам, регламентам 44-ФЗ / 223-ФЗ и сопоставлению ТЗ
                        </p>
                      </div>
                      <Link
                        href="/baza-znaniy"
                        className="inline-flex items-center gap-1 text-xs font-bold text-[#075b63] hover:text-[#06464c] transition-colors"
                      >
                        <span>Все статьи базы знаний</span>
                        <ArrowRight size={14} />
                      </Link>
                    </div>

                    <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
                      {relatedArticles.map((ra, idx) => (
                        <Link
                          key={idx}
                          href={`/baza-znaniy/${ra.slug}`}
                          className="p-5 rounded-2xl bg-[#f6f8f7] hover:bg-[#e5f4f3] border border-[#d8e3e1] hover:border-[#b8c8c5] transition-all flex flex-col justify-between group shadow-2xs"
                        >
                          <div className="space-y-2">
                            <span className="text-[10px] font-black text-[#075b63] uppercase tracking-wider block">
                              {ra.tag}
                            </span>
                            <h3 className="text-sm font-bold text-[#172120] group-hover:text-[#075b63] transition-colors leading-snug line-clamp-2">
                              {ra.title}
                            </h3>
                            <p className="text-xs text-[#697a77] line-clamp-2 leading-relaxed font-normal">
                              {ra.description}
                            </p>
                          </div>
                          <div className="pt-4 mt-auto flex items-center text-xs font-bold text-[#075b63]">
                            <span>Читать статью</span>
                            <ArrowRight size={13} className="ml-1 group-hover:translate-x-1 transition-transform" />
                          </div>
                        </Link>
                      ))}
                    </div>
                  </div>
                )}

                {/* ARTICLE IN-TEXT CTA (LIGHT EMERALD) */}
                <div className="my-10 p-6 sm:p-8 rounded-3xl bg-gradient-to-br from-[#e5f4f3] via-[#edf7df]/60 to-[#eef3f2] border-2 border-[#b8c8c5] text-[#172120] shadow-md space-y-5">
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white border border-[#b8c8c5] text-[#075b63] text-xs font-black uppercase tracking-wider shadow-2xs">
                    <Sparkles size={13} /> Автоматизация поиска и аудита
                  </div>
                  <h3 className="text-2xl sm:text-3xl font-black tracking-tight text-[#172120]">
                    Найдите надежных поставщиков по вашему ТЗ за 3 минуты
                  </h3>
                  <p className="text-[#2f3f3d] text-sm sm:text-base leading-relaxed">
                    Загрузите техническое задание или спецификацию. ИИ TenderLex сопоставит номенклатуру, найдет прямые контакты отделов сбыта заводов и официальных дилеров по всей России и сформирует готовый запрос КП.
                  </p>
                  <div className="flex flex-wrap items-center gap-3 pt-2">
                    <Button asChild size="lg" className="bg-[#075b63] hover:bg-[#06464c] text-white font-black shadow-md shadow-[#075b63]/20">
                      <Link href="/cabinet">
                        Начать бесплатно
                      </Link>
                    </Button>
                    <Button asChild variant="secondary" size="lg" className="border-[#b8c8c5] bg-white text-[#172120] hover:bg-[#eef3f2] font-bold">
                      <a href={botUrl} target="_blank" rel="noopener noreferrer">
                        Запустить в Telegram
                      </a>
                    </Button>
                  </div>
                  <p className="text-xs text-[#697a77] font-semibold pt-1">
                    ✓ Бесплатный тестовый доступ
                  </p>
                </div>
              </article>

              {/* STICKY SIDEBAR */}
              <aside className="lg:col-span-4 space-y-6">
                {/* TOOL CARD */}
                <div className="sticky top-24 space-y-6">
                  <div className="p-6 rounded-3xl bg-[#f6f8f7] border border-[#d8e3e1] shadow-xs space-y-4">
                    <div className="flex items-center gap-2 text-[#075b63] font-black text-xs uppercase tracking-wider">
                      <ShieldCheck size={16} className="text-[#075b63]" /> Инструмент закупщика
                    </div>
                    <h4 className="text-lg font-black text-[#172120] leading-snug">
                      Поиск поставщиков и анализ документации
                    </h4>
                    <p className="text-xs text-[#2f3f3d] leading-relaxed">
                      Автоматический анализ извещений, ТЗ и спецификаций. Бесплатный пробный доступ.
                    </p>
                    <Button asChild className="w-full bg-[#075b63] hover:bg-[#06464c] text-white font-bold text-sm shadow-xs">
                      <Link href="/cabinet">
                        Начать бесплатно
                      </Link>
                    </Button>
                    <a
                      href={botUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block text-center text-xs text-[#697a77] hover:text-[#075b63] font-bold transition-colors"
                    >
                      Или в Telegram
                    </a>
                  </div>

                  {/* RELATED ARTICLES */}
                  {relatedArticles && relatedArticles.length > 0 && (
                    <div className="p-6 rounded-3xl bg-white border border-[#d8e3e1] shadow-2xs space-y-4">
                      <h4 className="text-xs font-black uppercase tracking-wider text-[#075b63]">
                        Рекомендуемые руководства
                      </h4>
                      <div className="space-y-3">
                        {relatedArticles.map((ra, idx) => (
                          <Link
                            key={idx}
                            href={`/baza-znaniy/${ra.slug}`}
                            className="block p-3 rounded-xl bg-[#f6f8f7] hover:bg-[#e5f4f3] border border-[#d8e3e1] hover:border-[#b8c8c5] transition-all group"
                          >
                            <span className="text-[10px] font-bold text-[#075b63] uppercase block mb-1">
                              {ra.tag}
                            </span>
                            <span className="text-xs font-bold text-[#172120] group-hover:text-[#075b63] transition-colors line-clamp-2">
                              {ra.title}
                            </span>
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}

                  <Link
                    href="/baza-znaniy"
                    className="inline-flex items-center text-xs font-bold text-[#697a77] hover:text-[#075b63] transition-colors"
                  >
                    <ArrowLeft size={14} className="mr-1.5" /> Ко всем статьям базы знаний
                  </Link>
                </div>
              </aside>
            </div>
          </div>
        </section>

        <ContactSection />
        <SiteFooter />
      </main>
    </>
  );
}

