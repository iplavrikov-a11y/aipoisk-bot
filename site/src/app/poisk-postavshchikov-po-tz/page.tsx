import { getSiteData } from "@/lib/site-data";
import type { Metadata } from "next";
import Link from "next/link";
import { Search, CheckCircle2, FileText, Send, Building2 } from "lucide-react";
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
  title: { absolute: "Поиск поставщиков по ТЗ и спецификации | TenderLex" },
  description:
    "Поиск поставщиков по ТЗ: разберите спецификацию, соберите кандидатов для запроса КП и проверьте контакты и условия поставки.",
  keywords: [
    "поиск поставщиков по ТЗ",
    "подбор поставщиков по спецификации",
    "поиск производителей по ТЗ",
    "контакты отделов продаж заводов",
    "запрос коммерческого предложения",
    "производители по ГОСТ",
    "проверка ИНН поставщика",
    "база поставщиков для тендера",
    "запрос счета по спецификации",
    "TenderLex",
  ],
  alternates: {
    canonical: "/poisk-postavshchikov-po-tz",
  },
  openGraph: {
    type: "website",
    url: "/poisk-postavshchikov-po-tz",
    title: "Поиск поставщиков по ТЗ и спецификации | TenderLex",
    description:
      "Разбор спецификации, кандидаты на поставку и проект запроса КП. Контакты, цены и возможность поставки подтверждает поставщик.",
    siteName: "TenderLex",
    images: [
      {
        url: "/tenderlex-product-preview.png",
        width: 1200,
        height: 630,
        alt: "TenderLex — Поиск поставщиков и заводов по ТЗ",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Поиск поставщиков по ТЗ и спецификации | TenderLex",
    description:
      "Разбор спецификации, кандидаты на поставку и проект запроса КП. Контакты, цены и возможность поставки подтверждает поставщик.",
  },
};

const pagePath = "/poisk-postavshchikov-po-tz";

const faqItems: FaqItem[] = [
  {
    question: "Что нужно подготовить для поиска поставщиков по ТЗ?",
    answer:
      "Укажите наименование позиции, критичные характеристики, ГОСТ или ТУ, объём, регион, требуемый срок и комплектность. Если часть данных отсутствует, результат используют как список кандидатов для уточнения, а не как подтверждение возможности поставки.",
  },
  {
    question: "Чем поиск поставщиков через TenderLex отличается от обычных поисковиков?",
    answer:
      "TenderLex помогает структурировать требования, сформировать список кандидатов и проект запроса КП. Роль компании, действительность контактов, цену, срок и наличие продукции нужно подтвердить в ответе поставщика и по его документам.",
  },
  {
    question: "Что проверить до отправки запроса КП?",
    answer:
      "Проверьте соответствие технических параметров, полномочия дилера или изготовителя, реквизиты компании, комплектность, условия оплаты, срок и место поставки. Не переносите сведения из результата в договор или заявку без такой проверки.",
  },
  {
    question: "Можно ли подготовить единый запрос КП для рассылки поставщикам?",
    answer:
      "Да. Модуль готовит проект запроса с позициями из ТЗ. Перед отправкой добавьте объём, срок, адрес поставки, требования к документам и проверьте адресата.",
  },
  {
    question: "Где посмотреть условия и выбрать тариф?",
    answer:
      "Актуальные условия и доступные пакеты показываются в личном кабинете перед запуском задачи. Они управляются в системе и могут меняться; страница не фиксирует цену или объём услуги.",
  },
];

export default async function PoiskPostavshchikovPage() {
  const data = await getSiteData();
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Поиск поставщиков по ТЗ", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ",
    description: "Сервис подбора поставщиков и извлечения прямых контактов по техническому заданию.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как подобрать поставщиков по ТЗ",
    description: "Пошаговый процесс подбора контрагентов под спецификацию.",
    steps: [
      { name: "Загрузка файла ТЗ", text: "Загрузите файл Excel, Word или PDF." },
      { name: "Распознавание позиций", text: "Алгоритм извлекает ключевые параметры и стандарты." },
      { name: "Формирование пула поставщиков", text: "Выгрузка списка кандидатов и опубликованных контактов для проверки." },
      { name: "Подготовка запроса КП", text: "Единый текст обращения для сбора ценовых предложений." },
    ],
  });

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaBreadcrumb) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaService) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaFaq) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaHowTo) }} />

      <main className="bg-slate-50 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

        {/* HERO */}
        <section className="relative pt-12 pb-20 border-b border-slate-200 bg-gradient-to-b from-teal-50/50 via-slate-50 to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-bold uppercase tracking-wider shadow-2xs">
              <Search size={14} className="text-teal-600" />
                <span>Поиск поставщиков по спецификации</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Поиск поставщиков по ТЗ и спецификации
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-normal leading-relaxed">
              Загрузите файл документации или спецификации — TenderLex выделит номенклатуру, подберет релевантных производителей и поставщиков и подготовит проект запроса КП. Полноту и актуальность контактов следует проверить перед отправкой.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet?scenario=supplier_search"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-extrabold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Открыть поиск поставщиков</span>
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
                <h3 className="text-lg font-black text-slate-900">Структура требований для поиска</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Выделите марку, ГОСТ или ТУ, критичные параметры, объём, регион и срок. Так поставщику проще дать проверяемый ответ.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Кандидаты для запроса КП</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Результат помогает собрать компании и контакты для дальнейшего запроса. Статус изготовителя или дилера проверяют отдельно.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Проверяемый проект запроса</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Используйте проект запроса как основу: перед отправкой подтвердите адресата, номенклатуру, условия и приложенные документы.
                </p>
              </div>
            </div>

            {/* Cross-linking Banner: Подбор аналогов по ТЗ */}
            <div className="mt-12 p-8 sm:p-10 rounded-3xl bg-gradient-to-br from-teal-900 to-slate-900 text-white shadow-xl flex flex-col md:flex-row items-center justify-between gap-6">
              <div className="space-y-2 max-w-xl text-left">
                <span className="text-xs font-bold text-teal-300 uppercase tracking-wider bg-teal-400/20 px-3 py-1 rounded-full border border-teal-400/30 inline-block">
                  Смежный сервис
                </span>
                <h3 className="text-xl sm:text-2xl font-extrabold text-white">
                  Нужно выявить скрытую модель или подобрать аналоги по ТЗ?
                </h3>
                <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                  Сначала сопоставьте характеристики с документами изготовителя в модуле «Подбор товара и аналогов», затем используйте проверенную спецификацию для запроса КП.
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
              <h2 className="mt-3 text-2xl sm:text-3xl font-black text-slate-900">От требований к проверяемому запросу КП</h2>
              <p className="mt-3 text-sm sm:text-base text-slate-600 leading-relaxed">Это условная структура работы, а не реальная поставка, кейс или обещание результата.</p>
            </div>
            <ol className="grid md:grid-cols-3 gap-5 list-none">
              <li className="rounded-2xl border border-slate-200 bg-white p-6"><span className="text-xs font-bold text-teal-700">1. Входные требования</span><p className="mt-3 text-sm text-slate-700">«Кабель: марка, сечение, длина, ГОСТ или ТУ, количество, регион и срок».</p></li>
              <li className="rounded-2xl border border-slate-200 bg-white p-6"><span className="text-xs font-bold text-teal-700">2. Рабочий результат</span><p className="mt-3 text-sm text-slate-700">Список кандидатов и проект запроса КП с характеристиками, объёмом и вопросами о комплектности.</p></li>
              <li className="rounded-2xl border border-slate-200 bg-white p-6"><span className="text-xs font-bold text-teal-700">3. Проверка клиентом</span><p className="mt-3 text-sm text-slate-700">Сверьте роль компании, контакты, документы на товар, цену, срок и готовность отгрузки до заказа.</p></li>
            </ol>
            <div className="mt-8 flex flex-wrap gap-x-5 gap-y-3 text-sm">
              <Link className="text-teal-700 underline underline-offset-4" href="/baza-znaniy/kak-naiti-postavshchika-po-tz">Как подготовить поиск по ТЗ</Link>
              <Link className="text-teal-700 underline underline-offset-4" href="/baza-znaniy/kak-sostavit-zapros-kp-postavshchiku">Что включить в запрос КП</Link>
              <Link className="text-teal-700 underline underline-offset-4" href="/baza-znaniy/proverka-dilerskih-sertifikatov-b2b">Как проверить статус дилера</Link>
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
