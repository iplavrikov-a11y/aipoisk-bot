import { TenderLexLogo } from '@/components/logo';
import type { Metadata } from "next";
import Image from "next/image";
import { ShieldCheck, Building2, CheckCircle2, FileText, Lock, Users, ArrowLeft } from "lucide-react";

import { buildBreadcrumbJsonLd, buildOrganizationJsonLd } from "@/lib/seo";
import { Button } from "@/components/ui/button";

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
    description:
      "Принципы работы алгоритмов ИИ-поиска прямых контактов заводов, методология анализа рисков 44-ФЗ/223-ФЗ и юридическая информация.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

export default function AboutPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "О сервисе", path: "/about" },
  ]);

  const orgSchema = buildOrganizationJsonLd();

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(orgSchema) }}
      />

      {/* Navigation Header */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-slate-200/80 shadow-xs">
        <div className="container max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2.5 text-teal-700 font-extrabold text-xl tracking-tight">
            <TenderLexLogo size={36} />
          </a>

          <nav className="hidden md:flex items-center gap-8 text-sm font-semibold text-slate-600">
            <a href="/#features" className="hover:text-teal-700 transition-colors">Возможности</a>
            <a href="/regiony" className="hover:text-teal-700 transition-colors">Регионы</a>
            <a href="/baza-znaniy" className="hover:text-teal-700 transition-colors">База знаний</a>
            <a href="/about" className="text-teal-700 font-bold">О сервисе</a>
          </nav>

          <Button asChild className="bg-teal-600 hover:bg-teal-700 text-slate-900 font-bold shadow-sm shadow-teal-600/20 rounded-xl">
            <a href="/cabinet">Личный кабинет</a>
          </Button>
        </div>
      </header>

      {/* Main Content Container */}
      <div className="container max-w-4xl mx-auto px-4 py-12">
        <nav className="mb-8">
          <a href="/" className="inline-flex items-center text-xs font-bold text-teal-700 hover:text-teal-800 transition-colors">
            <ArrowLeft className="w-4 h-4 mr-1.5" /> Вернуться на главную TenderLex
          </a>
        </nav>

        {/* Hero Title Header */}
        <header className="mb-12 border-b border-slate-200 pb-10">
          <span className="text-xs font-bold uppercase tracking-wider text-teal-800 bg-teal-100/90 px-3 py-1 rounded-full border border-teal-200 inline-block mb-4">
            E-E-A-T Экспертиза и Прозрачность
          </span>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 leading-tight tracking-tight mb-4">
            О платформе TenderLex и технологии ИИ-анализа
          </h1>
          <p className="text-lg text-slate-600 leading-relaxed">
            TenderLex — специализированный российский B2B-сервис автоматизации работы отделов снабжения, закупщиков и тендерных специалистов, основанный на алгоритмах смыслового анализа документации.
          </p>
        </header>

        {/* Core Pillars Grid */}
        <div className="grid md:grid-cols-2 gap-6 mb-12">
          <section className="p-8 bg-white rounded-2xl border border-slate-200 shadow-sm space-y-4">
            <div className="w-12 h-12 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700">
              <Building2 className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-slate-900">Наша миссия</h2>
            <p className="text-sm text-slate-600 leading-relaxed">
              Сократить время поиска прямых контрагентов и подготовки Запроса КП с 6 часов ручной работы до 3 минут. Мы помогаем закупщикам напрямую связываться с отделами продаж заводов-изготовителей и официальных дилеров по всей России.
            </p>
          </section>

          <section className="p-8 bg-white rounded-2xl border border-slate-200 shadow-sm space-y-4">
            <div className="w-12 h-12 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-slate-900">Анализ рисков 44-ФЗ / 223-ФЗ</h2>
            <p className="text-sm text-slate-600 leading-relaxed">
              Алгоритмы сервиса считывают специфические требования контрактов, включая жесткие сроки поставки, скрытые штрафные санкции, нормативные реестры Минпромторга (Постановления № 616 и 617) и требования к сертификации.
            </p>
          </section>
        </div>

        {/* Technology Stack Details */}
        <section className="p-8 bg-white rounded-2xl border border-slate-200 shadow-sm mb-12 space-y-6">
          <h2 className="text-2xl font-bold text-slate-900">Принципы работы технологии TenderLex</h2>
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-teal-600 shrink-0 mt-0.5" />
              <div>
                <strong className="block text-slate-900 font-bold text-sm">Смысловой разбор номенклатуры ТЗ:</strong>
                <span className="text-xs text-slate-600">Извлечение конкретных наименований, стандартов ГОСТ/ТУ, типоразмеров и фасовок без канцелярита.</span>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-teal-600 shrink-0 mt-0.5" />
              <div>
                <strong className="block text-slate-900 font-bold text-sm">Прямое извлечение контактов отделов продаж:</strong>
                <span className="text-xs text-slate-600">Отсеивание досок объявлений и перекупщиков с прямым выходом на ком-отделы и службы сбыта.</span>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-teal-600 shrink-0 mt-0.5" />
              <div>
                <strong className="block text-slate-900 font-bold text-sm">Авто-генератор единого Запроса КП:</strong>
                <span className="text-xs text-slate-600">Формирование готового структурированного текста электронного письма для мгновенной рассылки.</span>
              </div>
            </div>
          </div>
        </section>

        {/* Legal & E-E-A-T Trust Section */}
        <section className="p-8 bg-slate-100/80 rounded-2xl border border-slate-200 space-y-6">
          <div className="flex items-center gap-2">
            <Lock className="w-5 h-5 text-teal-700" />
            <h2 className="text-xl font-bold text-slate-900">Правовая информация и реквизиты</h2>
          </div>

          <div className="grid sm:grid-cols-2 gap-4 text-xs text-slate-700">
            <div className="p-4 bg-white rounded-xl border border-slate-200 space-y-1">
              <span className="text-slate-500 font-medium">Наименование сервиса:</span>
              <strong className="block text-slate-900 font-bold">Онлайн-платформа TenderLex</strong>
            </div>
            <div className="p-4 bg-white rounded-xl border border-slate-200 space-y-1">
              <span className="text-slate-500 font-medium">Зона обслуживания:</span>
              <strong className="block text-slate-900 font-bold">Вся Российская Федерация (ИИ-сервис снабжения)</strong>
            </div>
            <div className="p-4 bg-white rounded-xl border border-slate-200 space-y-1">
              <span className="text-slate-500 font-medium">Защита персональных данных:</span>
              <strong className="block text-slate-900 font-bold">Соответствие 152-ФЗ РФ</strong>
            </div>
            <div className="p-4 bg-white rounded-xl border border-slate-200 space-y-1">
              <span className="text-slate-500 font-medium">Электронная почта поддержки:</span>
              <a href="mailto:support@tenderlex.ru" className="block text-teal-700 font-bold hover:underline">
                support@tenderlex.ru
              </a>
            </div>
          </div>
        </section>
      </div>

      {/* Footer */}
      <footer className="py-12 border-t border-slate-200 text-xs text-slate-600 bg-slate-100 mt-12">
        <div className="container max-w-6xl mx-auto px-4 flex flex-col md:flex-row justify-between items-center gap-6">
          <div>
            <strong className="text-slate-900 font-bold text-sm block mb-1">TenderLex</strong>
            <span>Зона обслуживания: Вся Россия (онлайн B2B-сервис снабжения)</span>
          </div>
          <div className="flex gap-6">
            <a href="/regiony" className="hover:text-teal-700 font-semibold">Регионы РФ</a>
            <a href="/baza-znaniy" className="hover:text-teal-700 font-semibold">База знаний</a>
            <a href="/about" className="hover:text-teal-700 font-semibold">О сервисе</a>
            <a href="/legal" className="hover:text-teal-700 font-semibold">Правовая информация</a>
            <a href="/privacy" className="hover:text-teal-700 font-semibold">Конфиденциальность</a>
          </div>
        </div>
      </footer>
    </main>
  );
}
