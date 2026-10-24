import type { Metadata } from "next";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { HomeV3Interactions } from "@/components/home-v3-interactions";
import {
  buildFaqJsonLd,
  buildServiceJsonLd,
  buildWebSiteJsonLd,
  type FaqItem,
} from "@/lib/seo";

import { HOME_V3_HTML } from "./home-v3-content";
import "./home-v3.css";

export const revalidate = 300;

export const metadata: Metadata = {
  title: {
    absolute: "Поиск поставщиков и аналогов по ТЗ — TenderLex",
  },
  description:
    "Передайте ТЗ или спецификацию: TenderLex соберёт кандидатов, сравнит аналоги и покажет условия контракта. Интерактивный разбор из 5 шагов, источники и проект запроса КП.",
  keywords: [
    "поиск поставщиков по ТЗ",
    "подбор аналогов по ТЗ",
    "поиск товаров по ТЗ",
    "эквивалент оборудования 44 фз",
    "поиск производителей Россия",
    "запрос коммерческого предложения",
    "контакты отделов продаж заводов",
    "реестр минпромторга аналоги",
    "анализ рисков 44-ФЗ и 223-ФЗ",
    "коммерческие закупки",
    "интерактивный разбор ТЗ",
    "TenderLex",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    title: "Поиск поставщиков и подбор аналогов по ТЗ — TenderLex",
    description:
      "TenderLex: кандидаты на поставку, сравнение аналогов и разбор условий контракта. Интерактивный разбор ТЗ из 5 шагов с источниками для проверки.",
    url: "https://tenderlex.ru",
    siteName: "TenderLex",
    locale: "ru_RU",
    type: "website",
    images: ["/tenderlex-og-1200x630.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Поиск поставщиков и аналогов по ТЗ — TenderLex",
    description:
      "Кандидаты, аналоги и условия контракта из вашего ТЗ. Интерактивный разбор из 5 шагов и источники для проверки.",
    images: ["/tenderlex-og-1200x630.png"],
  },
};

const mainFaqItems: FaqItem[] = [
  {
    question: "Это уже новый рабочий сайт?",
    answer:
      "Да, это обновлённая главная страница TenderLex. Интерактивный разбор показывает структуру результата и логику шагов. Рабочий сервис, кабинет и тарифы доступны по прежним адресам.",
  },
  {
    question: "Что можно передать в TenderLex?",
    answer:
      "Техническое задание, спецификацию, документы закупки, ссылку на процедуру или текст задачи. В демонстрации на этой странице файлы не загружаются и никуда не отправляются.",
  },
  {
    question: "Можно ли использовать результат без проверки?",
    answer:
      "Нет. Результат помогает подготовить решение: кандидатов, сравнение и вопросы. Роль компании, контакты, наличие, цену и условия поставки подтверждают у поставщика и по первоисточникам.",
  },
  {
    question: "Чем демонстрация отличается от запуска задачи?",
    answer:
      "Демонстрация показывает структуру результата и логику шагов. Она не запускает поиск, не отправляет запросы и не расходует баланс. Запуск задачи происходит в кабинете на ваших данных.",
  },
  {
    question: "Где посмотреть тарифы и условия?",
    answer:
      "Актуальные тарифы и доступные пакеты отображаются в кабинете до запуска. Стоимость и доступность управляются в системе, поэтому на этой странице нет захардкоженных цен.",
  },
];

const serviceSchemas = [
  buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ",
    description:
      "Поиск кандидатов на поставку по спецификации или техническому заданию: роль компании, регион, источники и проект запроса КП.",
    path: "/poisk-postavshchikov-po-tz",
    serviceType: "B2B supplier search",
  }),
  buildServiceJsonLd({
    name: "Подбор товара и аналогов по ТЗ",
    description:
      "Сопоставление требований ТЗ с характеристиками товаров и подготовка сравнения аналогов с отличиями и источниками для проверки.",
    path: "/podbor-tovara-i-analogov-po-tz",
    serviceType: "B2B product and analog matching",
  }),
  buildServiceJsonLd({
    name: "Анализ закупочной документации",
    description:
      "Разбор проекта контракта и извещения: сроки, оплата, приёмка, обеспечение и вопросы, которые стоит уточнить до заявки.",
    path: "/analiz-zakupochnoi-dokumentacii",
    serviceType: "Procurement document analysis",
  }),
];

const htmlWithSkipLink = '<a class="skip-link" href="#main-content">К содержанию</a>' + HOME_V3_HTML;

export default function HomePage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(buildWebSiteJsonLd()) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(buildFaqJsonLd(mainFaqItems)) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceSchemas) }}
      />
      <main className="tl-public">
        <SiteHeader />
        <div
          className="home-v3"
          id="main-content"
          dangerouslySetInnerHTML={{ __html: htmlWithSkipLink }}
        />
        <SiteFooter />
      </main>
      <HomeV3Interactions />
    </>
  );
}
