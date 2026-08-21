import type { Metadata } from "next";
import Link from "next/link";
import { FileText, CheckCircle2, Send, Building2, ArrowRight, Sparkles } from "lucide-react";
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
  title: "Запрос КП по ТЗ — автоматическая подготовка запросов цен",
  description:
    "Автоматическое составление официального запроса коммерческого предложения (RFQ) по спецификации. Структурированная таблица, объемы, ГОСТы и дедлайн.",
  keywords: [
    "запрос КП по ТЗ",
    "генератор запроса коммерческого предложения",
    "составить RFQ по спецификации",
    "шаблон запроса цен поставщикам",
    "TenderLex",
  ],
  alternates: {
    canonical: "/zapros-kp-po-tz",
  },
};

const pagePath = "/zapros-kp-po-tz";

const faqItems: FaqItem[] = [
  {
    question: "Как работает авто-генератор запроса КП?",
    answer:
      "TenderLex извлекает из вашего ТЗ перечень позиций, маркоразмеры, единицы измерения и объемы, после чего автоматически собирает деловое обращение с таблицей, требованиями к паспортам качества и сроками ответа.",
  },
  {
    question: "Можно ли отредактировать сформированный текст?",
    answer:
      "Да, текст формируется в удобном формате для копирования и редактирования в вашем почтовом клиенте или корпоративной CRM.",
  },
];

export default function ZaprosKpPoTzPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Запрос КП по ТЗ", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Генератор запроса КП по ТЗ",
    description: "Сервис автогенерации текстов запросов коммерческих предложений по спецификациям.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как составить запрос КП по ТЗ",
    description: "Пошаговый процесс автоматического формирования RFQ.",
    steps: [
      { name: "Загрузка спецификации", text: "Передайте файл или текст номенклатуры." },
      { name: "ИИ-структурирование", text: "Формирование таблицы параметров и объемов." },
      { name: "Добавление условий", text: "Указание адреса доставки, фасовки и дедлайна." },
      { name: "Копирование текста", text: "Готовое письмо для отправки поставщикам." },
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
              <FileText size={14} className="text-teal-600" />
              <span>Автоматическая генерация текста RFQ</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Генератор запроса коммерческого предложения (КП) по ТЗ
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Преобразуйте сырую спецификацию или проект в структурированное деловое письмо с таблицей номенклатуры, объемами и требованиями к сертификатам.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Сформировать запрос КП</span>
                <ArrowRight size={16} />
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
                <h3 className="text-lg font-black text-slate-900">Без ручного набора</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Исключение ошибок в маркировках сталей, ГОСТах и типоразмерах.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Четкий регламент</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Фиксация сроков ответа, условий доставки и запроса паспортов качества.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Готов к копированию</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Удобная вставка в Outlook, Thunderbird или корпоративную CRM за 1 клик.
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
