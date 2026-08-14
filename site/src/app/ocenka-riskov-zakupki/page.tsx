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
  title: "Оценка рисков закупки перед участием",
  description:
    "TenderLex помогает оценить риски закупки: сроки, обеспечение, приемку, штрафы, оплату, нацрежим, спорные условия договора и вопросы заказчику.",
  keywords: [
    "оценка рисков закупки",
    "риски закупочной документации",
    "проверка рисков тендера",
    "анализ рисков договора закупки",
    "риски участия в закупке",
    "TenderLex",
  ],
  alternates: {
    canonical: "/ocenka-riskov-zakupki",
  },
  openGraph: {
    type: "website",
    url: "/ocenka-riskov-zakupki",
    title: "Оценка рисков закупки перед участием | TenderLex",
    description:
      "Проверьте закупку до подачи заявки: сроки, обеспечение, штрафы, приемка, оплата, нацрежим и спорные условия договора.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Оценка рисков закупки перед участием | TenderLex",
    description:
      "TenderLex выделяет риски закупки и вопросы заказчику до подачи заявки.",
    images: ["/tenderlex-product-preview.png"],
  },
};

const pagePath = "/ocenka-riskov-zakupki";

const faqItems: FaqItem[] = [
  {
    question: "Какие риски закупки стоит проверить до подачи заявки?",
    answer:
      "Сроки исполнения, обеспечение заявки и договора, приемку, штрафы, оплату, требования к участнику, документы качества, нацрежим, возможность поставки нужного товара и спорные условия договора.",
  },
  {
    question: "Что считается критичным риском?",
    answer:
      "Критичный риск — это условие, которое может привести к отклонению заявки, невозможности поставить товар, кассовому разрыву, штрафам или спору при приемке. Такие пункты нужно выносить в решение об участии отдельно.",
  },
  {
    question: "TenderLex заменяет юриста?",
    answer:
      "Нет. Сервис ускоряет первичный анализ и показывает, какие условия требуют внимания. Финальную правовую позицию по договору и спорным пунктам должна подтвердить команда или профильный юрист.",
  },
  {
    question: "Можно ли сразу подготовить вопросы заказчику?",
    answer:
      "Да. В результате анализа формируются вопросы по неясным характеристикам, срокам, приемке, документам качества, нацрежиму и условиям договора.",
  },
];

export default function ProcurementRiskAssessmentPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Оценка рисков закупки", path: pagePath },
  ]);
  const schemaService = buildServiceJsonLd({
    name: "Оценка рисков закупки перед участием",
    description:
      "TenderLex анализирует закупочную и тендерную документацию, выделяет риски участия, спорные условия договора и вопросы заказчику.",
    path: pagePath,
    serviceType: "Procurement risk assessment",
  });
  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как оценить риски закупки с TenderLex",
    description:
      "Порядок проверки закупки: загрузить документацию, выделить условия, оценить риски и подготовить вопросы заказчику.",
    steps: [
      {
        name: "Передайте закупочную документацию",
        text: "Укажите номер извещения, ссылку на закупку или загрузите комплект документов.",
      },
      {
        name: "TenderLex выделяет ключевые условия",
        text: "Сервис извлекает сроки, обеспечение, оплату, приемку, штрафы, требования к участнику и условия договора.",
      },
      {
        name: "Риски группируются по влиянию",
        text: "Отдельно показываются пункты, которые могут повлиять на допуск, цену, исполнение договора или приемку товара.",
      },
      {
        name: "Готовятся вопросы заказчику",
        text: "По спорным формулировкам формируются вопросы, которые стоит задать до подачи заявки.",
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
          <h1>Оценка рисков закупки перед участием</h1>
          <p className="legal-date">
            Для тендерных отделов, которым нужно быстро понять, где заявка или исполнение могут стать проблемой. Обновлено {commercialPageLastUpdated}.
          </p>

          <section>
            <h2>Короткий ответ</h2>
            <p>
              Оценка рисков закупки помогает до подачи заявки увидеть условия, которые могут привести к отклонению,
              убыткам при исполнении, спору с заказчиком или невозможности поставить товар в срок.
            </p>
          </section>

          <section>
            <h2>Что проверяется в документации</h2>
            <p>
              TenderLex разбирает закупочную и тендерную документацию по блокам: предмет закупки, требования к участнику,
              сроки, обеспечение, оплату, поставку, приемку, штрафы, расторжение, нацрежим, документы качества и проект договора.
            </p>
            <p style={{ marginTop: 14 }}>
              Риск оценивается не абстрактно, а через влияние на решение об участии: можно ли подтвердить требования,
              успеть с поставкой, заложить расходы в цену и получить оплату без спорной приемки.
            </p>
          </section>

          <section>
            <h2>Какие риски чаще всего всплывают</h2>
            <p>
              Типовые проблемы: короткий срок поставки, жесткая приемка, непропорциональные штрафы, неясные характеристики,
              спорные требования к документам, кассовый разрыв из-за оплаты, ограничения по стране происхождения и неочевидные
              реестровые требования.
            </p>
          </section>

          <section>
            <h2>Что получает команда</h2>
            <p>
              Результат — структурированный список рисков, практический вывод по каждому блоку и вопросы заказчику.
              Его можно передать руководителю, юристу, снабжению или финансисту для решения: участвовать, уточнять условия
              или отказаться от закупки.
            </p>
          </section>

          <section>
            <h2>Связанные сценарии</h2>
            <p>
              Для полного разбора используйте <a href="/analiz-zakupochnoi-dokumentacii">анализ закупочной документации</a>.
              Если после оценки нужно понять рынок, запустите <a href="/poisk-postavshchikov-dlya-tendera">поиск поставщиков для тендера</a>.
              Для риска отклонения отдельно проверьте <a href="/reestr-minpromtorga-v-zakupkah">нацрежим и реестровые требования</a>.
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
            <h2>Запустить оценку рисков</h2>
            <p>
              Откройте <a href="/cabinet">личный кабинет</a> или отправьте номер закупки, ссылку или документы в{" "}
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
