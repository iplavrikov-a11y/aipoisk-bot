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

export const commercialPageLastUpdated = "26 июня 2026";

export function normalizedSiteUrl() {
  return (process.env.NEXT_PUBLIC_SITE_URL || DEFAULT_SITE_URL).replace(/\/+$/, "");
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
