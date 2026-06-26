import type { Metadata } from "next";

import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildHowToJsonLd,
  buildServiceJsonLd,
  commercialPageLastUpdated,
  type FaqItem,
} from "@/lib/seo";

export const metadata: Metadata = {
  title: "Кого запросить для получения цены",
  description:
    "TenderLex помогает понять, каким компаниям отправить запрос цены: контакты, профиль поставщиков, что уточнить и как сравнить ответы.",
  keywords: [
    "поставщики для запроса КП",
    "найти поставщиков для запроса коммерческого предложения",
    "запрос КП поставщикам",
    "поиск поставщиков по ТЗ",
    "TenderLex",
  ],
  alternates: {
    canonical: "/postavshchiki-dlya-zaprosa-kp",
  },
  openGraph: {
    type: "website",
    url: "/postavshchiki-dlya-zaprosa-kp",
    title: "Кого запросить для получения цены | TenderLex",
    description:
      "Найдите компании, которым можно отправить запрос цены: контакты, профиль, что уточнить и как сравнить ответы.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Кого запросить для получения цены | TenderLex",
    description:
      "TenderLex подбирает компании для первого запроса и помогает сформировать одинаковое обращение.",
    images: ["/tenderlex-product-preview.png"],
  },
};

const pagePath = "/postavshchiki-dlya-zaprosa-kp";

const faqItems: FaqItem[] = [
  {
    question: "Что важнее: сначала найти компании или сначала подготовить запрос?",
    answer:
      "Лучше делать оба шага вместе: список компаний отвечает на вопрос, кому писать, а текст запроса отвечает на вопрос, что отправить, чтобы получить сравнимые ответы.",
  },
  {
    question: "Какие данные нужны для запроса цены?",
    answer:
      "Нужны позиции, характеристики, количество, адрес или регион поставки, срок, требования к документам качества, гарантия, условия оплаты и вопросы по замене или аналогам.",
  },
  {
    question: "TenderLex сам рассылает запросы поставщикам?",
    answer:
      "TenderLex готовит список поставщиков и основу запроса. Отправку, переговоры и финальную коммерческую проверку выполняет ваша команда.",
  },
  {
    question: "Можно ли использовать результат для внутреннего снабжения?",
    answer:
      "Да. Сценарий подходит не только для тендеров, но и для внутренних закупок, когда нужно быстро собрать пул поставщиков и сравнить условия.",
  },
];

export default function SuppliersForQuoteRequestPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Кого запросить для получения цены", path: pagePath },
  ]);
  const schemaService = buildServiceJsonLd({
    name: "Подбор компаний для запроса цены",
    description:
      "TenderLex подбирает поставщиков для запроса цены, проверяет сайты и контакты, помогает сформировать одинаковое обращение для сравнения ответов.",
    path: pagePath,
    serviceType: "Supplier list for RFQ",
  });
  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как подобрать компании для запроса цены с TenderLex",
    description:
      "Порядок подготовки: найти релевантные компании, собрать контакты и сформировать одинаковый запрос цены.",
    steps: [
      {
        name: "Передайте спецификацию",
        text: "Загрузите описание товара, спецификацию, номер извещения или комплект документов.",
      },
      {
        name: "TenderLex выделяет параметры запроса",
        text: "Сервис определяет позиции, характеристики, количество, документы качества, сроки и условия поставки.",
      },
      {
        name: "Подбираются поставщики",
        text: "В результат попадают компании с подходящим профилем, рабочими контактами и комментарием по соответствию задаче.",
      },
      {
        name: "Готовится первое обращение",
        text: "Команда получает структуру письма, которую можно отправить найденным поставщикам для сравнения ответов.",
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
          <h1>Кого запросить для получения цены</h1>
          <p className="legal-date">
            Для закупщиков и снабжения, которым нужен список адресатов, а не случайная выдача сайтов. Обновлено {commercialPageLastUpdated}.
          </p>

          <section>
            <h2>Короткий ответ</h2>
            <p>
              TenderLex помогает собрать компании, которым можно отправить одинаковый запрос цены и получить
              сопоставимые ответы по срокам, документам и условиям поставки.
            </p>
          </section>

          <section>
            <h2>Почему список и письмо нужно готовить вместе</h2>
            <p>
              Если сначала собрать случайные контакты, ответы будут трудно сравнивать. Один поставщик уточнит марку, другой
              предложит аналог, третий не увидит требования к документам качества. Поэтому список компаний лучше сразу
              готовить вместе с единым текстом первого обращения.
            </p>
            <p style={{ marginTop: 14 }}>
              TenderLex выделяет из спецификации параметры, которые должны попасть в обращение: позиции, характеристики,
              количество, сроки, доставку, документы качества, гарантию и вопросы по аналогам.
            </p>
          </section>

          <section>
            <h2>Что входит в рабочий список</h2>
            <p>
              Для каждого поставщика нужны название компании, сайт, контактная страница, email или телефон, тип компании,
              региональная привязка и комментарий: почему эту компанию стоит включить в первый запрос.
            </p>
          </section>

          <section>
            <h2>Что отправлять поставщикам</h2>
            <p>
              Запрос цены должен содержать одинаковую структуру: предмет поставки, характеристики, количество, адрес или регион
              поставки, срок, условия оплаты, документы качества и прямые вопросы, которые помогут сравнить ответы.
              Подробнее: <a href="/zapros-kp-po-tz">письмо поставщику по спецификации</a>.
            </p>
          </section>

          <section>
            <h2>Связанные сценарии</h2>
            <p>
              Для закупочной процедуры используйте <a href="/poisk-postavshchikov-dlya-tendera">поиск поставщиков для тендера</a>.
              Для широкого подбора — <a href="/poisk-postavshchikov-po-tz">поставщики под спецификацию</a>.
            </p>
          </section>

          <section>
            <h2>Часто задаваемые вопросы</h2>
            <div style={{ display: "grid", gap: 20, marginTop: 8 }}>
              {faqItems.map((item, i) => (
                <div key={item.question} style={{ borderTop: i > 0 ? "1px solid var(--line)" : undefined, paddingTop: i > 0 ? 20 : 0 }}>
                  <h3 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 900 }}>{item.question}</h3>
                  <p style={{ margin: 0, color: "var(--ink-soft)", fontSize: 15, lineHeight: 1.65 }}>{item.answer}</p>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2>Запустить подбор</h2>
            <p>
              Откройте <a href="/cabinet">личный кабинет</a> или отправьте описание позиции в{" "}
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
