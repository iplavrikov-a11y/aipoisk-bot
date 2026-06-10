import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Политика конфиденциальности",
  description: "Как TenderLex обрабатывает данные пользователей сайта и личного кабинета.",
  alternates: {
    canonical: "/privacy",
  },
  openGraph: {
    type: "website",
    url: "/privacy",
    title: "Политика конфиденциальности | TenderLex",
    description: "Как TenderLex обрабатывает данные пользователей сайта и личного кабинета.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Политика конфиденциальности | TenderLex",
    description: "Как TenderLex обрабатывает данные пользователей сайта и личного кабинета.",
    images: ["/tenderlex-product-preview.png"],
  },
};

export default function PrivacyPage() {
  return (
    <main className="legal-shell">
      <article className="legal-document">
        <a className="legal-back" href="/">TenderLex</a>
        <h1>Политика конфиденциальности</h1>
        <p className="legal-date">Редакция от 7 июня 2026 года</p>

        <section>
          <h2>1. Что обрабатывается</h2>
          <p>
            TenderLex обрабатывает данные, которые пользователь передает при работе с сайтом и личным кабинетом:
            email, имя, загруженные документы, текстовые описания задач, ссылки или номера закупок, историю запусков
            и результаты обработки.
          </p>
        </section>

        <section>
          <h2>2. Для чего это нужно</h2>
          <p>
            Данные используются для регистрации и входа в кабинет, запуска анализа закупок, поиска поставщиков,
            подготовки результатов, учета доступных запусков, поддержки пользователей и защиты сервиса от злоупотреблений.
          </p>
        </section>

        <section>
          <h2>3. Документы и результаты</h2>
          <p>
            Загруженные материалы используются только для выполнения выбранной задачи. Результаты доступны пользователю
            в личном кабинете и могут храниться ограниченное время для повторного скачивания и поддержки.
          </p>
        </section>

        <section>
          <h2>4. Передача третьим лицам</h2>
          <p>
            Для выполнения анализа и поиска TenderLex может использовать внешние технические сервисы обработки данных.
            Данные не продаются и не передаются третьим лицам для самостоятельной рекламы.
          </p>
        </section>

        <section>
          <h2>5. Защита доступа</h2>
          <p>
            Доступ к личному кабинету выполняется по email и паролю. Пользователь отвечает за сохранность пароля и должен
            сообщить в поддержку, если доступ мог попасть к третьим лицам.
          </p>
        </section>

        <section>
          <h2>6. Контакты</h2>
          <p>
            По вопросам обработки данных и доступа к кабинету можно написать на{" "}
            <a href="mailto:snab@dealpartner.ru">snab@dealpartner.ru</a> или в Telegram{" "}
            <a href="https://t.me/lexelence" target="_blank" rel="noreferrer">@lexelence</a>.
          </p>
        </section>
      </article>
    </main>
  );
}
