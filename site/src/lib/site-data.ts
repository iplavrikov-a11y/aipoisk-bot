export type PublicTariff = {
  id: string;
  kind: "supplier_search" | "procurement_report" | "exact_product" | "supplier_search_extra" | "deposit" | string;
  label: string;
  name: string;
  units: number;
  price_kopeks: number;
  price_rub: number;
  bonus_kopeks?: number;
  bonus_rub?: number;
  credit_kopeks?: number;
  credit_rub?: number;
  total_kopeks?: number;
  total_rub?: number;
  badge?: string;
  description: string;
  sort_order: number;
};

export type FunctionPriceItem = {
  price_kopeks: number;
  price_rub: number;
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
  deposit_packages?: PublicTariff[];
  function_prices?: {
    supplier_search: FunctionPriceItem;
    exact_product: FunctionPriceItem;
    procurement_report: FunctionPriceItem;
    supplier_search_extra: FunctionPriceItem;
    analysis_and_suppliers: FunctionPriceItem;
  };
  tariff_groups: {
    deposit?: PublicTariff[];
    supplier_search: PublicTariff[];
    exact_product?: PublicTariff[];
    procurement_report: PublicTariff[];
    supplier_search_extra: PublicTariff[];
  };
  updated_at: string | null;
};


const defaultDepositPackages: PublicTariff[] = [
  {
    id: "dep-start",
    kind: "deposit",
    label: "Пополнение баланса",
    name: "Старт",
    units: 10,
    price_kopeks: 100000,
    price_rub: 1000,
    bonus_kopeks: 0,
    bonus_rub: 0,
    credit_kopeks: 100000,
    credit_rub: 1000,
    badge: "",
    description: "Для разовых тендеров и тестирования в бою",
    sort_order: 10,
  },
  {
    id: "dep-optimal",
    kind: "deposit",
    label: "Пополнение баланса",
    name: "Оптимальный",
    units: 35,
    price_kopeks: 300000,
    price_rub: 3000,
    bonus_kopeks: 50000,
    bonus_rub: 500,
    credit_kopeks: 350000,
    credit_rub: 3500,
    badge: "",
    description: "Для регулярной работы тендерного специалиста",
    sort_order: 20,
  },
  {
    id: "dep-pro",
    kind: "deposit",
    label: "Пополнение баланса",
    name: "Про",
    units: 65,
    price_kopeks: 500000,
    price_rub: 5000,
    bonus_kopeks: 150000,
    bonus_rub: 1500,
    credit_kopeks: 650000,
    credit_rub: 6500,
    badge: "Хит",
    description: "Для активного отдела закупок (несколько тендеров в неделю)",
    sort_order: 30,
  },
  {
    id: "dep-biz",
    kind: "deposit",
    label: "Пополнение баланса",
    name: "Бизнес",
    units: 140,
    price_kopeks: 1000000,
    price_rub: 10000,
    bonus_kopeks: 400000,
    bonus_rub: 4000,
    credit_kopeks: 1400000,
    credit_rub: 14000,
    badge: "",
    description: "Для дистрибьюторов, интеграторов и работы по API",
    sort_order: 40,
  },
  {
    id: "dep-corp",
    kind: "deposit",
    label: "Пополнение баланса",
    name: "Корпоративный",
    units: 375,
    price_kopeks: 2500000,
    price_rub: 25000,
    bonus_kopeks: 1250000,
    bonus_rub: 12500,
    credit_kopeks: 3750000,
    credit_rub: 37500,
    badge: "Максимум",
    description: "Для масштабных закупок и CRM-интеграций",
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
  tariffs: defaultDepositPackages,
  deposit_packages: defaultDepositPackages,
  function_prices: {
    supplier_search: { price_kopeks: 9900, price_rub: 99 },
    exact_product: { price_kopeks: 9900, price_rub: 99 },
    procurement_report: { price_kopeks: 9900, price_rub: 99 },
    supplier_search_extra: { price_kopeks: 4900, price_rub: 49 },
    analysis_and_suppliers: { price_kopeks: 19800, price_rub: 198 },
  },
  tariff_groups: {
    deposit: defaultDepositPackages,
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
