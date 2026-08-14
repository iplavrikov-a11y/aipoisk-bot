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
  title: "Поиск поставщиков для тендера — проверка рынка до заявки",
  description:
    "Передайте извещение или документы тендера и проверьте, какие компании могут закрыть условия, сроки и регион до решения об участии.",
  keywords: [
    "поиск поставщиков для тендера",
    "поставщики под закупку",
    "найти поставщика для участия в тендере",
    "проверить рынок перед участием в тендере",
    "TenderLex",
  ],
  alternates: {
    canonical: "/poisk-postavshchikov-dlya-tendera",
  },
  openGraph: {
    type: "website",
    url: "/poisk-postavshchikov-dlya-tendera",
    title: "Поиск поставщиков для тендера — проверка рынка до заявки | TenderLex",
    description:
      "Передайте извещение или документы тендера и проверьте, какие компании могут закрыть условия до решения об участии.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Поиск поставщиков для тендера — проверка рынка до заявки | TenderLex",
    description:
      "TenderLex помогает проверить рынок и собрать адресатов под условия конкретного тендера.",
    images: ["/tenderlex-product-preview.png"],
  },
};

const pagePath = "/poisk-postavshchikov-dlya-tendera";

const faqItems: FaqItem[] = [
  {
    question: "Чем этот сценарий отличается от поиска поставщиков по спецификации?",
    answer:
      "Здесь поиск привязан к конкретной закупке: учитываются предмет, объем, срок, регион, условия поставки и требования из документации. Результат нужен, чтобы оценить исполнимость и собрать первую волну запросов до подачи заявки.",
  },
  {
    question: "Можно начать с номера извещения или ссылки на закупку?",
    answer:
      "Да. TenderLex использует номер, ссылку, комплект документов или отдельную спецификацию, чтобы выделить позиции и условия, которые меняют состав списка поставщиков.",
  },
  {
    question: "Оценивает ли TenderLex шанс победить в тендере?",
    answer:
      "Нет. Сервис помогает проверить поставочную сторону задачи: кому запросить цену, какие условия уточнить и где есть риск не закрыть позицию. Решение об участии и юридическую оценку принимает ваша команда.",
  },
  {
    question: "Как учитываются ограничения допуска и нацрежим?",
    answer:
      "Ограничения из конкретной закупки выделяются как условия для проверки. Если вопрос связан с реестром или подтверждением происхождения, его нужно подтвердить по документации и в ответе поставщика.",
  },
  {
    question: "TenderLex отправляет заявку или запросы за команду?",
    answer:
      "Нет. Сервис готовит рабочий список и вопросы для первого обращения. Отправку запросов, переговоры, подачу заявки и финальную проверку выполняет ваша команда.",
  },
];

export default function TenderSupplierSearchPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Поиск поставщиков для тендера", path: pagePath },
  ]);
  const schemaService = buildServiceJsonLd({
    name: "Поиск поставщиков для тендера перед участием",
    description:
      "TenderLex собирает поставщиков под условия конкретной закупки, помогает проверить рынок и подготовить вопросы до решения об участии.",
    path: pagePath,
    serviceType: "Tender supplier search before participation",
  });
  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как проверить поставщиков под тендер с TenderLex",
    description:
      "Порядок работы: передать закупку, выделить условия, собрать адресатов и проверить, что нужно уточнить до подачи заявки.",
    steps: [
      {
        name: "Передайте закупку",
        text: "Укажите номер извещения, ссылку, загрузите документы или опишите нужную позицию.",
      },
      {
        name: "Выделите условия, влияющие на поставку",
        text: "Проверьте номенклатуру, объем, срок, регион, требования к документам и ограничения из закупки.",
      },
      {
        name: "Соберите первую волну адресатов",
        text: "В список попадают компании, которым можно задать одинаковые вопросы о цене, сроке и подтверждающих документах.",
      },
      {
        name: "Примите решение на основе ответов",
        text: "Команда сопоставляет ответы поставщиков с условиями закупки и самостоятельно решает вопрос об участии.",
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
          <h1>Проверить поставщиков под условия тендера</h1>
          <p className="legal-date">
            Для тендерных отделов и снабжения, которым нужно проверить рынок до решения об участии. Обновлено {seoPageLastUpdated}.
          </p>

          <section>
            <h2>Поставщики под конкретный тендер</h2>
            <p>
              Это не общий поиск сайтов по названию товара. В тендере список компаний строится вокруг конкретной
              поставки: что нужно поставить, в каком объеме и сроке, куда доставить и какие условия подтвердить.
            </p>
            <p style={{ marginTop: 14 }}>
              TenderLex помогает собрать адресатов для первой проверки рынка. Результат отвечает на практический вопрос:
              кому запросить цену и какие ответы нужны, чтобы понять исполнимость закупки до подачи заявки.
            </p>
          </section>

          <section>
            <h2>Какие условия тендера меняют список</h2>
            <p>
              На состав адресатов влияют не только характеристики товара. Важны объем и график поставки, регион или
              адрес, требования к документам качества, возможность предложить аналог и ограничения из закупочной
              документации. Эти параметры нужно вынести в первый запрос, иначе ответы нельзя будет честно сравнить.
            </p>
          </section>

          <section>
            <h2>Что получает тендерная команда</h2>
            <p>
              В рабочем списке видны компания, тип канала поставки, сайт и контакты, комментарий о связи с предметом
              закупки и вопросы для первого обращения. Это основа для проверки цены, срока, доступности товара и
              подтверждающих документов.
            </p>
          </section>

          <section>
            <h2>Что нужно подтвердить отдельно</h2>
            <p>
              TenderLex использует открытые сведения и не заменяет ответ поставщика. Наличие, цена, срок,
              договорные условия, правовой статус документов и окончательное соответствие позиции нужно подтвердить
              у компании и проверить внутри вашей команды.
            </p>
          </section>

          <section>
            <h2>Связанные задачи</h2>
            <p>
              Для полного разбора требований до поиска используйте <a href="/analiz-zakupochnoi-dokumentacii">анализ закупочной документации</a>.
              Если закупка уже разобрана и нужен широкий пул компаний под обычную спецификацию, подойдет{" "}
              <a href="/poisk-postavshchikov-po-tz">поиск поставщиков по ТЗ</a>. Для завода или официального канала
              используйте <a href="/poisk-proizvoditeley-po-tz">поиск производителей</a>.
            </p>
            <p style={{ marginTop: 14 }}>
              Когда рынок уже проверен, можно <a href="/postavshchiki-dlya-zaprosa-kp">отобрать первую волну адресатов</a>{" "}
              и <a href="/zapros-kp-po-tz">подготовить единый запрос КП</a>.
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
            <h2>Запустить проверку рынка</h2>
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
