import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Согласие на обработку персональных данных",
  description: "Согласие пользователя TenderLex на обработку данных для работы личного кабинета.",
  alternates: {
    canonical: "/personal-data",
  },
  openGraph: {
    type: "website",
    url: "/personal-data",
    title: "Согласие на обработку персональных данных | TenderLex",
    description: "Согласие пользователя TenderLex на обработку данных для работы личного кабинета.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Согласие на обработку персональных данных | TenderLex",
    description: "Согласие пользователя TenderLex на обработку данных для работы личного кабинета.",
    images: ["/tenderlex-product-preview.png"],
  },
};

export default function PersonalDataPage() {
  return (
    <main className="legal-shell">
      <article className="legal-document">
        <a className="legal-back" href="/">TenderLex</a>
        <h1>Согласие на обработку персональных данных</h1>
        <p className="legal-date">Редакция от 7 июня 2026 года</p>

        <section>
          <h2>1. Согласие пользователя</h2>
          <p>
            Создавая личный кабинет или отправляя данные через сайт TenderLex, пользователь дает согласие на обработку
            переданных данных для работы сервиса, поддержки и учета доступных запусков.
          </p>
        </section>

        <section>
          <h2>2. Состав данных</h2>
          <p>
            Обрабатываться могут email, имя, сведения о действиях в кабинете, документы и текстовые материалы,
            которые пользователь передает для анализа закупок или поиска поставщиков.
          </p>
        </section>

        <section>
          <h2>3. Действия с данными</h2>
          <p>
            Сервис может собирать, записывать, хранить, уточнять, использовать, удалять данные и передавать их
            техническим обработчикам только в объеме, необходимом для выполнения пользовательской задачи.
          </p>
        </section>

        <section>
          <h2>4. Срок действия согласия</h2>
          <p>
            Согласие действует до его отзыва пользователем или до удаления учетной записи и материалов, если более
            длительное хранение не требуется для защиты прав и законных интересов.
          </p>
        </section>

        <section>
          <h2>5. Отзыв согласия</h2>
          <p>
            Чтобы отозвать согласие или запросить удаление данных, напишите на{" "}
            <a href="mailto:snab@dealpartner.ru">snab@dealpartner.ru</a> или через{" "}
            <a href="https://t.me/lexelence" target="_blank" rel="noreferrer">Telegram</a>.
          </p>
        </section>
      </article>
    </main>
  );
}
