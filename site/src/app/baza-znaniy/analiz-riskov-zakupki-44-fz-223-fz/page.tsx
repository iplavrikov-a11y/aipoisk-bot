import type { Metadata } from "next";

import { buildBreadcrumbJsonLd, buildHowToJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Анализ рисков закупки по 44-ФЗ и 223-ФЗ до подачи заявки",
  description:
    "Как поставщику проверить закупочную документацию на скрытые риски: штрафы, приемка, жесткие сроки поставки и требования нацрежима Минпромторга.",
  keywords: [
    "анализ рисков закупки 44-ФЗ",
    "анализ рисков закупки 223-ФЗ",
    "проверка закупочной документации",
    "реестр Минпромторга закупки",
    "оценка контракта закупщика",
  ],
  alternates: {
    canonical: "/baza-znaniy/analiz-riskov-zakupki-44-fz-223-fz",
  },
  openGraph: {
    type: "article",
    url: "/baza-znaniy/analiz-riskov-zakupki-44-fz-223-fz",
    title: "Анализ рисков закупки по 44-ФЗ и 223-ФЗ | TenderLex",
    description:
      "Инструкция для тендерных специалистов по проверке контрактов и документации госзакупок до принятия решения об участии.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

const steps = [
  {
    name: "Проверка сроков и условий поставки",
    text: "Оцените реальность сроков выполнения работ или поставки товара. Выявите невязки между датой заключения контракта и требованием по приёмке.",
  },
  {
    name: "Анализ условий оплаты и авансирования",
    text: "Установите наличие аванса, размер обеспечения исполнения контракта и казначейского сопровождения.",
  },
  {
    name: "Анализ штрафных санкций и порядка приёмки",
    text: "Проверьте раздел ответственности сторон в проекте контракта: повышенные пени, нестандартные условия экспертизы товара.",
  },
  {
    name: "Проверка требований нацрежима и реестров",
    text: "Определите, распространяются ли ограничения Постановления № 616 или 617, требуется ли подтверждение происхождения товара в реестре Минпромторга.",
  },
];

export default function GuideRiskAnalysisPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "База знаний", path: "/baza-znaniy" },
    { name: "Анализ рисков 44-ФЗ и 223-ФЗ", path: "/baza-znaniy/analiz-riskov-zakupki-44-fz-223-fz" },
  ]);

  const howToSchema = buildHowToJsonLd({
    name: "Как проанализировать риски тендера по 44-ФЗ и 223-ФЗ",
    description:
      "Пошаговый аудит закупочной документации и проекта контракта для принятия взвешенного решения об участии в торговле.",
    steps,
  });

  return (
    <article className="min-h-screen py-12 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(howToSchema) }}
      />

      <nav className="mb-6">
        <a href="/baza-znaniy" className="text-sm font-medium text-teal-700 font-bold hover:underline">
          ← Назад в базу знаний
        </a>
      </nav>

      <header className="mb-8 border-b pb-6 border-gray-200">
        <span className="text-xs font-semibold text-teal-900 font-extrabold bg-teal-50/80 px-3 py-1 rounded-full uppercase">
          Руководство поставщикам
        </span>
        <h1 className="text-3xl font-extrabold text-gray-900 mt-3 mb-4">
          Анализ рисков закупки по 44-ФЗ и 223-ФЗ до подачи заявки
        </h1>
        <p className="text-lg text-gray-600">
          Чек-лист для тендерных специалистов: как защитить компанию от неисполнимых контрактов и неправомерных штрафов.
        </p>
      </header>

      <div className="prose prose-teal max-w-none text-gray-800 space-y-6">
        <h2>1. Зачем проверять закупку до подачи заявки</h2>
        <p>
          Победа в закупке — это только начало работы. Нарушение условий контракта может привести к попаданию компании в Реестр недобросовестных поставщиков (РНП) и удержанию обеспечения. Поэтому предварительный анализ условий договора критически важен.
        </p>

        <h2>2. Чек-лист проверки контракта</h2>
        <ol className="list-decimal pl-6 space-y-4">
          {steps.map((s, idx) => (
            <li key={idx}>
              <strong>{s.name}:</strong> {s.text}
            </li>
          ))}
        </ol>

        <h2>3. Автоматический экспресс-разбор с TenderLex</h2>
        <p>
          Сервис <strong>TenderLex</strong> позволяет загрузить документацию или номер извещения закупки и за считанные минуты получить структурированный отчет: условия участия, рискованные пункты договора, спорные места приёмки и перечень вопросов для запроса разъяснений заказчику.
        </p>

        <div className="my-8 p-6 bg-teal-50/80 rounded-2xl border border-teal-200 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-gray-900 m-0">Хотите проверить закупку прямо сейчас?</h3>
            <p className="text-sm text-gray-600 m-0 mt-1">
              Загрузите номер извещения или файл в TenderLex и получите разбор рисков.
            </p>
          </div>
          <a
            href="/analiz-zakupochnoi-dokumentacii"
            className="px-5 py-2.5 bg-teal-600 text-white font-extrabold font-medium rounded-lg text-sm hover:bg-teal-700 transition-colors whitespace-nowrap"
          >
            Разобрать документацию
          </a>
        </div>
      </div>
    </article>
  );
}
