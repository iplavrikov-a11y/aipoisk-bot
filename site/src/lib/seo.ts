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
  path?: string;
  item?: string;
};

type ServiceJsonLdOptions = {
  name: string;
  description: string;
  path: string;
  serviceType?: string;
};

type HowToJsonLdOptions = {
  name: string;
  description: string;
  steps?: (HowToStep | string)[];
  stepNames?: string[];
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

export function buildHowToJsonLd({ name, description, steps = [], stepNames = [] }: HowToJsonLdOptions) {
  const allSteps: HowToStep[] = steps.length > 0
    ? steps.map((s) => (typeof s === "string" ? { name: s, text: s } : s))
    : stepNames.map((s) => ({ name: s, text: s }));

  return {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name,
    description,
    step: allSteps.map((step) => ({
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
    itemListElement: items.map((item, index) => {
      const rawPath = item.path || item.item || "/";
      return {
        "@type": "ListItem",
        position: index + 1,
        name: item.name,
        item: absoluteUrl(rawPath),
      };
    }),
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
      telephone: "+7-921-146-00-80",
      contactType: "customer support",
      url: "https://t.me/tenderlex_bot",
      availableLanguage: ["Russian"],
    },
    telephone: "+7-921-146-00-80",
    sameAs: ["https://t.me/tenderlex_bot", "https://productradar.ru/product/tenderlex"],
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
    potentialAction: {
      "@type": "SearchAction",
      target: `${siteUrl}/poisk-postavshchikov-po-tz?q={search_term_string}`,
      "query-input": "required name=search_term_string",
    },
  };
}

export function buildServiceJsonLd({
  name,
  description,
  path,
  serviceType = "B2B Procurement Service",
}: ServiceJsonLdOptions) {
  const siteUrl = normalizedSiteUrl();
  return {
    "@context": "https://schema.org",
    "@type": "Service",
    "@id": `${siteUrl}${path}#service`,
    name,
    serviceType,
    description,
    provider: {
      "@type": "Organization",
      "@id": `${siteUrl}/#organization`,
      name: "TenderLex",
      url: siteUrl,
    },
    areaServed: {
      "@type": "Country",
      name: "Россия",
    },
    audience: {
      "@type": "Audience",
      audienceType: "Специалисты по закупкам, отделы снабжения, тендерные отделы",
    },
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "RUB",
      description: "Бесплатный пробный доступ при регистрации для тестирования поиска или анализа документации.",
      availability: "https://schema.org/InStock",
    },
  };
}

export function buildSoftwareApplicationJsonLd() {
  const siteUrl = normalizedSiteUrl();
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "TenderLex",
    operatingSystem: "Web, Telegram, iOS, Android, Windows, macOS, Linux",
    applicationCategory: "BusinessApplication",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "RUB",
      description: "Бесплатный пробный доступ при регистрации.",
    },
    aggregateRating: {
      "@type": "AggregateRating",
      ratingValue: "4.9",
      ratingCount: "148",
      bestRating: "5",
      worstRating: "1",
    },
    description:
      "TenderLex — веб-сервис и Telegram-бот для смыслового анализа технического задания, выявления рисков 44-ФЗ/223-ФЗ и поиска прямых контактов поставщиков.",
    url: siteUrl,
  };
}
