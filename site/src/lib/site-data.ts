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
    telegram: string;
    telegram_url: string;
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
    price_kopeks: 10000,
    price_rub: 100,
    description: "Разовый поиск email, телефонов, сайтов и комментариев по релевантности поставщиков.",
    sort_order: 100,
  },
  {
    id: "supplier-10",
    kind: "supplier_search",
    label: "Поставщики",
    name: "10 запросов контактов поставщиков",
    units: 10,
    price_kopeks: 100000,
    price_rub: 1000,
    description: "Пакет для регулярных запросов КП: поставщики, email, телефоны и страницы контактов.",
    sort_order: 100,
  },
  {
    id: "supplier-50",
    kind: "supplier_search",
    label: "Поставщики",
    name: "50 запросов контактов поставщиков",
    units: 50,
    price_kopeks: 500000,
    price_rub: 5000,
    description: "Для активного снабжения и тендерных команд с постоянным поиском рабочих контактов.",
    sort_order: 100,
  },
  {
    id: "report-1",
    kind: "procurement_report",
    label: "Анализ документации",
    name: "1 отчёт анализа документации",
    units: 1,
    price_kopeks: 10000,
    price_rub: 100,
    description: "Тендерный лист по закупочным документам: условия, позиции, риски, вопросы и рекомендации.",
    sort_order: 100,
  },
  {
    id: "report-10",
    kind: "procurement_report",
    label: "Анализ документации",
    name: "10 отчётов анализа документации",
    units: 10,
    price_kopeks: 100000,
    price_rub: 1000,
    description: "Пакет для регулярного анализа тендерной документации и подготовки рабочих материалов.",
    sort_order: 100,
  },
  {
    id: "report-50",
    kind: "procurement_report",
    label: "Анализ документации",
    name: "50 отчётов анализа документации",
    units: 50,
    price_kopeks: 500000,
    price_rub: 5000,
    description: "Для команд с постоянным потоком закупочных документов и повторяющимися проверками.",
    sort_order: 100,
  },
];

const fallbackData: PublicSitePayload = {
  site: {
    name: "TenderLex",
    domain: "https://tenderlex.ru",
    headline: "Анализ закупок и поиск поставщиков в одном Telegram-боте",
    description:
      "TenderLex помогает разобрать закупочную документацию, собрать поставщиков с контактами и попробовать оба сценария в Telegram.",
  },
  contacts: {
    email: "snab@dealpartner.ru",
    telegram: "@lexelence",
    telegram_url: "https://t.me/lexelence",
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
  },
  updated_at: null,
};

function apiBaseUrl() {
  return (process.env.AIPOISK_SITE_API_BASE_URL || "http://127.0.0.1:8088").replace(/\/+$/, "");
}

export async function getSiteData(): Promise<PublicSitePayload> {
  try {
    const response = await fetch(`${apiBaseUrl()}/api/public/site`, {
      cache: "no-store",
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
    return "AI-анализ закупочной документации с тендерным листом, рисками и ключевыми условиями.";
  }
  return "Поиск и проверка поставщиков, email, телефонов, сайтов, страниц контактов и соответствия закупочной задаче.";
}
