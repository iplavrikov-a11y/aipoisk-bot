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
  title: "Анализ рынка 44-ФЗ перед участием в закупке",
  description:
    "TenderLex помогает оценить рынок по 44-ФЗ: поставщики, конкуренция, цены, сроки, риски исполнения и вопросы заказчику перед подачей заявки.",
  keywords: [
    "анализ рынка 44 фз",
    "анализ рынка закупки",
    "анализ рынка поставщиков 44 фз",
    "оценка рынка перед тендером",
    "поиск поставщиков для 44 фз",
    "TenderLex",
  ],
  alternates: {
    canonical: "/analiz-rynka-44-fz",
  },
  openGraph: {
    type: "website",
    url: "/analiz-rynka-44-fz",
    title: "Анализ рынка 44-ФЗ перед участием в закупке | TenderLex",
    description:
      "Оцените поставщиков, цены, конкуренцию, сроки и исполнимость закупки до подачи заявки.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Анализ рынка 44-ФЗ перед участием в закупке | TenderLex",
    description:
      "TenderLex показывает рыночные сигналы, поставщиков и риски перед решением об участии.",
    images: ["/tenderlex-product-preview.png"],
  },
};

const pagePath = "/analiz-rynka-44-fz";

const faqItems: FaqItem[] = [
  {
    question: "Что входит в анализ рынка 44-ФЗ?",
    answer:
      "Проверяются потенциальные поставщики, доступность товара, ориентиры по цене, сроки поставки, регион, документы качества, конкурентность закупки и условия, которые могут повлиять на исполнение договора.",
  },
  {
    question: "Когда нужен анализ рынка перед участием?",
    answer:
      "Перед расчетом цены и решением об участии, особенно если предмет закупки нестандартный, сроки жесткие, есть ограничения допуска, непонятные характеристики или риск, что товар сложно поставить в нужном объеме.",
  },
  {
    question: "Чем анализ рынка отличается от поиска поставщиков?",
    answer:
      "Поиск поставщиков дает список компаний и контактов. Анализ рынка шире: он помогает понять, насколько задача исполнима, какая конкуренция возможна, какие условия влияют на цену и какие вопросы стоит задать заказчику.",
  },
  {
    question: "Можно ли использовать результат для решения об участии?",
    answer:
      "Да. Результат подходит как рабочая основа для коммерческого решения: участвовать, уточнять условия, менять цену или отказаться. Финальное юридическое и финансовое решение остается за командой.",
  },
];

export default function MarketAnalysis44FzPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Анализ рынка 44-ФЗ", path: pagePath },
  ]);
  const schemaService = buildServiceJsonLd({
    name: "Анализ рынка 44-ФЗ перед участием в закупке",
    description:
      "TenderLex оценивает рынок закупки по 44-ФЗ: поставщиков, конкуренцию, сроки, доступность товара, риски исполнения и вопросы заказчику.",
    path: pagePath,
    serviceType: "Procurement market analysis",
  });
  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как провести анализ рынка 44-ФЗ с TenderLex",
    description:
      "Порядок оценки рынка: передать закупку, выделить предмет, найти рыночные сигналы, оценить риски и подготовить вопросы заказчику.",
    steps: [
      {
        name: "Передайте закупку или спецификацию",
        text: "Укажите номер извещения, ссылку на закупку, описание позиции или комплект документов.",
      },
      {
        name: "TenderLex выделяет предмет и условия",
        text: "Сервис определяет товар, характеристики, сроки, регион поставки, документы качества, ограничения и условия договора.",
      },
      {
        name: "Оцениваются рыночные сигналы",
        text: "Проверяются потенциальные поставщики, доступность товара, конкуренция, ценовые ориентиры и условия, которые могут повлиять на цену.",
      },
      {
        name: "Формируется вывод для решения",
        text: "Команда получает практический вывод: участвовать, уточнить условия, скорректировать цену или не заходить в закупку.",
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
          <h1>Анализ рынка 44-ФЗ перед участием в закупке</h1>
          <p className="legal-date">
            Для тендерных отделов и поставщиков, которым нужно понять рынок, цену и исполнимость закупки до подачи заявки. Обновлено {commercialPageLastUpdated}.
          </p>

          <section>
            <h2>Короткий ответ</h2>
            <p>
              Анализ рынка 44-ФЗ помогает до участия понять, есть ли реальные поставщики,
              насколько исполнимы сроки и условия, какая конкуренция возможна и какие вопросы
              стоит задать заказчику до расчета цены.
            </p>
          </section>

          <section>
            <h2>Что оценивается на рынке</h2>
            <p>
              TenderLex разбирает предмет закупки, характеристики товара, регион, сроки,
              требования к документам, ограничения допуска, проект договора и открытые рыночные
              сигналы по поставщикам.
            </p>
            <p style={{ marginTop: 14 }}>
              Цель анализа — не просто найти несколько сайтов, а понять, можно ли закрыть закупку
              без потери маржи, срыва сроков, отклонения заявки или спорной приемки.
            </p>
          </section>

          <section>
            <h2>Какие выводы получает команда</h2>
            <p>
              В результате видно, какие компании могут быть релевантны, какие характеристики
              требуют уточнения, где возможны проблемы с наличием, логистикой, документами качества,
              нацрежимом или ценой исполнения.
            </p>
          </section>

          <section>
            <h2>Когда это особенно полезно</h2>
            <p>
              Анализ рынка нужен перед участием в закупках с нестандартным товаром, короткими сроками,
              жесткими требованиями к документам, сложной логистикой, ограничениями допуска или
              неочевидной ценой поставки.
            </p>
          </section>

          <section>
            <h2>Связанные сценарии</h2>
            <p>
              Если нужен список компаний, используйте <a href="/poisk-postavshchikov-po-tz">поиск поставщиков по ТЗ</a>.
              Для полного разбора условий подойдет <a href="/analiz-zakupochnoi-dokumentacii">анализ закупочной документации</a>.
              Перед финальным решением можно отдельно провести <a href="/ocenka-riskov-zakupki">оценку рисков закупки</a>.
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
            <h2>Запустить анализ рынка</h2>
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
