import type { Metadata } from "next";

import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildHowToJsonLd,
  buildServiceJsonLd,
  seoPageLastUpdated,
  type FaqItem,
} from "@/lib/seo";

export const metadata: Metadata = {
  title: "Поставщики для запроса КП — первая волна адресатов",
  description:
    "Загрузите уже собранный список компаний и получите первую волну адресатов: без дублей, с каналом связи и вопросами для сопоставимых ответов.",
  keywords: [
    "список поставщиков для запроса цены",
    "кому отправить запрос цены",
    "поставщики для запроса КП",
    "адресаты для коммерческого предложения",
    "TenderLex",
  ],
  alternates: {
    canonical: "/postavshchiki-dlya-zaprosa-kp",
  },
  openGraph: {
    type: "website",
    url: "/postavshchiki-dlya-zaprosa-kp",
    title: "Поставщики для запроса КП — первая волна адресатов | TenderLex",
    description:
      "Загрузите собранный список компаний и получите первую волну адресатов без дублей, с каналом связи и вопросами.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Поставщики для запроса КП — первая волна адресатов | TenderLex",
    description:
      "TenderLex помогает собрать первую волну адресатов и подготовить основу для сравнимых ответов.",
    images: ["/tenderlex-product-preview.png"],
  },
};

const pagePath = "/postavshchiki-dlya-zaprosa-kp";

const faqItems: FaqItem[] = [
  {
    question: "Чем список адресатов отличается от поиска поставщиков?",
    answer:
      "Поиск поставщиков собирает рынок под спецификацию. Этот сценарий работает с уже собранным пулом и отвечает на следующий вопрос: кому написать в первую очередь, по какому каналу и с какими вопросами.",
  },
  {
    question: "Как выбрать первую волну адресатов?",
    answer:
      "В нее включают компании с понятной связью с товаром, рабочим каналом связи и достаточным покрытием по типам поставщиков и регионам. Дубли и случайные каталоги исключаются.",
  },
  {
    question: "Что нужно отправлять вместе со списком?",
    answer:
      "Каждому адресату нужен одинаковый запрос: позиции, характеристики, количество, срок, адрес поставки, требования к документам и вопросы по заменам или аналогам.",
  },
  {
    question: "TenderLex сам рассылает запросы?",
    answer:
      "Нет. Сервис готовит рабочий список и основу обращения. Отправку, переговоры и проверку полученных предложений выполняет ваша команда.",
  },
];

export default function SuppliersForQuoteRequestPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Поставщики для первого запроса КП", path: pagePath },
  ]);
  const schemaService = buildServiceJsonLd({
    name: "Отбор поставщиков для первого запроса КП",
    description:
      "TenderLex помогает очистить уже собранный список компаний, убрать дубли и отобрать адресатов для первого запроса КП.",
    path: pagePath,
    serviceType: "Supplier outreach list for price request",
  });
  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как отобрать первую волну адресатов с TenderLex",
    description:
      "Порядок подготовки первой волны: от готового списка компаний до приоритетных адресатов и единого запроса.",
    steps: [
      {
        name: "Передайте собранный список компаний",
        text: "Загрузите таблицу, документ или другой материал с ранее найденными компаниями и доступными контактами.",
      },
      {
        name: "Определите критерии первой волны",
        text: "Учитываются профиль компании, тип поставщика, регион, доступный канал связи и релевантность номенклатуре.",
      },
      {
        name: "Получите список адресатов",
        text: "Для каждой компании фиксируются контактный канал и комментарий, почему ее стоит включить в первый запрос.",
      },
      {
        name: "Отправьте единое обращение",
        text: "Команда проверяет текст и отправляет одинаковый запрос, чтобы сопоставить ответы по одинаковым условиям.",
      },
    ],
  });

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaBreadcrumb) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaService) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaFaq) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaHowTo) }} />
      <main className="legal-shell">
        <article className="legal-document">
          <a className="legal-back" href="/">
            ← TenderLex
          </a>
          <h1>Отобрать поставщиков для первого запроса КП</h1>
          <p className="legal-date">
            Для закупщиков и снабжения, которым нужна первая волна адресатов, а не случайная выдача сайтов. Обновлено {seoPageLastUpdated}.
          </p>

          <section>
            <h2>Кому отправлять первый запрос цены</h2>
            <p>
              Этот сценарий нужен, когда пул компаний уже собран, но рассылать всем подряд нельзя. В первой волне
              важны релевантность позиции, рабочий контакт и понятная причина, почему
              компании стоит задать одинаковый набор вопросов.
            </p>
          </section>

          <section>
            <h2>Как отбирается первая волна</h2>
            <p>
              TenderLex отделяет производителей, дилеров, дистрибьюторов и профильных поставщиков, фиксирует сайт,
              страницу связи, email или телефон и убирает повторяющиеся или неподходящие записи. Так у команды
              остается управляемый список для первого обращения, а не набор ссылок из поиска.
            </p>
          </section>

          <section>
            <h2>Что должно быть у каждого адресата</h2>
            <p>
              В рабочем списке указываются компания, роль в цепочке поставки, канал связи и комментарий по
              релевантности. Отдельно фиксируются вопросы, которые нужны именно для этой позиции: цена, срок,
              наличие, документы качества, условия доставки и возможность аналога.
            </p>
          </section>

          <section>
            <h2>Письмо и список решают разные задачи</h2>
            <p>
              Список отвечает на вопрос, кому писать. Запрос цены отвечает на вопрос, что отправить всем
              адресатам для сравнимого ответа. Для подготовки текста используйте{" "}
              <a href="/zapros-kp-po-tz">запрос цены поставщику</a>.
            </p>
          </section>

          <section>
            <h2>Связанные задачи</h2>
            <p>
              Если сначала нужно найти компании по новой номенклатуре, начните с{" "}
              <a href="/poisk-postavshchikov-po-tz">поиска поставщиков по ТЗ</a>. Для поставки под конкретную процедуру
              используйте <a href="/poisk-postavshchikov-dlya-tendera">поиск поставщиков для тендера</a>.
            </p>
          </section>

          <section>
            <h2>Часто задаваемые вопросы</h2>
            <div style={{ display: "grid", gap: 20, marginTop: 8 }}>
              {faqItems.map((item, index) => (
                <div
                  key={item.question}
                  style={{ borderTop: index > 0 ? "1px solid var(--line)" : undefined, paddingTop: index > 0 ? 20 : 0 }}
                >
                  <h3 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 900 }}>{item.question}</h3>
                  <p style={{ margin: 0, color: "var(--ink-soft)", fontSize: 15, lineHeight: 1.65 }}>{item.answer}</p>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2>Собрать адресатов</h2>
            <p>
              Откройте <a href="/cabinet">личный кабинет</a> или отправьте собранный список компаний в{" "}
              <a href="https://t.me/tenderlex_bot" target="_blank" rel="noreferrer">
                Telegram-бот TenderLex
              </a>
              .
            </p>
          </section>
        </article>
      </main>
    </>
  );
}
