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
  title: "Поиск производителей по ТЗ — заводы и официальные каналы",
  description:
    "Передайте ТЗ и получите заводы, бренды и официальные каналы, чтобы подтвердить происхождение, характеристики и возможность поставки.",
  keywords: [
    "поиск производителей по ТЗ",
    "найти производителя по техническому заданию",
    "поиск завода по спецификации",
    "официальный представитель производителя",
    "TenderLex",
  ],
  alternates: {
    canonical: "/poisk-proizvoditeley-po-tz",
  },
  openGraph: {
    type: "website",
    url: "/poisk-proizvoditeley-po-tz",
    title: "Поиск производителей по ТЗ — заводы и официальные каналы | TenderLex",
    description:
      "Найдите завод, бренд или официальный канал поставки по характеристикам товара.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Поиск производителей по ТЗ — заводы и официальные каналы | TenderLex",
    description:
      "TenderLex помогает найти производителей и подготовить вопросы для подтверждения товара.",
    images: ["/tenderlex-product-preview.png"],
  },
};

const pagePath = "/poisk-proizvoditeley-po-tz";

const faqItems: FaqItem[] = [
  {
    question: "Когда нужен именно поиск производителя?",
    answer:
      "Он нужен, когда важны происхождение товара, производство под заказ, техническая экспертиза, бренд, гарантия или официальный канал поставки. Для обычного запроса цены по широкой номенклатуре подходит общий поиск поставщиков.",
  },
  {
    question: "Как отличить производителя от продавца?",
    answer:
      "По открытым данным можно проверить продуктовую линейку, описание производства, официальный сайт и контакты. Окончательное подтверждение статуса, полномочий и возможности поставки получает ваша команда в ответе компании.",
  },
  {
    question: "Можно ли искать производителя аналога?",
    answer:
      "Да, если закупка допускает аналог или эквивалент. Поиск строится по назначению, материалу, стандартам, диапазону характеристик и другим признакам, а не только по одному названию модели.",
  },
  {
    question: "Какие вопросы задать производителю?",
    answer:
      "Обычно уточняют соответствие характеристикам, комплектность, документы качества, минимальную партию, срок производства или отгрузки, гарантию, доставку и официальный статус канала поставки.",
  },
];

export default function ManufacturerSearchPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Поиск производителей по ТЗ", path: pagePath },
  ]);
  const schemaService = buildServiceJsonLd({
    name: "Поиск производителей по ТЗ",
    description:
      "TenderLex помогает найти заводы, бренды и официальные каналы поставки по спецификации, чтобы подтвердить происхождение и характеристики товара.",
    path: pagePath,
    serviceType: "Manufacturer search by technical specification",
  });
  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как найти производителя по ТЗ с TenderLex",
    description:
      "Порядок поиска производителя: от характеристик товара до списка заводов и вопросов для подтверждения.",
    steps: [
      {
        name: "Передайте характеристики товара",
        text: "Загрузите спецификацию, ссылку на закупку или описание с назначением, материалами, стандартами и ограничениями.",
      },
      {
        name: "Выделите признаки для поиска",
        text: "TenderLex использует модельные признаки, назначение, размеры, стандарты, возможные аналоги и требования к документам.",
      },
      {
        name: "Найдите завод или официальный канал",
        text: "В результат попадают производители, бренды и официальные представители с доступными каналами связи.",
      },
      {
        name: "Подтвердите статус и возможность поставки",
        text: "Команда направляет вопросы о соответствии, документах, сроке, минимальной партии и полномочиях поставщика.",
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
          <h1>Найти производителя по ТЗ</h1>
          <p className="legal-date">
            Для закупок и снабжения, когда нужен завод, бренд или официальный канал поставки. Обновлено {seoPageLastUpdated}.
          </p>

          <section>
            <h2>Когда нужен именно производитель</h2>
            <p>
              Этот сценарий нужен, когда недостаточно найти продавца. Команде важно выйти на завод, бренд или
              официального представителя, чтобы подтвердить происхождение товара, получить технический ответ или
              проверить возможность производства и поставки.
            </p>
          </section>

          <section>
            <h2>Что отличает завод от общего списка поставщиков</h2>
            <p>
              Поиск производителя опирается на признаки производства: продуктовую линейку, технические характеристики,
              стандарты, модельные обозначения и официальный канал продаж. Дилер или дистрибьютор может остаться в
              списке только как способ связаться с брендом или закрыть поставку в нужном регионе.
            </p>
          </section>

          <section>
            <h2>Какие параметры помогают найти нужный завод</h2>
            <p>
              TenderLex выделяет назначение товара, материал, размеры, стандарты, марки, диапазон характеристик,
              требования к сертификатам и допустимые аналоги. Это позволяет искать производителя сопоставимого решения,
              а не ограничиваться совпадением по названию.
            </p>
          </section>

          <section>
            <h2>Что подтвердить до выбора канала поставки</h2>
            <p>
              У компании нужно подтвердить статус, соответствие характеристикам, документы качества, минимальную
              партию, срок производства или отгрузки, гарантию, возможность доставки и условия работы через
              официального дилера, если он участвует в поставке.
            </p>
          </section>

          <section>
            <h2>Связанные задачи</h2>
            <p>
              Если подходят производители, дилеры и другие профильные компании, используйте{" "}
              <a href="/poisk-postavshchikov-po-tz">поиск поставщиков по ТЗ</a>. Для поставки под условия конкретной
              процедуры подойдет <a href="/poisk-postavshchikov-dlya-tendera">поиск поставщиков для тендера</a>.
            </p>
            <p style={{ marginTop: 14 }}>
              После выбора производителя или официального канала подготовьте{" "}
              <a href="/zapros-kp-po-tz">единый запрос КП по ТЗ</a>, чтобы сравнить цену, сроки и условия поставки.
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
            <h2>Начать поиск производителя</h2>
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
