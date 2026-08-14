import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Правовая информация",
  description: "Документы и реквизиты сервиса TenderLex.",
  alternates: { canonical: "/legal" },
};

export default function LegalPage() {
  return (
    <main className="legal-shell">
      <article className="legal-document legal-index">
        <a className="legal-back" href="/">← TenderLex</a>
        <h1>Правовая информация</h1>
        <p className="legal-date">Актуальная редакция документов: 17 июля 2026 года · версия 2026-07-17</p>

        <div className="legal-cards">
          <a href="/terms">
            <strong>Публичная оферта</strong>
            <span>Условия работы, оплаты, оказания услуг и использования результатов.</span>
          </a>
          <a href="/privacy">
            <strong>Политика обработки персональных данных</strong>
            <span>Какие данные используются на сайте, в кабинете и Telegram-боте.</span>
          </a>
          <a href="/personal-data">
            <strong>Согласие на обработку персональных данных</strong>
            <span>Отдельный текст согласия, подтверждаемого пользователем.</span>
          </a>
        </div>

        <section>
          <h2>Владелец и реквизиты сервиса</h2>
          <p>
            Индивидуальный предприниматель Груздев Игорь Вячеславович<br />
            ИНН 352516048881 · ОГРНИП 323352500038991<br />
            Адрес: 160541, Вологодская область, Вологодский район, деревня Тарасово, д. 3<br />
            Email: <a href="mailto:info@tenderlex.ru">info@tenderlex.ru</a><br />
            Telegram: <a href="https://t.me/lexelence" target="_blank" rel="noreferrer">@lexelence</a>
          </p>
        </section>
      </article>
    </main>
  );
}
