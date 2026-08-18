import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  FileText,
  Mail,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users,
  Layers,
  Zap,
  TrendingUp,
  FileCheck,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatRubles, getSiteData, type PublicTariff } from "@/lib/site-data";
import {
  buildFaqJsonLd,
  buildOrganizationJsonLd,
  buildSoftwareApplicationJsonLd,
  buildWebSiteJsonLd,
  type FaqItem,
} from "@/lib/seo";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { RfqPreviewWidget } from "@/components/rfq-preview-widget";
import { ProcurementCalculator } from "@/components/procurement-calculator";
import { ComparisonSection } from "@/components/comparison-section";
import { ScrollWorldViewer } from "@/components/scroll-world/scroll-world-viewer";

export const revalidate = 300;

export const metadata: Metadata = {
  title: "TenderLex — Интерактивный WOW-сценарий снабжения и поиска заводов",
  description:
    "Демонстрация работы платформы TenderLex: сквозной сценарий от загрузки сырого ТЗ и аудита рисков 44-ФЗ до поиска прямых заводов РФ и победы в закупке.",
  robots: {
    index: false,
    follow: false,
  },
};

const mainFaqItems: FaqItem[] = [
  {
    question: "Как TenderLex находит поставщиков по всей России?",
    answer:
      "TenderLex выполняет смысловой анализ вашего ТЗ или спецификации, определяет маркоразмеры, ГОСТы и технические требования, после чего сопоставляет данные с общероссийской базой предприятий. Сервис извлекает прямые email-адреса отделов сбыта, телефоны и классифицирует поставщиков на заводы-изготовители и официальных дилеров.",
  },
  {
    question: "Как формируется готовый Запрос коммерческого предложения (КП)?",
    answer:
      "На основе номенклатуры ТЗ алгоритм автоматически собирает официальное письмо с таблицей позиций, объемами, требованиями по доставке и запросом сертификатов соответствия.",
  },
  {
    question: "Что проверяет модуль анализа документации 44-ФЗ и 223-ФЗ?",
    answer:
      "Модуль проверяет проект контракта и извещение на наличие нетипичных штрафов, несоответствия сроков поставки и приемки, условий авансирования и требований национального режима (реестр Минпромторга, Постановления № 616 и 617).",
  },
  {
    question: "Как протестировать сервис бесплатно?",
    answer:
      "При регистрации в личном кабинете или в Telegram-боте каждому новому пользователю автоматически предоставляется бесплатный пробный доступ для тестирования поиска или аудита контракта.",
  },
];

export default async function DemoWorldPage() {
  const data = await getSiteData();
  const botUrl = process.env.NEXT_PUBLIC_BOT_URL || "https://t.me/tenderlex_bot";
  const cabinetUrl = "/cabinet";
  const supplierTariffs = data.tariff_groups?.supplier_search || [];
  const reportTariffs = data.tariff_groups?.procurement_report || [];

  return (
    <main className="bg-slate-50 text-slate-900 min-h-screen font-sans">
      <SiteHeader />

      {/* DEMO NOTICE BANNER */}
      <div className="bg-teal-950 text-teal-200 border-b border-teal-800/80 py-2.5 px-4 text-xs font-semibold text-center">
        <div className="container max-w-6xl mx-auto flex items-center justify-center gap-2">
          <Sparkles className="w-4 h-4 text-teal-400 animate-pulse" />
          <span>
            <strong>Демонстрационный дубликат главной страницы</strong> с интерактивным сценарием &laquo;Scroll-World Diorama&raquo;
          </span>
          <span className="text-teal-400/60 hidden sm:inline">•</span>
          <Link href="/" className="underline text-teal-300 hover:text-white transition-colors hidden sm:inline">
            Вернуться на стандартную главную
          </Link>
        </div>
      </div>

      {/* HERO SECTION WITH WOW SCROLL-WORLD */}
      <section className="relative pt-10 pb-16 border-b border-slate-200 bg-gradient-to-b from-teal-50/50 via-slate-50 to-white">
        <div className="container max-w-6xl mx-auto px-4 sm:px-6">
          {/* Hero Header */}
          <div className="max-w-3xl mx-auto text-center space-y-4 mb-10">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-bold shadow-2xs">
              <Sparkles size={14} className="text-teal-600 animate-pulse" />
              <span>Интерактивный сценарий закупки TenderLex</span>
            </div>

            <h1 className="text-3xl sm:text-4xl lg:text-[42px] font-extrabold text-slate-900 leading-[1.2] tracking-tight">
              Путь закупки: от сложного ТЗ до прямого завода и выигранного тендера
            </h1>

            <p className="text-base sm:text-lg text-slate-600 font-normal leading-relaxed">
              Пошаговый интерактивный процесс: как искусственный интеллект TenderLex разбирает спецификацию, устраняет правовые ловушки 44-ФЗ и находит производителей по всей России.
            </p>
          </div>

          {/* THE WOW SCROLL-WORLD COMPONENT */}
          <div className="mb-12">
            <ScrollWorldViewer />
          </div>

          {/* Metric Bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-6 bg-white rounded-2xl border border-slate-200 shadow-sm text-center">
            <div>
              <strong className="block text-2xl font-black text-teal-700">3 минуты</strong>
              <span className="text-xs text-slate-500">на разбор любого ТЗ</span>
            </div>
            <div>
              <strong className="block text-2xl font-black text-teal-700">350 000+</strong>
              <span className="text-xs text-slate-500">предприятий в базе РФ</span>
            </div>
            <div>
              <strong className="block text-2xl font-black text-teal-700">до 22%</strong>
              <span className="text-xs text-slate-500">снижение себестоимости</span>
            </div>
            <div>
              <strong className="block text-2xl font-black text-teal-700">100%</strong>
              <span className="text-xs text-slate-500">защита от штрафов и РНП</span>
            </div>
          </div>
        </div>
      </section>

      {/* TWO PRIMARY MODULES (Core Platform Architecture) */}
      <section className="py-16 sm:py-24 bg-white border-b border-slate-200">
        <div className="container max-w-6xl mx-auto px-4 sm:px-6">
          <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
            <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
              Два ключевых модуля платформы
            </span>
            <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
              Инструменты для эффективного снабжения и участия в закупках
            </h2>
            <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
              TenderLex закрывает две главные задачи бизнеса: быстрый выход на прямых поставщиков и правовая защита при участии в торгах.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Module 1 */}
            <div className="p-8 bg-slate-50 rounded-3xl border-2 border-slate-200 flex flex-col justify-between space-y-6 shadow-sm hover:border-teal-500 transition-all">
              <div className="space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center">
                  <Search className="w-6 h-6" />
                </div>
                <span className="text-xs font-bold text-teal-700 uppercase tracking-wider block">Модуль 1</span>
                <h3 className="text-2xl font-extrabold text-slate-900">
                  Поиск поставщиков и заводов по всей России
                </h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Автоматический разбор сложных спецификаций, распознавание ГОСТ, марок сталей и типоразмеров. Сбор прямых контактов отделов сбыта без посредников.
                </p>

                <ul className="space-y-3 pt-2 border-t border-slate-200">
                  <li className="flex items-start text-xs text-slate-700 font-semibold">
                    <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2.5 shrink-0 mt-0.5" />
                    <span>Прямые e-mail адреса и телефоны менеджеров по продажам</span>
                  </li>
                  <li className="flex items-start text-xs text-slate-700 font-semibold">
                    <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2.5 shrink-0 mt-0.5" />
                    <span>Разделение компаний на заводы-изготовители и дилерские сети</span>
                  </li>
                  <li className="flex items-start text-xs text-slate-700 font-semibold">
                    <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2.5 shrink-0 mt-0.5" />
                    <span>Авто-генератор готового текста Запроса коммерческого предложения (RFQ)</span>
                  </li>
                </ul>
              </div>

              <div className="pt-4">
                <Button asChild className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold h-11 text-xs shadow-md shadow-teal-600/20">
                  <Link href="/poisk-postavshchikov-po-tz">
                    <span>Подробнее о поиске поставщиков</span>
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Link>
                </Button>
              </div>
            </div>

            {/* Module 2 */}
            <div className="p-8 bg-slate-50 rounded-3xl border-2 border-slate-200 flex flex-col justify-between space-y-6 shadow-sm hover:border-teal-500 transition-all">
              <div className="space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center">
                  <ShieldAlert className="w-6 h-6" />
                </div>
                <span className="text-xs font-bold text-teal-700 uppercase tracking-wider block">Модуль 2</span>
                <h3 className="text-2xl font-extrabold text-slate-900">
                  Экспресс-аудит закупочной документации 44-ФЗ / 223-ФЗ
                </h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Проверка проекта контракта до подачи заявки на участие: выявление скрытых штрафов, невыполнимых сроков и ограничений национального режима.
                </p>

                <ul className="space-y-3 pt-2 border-t border-slate-200">
                  <li className="flex items-start text-xs text-slate-700 font-semibold">
                    <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2.5 shrink-0 mt-0.5" />
                    <span>Сверка графиков поставки и сроков приемки заказчиком</span>
                  </li>
                  <li className="flex items-start text-xs text-slate-700 font-semibold">
                    <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2.5 shrink-0 mt-0.5" />
                    <span>Аудит штрафов и неустоек на соответствие ПП РФ № 1042</span>
                  </li>
                  <li className="flex items-start text-xs text-slate-700 font-semibold">
                    <CheckCircle2 className="w-4 h-4 text-teal-600 mr-2.5 shrink-0 mt-0.5" />
                    <span>Проверка требований Минпромторга (Постановления № 616 и № 617)</span>
                  </li>
                </ul>
              </div>

              <div className="pt-4">
                <Button asChild className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold h-11 text-xs shadow-md shadow-teal-600/20">
                  <Link href="/analiz-zakupochnoi-dokumentacii">
                    <span>Подробнее об анализе документации</span>
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* COMPARISON SECTION */}
      <section className="py-16 sm:py-24 bg-slate-50 border-b border-slate-200">
        <div className="container max-w-6xl mx-auto px-4 sm:px-6">
          <div className="text-center max-w-2xl mx-auto mb-12 sm:mb-16 space-y-3">
            <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
              Сравнение подходов
            </span>
            <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
              Ручной поиск в поисковиках против ИИ TenderLex
            </h2>
            <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
              Почему специалисты по закупкам выбирают автоматизированный сбор контактов.
            </p>
          </div>

          <ComparisonSection />
        </div>
      </section>

      {/* RFQ GENERATOR WIDGET */}
      <section className="py-16 sm:py-24 bg-white border-b border-slate-200">
        <div className="container max-w-6xl mx-auto px-4 sm:px-6">
          <RfqPreviewWidget />
        </div>
      </section>

      {/* PROCUREMENT CALCULATOR */}
      <section id="calculator" className="py-16 sm:py-24 bg-slate-50 border-b border-slate-200">
        <div className="container max-w-6xl mx-auto px-4 sm:px-6">
          <ProcurementCalculator />
        </div>
      </section>

      {/* PRICING & TARIFFS */}
      <section id="pricing" className="py-16 sm:py-24 bg-white border-b border-slate-200">
        <div className="container max-w-6xl mx-auto px-4 sm:px-6">
          <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
            <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
              Тарифы сервиса
            </span>
            <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
              Прозрачная стоимость без скрытых платежей
            </h2>
            <p className="text-slate-600 text-sm sm:text-base">
              Бесплатный пробный доступ предоставляется автоматически при регистрации.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            {/* Поставщики */}
            <div className="p-8 bg-gradient-to-br from-white to-teal-50/40 rounded-3xl border-2 border-slate-200 shadow-md flex flex-col justify-between">
              <div>
                <span className="text-xs font-bold text-teal-700 uppercase tracking-wider">Подбор поставщиков по ТЗ</span>
                <h3 className="text-2xl font-extrabold text-slate-900 mt-1 mb-2">Контакты поставщиков</h3>
                <p className="text-xs text-slate-600 mb-4">Извлечение direct email, телефонов отделов продаж и ролей компаний по всей РФ.</p>
                <div className="space-y-3 border-t border-slate-200 pt-4 mb-6">
                  {supplierTariffs.map((t: PublicTariff) => (
                    <div key={t.id} className="flex justify-between items-center text-xs">
                      <span className="text-slate-800 font-bold">{t.name}</span>
                      <strong className="text-teal-700 font-extrabold">{formatRubles(t.price_kopeks)}</strong>
                    </div>
                  ))}
                </div>
              </div>
              <Button asChild className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold h-11 text-xs shadow-md shadow-teal-600/20">
                <a href={cabinetUrl}>Выбрать пакет поставщиков</a>
              </Button>
            </div>

            {/* Анализ документации */}
            <div className="p-8 bg-gradient-to-br from-white to-teal-50/40 rounded-3xl border-2 border-slate-200 shadow-md flex flex-col justify-between">
              <div>
                <span className="text-xs font-bold text-teal-700 uppercase tracking-wider">Анализ 44-ФЗ / 223-ФЗ</span>
                <h3 className="text-2xl font-extrabold text-slate-900 mt-1 mb-2">Анализ документации</h3>
                <p className="text-xs text-slate-600 mb-4">Аудит рисков контракта, нетипичных штрафов, сроков и Минпромторга.</p>
                <div className="space-y-3 border-t border-slate-200 pt-4 mb-6">
                  {reportTariffs.map((t: PublicTariff) => (
                    <div key={t.id} className="flex justify-between items-center text-xs">
                      <span className="text-slate-800 font-bold">{t.name}</span>
                      <strong className="text-teal-700 font-extrabold">{formatRubles(t.price_kopeks)}</strong>
                    </div>
                  ))}
                </div>
              </div>
              <Button asChild className="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold h-11 text-xs shadow-md shadow-teal-600/20">
                <a href={cabinetUrl}>Выбрать пакет отчетов</a>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ SECTION */}
      <section id="faq" className="py-16 sm:py-24 border-b border-slate-200 bg-slate-50">
        <div className="container max-w-4xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-12 space-y-3">
            <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">Часто задаваемые вопросы</h2>
            <p className="text-slate-600 text-sm">Ответы на ключевые вопросы о работе сервиса.</p>
          </div>

          <div className="space-y-4">
            {mainFaqItems.map((faq, idx) => (
              <details key={idx} className="group bg-white p-6 rounded-2xl border-2 border-slate-200 text-left shadow-2xs">
                <summary className="font-bold text-slate-900 text-base cursor-pointer flex justify-between items-center list-none">
                  <span>{faq.question}</span>
                  <span className="transition group-open:rotate-180 text-teal-700">▼</span>
                </summary>
                <p className="mt-4 text-sm text-slate-700 font-normal leading-relaxed border-t border-slate-200 pt-4">
                  {faq.answer}
                </p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* CONTACT SECTION */}
      <ContactSection />

      <SiteFooter />
    </main>
  );
}
