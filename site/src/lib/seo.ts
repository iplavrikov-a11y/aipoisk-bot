export type FaqItem = {
  question: string;
  answer: string;
};

export type HowToStep = {
  name: string;
  text: string;
};

export type BreadcrumbItem = {
  name: string;
  path: string;
};

type ServiceJsonLdOptions = {
  name: string;
  description: string;
  path: string;
  serviceType: string;
};

type HowToJsonLdOptions = {
  name: string;
  description: string;
  steps: HowToStep[];
};

const DEFAULT_SITE_URL = "https://tenderlex.ru";

export const commercialPageLastUpdated = "6 июля 2026";
export const commercialPageLastModified = "2026-07-06";
export const seoPageLastUpdated = "16 июля 2026";
export const seoPageLastModified = "2026-07-16";

export function normalizedSiteUrl() {
  return DEFAULT_SITE_URL;
}

export function absoluteUrl(path: string) {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  return `${normalizedSiteUrl()}${path.startsWith("/") ? path : `/${path}`}`;
}

export function buildFaqJsonLd(items: FaqItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };
}

export function buildHowToJsonLd({ name, description, steps }: HowToJsonLdOptions) {
  return {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name,
    description,
    step: steps.map((step) => ({
      "@type": "HowToStep",
      name: step.name,
      text: step.text,
    })),
  };
}

export function buildBreadcrumbJsonLd(items: BreadcrumbItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  };
}

export function buildOrganizationJsonLd() {
  const siteUrl = normalizedSiteUrl();
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${siteUrl}/#organization`,
    name: "TenderLex",
    alternateName: ["ТендерЛекс", "TenderLex B2B"],
    url: siteUrl,
    logo: {
      "@type": "ImageObject",
      url: `${siteUrl}/icon.png`,
      width: 120,
      height: 120,
    },
    description:
      "TenderLex — онлайн ИИ-сервис поиска поставщиков и анализа закупок под спецификации и технические задания по всей России.",
    areaServed: {
      "@type": "Country",
      name: "Россия",
    },
    contactPoint: {
      "@type": "ContactPoint",
      contactType: "customer support",
      url: "https://t.me/TenderLexBot",
      availableLanguage: ["Russian"],
    },
    sameAs: ["https://t.me/TenderLexBot", "https://productradar.ru/product/tenderlex"],
    knowsAbout: [
      "Поиск поставщиков по ТЗ",
      "Анализ 44-ФЗ и 223-ФЗ",
      "Реестр Минпромторга",
      "Подготовка запросов КП",
      "Оценка рисков закупок",
    ],
  };
}

export function buildWebSiteJsonLd() {
  const siteUrl = normalizedSiteUrl();
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${siteUrl}/#website`,
    url: siteUrl,
    name: "TenderLex",
    alternateName: "ТендерЛекс — ИИ-платформа поиска поставщиков и разбора ТЗ",
    publisher: {
      "@type": "Organization",
      "@id": `${siteUrl}/#organization`,
    },
    inLanguage: "ru-RU",
  };
}

export function buildSoftwareApplicationJsonLd() {
  const siteUrl = normalizedSiteUrl();
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "@id": `${siteUrl}/#software`,
    name: "TenderLex",
    operatingSystem: "Web, Telegram",
    applicationCategory: "BusinessApplication",
    description:
      "ИИ-сервис для отдела снабжения и тендерных специалистов: извлечение номенклатуры из ТЗ, сбор прямых контактов заводов и дилеров по всей России, автоматическая проверка реестров Минпромторга и экспресс-анализ 44-ФЗ / 223-ФЗ.",
    url: siteUrl,
    aggregateRating: {
      "@type": "AggregateRating",
      ratingValue: "4.9",
      ratingCount: "38",
      bestRating: "5",
      worstRating: "1",
    },
    offers: [
      {
        "@type": "Offer",
        name: "Приветственный бесплатный баланс при регистрации",
        price: "0",
        priceCurrency: "RUB",
        description: "Каждому новому пользователю начисляется 200 ₽ при регистрации для бесплатных первых проверок.",
        url: `${siteUrl}/cabinet`,
      },
      {
        "@type": "Offer",
        name: "1 поиск поставщиков по ТЗ",
        price: "100",
        priceCurrency: "RUB",
        description: "Извлечение спецификации из ТЗ и сбор прямых контактов заводов и дилеров.",
        url: `${siteUrl}/cabinet`,
      },
      {
        "@type": "Offer",
        name: "1 отчёт анализа закупочной документации",
        price: "100",
        priceCurrency: "RUB",
        description: "Экспресс-аудит 44-ФЗ / 223-ФЗ, выявление скрытых рисков, штрафов и ограничений.",
        url: `${siteUrl}/cabinet`,
      },
    ],
    author: {
      "@type": "Organization",
      "@id": `${siteUrl}/#organization`,
    },
  };
}

export function buildServiceJsonLd({ name, description, path, serviceType }: ServiceJsonLdOptions) {
  const siteUrl = normalizedSiteUrl();
  return {
    "@context": "https://schema.org",
    "@type": "Service",
    "@id": `${absoluteUrl(path)}#service`,
    name,
    description,
    serviceType,
    url: absoluteUrl(path),
    inLanguage: "ru-RU",
    areaServed: {
      "@type": "Country",
      name: "Россия",
    },
    provider: {
      "@type": "Organization",
      "@id": `${siteUrl}/#organization`,
      name: "TenderLex",
      url: siteUrl,
    },
    availableChannel: {
      "@type": "ServiceChannel",
      serviceUrl: absoluteUrl("/cabinet"),
      availableLanguage: ["ru"],
    },
  };
}
