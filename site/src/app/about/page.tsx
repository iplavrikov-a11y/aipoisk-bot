import type { Metadata } from "next";
import Link from "next/link";
import { ShieldCheck, Building2, CheckCircle2, FileText, Users, Phone, Mail, Send, MessageCircle, Sparkles } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { buildBreadcrumbJsonLd } from "@/lib/seo";
import { getSiteData } from "@/lib/site-data";

export const metadata: Metadata = {
  title: "О сервисе — технологии и контакты",
  description:
    "Официальная информация о B2B-платформе TenderLex: миссия, алгоритмы смыслового анализа ТЗ, обработка данных и контакты сервиса снабжения.",
  alternates: {
    canonical: "/about",
  },
  openGraph: {
    type: "website",
    url: "/about",
    title: "О сервисе TenderLex | Платформа автоматизации снабжения",
    description: "Принципы работы алгоритмов ИИ-поиска прямых контактов заводов, методология анализа рисков 44-ФЗ, 223-ФЗ, коммерческих закупок и юридическая информация.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

export default async function AboutPage() {
  const data = await getSiteData();
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
                  Сократить ручную работу со спецификациями, помочь закупщикам находить профильных производителей и заранее выявлять риски участия в невыгодных или рискованных процедурах по 44-ФЗ, 223-ФЗ и коммерческим торгам.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200 space-y-4 shadow-2xs">
                <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center">
                  <ShieldCheck size={24} />
                </div>
                <h2 className="text-xl font-black text-slate-900">Данные и настройки аналитики</h2>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Доступ к задачам и результатам связан с учётной записью пользователя. Необязательная аналитика включается с согласия, а загруженные документы и текст задания не передаются в события Метрики. Порядок обработки данных и способы связи описаны в политике конфиденциальности.
                </p>
                <Link href="/privacy" className="inline-flex text-sm font-bold text-teal-700 underline underline-offset-4">Прочитать политику конфиденциальности</Link>
              </div>
            </div>

            <section className="rounded-3xl border-2 border-slate-200 bg-white p-6 sm:p-8 space-y-5">
              <h2 className="text-2xl font-black text-slate-900">Как оценить результат до закупочного решения</h2>
              <ol className="list-decimal pl-5 space-y-3 text-sm leading-relaxed text-slate-700">
                <li>Задайте предмет закупки, обязательные характеристики и условия поставки. Неопределённые требования отметьте отдельно.</li>
                <li>Поиск поставщиков помогает составить список компаний для обращения. Наличие компании в списке не подтверждает остаток товара, цену или готовность поставить его в нужный срок.</li>
                <li>Подбор товара и аналогов сопоставляет требования с доступными характеристиками. Существенные параметры и допустимость замены проверьте по документам производителя и условиям закупки.</li>
                <li>Анализ документации выделяет вопросы и риски для проверки. Он не заменяет заключение профильного специалиста и не гарантирует допуск к закупке.</li>
                <li>Перед использованием результата уточните сведения у поставщика и сравните их с исходным заданием. Если результат вызывает вопросы, обратитесь в поддержку с описанием задачи.</li>
              </ol>
              <div className="flex flex-wrap gap-4 text-sm font-bold text-teal-700">
                <Link href="/baza-znaniy" className="underline underline-offset-4">Практические инструкции и источники</Link>
                <Link href="/terms" className="underline underline-offset-4">Условия использования</Link>
                <Link href="/#pricing" className="underline underline-offset-4">Доступные тарифы</Link>
              </div>
              <p className="text-xs leading-relaxed text-slate-500">Примеры на сайте показывают структуру результата на учебных данных. Они не являются отзывами клиентов или подтверждением конкретной поставки.</p>
            </section>

            {/* Contacts Block */}
            <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200 space-y-6 shadow-2xs">
              <h2 className="text-2xl font-black text-slate-900">Контакты сервиса</h2>
              <div className="text-xs text-slate-700 font-medium space-y-2.5 max-w-lg">
                <p><strong className="text-slate-900 font-bold">Telegram-бот:</strong> <a href={data.bot.telegram_url} target="_blank" rel="noreferrer" className="text-teal-700 font-bold hover:underline">{data.bot.telegram || "Открыть бота"}</a></p>
                <p><strong className="text-slate-900 font-bold">Telegram:</strong> <a href={data.contacts.telegram_url} target="_blank" rel="noreferrer" className="text-teal-700 font-bold hover:underline">{data.contacts.telegram || "Написать в Telegram"}</a></p>
                <p><strong className="text-slate-900 font-bold">Email:</strong> <a href={`mailto:${data.contacts.email}`} className="text-teal-700 font-bold hover:underline">{data.contacts.email}</a></p>
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
