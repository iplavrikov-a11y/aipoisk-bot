export type PublicTariff = {
  id: string;
  kind: "supplier_search" | "procurement_report" | string;
  label: string;
  name: string;
  units: number;
  price_kopeks: number;
  price_rub: number;
  description: string;
  sort_order: number;
};

export type PublicSitePayload = {
  site: {
    name: string;
    domain: string;
    headline: string;
    description: string;
  };
  contacts: {
    email: string;
    phone?: string;
    phone_url?: string;
    telegram: string;
    telegram_url: string;
    max: string;
    max_url: string;
    website: string;
    website_url: string;
  };
  bot: {
    telegram: string;
    telegram_url: string;
  };
  trial: {
    enabled: boolean;
    supplier_search_limit: number;
    procurement_report_limit: number;
    file_limit: number;
  };
  tariffs: PublicTariff[];
  tariff_groups: {
    supplier_search: PublicTariff[];
    procurement_report: PublicTariff[];
    supplier_search_extra: PublicTariff[];
  };
  updated_at: string | null;
};

const fallbackTariffs: PublicTariff[] = [
  {
    id: "supplier-1",
    kind: "supplier_search",
    label: "Поставщики",
    name: "1 запрос контактов поставщиков",
    units: 1,
    price_kopeks: 9900,
    price_rub: 99,
    description: "Разовый подбор релевантных компаний и direct email отделов продаж.",
    sort_order: 10,
  },
  {
    id: "supplier-5",
    kind: "supplier_search",
    label: "Поставщики",
    name: "5 запросов контактов поставщиков",
    units: 5,
    price_kopeks: 49000,
    price_rub: 490,
    description: "Мини-пакет для подбора поставщиков по ключевым позициям (98 ₽/поиск).",
    sort_order: 20,
  },
  {
    id: "supplier-10",
    kind: "supplier_search",
    label: "Поставщики",
    name: "10 запросов контактов поставщиков",
    units: 10,
    price_kopeks: 89000,
    price_rub: 890,
    description: "Оптимальный пакет для регулярных запросов КП и снабжения (89 ₽/поиск).",
    sort_order: 30,
  },
  {
    id: "supplier-25",
    kind: "supplier_search",
    label: "Поставщики",
    name: "25 запросов контактов поставщиков",
    units: 25,
    price_kopeks: 199000,
    price_rub: 1990,
    description: "Для активной работы со спецификациями и тендерами (79.6 ₽/поиск).",
    sort_order: 40,
  },
  {
    id: "supplier-50",
    kind: "supplier_search",
    label: "Поставщики",
    name: "50 запросов контактов поставщиков",
    units: 50,
    price_kopeks: 379000,
    price_rub: 3790,
    description: "Максимальный пакет для снабжения и тендерных отделов (75.8 ₽/поиск).",
    sort_order: 50,
  },
  {
    id: "report-1",
    kind: "procurement_report",
    label: "Анализ документации",
    name: "1 отчёт анализа документации",
    units: 1,
    price_kopeks: 9900,
    price_rub: 99,
    description: "Экспресс-аудит проекта контракта: проверка скрытых штрафов, сроков и нацрежима.",
    sort_order: 10,
  },
  {
    id: "report-5",
    kind: "procurement_report",
    label: "Анализ документации",
    name: "5 отчётов анализа документации",
    units: 5,
    price_kopeks: 49000,
    price_rub: 490,
    description: "Пакет для регулярной проверки условий закупки перед подачей (98 ₽/отчет).",
    sort_order: 20,
  },
  {
    id: "report-10",
    kind: "procurement_report",
    label: "Анализ документации",
    name: "10 отчётов анализа документации",
    units: 10,
    price_kopeks: 89000,
    price_rub: 890,
    description: "Оптимальный аудит рисков документации для специалистов (89 ₽/отчет).",
    sort_order: 30,
  },
  {
    id: "report-25",
    kind: "procurement_report",
    label: "Анализ документации",
    name: "25 отчётов анализа документации",
    units: 25,
    price_kopeks: 199000,
    price_rub: 1990,
    description: "Пакет проверок проектов контрактов с оценкой рисков и неустоек (79.6 ₽/отчет).",
    sort_order: 40,
  },
  {
    id: "report-50",
    kind: "procurement_report",
    label: "Анализ документации",
    name: "50 отчётов анализа документации",
    units: 50,
    price_kopeks: 379000,
    price_rub: 3790,
    description: "Корпоративный аудит закупочной документации на постоянной основе (75.8 ₽/отчет).",
    sort_order: 50,
  },
];

const fallbackData: PublicSitePayload = {
  site: {
    name: "TenderLex",
    domain: "https://tenderlex.ru",
    headline: "Поиск поставщиков под спецификацию на сайте и в Telegram",
    description:
      "TenderLex помогает подобрать компании для запроса цены, проверить контакты и разобрать закупочную документацию на сайте или в Telegram.",
  },
  contacts: {
    email: "support@tenderlex.ru",
    phone: "+7 (921) 146-00-80",
    phone_url: "tel:+79211460080",
    telegram: "Telegram",
    telegram_url: "https://t.me/tenderlex_bot",
    max: "",
    max_url: "",
    website: "tenderlex.ru",
    website_url: "https://tenderlex.ru",
  },
  bot: {
    telegram: "@tenderlex_bot",
    telegram_url: "https://t.me/tenderlex_bot",
  },
  trial: {
    enabled: true,
    supplier_search_limit: 1,
    procurement_report_limit: 1,
    file_limit: 10,
  },
  tariffs: fallbackTariffs,
  tariff_groups: {
    supplier_search: fallbackTariffs.filter((item) => item.kind === "supplier_search"),
    procurement_report: fallbackTariffs.filter((item) => item.kind === "procurement_report"),
    supplier_search_extra: fallbackTariffs.filter((item) => item.kind === "supplier_search_extra"),
  },
  updated_at: null,
};

function apiBaseUrl() {
  return (process.env.AIPOISK_SITE_API_BASE_URL || "http://127.0.0.1:8088").replace(/\/+$/, "");
}

export async function getSiteData(): Promise<PublicSitePayload> {
  try {
    const response = await fetch(`${apiBaseUrl()}/api/public/site`, {
      next: { revalidate: 300 },
      headers: {
        accept: "application/json",
      },
    });
    if (!response.ok) {
      return fallbackData;
    }
    return (await response.json()) as PublicSitePayload;
  } catch {
    return fallbackData;
  }
}

export function formatRubles(priceKopeks: number) {
  if (!priceKopeks) {
    return "по запросу";
  }
  return `${new Intl.NumberFormat("ru-RU").format(Math.round(priceKopeks / 100))} ₽`;
}

export function tariffDescription(tariff: PublicTariff) {
  if (tariff.description.trim()) {
    return tariff.description;
  }
  if (tariff.kind === "procurement_report") {
    return "Анализ закупочной документации: требования, условия, риски и вопросы заказчику.";
  }
  return "Подбор релевантных компаний и контактов для запроса цены под вашу закупочную задачу.";
}
