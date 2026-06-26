import type { Metadata } from "next";

import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildServiceJsonLd,
  commercialPageLastUpdated,
  type FaqItem,
} from "@/lib/seo";

export const metadata: Metadata = {
  title: "Минпромторг и реестровые требования в закупках",
  description:
    "TenderLex помогает отличить запрет, ограничение и преимущество по нацрежиму и понять, когда действительно нужна реестровая запись Минпромторга.",
  alternates: {
    canonical: "/reestr-minpromtorga-v-zakupkah",
  },
  openGraph: {
    type: "website",
    url: "/reestr-minpromtorga-v-zakupkah",
    title: "Минпромторг и реестровые требования в закупках | TenderLex",
    description:
      "Проверка требований к выпискам и реестровым записям Минпромторга: запрет, ограничение, преимущество и поиск поставщиков.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Минпромторг и реестровые требования в закупках | TenderLex",
    description:
      "Когда нужна реестровая запись Минпромторга, а когда действует ограничение или преимущество без обязательной выписки.",
    images: ["/tenderlex-product-preview.png"],
  },
};

const pagePath = "/reestr-minpromtorga-v-zakupkah";

const faqItems: FaqItem[] = [
  {
    question: "Когда нужна выписка из реестра Минпромторга?",
    answer:
      "Как обязательное условие допуска реестровая запись нужна при действующем запрете, когда документация прямо требует товар из реестра российской промышленной продукции, ГИСП или Евразийского реестра.",
  },
  {
    question: "Нужна ли выписка при ограничении?",
    answer:
      "Ограничение не равно запрету. При ограничении работает отдельный механизм допуска, поэтому выписку Минпромторга нельзя автоматически требовать как обязательное условие для каждого поставщика.",
  },
  {
    question: "Нужна ли выписка при преимуществе?",
    answer:
      "Преимущество товарам российского происхождения само по себе не делает реестровую запись обязательным условием допуска. Его нужно отличать от запрета.",
  },
  {
    question: "Что запросить у поставщика при запрете?",
    answer:
      "Нужно запросить номер действующей реестровой записи, источник записи и подтверждение, что запись относится к товару или производителю, указанному в техническом задании.",
  },
];

export default function MinpromRegistryPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Минпромторг в закупках", path: pagePath },
  ]);
  const schemaService = buildServiceJsonLd({
    name: "Проверка реестровых требований Минпромторга в закупках",
    description:
      "TenderLex помогает отличить запрет, ограничение и преимущество по нацрежиму, понять, когда нужна реестровая запись Минпромторга, и учесть это при поиске поставщиков.",
    path: pagePath,
    serviceType: "Procurement registry requirements check",
  });
  const schemaFaq = buildFaqJsonLd(faqItems);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaBreadcrumb) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaService) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaFaq) }}
      />
      <main className="legal-shell">
        <article className="legal-document">
          <a className="legal-back" href="/">
            ← TenderLex
          </a>
          <h1>Минпромторг и реестровые требования в закупках</h1>
          <p className="legal-date">Запрет, ограничение и преимущество нужно различать до первого письма поставщику. Обновлено {commercialPageLastUpdated}.</p>

          <section>
            <h2>Почему это важно</h2>
            <p>
              В закупках может встречаться национальный режим, запрет, ограничение, преимущество или требование к
              подтверждению страны происхождения. Для участника важно заранее понять, нужна ли выписка или реестровая
              запись Минпромторга, и не строить заявку на неверном предположении.
            </p>
            <p style={{ marginTop: 14 }}>
              Ключевое правило для работы с поставщиками: обязательную реестровую запись нужно искать и запрашивать
              при действующем запрете. Ограничение и преимущество требуют другой оценки и не должны автоматически
              превращаться в требование выписки.
            </p>
          </section>

          <section>
            <h2>Что делает TenderLex</h2>
            <p>
              При анализе документации сервис отдельно показывает вид меры и прямой ответ: требуются ли выписки из
              реестра Минпромторга. При поиске поставщиков этот контекст нужен для проверки производителей,
              дилеров и дистрибьюторов по релевантности товара и необходимости запросить подтверждающие документы.
            </p>
            <p style={{ marginTop: 14 }}>
              Если запрет действует, в <a href="/zapros-kp-po-tz">письмо поставщику по спецификации</a> нужно включить условие о
              действующей реестровой записи и попросить поставщика указать номер записи по конкретной позиции.
            </p>
          </section>

          <section>
            <h2>Где нужна проверка человека</h2>
            <p>
              Требования по нацрежиму зависят от конкретной редакции документации и формулировок заказчика. TenderLex
              ускоряет первичный разбор и подготовку вопросов, но финальное решение по допуску, заявке и комплекту
              документов должен подтвердить специалист.
            </p>
          </section>

          <section>
            <h2>Часто задаваемые вопросы</h2>
            <div style={{ display: "grid", gap: 20, marginTop: 8 }}>
              {faqItems.map((item, i) => (
                <div
                  key={i}
                  style={{
                    borderTop: i > 0 ? "1px solid var(--line)" : undefined,
                    paddingTop: i > 0 ? 20 : 0,
                  }}
                >
                  <h3 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 900 }}>
                    {item.question}
                  </h3>
                  <p
                    style={{
                      margin: 0,
                      color: "var(--ink-soft)",
                      fontSize: 15,
                      lineHeight: 1.65,
                    }}
                  >
                    {item.answer}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2>Что делать дальше</h2>
            <p>
              Запустите <a href="/analiz-zakupochnoi-dokumentacii">анализ закупочной документации</a>, а затем при
              необходимости используйте <a href="/poisk-postavshchikov-po-tz">поиск поставщиков под спецификацию</a> и подготовку
              первого письма поставщику.
            </p>
          </section>
        </article>
      </main>
    </>
  );
}
