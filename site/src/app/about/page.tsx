import type { Metadata } from "next";
import Link from "next/link";
import { ShieldCheck, Building2, CheckCircle2, FileText, Users, Phone, Mail, Send, MessageCircle, Sparkles } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { buildBreadcrumbJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "О сервисе TenderLex — Юридические данные, Технология и Команда",
  description:
    "Официальная информация о B2B-платформе TenderLex: миссия, алгоритмы смыслового анализа ТЗ, соблюдение 152-ФЗ и реквизиты сервиса снабжения.",
  alternates: {
    canonical: "/about",
  },
  openGraph: {
    type: "website",
    url: "/about",
    title: "О сервисе TenderLex | Платформа автоматизации снабжения",
    description: "Принципы работы алгоритмов ИИ-поиска прямых контактов заводов, методология анализа рисков 44-ФЗ/223-ФЗ и юридическая информация.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

export default function AboutPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "О сервисе", item: "https://tenderlex.ru/about" },
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
          <div className="container max-w-4xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-black uppercase tracking-wider shadow-2xs">
              <Building2 size={14} className="text-teal-600" />
              <span>О платформе TenderLex</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight leading-tight">
              Интеллектуальная автоматизация снабжения и закупок
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              TenderLex разрабатывается для решения ключевой боли специалистов по снабжению и тендерных экспертов — долгого и рутинного ручного сбора прямых контактов контрагентов и разбора сложных спецификаций.
            </p>
          </div>
        </section>

        {/* MISSION & TECHNOLOGY */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6 space-y-12">
            <div className="grid sm:grid-cols-2 gap-8">
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200 space-y-4 shadow-2xs">
                <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center">
                  <FileText size={24} />
                </div>
                <h2 className="text-xl font-black text-slate-900">Наша миссия</h2>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Сократить время обработки одной закупочной спецификации с 8 часов до 3 минут, дать закупщикам возможность быстро выходить напрямую на заводы-производители и исключить риски участия в невыгодных или рискованных процедурах 44-ФЗ.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200 space-y-4 shadow-2xs">
                <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center">
                  <ShieldCheck size={24} />
                </div>
                <h2 className="text-xl font-black text-slate-900">Безопасность и 152-ФЗ</h2>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Все данные пользователей и загружаемая документация обрабатываются на защищенных серверах в Российской Федерации в строгом соответствии с Федеральным законом № 152-ФЗ «О персональных данных».
                </p>
              </div>
            </div>

            {/* Requisites Block */}
            <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200 space-y-6 shadow-2xs">
              <h2 className="text-2xl font-black text-slate-900">Официальные юридические реквизиты</h2>
              <div className="grid sm:grid-cols-2 gap-6 text-xs text-slate-700 font-medium">
                <div className="space-y-2">
                  <p><strong className="text-slate-900 font-bold">Оператор сервиса:</strong> ИП Груздев Игорь Вячеславович</p>
                  <p><strong className="text-slate-900 font-bold">ИНН:</strong> 352516048881</p>
                  <p><strong className="text-slate-900 font-bold">ОГРНИП:</strong> 323352500038991</p>
                  <p><strong className="text-slate-900 font-bold">Адрес:</strong> 160541, Вологодская обл., Вологодский р-н, дер. Тарасово, д. 3</p>
                </div>
                <div className="space-y-2">
                  <p><strong className="text-slate-900 font-bold">Телефон:</strong> <a href="tel:+79211460080" className="text-teal-700 font-bold hover:underline">+7 (921) 146-00-80</a></p>
                  <p><strong className="text-slate-900 font-bold">WhatsApp:</strong> <a href="https://wa.me/79211460080" target="_blank" rel="noreferrer" className="text-teal-700 font-bold hover:underline">+7 (921) 146-00-80</a></p>
                  <p><strong className="text-slate-900 font-bold">Telegram-бот:</strong> <a href="https://t.me/tenderlex_bot" target="_blank" rel="noreferrer" className="text-teal-700 font-bold hover:underline">@tenderlex_bot</a></p>
                  <p><strong className="text-slate-900 font-bold">Telegram поддержка:</strong> <a href="https://t.me/lexelence" target="_blank" rel="noreferrer" className="text-teal-700 font-bold hover:underline">@lexelence</a></p>
                  <p><strong className="text-slate-900 font-bold">Max:</strong> <a href="https://max.ru/u/f9LHodD0cOJBLDdTXMGDPUvHbbK_bKtz9e0GgYPWHvxUgk9rZvGGwCdYvqs" target="_blank" rel="noreferrer" className="text-teal-700 font-bold hover:underline">+7 (921) 062-99-09</a></p>
                  <p><strong className="text-slate-900 font-bold">Email:</strong> <a href="mailto:support@tenderlex.ru" className="text-teal-700 font-bold hover:underline">support@tenderlex.ru</a> / <a href="mailto:info@tenderlex.ru" className="text-teal-700 font-bold hover:underline">info@tenderlex.ru</a></p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <ContactSection />

        <SiteFooter />
      </main>
    </>
  );
}
