import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Страница не найдена",
  description: "Запрошенная страница не существует или была перемещена.",
};

export default function NotFound() {
  return (
    <main className="legal-shell">
      <article className="legal-document">
        <a className="legal-back" href="/">
          ← TenderLex
        </a>
        <h1>Страница не найдена</h1>
        <p className="legal-date">Проверьте адрес или вернитесь к доступным сценариям TenderLex.</p>

        <section>
          <h2>Куда перейти</h2>
          <p>
            На главной странице можно выбрать <a href="/poisk-postavshchikov-po-tz">поиск поставщиков по ТЗ</a>,{" "}
            <a href="/analiz-zakupochnoi-dokumentacii">анализ закупочной документации</a> или открыть{" "}
            <a href="/cabinet">личный кабинет</a>.
          </p>
        </section>
      </article>
    </main>
  );
}
