"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Check, ChevronDown, FileText } from "lucide-react";
import "./product-walkthrough.css";

const examples = [
  {
    id: "supplier_search",
    label: "Поставщики",
    input: "Кабель ВВГнг(А)-LS 3×2,5 — 1 000 м. Поставка в Казань.",
    title: "От спецификации — к запросу поставщикам",
    output: [
      "Кандидаты на поставку: компания, её роль, сайт и контакты.",
      "Источники сведений, чтобы проверить соответствие вашей задаче.",
      "Проект запроса КП с позициями и вопросами об условиях поставки.",
    ],
    fragmentTitle: "Развернуть пример запроса КП",
    fragment:
      "Просим предложить кабель ВВГнг(А)-LS 3×2,5, объём 1 000 м, с доставкой в Казань. Укажите изготовителя, наличие, срок поставки, цену с НДС и стоимость доставки. Приложите паспорт и документы о соответствии продукции.",
    next: "Наличие, цену и срок поставки подтверждает поставщик в ответе на запрос.",
    action: "Найти поставщиков по своему ТЗ",
  },
  {
    id: "exact_product",
    label: "Аналоги",
    input: "Насос: подача 12 м³/ч, напор 30 м, питание 380 В. Нужен аналог.",
    title: "От требований — к сравнению вариантов",
    output: [
      "Характеристики исходной позиции и кандидатов на замену.",
      "Различия по параметрам и ссылки на технические документы.",
      "Рабочий отчёт для проверки модели и допустимости замены.",
    ],
    fragmentTitle: "Развернуть пример сравнения",
    rows: [
      [
        "Подача: 12 м³/ч",
        "Сопоставить с рабочей точкой на характеристике насоса.",
      ],
      [
        "Напор: 30 м",
        "Проверить напор при требуемой подаче, а не только максимальное значение.",
      ],
      ["Питание: 380 В", "Сверить исполнение и комплектность по паспорту."],
    ],
    next: "В примере показаны вопросы для сравнения. Конкретную модель проверяют по документации изготовителя и условиям закупки.",
    action: "Подобрать товар и аналоги",
  },
  {
    id: "procurement_report",
    label: "Анализ ТЗ",
    input:
      "Проект контракта: приёмка — 5 дней, оплата — после подписания акта.",
    title: "От документов — к списку уточнений",
    output: [
      "Сводка условий: сроки, оплата, приёмка и обеспечение.",
      "Фрагменты документа, которые требуют внимания.",
      "Вопросы для уточнения до подготовки заявки или подписания договора.",
    ],
    fragmentTitle: "Развернуть пример разбора условий",
    rows: [
      [
        "Оплата после подписания акта",
        "В этом фрагменте нет срока оплаты. Найти его в других пунктах или запросить уточнение.",
      ],
      [
        "Приёмка — 5 дней",
        "Уточнить начало отсчёта, вид дней и порядок уведомления о замечаниях.",
      ],
    ],
    next: "Это учебный разбор фрагмента. Выводы по закупке сверяют с полным комплектом документов и применимыми нормами.",
    action: "Разобрать свою документацию",
  },
];

export function ProductWalkthrough() {
  const [active, setActive] = useState(0);
  const example = examples[active];
  return (
    <section className="tl-demo" aria-labelledby="demo-title">
      <div className="tl-demo__heading">
        <span className="tl-demo__eyebrow">Учебный пример</span>
        <h2 id="demo-title">Что вы получите</h2>
        <p>Выберите задачу и посмотрите, как использовать результат.</p>
      </div>
      <div
        className="tl-demo__choices"
        role="group"
        aria-label="Выберите пример задачи"
      >
        {examples.map((item, index) => (
          <button
            key={item.id}
            type="button"
            aria-pressed={active === index}
            aria-controls="demo-content"
            onClick={() => setActive(index)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div id="demo-content" className="tl-demo__content" key={example.id}>
        <div className="tl-demo__input">
          <FileText size={20} aria-hidden="true" />
          <div>
            <span>Исходные данные · учебный пример</span>
            <p>{example.input}</p>
          </div>
        </div>
        <div className="tl-demo__output">
          <h3>{example.title}</h3>
          <ul>
            {example.output.map((item) => (
              <li key={item}>
                <Check size={16} aria-hidden="true" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
          <details className="tl-demo__fragment">
            <summary>
              {example.fragmentTitle}
              <ChevronDown size={16} aria-hidden="true" />
            </summary>
            {example.fragment ? (
              <blockquote>{example.fragment}</blockquote>
            ) : (
              <dl>
                {example.rows?.map(([term, description]) => (
                  <div key={term}>
                    <dt>{term}</dt>
                    <dd>{description}</dd>
                  </div>
                ))}
              </dl>
            )}
            <p>{example.next}</p>
          </details>
          <Link
            className="tl-demo__action"
            href={`/cabinet?scenario=${example.id}`}
          >
            {example.action}
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </div>
      </div>
      <p className="tl-demo__note">
        Учебный пример структуры результата. Переключение не запускает поиск и
        не расходует баланс.
      </p>
    </section>
  );
}
