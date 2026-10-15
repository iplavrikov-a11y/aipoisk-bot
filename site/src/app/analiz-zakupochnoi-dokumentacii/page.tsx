import { getSiteData } from "@/lib/site-data";
import type { Metadata } from "next";
import Link from "next/link";
import { ShieldAlert, Send } from "lucide-react";
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
  title: { absolute: "Анализ закупочной документации и проекта контракта | TenderLex" },
  description:
    "Анализ закупочной документации, ТЗ и проекта контракта: сроки, обеспечение, штрафы и вопросы для проверки до подачи заявки.",
  keywords: [
    "анализ закупочной документации",
    "проверка контракта 44-ФЗ 223-ФЗ",
    "коммерческие торги",
    "аудит рисков закупки",
    "анализ ТЗ договора",
    "риски 44 фз",
    "расчет нмцк онлайн",
    "TenderLex",
  ],
  alternates: {
    canonical: "/analiz-zakupochnoi-dokumentacii",
  },
  openGraph: {
    type: "website",
    url: "/analiz-zakupochnoi-dokumentacii",
    title: "Анализ закупочной документации и рисков контракта | TenderLex",
    description:
      "Разберите ТЗ и проект контракта до подачи заявки: сроки, обеспечение, штрафы и вопросы для проверки.",
    siteName: "TenderLex",
    images: [
      {
        url: "/tenderlex-product-preview.png",
        width: 1200,
        height: 630,
        alt: "TenderLex — Анализ закупочной документации и рисков",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Анализ закупочной документации и рисков контракта | TenderLex",
    description:
      "Разберите ТЗ и проект контракта до подачи заявки: сроки, обеспечение, штрафы и вопросы для проверки.",
  },
};

const pagePath = "/analiz-zakupochnoi-dokumentacii";

const faqItems: FaqItem[] = [
  {
    question: "Какие закупки и риски анализирует модуль документации?",
    answer:
      "Модуль помогает структурировать условия 44-ФЗ, 223-ФЗ и коммерческих закупок: сроки поставки и приемки, обеспечение, штрафы, порядок оплаты, национальный режим и требования к документам. Выводы требуют проверки по извещению, проекту контракта и применимому праву.",
  },
  {
    question: "Помогает ли сервис составить запрос на разъяснение положений извещения?",
    answer:
      "Да. При обнаружении неясного или противоречивого условия можно подготовить черновик вопроса для проверки перед отправкой. Срок, способ подачи и допустимость вопроса участник определяет по правилам конкретной процедуры.",
  },
  {
    question: "Как модуль помогает защититься от попадания в РНП?",
    answer:
      "Модуль помогает заметить условия, которые стоит отдельно проверить: сроки, обеспечение исполнения, порядок приемки, основания отказа и последствия неисполнения. Он не даёт юридической оценки и не исключает риск включения в РНП.",
  },
  {
    question: "Можно ли рассчитать риски НМЦК по методике сопоставимых цен?",
    answer:
      "На странице сервиса не рассчитывается НМЦК как юридически значимый результат. Для обоснования цены используйте отдельный расчёт, запросы КП и документы, предусмотренные процедурой.",
  },
];

export default async function AnalizZakupochnoiDokumentaciiPage() {
  const data = await getSiteData();
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Анализ закупочной документации", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Анализ закупочной документации",
    description: "Сервис экспресс-аудита рисков контрактов 44-ФЗ, 223-ФЗ и коммерческих закупок.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как проверить закупочную документацию",
    description: "Пошаговый процесс экспресс-аудита рисков любых закупок.",
    steps: [
      { name: "Загрузка проекта контракта", text: "Передайте файл извещения или проект договора." },
      { name: "Смысловой ИИ-анализ условий", text: "Аудит сроков, штрафов и обеспечения." },
      { name: "Формирование отчета о рисках", text: "Выгрузка сводки с оценкой критичности." },
      { name: "Подготовка запроса разъяснений", text: "Готовые формулировки для обращения к заказчику." },
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
              <ShieldAlert size={14} className="text-teal-600" />
              <span>Экспресс-аудит проекта контракта</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Анализ закупочной документации: 44-ФЗ, 223-ФЗ и коммерческие закупки
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Загрузите извещение, ТЗ или проект контракта. TenderLex выделит условия, которые удобно проверить до подачи заявки: сроки, обеспечение, штрафы, оплату и требования к документам.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet?scenario=doc_analysis"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Проверить документацию</span>
              </a>
              <a
                href={data.bot.telegram_url}
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
                <h3 className="text-lg font-black text-slate-900">Условия, влияющие на исполнение</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Сроки, объём, обеспечение, порядок приемки и основания отказа собраны в рабочую структуру для отдельной правовой и коммерческой проверки.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Штрафы и ответственность</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Условия неустоек и удержаний можно сопоставить с документами процедуры. Применимость нормы и расчёт проверяют по действующей редакции и договору.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Вопросы для уточнения</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Результат помогает сформулировать вопросы по противоречиям и недостающим условиям перед отправкой через предусмотренный процедурой канал.
                </p>
              </div>
            </div>

            <p className="mt-8 text-sm text-slate-600">
              <Link href="/ocenka-riskov-zakupki" className="font-semibold text-teal-700 underline">Как оценить риски закупки перед подачей заявки</Link>: сроки, обеспечение, штрафы и коммерческие условия.
            </p>

            {/* Cross-linking Banner: Заточка в ТЗ? Подберите эквивалент */}
            <div className="mt-12 p-8 sm:p-10 rounded-3xl bg-gradient-to-br from-teal-900 to-slate-900 text-white shadow-xl flex flex-col md:flex-row items-center justify-between gap-6">
              <div className="space-y-2 max-w-xl text-left">
                <span className="text-xs font-bold text-teal-300 uppercase tracking-wider bg-teal-400/20 px-3 py-1 rounded-full border border-teal-400/30 inline-block">
                  Смежный модуль
                </span>
                <h3 className="text-xl sm:text-2xl font-extrabold text-white">
                  В документации есть параметры товара, которые требуют отдельной проверки?
                </h3>
                <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                  Используйте модуль «Подбор товара и аналогов», чтобы сопоставить параметры с документами изготовителя и сформировать список вопросов к возможным вариантам. Решение о соответствии принимает участник закупки.
                </p>
              </div>
              <Link
                href="/podbor-tovara-i-analogov-po-tz"
                className="shrink-0 px-6 py-3.5 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 font-black text-xs shadow-md transition-all hover:scale-102"
              >
                Подобрать аналоги по ТЗ →
              </Link>
            </div>
          </div>
        </section>

        <section className="py-16 sm:py-20 border-b border-slate-200 bg-slate-50">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6">
            <div className="max-w-3xl mb-8">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700">Учебный пример</span>
              <h2 className="mt-3 text-2xl sm:text-3xl font-black text-slate-900">Как использовать результат анализа документации</h2>
              <p className="mt-3 text-sm sm:text-base text-slate-600 leading-relaxed">Пример показывает последовательность проверки, а не реальную закупку, заключение или юридическую консультацию.</p>
            </div>
            <ol className="grid md:grid-cols-3 gap-5 list-none">
              <li className="rounded-2xl border border-slate-200 bg-white p-6"><span className="text-xs font-bold text-teal-700">1. Входные документы</span><p className="mt-3 text-sm text-slate-700">Извещение, ТЗ, проект контракта и приложения: сроки, обеспечение, порядок приемки и оплаты.</p></li>
              <li className="rounded-2xl border border-slate-200 bg-white p-6"><span className="text-xs font-bold text-teal-700">2. Рабочий результат</span><p className="mt-3 text-sm text-slate-700">Список условий и вопросов: например, о сроке поставки, комплектации, документе о происхождении или приемке.</p></li>
              <li className="rounded-2xl border border-slate-200 bg-white p-6"><span className="text-xs font-bold text-teal-700">3. Проверка клиентом</span><p className="mt-3 text-sm text-slate-700">Сверьте каждый пункт с первичным документом, правилами процедуры и возможностью исполнить обязательство.</p></li>
            </ol>
            <div className="mt-8 flex flex-wrap gap-x-5 gap-y-3 text-sm">
              <Link className="text-teal-700 underline underline-offset-4" href="/baza-znaniy/ai-audit-zakupochnoi-dokumentacii-na-riski">Как разбирать риски в документации</Link>
              <Link className="text-teal-700 underline underline-offset-4" href="/baza-znaniy/analiz-riskov-zakupki-44-fz-223-fz">Чек-лист рисков закупки</Link>
              <Link className="text-teal-700 underline underline-offset-4" href="/baza-znaniy/reestr-nedobrosovestnyh-postavshchikov-rnp-proverka">Что проверить при риске РНП</Link>
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
