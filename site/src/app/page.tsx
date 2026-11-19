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
import { getSiteData, type PublicSitePayload } from "@/lib/site-data";

import { HOME_V3_HTML } from "./home-v3-content";
import "./home-v3.css";

export const revalidate = 60;

export const metadata: Metadata = {
  title: {
    absolute: "Поиск поставщиков и подбор аналогов по ТЗ за 3 минуты — TenderLex",
  },
  description:
    "Сервис поиска прямых поставщиков и подбора аналогов товаров по ТЗ за 3 минуты. Проверка по реестрам РФ и ЕАЭС, контакты отделов продаж, расчет НМЦК и проект запроса КП.",
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
    title: "Поиск поставщиков и подбор аналогов по ТЗ за 3 минуты — TenderLex",
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
    title: "Поиск поставщиков и подбор аналогов по ТЗ за 3 минуты — TenderLex",
    description:
      "Кандидаты, аналоги и условия контракта из вашего ТЗ. Интерактивный разбор из 5 шагов и источники для проверки.",
    images: ["/tenderlex-og-1200x630.png"],
  },
};

type HomePricingSummary = {
  searchRub: number;
  exactRub: number;
  reportRub: number;
  minSingleRub: number;
  minPkgTaskRub: number;
  searchFromRub: number;
  exactFromRub: number;
  reportFromRub: number;
  trialRub: number;
};

function computeHomePricing(siteData: PublicSitePayload): HomePricingSummary {
  const fp = siteData.function_prices;
  const searchRub = fp?.supplier_search?.price_rub ?? 99;
  const exactRub = fp?.exact_product?.price_rub ?? 99;
  const reportRub = fp?.procurement_report?.price_rub ?? 99;
  const minSingleRub = Math.min(searchRub, exactRub, reportRub);

  const depositPkgs = (siteData.deposit_packages || siteData.tariffs || []).filter(
    (p) => p.kind === "deposit" && (p.price_rub ?? 0) > 0,
  );
  let bestRatio = 1;
  for (const pkg of depositPkgs) {
    const credit = pkg.credit_rub || pkg.total_rub || pkg.price_rub;
    if (credit > 0) {
      bestRatio = Math.min(bestRatio, pkg.price_rub / credit);
    }
  }
  const searchFromRub = Math.max(1, Math.round(searchRub * bestRatio));
  const exactFromRub = Math.max(1, Math.round(exactRub * bestRatio));
  const reportFromRub = Math.max(1, Math.round(reportRub * bestRatio));
  const minPkgTaskRub = Math.min(searchFromRub, exactFromRub, reportFromRub);
  const trialRub = Math.max(0, siteData.trial?.balance_rub ?? 495);

  return {
    searchRub,
    exactRub,
    reportRub,
    minSingleRub,
    minPkgTaskRub,
    searchFromRub,
    exactFromRub,
    reportFromRub,
    trialRub,
  };
}

function formatModulePriceLabel(fromRub: number, singleRub: number, unitLabel = "задача") {
  if (fromRub < singleRub) {
    return `от ${fromRub} ₽ / ${unitLabel} (разово ${singleRub} ₽)`;
  }
  return `${singleRub} ₽ / ${unitLabel}`;
}

function buildMainFaqItems(pricing: HomePricingSummary): FaqItem[] {
  const trialSentence =
    pricing.trialRub > 0
      ? `При создании кабинета на баланс начисляется ${pricing.trialRub.toLocaleString("ru-RU")} ₽ для бесплатной проверки на вашей спецификации без привязки банковской карты.`
      : "При создании кабинета вы можете сразу протестировать сервис на своей спецификации.";
  const priceLead =
    pricing.minPkgTaskRub < pricing.minSingleRub
      ? `Стоимость одной задачи — от ${pricing.minPkgTaskRub} ₽ в пакетах или от ${pricing.minSingleRub} ₽ при разовом запросе.`
      : `Стоимость одной задачи — от ${pricing.minSingleRub} ₽ при разовом запросе.`;

  return [
    {
      question: "Что делает сервис TenderLex?",
      answer:
        "TenderLex — профессиональный сервис для специалистов по закупкам и поставщиков. Сервис автоматически находит прямых производителей и поставщиков по ТЗ, подбирает российские аналоги по реестрам Минпромторга и ЕАЭС, а также анализирует закупочную документацию по 44-ФЗ и 223-ФЗ, выявляя скрытые риски и требования контракта.",
    },
    {
      question: "Какие данные и файлы можно загрузить?",
      answer:
        "Любые файлы спецификаций и технических заданий в форматах Word (DOCX/DOC), Excel (XLSX/XLS), PDF (включая сканы), архивы, прямые ссылки на закупки ЕИС или номера процедур по 44-ФЗ и 223-ФЗ.",
    },
    {
      question: "Можно ли использовать результат без проверки?",
      answer:
        "Нет. Результат помогает подготовить решение: кандидатов, сравнение и вопросы. Роль компании, контакты, наличие, цену и условия поставки подтверждают у поставщика и по первоисточникам.",
    },
    {
      question: "Как протестировать сервис перед оплатой?",
      answer: `${trialSentence} Вы можете сразу загрузить своё ТЗ и получить полный рабочий результат.`,
    },
    {
      question: "Какая география поиска поддерживается — только РФ или весь мир?",
      answer:
        "В личном кабинете TenderLex можно гибко выбрать охват: «Только Россия» (строго отечественные поставщики и производители с ИНН РФ для закупок с нацрежимом), «РФ и СНГ (ЕАЭС)» (поставщики России, Беларуси, Казахстана, Армении и Кыргызстана) или «Весь мир» для поиска прямых фабрик и параллельного импорта.",
    },
    {
      question: "Как оплатить и сколько это стоит?",
      answer: `${priceLead} Для новых пользователей доступно бесплатное тестирование на своей спецификации. Оплата доступна онлайн (банковские карты, СБП) и по безналичному расчету для юридических лиц и ИП с выставлением счета и закрывающими документами через ЭДО (Диадок, СБИС).`,
    },
  ];
}

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

function renderHomeHtml(pricing: HomePricingSummary): string {
  const pkgPhrase =
    pricing.minPkgTaskRub < pricing.minSingleRub
      ? `Разовые задачи от ${pricing.minSingleRub} ₽ или выгодные пакеты от ${pricing.minPkgTaskRub} ₽.`
      : `Разовые задачи от ${pricing.minSingleRub} ₽.`;

  const faqPriceSentence =
    pricing.minPkgTaskRub < pricing.minSingleRub
      ? `Стоимость одной задачи — от ${pricing.minPkgTaskRub} ₽ в пакетах или от ${pricing.minSingleRub} ₽ при разовом запросе.`
      : `Стоимость одной задачи — от ${pricing.minSingleRub} ₽ при разовом запросе.`;

  return (
    '<a class="skip-link" href="#main-content">К содержанию</a>' +
    HOME_V3_HTML
      .replace(
        "Разовые задачи от 99 ₽ или выгодные пакеты от 76 ₽.",
        pkgPhrase,
      )
      .replace(
        "Кандидаты, контакты сбыта, производители из реестров и проект КП · от 76 ₽ / задача",
        `Кандидаты, контакты сбыта, производители из реестров и проект КП · ${formatModulePriceLabel(pricing.searchFromRub, pricing.searchRub, "задача")}`,
      )
      .replace(
        "Сверка характеристик по ТЗ, проверка реестра Минпромторга и таблица параметров · от 76 ₽ / задача",
        `Сверка характеристик по ТЗ, проверка реестра Минпромторга и таблица параметров · ${formatModulePriceLabel(pricing.exactFromRub, pricing.exactRub, "поз.")}`,
      )
      .replace(
        "Скрытые риски контракта, неустойки, условия приёмки и нацрежим 44/223-ФЗ · от 76 ₽ / задача",
        `Скрытые риски контракта, неустойки, условия приёмки и нацрежим 44/223-ФЗ · ${formatModulePriceLabel(pricing.reportFromRub, pricing.reportRub, "задача")}`,
      )
      .replace(
        "При создании кабинета на баланс начисляется 495 ₽ для бесплатной проверки на вашей спецификации без привязки банковской карты.",
        pricing.trialRub > 0
          ? `При создании кабинета на баланс начисляется ${pricing.trialRub.toLocaleString("ru-RU")} ₽ для бесплатной проверки на вашей спецификации без привязки банковской карты.`
          : "При создании кабинета вы можете сразу бесплатно проверить работу сервиса на вашей спецификации без привязки банковской карты.",
      )
      .replace(
        "Стоимость одной задачи — от 76 ₽ в пакетах или 99 ₽ при разовом запросе.",
        faqPriceSentence,
      )
  );
}

export default async function HomePage() {
  const siteData = await getSiteData();
  const pricing = computeHomePricing(siteData);
  const mainFaqItems = buildMainFaqItems(pricing);
  const htmlWithSkipLink = renderHomeHtml(pricing);

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
