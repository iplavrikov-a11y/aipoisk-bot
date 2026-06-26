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
  title: "Выйти на производителя по спецификации",
  description:
    "TenderLex помогает найти производителей по спецификации: заводы, бренды, официальные представители, контакты и вопросы для проверки товара.",
  keywords: [
    "поиск производителей по ТЗ",
    "найти производителя по техническому заданию",
    "производители по техзаданию",
    "подбор производителей",
    "TenderLex",
  ],
  alternates: {
    canonical: "/poisk-proizvoditeley-po-tz",
  },
  openGraph: {
    type: "website",
    url: "/poisk-proizvoditeley-po-tz",
    title: "Выйти на производителя по спецификации | TenderLex",
    description:
      "Поиск заводов, производителей и официальных представителей с контактами и вопросами для проверки товара.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Выйти на производителя по спецификации | TenderLex",
    description:
      "TenderLex помогает найти производителей по спецификации и подготовить вопросы для проверки товара.",
    images: ["/tenderlex-product-preview.png"],
  },
};

const pagePath = "/poisk-proizvoditeley-po-tz";

const faqItems: FaqItem[] = [
  {
    question: "TenderLex ищет только производителей?",
    answer:
      "Нет. Сервис может искать производителей, заводы, официальных представителей, дилеров и дистрибьюторов. На этой странице акцент именно на производителях и подтверждении связи компании с товаром.",
  },
  {
    question: "Как понять, что компания действительно производитель?",
    answer:
      "Проверяются сайт, описание производства, продуктовая линейка, документы, страницы контактов и признаки официального представительства. Финальное подтверждение нужно запрашивать у компании напрямую.",
  },
  {
    question: "Можно ли искать производителей аналогов?",
    answer:
      "Да. Если спецификация допускает аналоги или эквиваленты, TenderLex может искать производителей по ключевым характеристикам, назначению, материалу, стандартам и товарной группе.",
  },
  {
    question: "Что запросить у производителя?",
    answer:
      "Нужно запросить цену, техническое описание, документы качества, срок производства или отгрузки, гарантию, условия доставки и подтверждение соответствия требованиям.",
  },
];

export default function ManufacturerSearchPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Выйти на производителя по спецификации", path: pagePath },
  ]);
  const schemaService = buildServiceJsonLd({
    name: "Поиск производителей по спецификации",
    description:
      "TenderLex помогает найти производителей, заводы и официальных представителей по спецификации, проверить профиль компании и подготовить вопросы для первого запроса.",
    path: pagePath,
    serviceType: "Manufacturer search by technical specification",
  });
  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как найти производителей по спецификации с TenderLex",
    description:
      "Порядок поиска производителей: от загрузки спецификации до списка компаний и вопросов для проверки соответствия.",
    steps: [
      {
        name: "Передайте спецификацию",
        text: "Загрузите документ, ссылку на закупку или описание товара с ключевыми характеристиками.",
      },
      {
        name: "TenderLex выделяет признаки товара",
        text: "Сервис определяет назначение, материалы, размеры, стандарты, марки, аналоги и ограничения.",
      },
      {
        name: "Ищутся производители и официальные представители",
        text: "В приоритете заводы, бренды, производственные компании и официальные каналы продаж.",
      },
      {
        name: "Собираются вопросы для проверки",
        text: "В результат попадают контакты и список параметров, которые нужно подтвердить у производителя перед сравнением предложений.",
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
          <h1>Выйти на производителя по спецификации</h1>
          <p className="legal-date">
            Для закупок и снабжения, когда нужен завод, бренд или официальный представитель. Обновлено {commercialPageLastUpdated}.
          </p>

          <section>
            <h2>Короткий ответ</h2>
            <p>
              Этот сценарий нужен, когда важно выйти не только на продавца, но и на завод, бренд или официального представителя.
              TenderLex разбирает спецификацию и помогает найти компании, связанные с нужной номенклатурой и характеристиками.
            </p>
          </section>

          <section>
            <h2>Когда производитель важнее посредника</h2>
            <p>
              Производитель нужен, если требуется подтвердить происхождение товара, документы качества, гарантию, производство под заказ,
              серийность, совместимость с требованиями или наличие официального канала поставки.
            </p>
            <p style={{ marginTop: 14 }}>
              Для сложной номенклатуры полезно искать сразу несколько уровней: производителя, официального дилера,
              регионального представителя и дистрибьютора. Так команда получает больше вариантов по цене, срокам и документам.
            </p>
          </section>

          <section>
            <h2>Какие признаки используются для поиска</h2>
            <p>
              TenderLex выделяет назначение товара, материал, стандарт, диапазон характеристик, модельные признаки,
              требования к сертификатам, условия поставки и возможные аналоги. Это помогает искать не только точное название,
              но и производителей сопоставимых решений.
            </p>
          </section>

          <section>
            <h2>Что нужно проверить у производителя</h2>
            <p>
              Перед выбором поставщика нужно запросить подтверждение соответствия, техническое описание, документы качества,
              гарантию, срок производства или отгрузки, возможность поставки нужного количества и условия доставки.
            </p>
          </section>

          <section>
            <h2>Связанные сценарии</h2>
            <p>
              Если подходят не только производители, используйте <a href="/poisk-postavshchikov-po-tz">поиск поставщиков под спецификацию</a>.
              Если подбор нужен под конкретную закупку, см. <a href="/poisk-postavshchikov-dlya-tendera">поиск поставщиков для тендера</a>.
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
              Откройте <a href="/cabinet">личный кабинет</a> или отправьте спецификацию в{" "}
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
