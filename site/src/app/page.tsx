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
  expressRub: number;
  monitoringRub: number;
  minSingleRub: number;
  minPkgTaskRub: number;
  searchFromRub: number;
  exactFromRub: number;
  reportFromRub: number;
  expressFromRub: number;
  monitoringFromRub: number;
  trialRub: number;
  depositPackages: Array<{
    name: string;
    priceRub: number;
    bonusRub: number;
    creditRub: number;
    badge: string;
  }>;
};

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function computeHomePricing(siteData: PublicSitePayload): HomePricingSummary {
  const fp = siteData.function_prices;
  const searchRub = fp?.supplier_search?.price_rub ?? 99;
  const exactRub = fp?.exact_product?.price_rub ?? 99;
  const reportRub = fp?.procurement_report?.price_rub ?? 50;
  const expressRub = fp?.custom_batch_report?.price_rub ?? 30;
  const monitoringRub = fp?.price_monitoring?.price_rub ?? 90;
  const minSingleRub = Math.min(searchRub, exactRub, reportRub, expressRub);

  const depositPkgs = (siteData.deposit_packages || siteData.tariffs || [])
    .filter((p) => p.kind === "deposit" && (p.price_rub ?? 0) > 0)
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0));
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
  const expressFromRub = Math.max(1, Math.round(expressRub * bestRatio));
  const monitoringFromRub = Math.max(1, Math.round(monitoringRub * bestRatio));
  const minPkgTaskRub = Math.min(searchFromRub, exactFromRub, reportFromRub, expressFromRub);
  const trialRub = Math.max(0, siteData.trial?.balance_rub ?? 250);

  return {
    searchRub,
    exactRub,
    reportRub,
    expressRub,
    monitoringRub,
    minSingleRub,
    minPkgTaskRub,
    searchFromRub,
    exactFromRub,
    reportFromRub,
    expressFromRub,
    monitoringFromRub,
    trialRub,
    depositPackages: depositPkgs.map((pkg) => ({
      name: pkg.name,
      priceRub: Math.round(pkg.price_rub),
      bonusRub: Math.round(pkg.bonus_rub || 0),
      creditRub: Math.round(pkg.credit_rub || pkg.total_rub || pkg.price_rub),
      badge: (pkg.badge || "").trim(),
    })),
  };
}

function formatModulePriceLabel(fromRub: number, singleRub: number, unitLabel = "задача") {
  if (fromRub < singleRub) {
    return `от ${fromRub} ₽ / ${unitLabel} (разово ${singleRub} ₽)`;
  }
  return `${singleRub} ₽ / ${unitLabel}`;
}

function renderDepositPackagesHtml(pricing: HomePricingSummary): string {
  if (!pricing.depositPackages.length) return "";
  const cards = pricing.depositPackages
    .map((pkg) => {
      const isHit = Boolean(pkg.badge);
      const bonusPct = pkg.priceRub > 0 && pkg.bonusRub > 0 ? Math.round((pkg.bonusRub / pkg.priceRub) * 100) : 0;
      const bonusLine =
        pkg.bonusRub > 0
          ? `<span class="deposit-pill__bonus">+${pkg.bonusRub.toLocaleString("ru-RU")} ₽ бонус (+${bonusPct}%)</span><span class="deposit-pill__meta">На баланс: ${pkg.creditRub.toLocaleString("ru-RU")} ₽</span>`
          : `<span class="deposit-pill__meta">На баланс: ${pkg.creditRub.toLocaleString("ru-RU")} ₽ · без срока сгорания</span>`;
      return `<a class="deposit-pill${isHit ? " deposit-pill--hit" : ""}" href="/cabinet?tab=billing"><div class="deposit-pill__top"><span class="deposit-pill__name">${escapeHtml(pkg.name)}</span>${pkg.badge ? `<span class="deposit-pill__badge">${escapeHtml(pkg.badge)}</span>` : ""}</div><strong class="deposit-pill__price">${pkg.priceRub.toLocaleString("ru-RU")} ₽</strong>${bonusLine}</a>`;
    })
    .join("");
  return `<div class="access__deposits" data-reveal><div class="access__deposits-head"><strong>Пакеты пополнения единого баланса</strong><span>Средства не сгорают и подходят для всех инструментов: веб-кабинета, Telegram-бота и API</span></div><div class="access__deposits-grid">${cards}</div></div>`;
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
        "TenderLex — профессиональный сервис для специалистов по закупкам и поставщиков. Сервис находит производителей, поставщиков товаров и подрядчиков услуг по ТЗ, подбирает аналоги по реестрам Минпромторга и ЕАЭС, анализирует документацию 44-ФЗ и 223-ФЗ (по одной или пакетом до 10 закупок), делает быструю экспресс-оценку до 30 закупок и мониторинг цен по спецификации.",
    },
    {
      question: "Какие данные и файлы можно загрузить?",
      answer:
        "Любые файлы спецификаций и ТЗ: Word (DOCX/DOC), Excel (XLSX/XLS/CSV), PDF (включая сканы), изображения и скриншоты (PNG, JPG, WEBP), архивы, прямые ссылки на закупки ЕИС или списки номеров процедур по 44-ФЗ и 223-ФЗ.",
    },
    {
      question: "Чем экспресс-оценка отличается от полного анализа документации?",
      answer:
        "Экспресс-оценка позволяет загрузить сразу до 30 закупок из таблицы, списка или скриншота, быстро отсортировать их по сроку подачи и НМЦК и отсеять неподходящие. Полный «Анализ документации» разбирает контракт и ТЗ глубоко (можно запускать по одной или пакетом до 10 закупок), а из карточки экспресс-оценки можно в один клик перейти в детальный разбор.",
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
        "Поставщики товаров и подрядчики услуг, контакты сбыта, приоритет по радиусу доставки и проект КП · от 76 ₽ / задача",
        `Поставщики товаров и подрядчики услуг, контакты сбыта, приоритет по радиусу доставки и проект КП · ${formatModulePriceLabel(pricing.searchFromRub, pricing.searchRub, "задача")}`,
      )
      .replace(
        "Сверка характеристик по ТЗ, проверка реестра Минпромторга и отчёт в Word · от 76 ₽ / задача",
        `Сверка характеристик по ТЗ, проверка реестра Минпромторга и отчёт в Word · ${formatModulePriceLabel(pricing.exactFromRub, pricing.exactRub, "поз.")}`,
      )
      .replace(
        "Риски контракта, штрафы, нацрежим 44/223-ФЗ · разовый и пакетный запуск до 10 закупок · от 76 ₽ / задача",
        `Риски контракта, штрафы, нацрежим 44/223-ФЗ · разовый и пакетный запуск до 10 закупок · ${formatModulePriceLabel(pricing.reportFromRub, pricing.reportRub, "задача")}`,
      )
      .replace(
        "__EXPRESS_PRICE__",
        formatModulePriceLabel(pricing.expressFromRub, pricing.expressRub, "закупка"),
      )
      .replace(
        "__MONITORING_PRICE__",
        formatModulePriceLabel(pricing.monitoringFromRub, pricing.monitoringRub, "поз."),
      )
      .replace(
        "__DEPOSIT_PACKAGES__",
        renderDepositPackagesHtml(pricing),
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
