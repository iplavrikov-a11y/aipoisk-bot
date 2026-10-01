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
    max?: string;
    max_url?: string;
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
    exact_product?: PublicTariff[];
    procurement_report: PublicTariff[];
    supplier_search_extra: PublicTariff[];
  };
  updated_at: string | null;
};


const fallbackData: PublicSitePayload = {
  site: {
    name: "TenderLex",
    domain: "https://tenderlex.ru",
    headline: "Поиск поставщиков под спецификацию на сайте и в Telegram",
    description:
      "TenderLex помогает подобрать компании для запроса цены, проверить контакты и разобрать закупочную документацию на сайте или в Telegram.",
  },
  contacts: {
    email: "info@tenderlex.ru",
    telegram: "Telegram",
    telegram_url: "https://t.me/lexelence",
    website: "tenderlex.ru",
    website_url: "https://tenderlex.ru",
  },
  bot: {
    telegram: "@tenderlex_bot",
    telegram_url: "https://t.me/tenderlex_bot",
  },
  trial: {
    enabled: false,
    supplier_search_limit: 1,
    procurement_report_limit: 1,
    file_limit: 10,
  },
  tariffs: [],
  tariff_groups: {
    supplier_search: [],
    exact_product: [],
    procurement_report: [],
    supplier_search_extra: [],
  },
  updated_at: null,
};

function apiBaseUrl() {
  return (
    process.env.TENDERLEX_SITE_API_BASE_URL ||
    process.env.AIPOISK_SITE_API_BASE_URL ||
    "http://127.0.0.1:8088"
  ).replace(/\/+$/, "");
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
  if (tariff.kind === "exact_product") {
    return "Выявление скрытой модели по ТЗ, таблица с конкретными показателями, проверка реестра Минпромторга и подбор аналогов.";
  }
  if (tariff.kind === "procurement_report") {
    return "Анализ закупочной документации: требования, условия, риски и вопросы заказчику.";
  }
  return "Подбор релевантных компаний и контактов для запроса цены под вашу закупочную задачу.";
}
