import { PublicSiteLink } from "@/components/public-site-link";
import type { Metadata } from "next";
import Link from "next/link";
import { Building2, CheckCircle2, FileText, Send, Sparkles, Factory } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { SeoContentBlocks } from "@/components/seo-content-blocks";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildHowToJsonLd,
  buildServiceJsonLd,
  type FaqItem,
} from "@/lib/seo";

export const metadata: Metadata = {
  title: { absolute: "Поиск заводов-производителей и фабрик по ТЗ без посредников — TenderLex" },
  description:
    "Прямой выход на заводы-производители и фабрики по спецификации ТЗ за 3 минуты. Прямые контакты отделов сбыта, проверка ИНН и производства в реестрах РФ и ЕАЭС.",
  keywords: [
    "поиск производителей по ТЗ",
    "база заводов изготовителей",
    "найти завод по спецификации",
    "прямые контакты производителей",
    "производители без посредников",
    "заводы России по ГОСТ",
    "TenderLex",
  ],
  alternates: {
    canonical: "/poisk-proizvoditeley-po-tz",
  },
  openGraph: {
    type: "website",
    url: "/poisk-proizvoditeley-po-tz",
    title: "Поиск заводов-производителей и фабрик по ТЗ без посредников — TenderLex",
    description:
      "Прямой выход на заводы-производители и фабрики по спецификации ТЗ за 3 минуты. Прямые контакты отделов сбыта, проверка ИНН и производства в реестрах РФ и ЕАЭС.",
    siteName: "TenderLex",
    images: [
      {
        url: "/tenderlex-product-preview.png",
        width: 1200,
        height: 630,
        alt: "TenderLex — Поиск заводов-производителей по ТЗ",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Поиск заводов-производителей и фабрик по ТЗ без посредников — TenderLex",
    description:
      "Прямой выход на заводы-производители и фабрики по спецификации ТЗ за 3 минуты. Прямые контакты отделов сбыта, проверка ИНН и производства в реестрах РФ и ЕАЭС.",
  },
};

const pagePath = "/poisk-proizvoditeley-po-tz";

const faqItems: FaqItem[] = [
  {
    question: "Как TenderLex отличает завод-изготовитель от перекупщика?",
    answer:
      "Сервис ищет признаки производителя в открытых источниках: каталог выпускаемой продукции, упоминания производства, сертификаты и документы. Это ориентир для проверки, а роль компании всё равно подтверждают по её сайту и документам.",
  },
  {
    question: "Какие контактные данные заводов предоставляет сервис?",
    answer:
      "Сервис собирает опубликованные контакты отдела продаж, сайт предприятия и доступные реквизиты. Актуальность контакта, полномочия сотрудника и условия поставки подтверждают у самой компании.",
  },
  {
    question: "Сколько времени занимает поиск производителей по ТЗ?",
    answer:
      "Время зависит от объёма спецификации, доступности источников и выбранного сценария. Перед запуском проверьте состав задачи и стоимость в кабинете.",
  },
  {
    question: "Что делать, если производитель не продаёт напрямую?",
    answer:
      "Уточните у завода официальные каналы продаж и дилеров в вашем регионе. Если прямая поставка недоступна, сравните дистрибьюторов по наличию, сроку, документам и итоговой цене.",
  },
  {
    question: "Можно ли проверить завод по ИНН?",
    answer:
      "ИНН помогает сверить юридическое лицо, но не подтверждает производство конкретной продукции. Дополнительно проверяйте сайт, каталог, сертификаты и документы на товар.",
  },
  {
    question: "Обязательно ли выбирать только производителя?",
    answer:
      "Нет. Для небольшой партии, срочной поставки или редкой позиции дистрибьютор может быть удобнее. Решение зависит от наличия, срока, документов и условий закупки.",
  },
];

const contentSections = [
  {
    title: "Зачем искать завод, а не посредника",
    paragraphs: [
      "Прямой производитель может дать более понятные условия по цене, срокам и документам, особенно если речь идёт о серийной или крупной партии. Но «прямой» не всегда значит «выгодный»: у завода может не быть склада в вашем регионе или минимальной партии.",
      "Поиск завода помогает сузить круг кандидатов и понять, кто в цепочке отвечает за производство. Дальше решение принимают по наличию, сроку, цене и условиям поставки.",
    ],
    bullets: [
      "кто выпускает продукцию;",
      "есть ли прямые продажи;",
      "какие документы предоставляет завод;",
      "какой минимальный объём;",
      "как организована доставка.",
    ],
  },
  {
    title: "Как отличить производителя от перекупщика",
    paragraphs: [
      "Смотрите не на слово «завод» в названии, а на признаки производства: каталог выпускаемой продукции, упоминания цехов или линий, сертификаты, паспорта и технические условия. Если сайт состоит только из прайс-листов и «склада», это повод проверить роль компании.",
      "Не делайте вывод по одному признаку. Название, ИНН, сайт и документы проверяют вместе. Если данных мало, задайте вопрос напрямую.",
    ],
    bullets: [
      "каталог и технические характеристики;",
      "сертификаты и паспорта;",
      "адрес производства;",
      "упоминания оборудования;",
      "официальные дилеры.",
    ],
  },
  {
    title: "Что проверить в карточке завода",
    paragraphs: [
      "Карточка кандидата должна помогать проверке, а не заменять её. Сверьте юридическое лицо, сайт, контакты и товар. Если контакт ведёт на общую форму или сторонний маркетплейс, уточните, кто отвечает за поставку.",
      "Для закупки важны не только реквизиты, но и документы на конкретную модель: паспорт, сертификат, сведения о реестре, если это требуется.",
    ],
    bullets: [
      "название и ИНН;",
      "сайт и раздел продукции;",
      "контакт отдела продаж;",
      "документы на товар;",
      "регион производства и поставки.",
    ],
  },
  {
    title: "Когда дистрибьютор уместен",
    paragraphs: [
      "Дистрибьютор может быть полезен, если нужна небольшая партия, срочная отгрузка со склада или позиция нескольких производителей. В этом случае сравнивайте не только цену, но и наличие, срок, гарантию и документы.",
      "Проверьте, является ли компания официальным каналом продаж. Если статус не подтверждён, запросите документы и уточните происхождение товара.",
    ],
  },
];

export default function PoiskProizvoditeleyPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Поиск заводов-производителей", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Поиск заводов-производителей по ТЗ",
    description: "Сервис поиска прямых контактов заводов-изготовителей по спецификации.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как найти производителей по ТЗ",
    description: "Пошаговый процесс поиска заводов-изготовителей.",
    steps: [
      { name: "Загрузка спецификации", text: "Загрузите файл ТЗ или описание номенклатуры." },
      { name: "ИИ-анализ стандартов", text: "Система выделяет марки, ГОСТы и технические параметры." },
      { name: "Подбор заводов", text: "Формирование реестра прямых изготовителей по РФ." },
      { name: "Генерация запроса КП", text: "Готовое письмо для отправки на заводы." },
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
              <Factory size={14} className="text-teal-600" />
              <span>Прямой выход на производственные предприятия РФ</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Поиск заводов-производителей по ТЗ и спецификациям
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Мгновенный сбор прямых e-mail адресов и телефонов отделов сбыта отечественных заводов без переплат посредникам и трейдерам.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Найти заводы</span>
              </a>
              <PublicSiteLink
                channel="bot"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-extrabold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
              >
                <Send size={16} className="text-teal-600" />
                <span>Запустить в Telegram</span>
              </PublicSiteLink>
            </div>
          </div>
        </section>

        {/* BENEFITS */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Без посредников</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Прямое обращение к изготовителю помогает запросить актуальные цену, срок и условия. Экономический эффект зависит от конкретной сделки.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Проверка сертификации</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Сопоставление номенклатуры с действующими паспортами качества, ГОСТами и ТР ТС.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Единый запрос цен</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Автоматическая генерация официального письма-запроса КП с таблицей позиций и сроком ответа.
                </p>
              </div>
            </div>
          </div>
        </section>

        <SeoContentBlocks sections={contentSections} />

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
