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
  title: "Поиск поставщиков для тендера",
  description:
    "TenderLex помогает найти поставщиков для тендера: производители, дилеры, дистрибьюторы, контакты и вопросы для первого запроса.",
  keywords: [
    "поиск поставщиков для тендера",
    "найти поставщиков для тендера",
    "поставщики для участия в тендере",
    "поиск поставщиков по ТЗ",
    "TenderLex",
  ],
  alternates: {
    canonical: "/poisk-postavshchikov-dlya-tendera",
  },
  openGraph: {
    type: "website",
    url: "/poisk-postavshchikov-dlya-tendera",
    title: "Поиск поставщиков для тендера | TenderLex",
    description:
      "Подбор поставщиков под тендерную задачу: кто может поставить товар, какие контакты использовать и что запросить для сравнения предложений.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Поиск поставщиков для тендера | TenderLex",
    description:
      "TenderLex находит поставщиков для тендера и помогает подготовить первый запрос по цене, срокам и документам.",
    images: ["/tenderlex-product-preview.png"],
  },
};

const pagePath = "/poisk-postavshchikov-dlya-tendera";

const faqItems: FaqItem[] = [
  {
    question: "Чем поиск поставщиков для тендера отличается от обычного поиска в интернете?",
    answer:
      "Для тендера важно не просто найти сайт компании, а понять, может ли поставщик закрыть позицию, есть ли рабочие контакты, какие документы и условия нужно запросить до подачи заявки.",
  },
  {
    question: "Можно ли искать поставщиков по номеру закупки?",
    answer:
      "Да. TenderLex может использовать номер извещения, ссылку на закупку, комплект документов или отдельное описание позиции, чтобы выделить предмет поставки и требования к товару.",
  },
  {
    question: "Какие поставщики попадают в результат?",
    answer:
      "В результат попадают производители, официальные дилеры, дистрибьюторы, региональные поставщики и профильные B2B-компании. Нерелевантные справочники, маркетплейсы и площадки отсеиваются.",
  },
  {
    question: "Что делать после получения списка поставщиков?",
    answer:
      "Следующий шаг — отправить одинаковый запрос цены: позиции, характеристики, количество, документы качества, срок поставки, доставку и условия оплаты.",
  },
];

export default function TenderSupplierSearchPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Поиск поставщиков для тендера", path: pagePath },
  ]);
  const schemaService = buildServiceJsonLd({
    name: "Поиск поставщиков для тендера",
    description:
      "TenderLex подбирает поставщиков для тендера, проверяет профиль компаний, сайты и контакты, помогает подготовить первый запрос.",
    path: pagePath,
    serviceType: "Tender supplier search",
  });
  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как найти поставщиков для тендера с TenderLex",
    description:
      "Порядок работы: передать закупку, получить список релевантных компаний и подготовить первый запрос.",
    steps: [
      {
        name: "Передайте закупку или техническое задание",
        text: "Укажите номер извещения, ссылку на закупку, загрузите документы или вставьте описание товарной позиции.",
      },
      {
        name: "TenderLex выделяет предмет поставки",
        text: "Сервис извлекает товарную группу, характеристики, количество, стандарты, ограничения и требования к подтверждающим документам.",
      },
      {
        name: "Формируется список поставщиков",
        text: "В список попадают компании с подходящим профилем, сайтом, контактами и признаками соответствия позиции.",
      },
      {
        name: "Подготовьте запрос предложения",
        text: "Используйте найденные контакты и одинаковый запрос цены, чтобы сравнить цену, сроки, наличие, доставку и документы качества.",
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
          <h1>Поиск поставщиков для тендера</h1>
          <p className="legal-date">
            Для тендерных отделов и снабжения, которым нужно понять рынок до решения об участии. Обновлено {commercialPageLastUpdated}.
          </p>

          <section>
            <h2>Короткий ответ</h2>
            <p>
              Это подбор компаний, которые реально могут поставить нужную позицию и ответить по цене до решения об участии.
              TenderLex ищет таких поставщиков по смыслу закупки, а не только по одному названию товара.
            </p>
          </section>

          <section>
            <h2>Когда нужен отдельный поиск</h2>
            <p>
              В тендерной работе часто нужно быстро понять, кто может закрыть поставку: производитель, дилер, дистрибьютор или
              региональный поставщик. Ручной поиск занимает время, потому что нужно сверить характеристики, найти контакты и
              отсечь сайты, которые не подходят под предмет закупки.
            </p>
            <p style={{ marginTop: 14 }}>
              TenderLex помогает до подачи заявки собрать рабочий пул компаний, которым можно отправить одинаковый запрос
              цены и сравнить ответы по срокам, документам и условиям доставки.
            </p>
          </section>

          <section>
            <h2>Что проверяется в поставщике</h2>
            <p>
              Для каждого кандидата важны профиль компании, связь с нужной товарной группой, наличие сайта, контактов и
              признаков, что компания работает с такой номенклатурой. Если в закупке есть требования к стране происхождения
              или реестровым записям, этот контекст нужно вынести в запрос поставщику.
            </p>
          </section>

          <section>
            <h2>Что получает команда</h2>
            <p>
              Результат — структурированный список: компания, тип поставщика, сайт, контакты, комментарий о релевантности,
              что уточнить перед сравнением ответов. После этого можно перейти к{" "}
              <a href="/zapros-kp-po-tz">письму поставщику по спецификации</a>.
            </p>
          </section>

          <section>
            <h2>Связанные сценарии</h2>
            <p>
              Если задача шире тендера, используйте <a href="/poisk-postavshchikov-po-tz">поиск поставщиков под спецификацию</a>.
              Если нужен именно производитель, а не торговая компания, см.{" "}
              <a href="/poisk-proizvoditeley-po-tz">выход на производителя</a>.
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
            <h2>Запустить поиск</h2>
            <p>
              Откройте <a href="/cabinet">личный кабинет</a> или отправьте закупку в{" "}
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
