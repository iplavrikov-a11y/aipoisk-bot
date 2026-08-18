import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { BookOpen, ArrowLeft, ArrowRight, CheckCircle2, FileText, Sparkles } from "lucide-react";

interface KnowledgeArticleLayoutProps {
  tag: string;
  title: string;
  subtitle: string;
  steps?: { name: string; text: string }[];
  children: React.ReactNode;
  breadcrumbSchema: object;
  howToSchema?: object;
}

export function KnowledgeArticleLayout({
  tag,
  title,
  subtitle,
  steps,
  children,
  breadcrumbSchema,
  howToSchema,
}: KnowledgeArticleLayoutProps) {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      {howToSchema && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(howToSchema) }}
        />
      )}

      <main className="bg-slate-50/60 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

        <article className="py-16 sm:py-24 border-b border-slate-200">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6">
            <Link
              href="/baza-znaniy"
              className="inline-flex items-center text-xs font-bold text-teal-700 hover:text-teal-900 transition-colors uppercase tracking-wider mb-6"
            >
              <ArrowLeft size={14} className="mr-1.5" /> Назад в базу знаний
            </Link>

            <header className="mb-12 space-y-4 border-b border-slate-200 pb-8">
              <span className="inline-block px-3 py-1 text-[10px] font-black uppercase tracking-wider text-teal-900 bg-teal-100 border border-teal-300 rounded-lg">
                {tag}
              </span>
              <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight leading-tight">
                {title}
              </h1>
              <p className="text-base sm:text-lg text-slate-600 font-medium leading-relaxed">
                {subtitle}
              </p>
            </header>

            <div className="space-y-8 text-slate-700 text-sm sm:text-base leading-relaxed">
              {children}

              {steps && steps.length > 0 && (
                <div className="my-10 p-8 rounded-3xl bg-white border-2 border-slate-200 shadow-sm space-y-6">
                  <h2 className="text-xl font-black text-slate-900">Пошаговый регламент действий</h2>
                  <div className="space-y-4">
                    {steps.map((s, idx) => (
                      <div key={idx} className="flex items-start gap-4">
                        <span className="w-8 h-8 rounded-xl bg-teal-100 border border-teal-300 text-teal-800 font-black flex items-center justify-center shrink-0 text-xs">
                          {idx + 1}
                        </span>
                        <div>
                          <strong className="text-slate-900 block text-sm font-bold">{s.name}</strong>
                          <p className="text-xs text-slate-600 mt-1 leading-relaxed">{s.text}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </article>

        <ContactSection />

        <SiteFooter />
      </main>
    </>
  );
}
