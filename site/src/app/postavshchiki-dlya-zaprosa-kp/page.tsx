import type { Metadata } from "next";
import Link from "next/link";
import { Mail, CheckCircle2, FileText, Send, Building2, Sparkles } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildHowToJsonLd,
  buildServiceJsonLd,
  type FaqItem,
} from "@/lib/seo";

export const metadata: Metadata = {
  title: "Поставщики для запроса КП — поиск отделов продаж",
  description:
    "Быстрый отбор проверенных поставщиков и заводов для веерной рассылки запросов коммерческих предложений (RFQ) по спецификации.",
  keywords: [
    "поставщики для запроса КП",
    "база поставщиков для RFQ",
    "запрос цен по спецификации",
    "контакты отделов сбыта",
    "TenderLex",
  ],
  alternates: {
    canonical: "/postavshchiki-dlya-zaprosa-kp",
  },
};

const pagePath = "/postavshchiki-dlya-zaprosa-kp";

const faqItems: FaqItem[] = [
  {
    question: "Чем база TenderLex отличается от обычных телефонных справочников?",
    answer:
      "TenderLex не выдает устаревшие общие справочники, а в режиме реального времени сопоставляет номенклатуру вашего ТЗ с сайтами и прайсами компаний, извлекая прямые e-mail отделов продаж.",
  },
  {
    question: "Как использовать полученный список контрагентов?",
    answer:
      "Вы можете скачать готовый структурированный список контактов или воспользоваться встроенным автогенератором текста запроса КП для мгновенной отправки.",
  },
];

export default function PostavshchikiDlyaZaprosaKpPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Поставщики для запроса КП", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Поставщики для запроса КП",
    description: "Сервис подбора контактов поставщиков для веерной рассылки запросов цен.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как отобрать поставщиков для запроса КП",
    description: "Пошаговый процесс подбора базы для рассылки RFQ.",
    steps: [
      { name: "Загрузка позиций ТЗ", text: "Передайте список номенклатуры." },
      { name: "ИИ-поиск контактов", text: "Сбор direct email и телефонов отделов продаж." },
      { name: "Фильтрация ролей", text: "Разделение на заводы и дилерские сети." },
      { name: "Отправка запроса КП", text: "Массовая отправка готового письма." },
    ],
  });

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaBreadcrumb) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaService) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaFaq) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaHowTo) }} />

      <main className="bg-slate-50/60 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

        {/* HERO */}
        <section className="relative overflow-hidden pt-12 pb-20 border-b border-slate-200/90 bg-gradient-to-b from-teal-50/60 via-slate-50 to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-black uppercase tracking-wider shadow-2xs">
              <Mail size={14} className="text-teal-600" />
              <span>База адресатов для веерного сбора цен</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Отбор поставщиков для запроса коммерческого предложения (КП)
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Сбор прямых контактов менеджеров по продажам заводов и дилеров по вашей спецификации для получения минимальной цены в кратчайшие сроки.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Отобрать поставщиков</span>
              </a>
              <a
                href="https://t.me/tenderlex_bot"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-extrabold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
              >
                <Send size={16} className="text-teal-600" />
                <span>Запустить в Telegram</span>
              </a>
            </div>
          </div>
        </section>

        {/* BENEFITS */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Direct Email</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Прямые адреса менеджеров по продажам вместо инфо-ящиков.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Высокая конверсия ответа</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Обращение попадает сразу к профильному сотруднику сбыта.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Экономия времени</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Подготовка базы и текста запроса занимает 3 минуты вместо полудня.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-slate-50">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6">
            <h2 className="text-2xl sm:text-4xl font-black text-slate-900 text-center mb-12">
              Часто задаваемые вопросы
            </h2>
            <div className="space-y-4">
              {faqItems.map((item, index) => (
                <details key={index} className="group bg-white p-6 rounded-2xl border-2 border-slate-200 text-left shadow-2xs">
                  <summary className="font-bold text-slate-900 text-base cursor-pointer flex justify-between items-center list-none">
                    <span>{item.question}</span>
                    <span className="transition group-open:rotate-180 text-teal-700">▼</span>
                  </summary>
                  <p className="mt-4 text-sm text-slate-700 font-medium leading-relaxed border-t border-slate-200 pt-4">
                    {item.answer}
                  </p>
                </details>
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
