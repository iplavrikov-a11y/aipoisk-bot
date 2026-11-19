"use client";

import "./cabinet-redesign.css";

import Image from "next/image";
import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent, type MouseEvent } from "react";
import { TelegramLoginWidget } from "@/components/telegram-login-widget";
import {
  BatchResultsReaderModal,
  BatchSelectionModal,
  BatchSheetSelectorModal,
  type BatchRegistryPreviewData,
  type BatchRegistryPreviewItem,
  type BatchReportReaderData,
} from "@/components/custom-batch-report-modals";
import { ANALYTICS_CONSENT_KEY, trackGoal } from "@/lib/analytics";
import { pendingSeoEntry } from "@/lib/seo-funnel";
import {
  AlertTriangle,
  ArrowRight,
  Bell,
  BellOff,
  BellRing,
  BookOpen,
  Building2,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock3,
  Compass,
  Copy,
  CreditCard,
  Download,
  Eye,
  EyeOff,
  FileSpreadsheet,
  FileText,
  Gift,
  Globe,
  HelpCircle,
  History,
  Key,
  Layers,
  Loader2,
  LogOut,
  Mail,
  MapPin,
  MessageCircle,
  MessageSquare,
  Paperclip,
  Pencil,
  Phone,
  PlusCircle,
  Printer,
  QrCode,
  Receipt,
  RotateCcw,
  Search,
  Send,
  ShieldAlert,
  Sliders,
  Sparkles,
  Upload,
  User,
  Wallet,
  X,
  XCircle,
  Coins,
  type LucideIcon,
} from "lucide-react";

type JobMode = "supplier_search" | "procurement_report" | "analysis_and_suppliers" | "exact_product" | "price_monitoring";
type Scenario = "supplier_search" | "procurement_report" | "analysis_and_suppliers" | "exact_product" | "price_monitoring" | "custom_batch_report";
type SupplierSearchPolicy = "normal" | "minprom_registry_only" | "minprom_registry_priority";
type GeoScope = "ru" | "cis" | "world";

function normalizeSupplierSearchPolicy(val?: string | null): SupplierSearchPolicy {
  if (val === "minprom_registry_priority" || val === "minprom_registry_only") {
    return val;
  }
  return "normal";
}

function normalizeMultiItemMode(val?: string | null): "balanced" | "per_item" {
  return val === "per_item" ? "per_item" : "balanced";
}

function declensionCategory(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 19) return "категорий";
  if (mod10 === 1) return "категория";
  if (mod10 >= 2 && mod10 <= 4) return "категории";
  return "категорий";
}

function declensionTasks(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 19) return "задач";
  if (mod10 === 1) return "задача";
  if (mod10 >= 2 && mod10 <= 4) return "задачи";
  return "задач";
}

function declensionFiles(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 19) return "файлов";
  if (mod10 === 1) return "файл";
  if (mod10 >= 2 && mod10 <= 4) return "файла";
  return "файлов";
}

function formatPhoneRu(raw: string): string {
  const digits = raw.replace(/\D/g, "");
  if (!digits) return "";
  let norm = digits;
  if (digits[0] === "8" || digits[0] === "7") {
    norm = digits.slice(1);
  }
  let res = "+7";
  if (norm.length > 0) res += ` (${norm.slice(0, 3)}`;
  if (norm.length >= 3) res += `) ${norm.slice(3, 6)}`;
  if (norm.length >= 6) res += `-${norm.slice(6, 8)}`;
  if (norm.length >= 8) res += `-${norm.slice(8, 10)}`;
  return res;
}

type BalanceCounter = {
  label: string;
  available: number | null;
  reserved: number;
  spent: number;
  granted: number;
  low: boolean;
  unlimited?: boolean;
  price_kopeks?: number;
  price_rub?: number;
};

type Tariff = {
  id: string;
  kind: string;
  name: string;
  units: number;
  price_kopeks: number;
  description: string;
};

type DepositPackage = {
  id: string;
  kind?: string;
  name: string;
  price_kopeks: number;
  bonus_kopeks: number;
  total_kopeks: number;
  credit_kopeks?: number;
  price_rub: number;
  bonus_rub: number;
  total_rub: number;
  credit_rub?: number;
  bonus_percent?: number;
  badge?: string;
  description?: string;
  approx_tasks?: number;
};

const DEFAULT_DEPOSIT_PACKAGES: DepositPackage[] = [
  { id: "dep-1000", name: "Старт", price_kopeks: 100000, bonus_kopeks: 0, total_kopeks: 100000, price_rub: 1000, bonus_rub: 0, total_rub: 1000, bonus_percent: 0, badge: "", approx_tasks: 10 },
  { id: "dep-3000", name: "Оптимальный", price_kopeks: 300000, bonus_kopeks: 50000, total_kopeks: 350000, price_rub: 3000, bonus_rub: 500, total_rub: 3500, bonus_percent: 17, badge: "+500 ₽", approx_tasks: 35 },
  { id: "dep-5000", name: "Про", price_kopeks: 500000, bonus_kopeks: 150000, total_kopeks: 650000, price_rub: 5000, bonus_rub: 1500, total_rub: 6500, bonus_percent: 30, badge: "Хит (+1 500 ₽)", approx_tasks: 65 },
  { id: "dep-10000", name: "Бизнес", price_kopeks: 1000000, bonus_kopeks: 400000, total_kopeks: 1400000, price_rub: 10000, bonus_rub: 4000, total_rub: 14000, bonus_percent: 40, badge: "+4 000 ₽", approx_tasks: 140 },
  { id: "dep-25000", name: "Корпоративный", price_kopeks: 2500000, bonus_kopeks: 1250000, total_kopeks: 3750000, price_rub: 25000, bonus_rub: 12500, total_rub: 37500, bonus_percent: 50, badge: "+12 500 ₽", approx_tasks: 375 },
];

function calculateDepositBonus(amountRub: number): { bonusRub: number; totalRub: number; percent: number } {
  const safeRub = Math.max(0, Math.floor(amountRub || 0));
  if (safeRub < 1000) return { bonusRub: 0, totalRub: safeRub, percent: 0 };
  if (safeRub < 3000) return { bonusRub: 0, totalRub: safeRub, percent: 0 };
  if (safeRub < 5000) {
    const bonus = Math.round(safeRub * 0.1667);
    return { bonusRub: bonus, totalRub: safeRub + bonus, percent: 17 };
  }
  if (safeRub < 10000) {
    const bonus = Math.round(safeRub * 0.30);
    return { bonusRub: bonus, totalRub: safeRub + bonus, percent: 30 };
  }
  if (safeRub < 25000) {
    const bonus = Math.round(safeRub * 0.40);
    return { bonusRub: bonus, totalRub: safeRub + bonus, percent: 40 };
  }
  const bonus = Math.round(safeRub * 0.50);
  return { bonusRub: bonus, totalRub: safeRub + bonus, percent: 50 };
}

type SessionPayload = {
  authenticated: boolean;
  csrf_token?: string;
  user?: {
    email: string;
    name: string;
    phone?: string;
    telegram_username?: string;
    is_trial: boolean;
    is_email_verified: boolean;
    has_telegram?: boolean;
    allowed_price_monitoring?: boolean;
    allowed_geo_radius?: boolean;
    allowed_custom_batch_report?: boolean;
    custom_report_separate_tab?: boolean;
    batch_report_max_items?: number;
    geo_radius_surcharge_pct?: number;
  };
  balance?: {
    supplier_search: BalanceCounter;
    procurement_report: BalanceCounter;
    supplier_search_extra?: BalanceCounter;
    money?: {
      balance_kopeks: number;
      reserved_kopeks: number;
      available_kopeks: number;
      balance_rub: number;
      reserved_rub: number;
      available_rub: number;
    };
    has_custom_tariffs?: boolean;
    effective_prices?: Record<string, { label: string; price_kopeks: number; price_rub: number; enabled: boolean; source: string }>;
  };
  has_custom_tariffs?: boolean;
  limits?: {
    max_upload_mb: number;
    max_files_per_batch: number;
    default_supplier_target: number;
  };
  deposit_packages?: DepositPackage[];
  function_prices?: Record<string, { price_rub: number; price_kopeks: number }>;
  tariff_groups?: {
    deposit?: DepositPackage[];
    supplier_search: Tariff[];
    exact_product?: Tariff[];
    procurement_report: Tariff[];
    supplier_search_extra?: Tariff[];
  };
  contacts?: {
    email: string;
    telegram: string;
    telegram_url: string;
    max: string;
    max_url: string;
  };
  payment?: {
    provider: string;
    instructions: string;
    yookassa_ready: boolean;
  };
  referral?: {
    referral_code: string;
    invited_count: number;
    activated_count: number;
    bonus_earned_rub: number;
    balance_rub: number;
    invite_url_web: string;
    invite_url_bot: string;
  };
  verification_email_sent?: boolean;
  message?: string;
};

type PositionSelection = {
  revision: string;
  max_positions: number;
  price_kopeks: number;
  pricing_mode?: "fixed_task" | "per_found_position" | string;
  has_short_prompt?: boolean;
  groups?: Array<{
    id?: string;
    name?: string;
    label?: string;
    title?: string;
    item_ids?: string[];
  }>;
  items: Array<{
    id: string;
    position_no: number;
    name: string;
    requirements: unknown;
    unit?: string;
    quantity?: string;
    source_excerpt?: string;
    category?: string;
    is_short_prompt?: boolean;
  }>;
  selected_ids?: string[];
  confirmed?: boolean;
};

type CustomerInvoice = {
  id: string;
  invoice_number: string;
  amount_rub: number;
  bonus_rub: number;
  total_credit_rub: number;
  status: string;
  created_at?: string;
  paid_at?: string | null;
  proof_submitted_at?: string | null;
  buyer_email?: string;
  buyer_name?: string;
  buyer_inn?: string;
};

type CustomerJob = {
  id: string;
  job_number?: number | null;
  client_id?: string;
  mode: JobMode;
  mode_label: string;
  supplier_search_policy?: string;
  multi_item_mode?: string;
  delivery_city?: string;
  geo_radius_km?: number | null;
  geo_scope?: GeoScope;
  status: string;
  status_label: string;
  progress: number;
  message: string;
  human_title: string;
  target_suppliers: number;
  verified_count: number;
  file_count: number;
  has_result: boolean;
  can_download: boolean;
  can_cancel: boolean;
  can_find_more_suppliers: boolean;
  can_start_supplier_search?: boolean;
  is_custom_batch_report?: boolean;
  exact_product_selection?: PositionSelection | null;
  position_selection?: PositionSelection | null;
  exact_product_positions?: Array<{
    id?: string;
    position_no?: number;
    name: string;
    status?: string;
    model?: string;
    manufacturer?: string;
    alternatives?: string[];
    error?: string;
    source_url?: string;
    can_retry_position?: boolean;
  }>;
  exact_product_summary?: {
    primary_product?: string;
    brand?: string;
    model?: string;
    manufacturer?: string;
    name_in_tz?: string;
    alternatives?: string[];
    total_positions?: number;
  } | null;
  result_files: Array<{
    kind: string;
    label: string;
    filename: string;
    is_admin_supplement?: boolean;
  }>;
  has_admin_supplement?: boolean;
  admin_comment?: string;
  admin_supplement_name?: string;
  admin_supplement_at?: string | null;
  chat_messages?: Array<{
    id: string;
    job_id: string;
    client_id: string;
    sender_role: "admin" | "client";
    message: string;
    attachments: Array<{
      index: number;
      name: string;
      label: string;
      size: number;
      url: string;
      customer_url: string;
    }>;
    is_read_by_client: boolean;
    is_read_by_admin: boolean;
    created_at: string | null;
  }>;
  unread_admin_messages_count?: number;
  awaiting_customer_confirmation: boolean;
  confirmation_kind?: string;
  multi_item_details?: {
    items?: Array<{
      id?: string;
      name: string;
      quantity?: string;
      unit?: string;
      is_core?: boolean;
      is_auxiliary?: boolean;
      included_sub_items?: string[];
      cost_tier?: string;
    }>;
    total_items?: number;
  } | null;
  error: string;
  created_at: string | null;
  completed_at?: string | null;
  updated_at: string | null;
};

type QuoteRequestModal = {
  job: CustomerJob;
  html: string;
  filename: string;
  copied: boolean;
  rawMarkdown?: string;
  items?: Array<{ index: number; name: string }>;
  selectedItemIndexes: number[];
};

type ActiveToast = {
  id: string;
  jobId: string;
  title: string;
  modeLabel?: string;
};

type CustomerJobsResponse = {
  items: CustomerJob[];
  total: number;
  limit: number;
  offset: number;
};

type CustomerBillingTransaction = {
  id: string;
  job_id: string | null;
  operation: string;
  operation_label: string;
  kind: string;
  kind_label: string;
  title: string;
  note: string;
  units: number;
  amount_kopeks: number;
  amount_rub: number;
  created_at: string | null;
};

const DEFAULT_CUSTOMER_JOBS_PAGE_SIZE = 15;
const CUSTOMER_JOB_FETCH_OPTIONS: RequestInit = {
  credentials: "same-origin",
  cache: "no-store",
};
const NOTIFICATION_FEATURE_START_TS = new Date("2026-08-21T13:30:00Z").getTime();

const scenarioOptions: Array<{
  id: Scenario;
  label: string;
  description: string;
  inputBadge: string;
  icon: LucideIcon;
}> = [
  {
    id: "procurement_report",
    label: "Анализ документации",
    description: "Условия контракта, риски и вопросы заказчику",
    inputBadge: "Номер ЕИС или файлы закупки",
    icon: FileText,
  },
  {
    id: "supplier_search",
    label: "Поиск поставщиков",
    description: "Производители, дилеры, контакты и запрос КП",
    inputBadge: "ТЗ файлом или текстом",
    icon: Search,
  },
  {
    id: "analysis_and_suppliers",
    label: "Анализ + поиск",
    description: "Разбор закупки и сразу подбор поставщиков",
    inputBadge: "Номер ЕИС или документы",
    icon: Receipt,
  },
  {
    id: "exact_product",
    label: "Подбор товара и аналогов",
    description: "Модель по ТЗ, таблица параметров и аналоги (.docx)",
    inputBadge: "ТЗ файлом или текстом",
    icon: CheckCircle2,
  },
];

const modeCopy: Record<Scenario, {
  mode: JobMode;
  title: string;
  formSubtitle: string;
  uploadTitle: string;
  uploadText: string;
  multipleFiles: boolean;
  textLabel?: string;
  textPlaceholder?: string;
  sourceLabel?: string;
  sourcePlaceholder?: string;
  hint: string;
  submit: string;
}> = {
  exact_product: {
    mode: "exact_product",
    title: "Подбор товара и аналогов",
    formSubtitle: "Определение точной модели по характеристикам ТЗ, проверка реестра Минпромторга и таблица сравнения аналогов (.docx).",
    uploadTitle: "Прикрепить файл ТЗ или спецификацию",
    uploadText: "Перетащите файлы или фото/скриншот ТЗ сюда (PDF, DOCX, XLSX, PNG, JPG, TXT, ZIP)",
    multipleFiles: true,
    textLabel: "Характеристики объекта закупки текстом",
    textPlaceholder: "Вставьте наименование и параметры из ТЗ: мощность, размеры, материал, ГОСТ и другие требования...",
    hint: "Результат формируется в формате Word (.docx) со сводной таблицей параметров, источников и аналогов.",
    submit: "Запустить подбор",
  },
  supplier_search: {
    mode: "supplier_search",
    title: "Поиск поставщиков",
    formSubtitle: "Подбор производителей и поставщиков под вашу спецификацию с проверенными контактами отделов продаж и проектом запроса КП.",
    uploadTitle: "Прикрепить техническое задание или смету",
    uploadText: "Перетащите файлы ТЗ или фото/скриншот сюда (PDF, DOCX, XLSX, PNG, JPG, ZIP, RAR)",
    multipleFiles: true,
    textLabel: "Список позиций или текст технического задания",
    textPlaceholder: "Например: кабель силовой ВВГнг(А)-LS 3×2,5 ГОСТ 31996-2012 — 1 500 м, доставка в Казань...",
    hint: "Можно прикрепить сразу несколько файлов закупки, архив или фото/скриншот ТЗ — система объединит их в единый расчёт.",
    submit: "Запустить поиск поставщиков",
  },
  procurement_report: {
    mode: "procurement_report",
    title: "Анализ документации",
    formSubtitle: "Разбор извещения, проекта контракта и требований закупки: сроки, оплата, обеспечение, нацрежим, риски и вопросы заказчику.",
    uploadTitle: "Или прикрепите файлы закупки, фото/скриншот или таблицу закупок",
    uploadText: "ТЗ, контракт, фото/скриншот или список до 10 закупок (PDF, DOCX, XLSX, PNG, JPG, ZIP)",
    multipleFiles: true,
    sourceLabel: "Номера извещений ЕИС (1 или до 10 шт. в столбик / через запятую) или ссылки на закупки",
    sourcePlaceholder: "Например: 0173200001424000001 (или сразу несколько номеров / ссылок в столбик)...",
    hint: "Можно указать одну закупку (запустится сразу) или сразу список до 10 закупок — перед запуском вы выберете нужные.",
    submit: "Запустить анализ документации",
  },
  analysis_and_suppliers: {
    mode: "analysis_and_suppliers",
    title: "Анализ + поиск поставщиков",
    formSubtitle: "Комплексный разбор рисков закупочной документации и одновременный подбор поставщиков под предмет контракта.",
    uploadTitle: "Или прикрепите комплект документов закупки",
    uploadText: "Документация закупки, техническое задание, фото/скриншот или архив (PDF, DOCX, XLSX, PNG, JPG, ZIP)",
    multipleFiles: true,
    sourceLabel: "Номер извещения ЕИС (11 или 19 цифр) или прямая ссылка на zakupki.gov.ru",
    sourcePlaceholder: "Например: 0173200001424000001 или https://zakupki.gov.ru/...",
    hint: "На выходе вы получите и аналитический разбор условий закупки, и реестр подходящих поставщиков.",
    submit: "Запустить анализ + поиск",
  },
  price_monitoring: {
    mode: "price_monitoring",
    title: "Мониторинг цен по спецификации",
    formSubtitle: "Поиск актуальных рыночных цен, ИНН и ссылок на поставщиков по каждой позиции вашей спецификации.",
    uploadTitle: "Прикрепить спецификацию или ведомость",
    uploadText: "Таблицы, документы и фото/скриншоты со списком позиций (XLSX, DOCX, PDF, PNG, JPG, TXT, ZIP — до 1 000 строк)",
    multipleFiles: true,
    textLabel: "Или вставьте перечень позиций построчно",
    textPlaceholder: "1. Кислород газообразный технический, м3\n2. Подшипник 13630, шт.\n3. Клапан обратный 19с53нж Ду100, шт.",
    hint: "Можно загрузить Excel, Word или фото таблицы до 1 000 строк — перед запуском вы выберете нужные позиции.",
    submit: "Запустить мониторинг цен",
  },
  custom_batch_report: {
    mode: "procurement_report",
    title: "Экспресс-оценка закупок",
    formSubtitle: "Быстрый коммерческий просчёт от 1 закупки или выгрузки: подходящий товар со ссылкой, заводы-поставщики, логистика и маржа.",
    uploadTitle: "Или загрузите таблицу / скриншот с перечнем закупок (или файл ТЗ)",
    uploadText: "Выгрузка реестра закупок, фото/скриншот таблицы или документация (XLSX, CSV, DOCX, PDF, PNG, JPG, ZIP)",
    multipleFiles: true,
    sourceLabel: "Номера извещений (от 1 шт., в столбик или через запятую) либо ссылки на закупки",
    sourcePlaceholder: "Вставьте 1 или несколько номеров извещений (в столбик из Excel или через запятую)...",
    hint: "Работает для 1 закупки, списка номеров, Excel, Word, PDF или скриншота таблицы (с выбором строк перед запуском).",
    submit: "Запустить экспресс-оценку",
  },
};




const supplierPolicyOptions: Array<{ id: SupplierSearchPolicy; label: string; description: string }> = [
  {
    id: "normal",
    label: "Обычный поиск",
    description: "без обязательного фильтра по реестру",
  },
  {
    id: "minprom_registry_only",
    label: "Только реестр (Минпромторг)",
    description: "для закупок с запретом",
  },
  {
    id: "minprom_registry_priority",
    label: "Реестр в приоритете (Минпромторг)",
    description: "для закупок с ограничением",
  },
];

const geoScopeOptions: Array<{ id: GeoScope; label: string; description: string }> = [
  {
    id: "ru",
    label: "Только Россия",
    description: "поставщики и дистрибьюторы с ИНН РФ (для 44-ФЗ и нацрежима)",
  },
  {
    id: "cis",
    label: "РФ и СНГ (ЕАЭС)",
    description: "Россия, Беларусь, Казахстан, Армения, Кыргызстан",
  },
  {
    id: "world",
    label: "Весь мир",
    description: "прямые фабрики и производители мира без посредников",
  },
];


const statusClasses: Record<string, string> = {
  pending: "pending",
  running: "running",
  completed: "completed",
  partial: "completed",
  needs_review: "review",
  awaiting_customer_confirmation: "review",
  awaiting_exact_selection: "review",
  awaiting_position_selection: "review",
  failed: "failed",
  customer_declined: "failed",
  cancelled: "failed",
};

const MOSCOW_TIME_ZONE = "Europe/Moscow";

function apiDateValue(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return trimmed;
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return `${trimmed}T00:00:00Z`;
  }
  if (/(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed)) {
    return trimmed;
  }
  return `${trimmed}Z`;
}


function formatJobDuration(
  job: { created_at?: string | null; completed_at?: string | null; updated_at?: string | null; status?: string },
  nowTs: number
): string | null {
  if (!job.created_at) return null;
  const startTime = new Date(apiDateValue(job.created_at)).getTime();
  if (Number.isNaN(startTime)) return null;

  const isRunning = job.status === "pending" || job.status === "running" || job.status === "queued" || job.status === "in_progress";

  let totalSeconds = 0;
  if (!isRunning) {
    const endStr = job.completed_at || job.updated_at;
    if (!endStr) return null;
    const endTime = new Date(apiDateValue(endStr)).getTime();
    if (Number.isNaN(endTime) || endTime < startTime) return null;
    totalSeconds = Math.floor((endTime - startTime) / 1000);
  } else {
    totalSeconds = Math.max(0, Math.floor((nowTs - startTime) / 1000));
  }

  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  if (isRunning) {
    const mm = String(minutes).padStart(2, "0");
    const ss = String(seconds).padStart(2, "0");
    return `${mm}:${ss}`;
  }

  if (minutes === 0) {
    return `${seconds} сек`;
  }
  if (minutes < 60) {
    return `${minutes} мин ${seconds} сек`;
  }
  const hours = Math.floor(minutes / 60);
  const remMin = minutes % 60;
  return `${hours} ч ${remMin} мин`;
}

function formatDate(value: string | null) {
  if (!value) return "-";
  const date = new Date(apiDateValue(value));
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  return date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short", timeZone: MOSCOW_TIME_ZONE });
}

function formatArtifactLabel(label?: string | null): string {
  if (!label) return "Скачать";
  let clean = label.replace(/\s*\(\.(?:xlsx|docx|pdf)\)/gi, "").trim();
  const lower = clean.toLowerCase();
  if (lower === "отчет по ценам поставщиков" || lower === "отчет по ценам" || lower === "отчет по ценам поставщиков (.xlsx)") {
    clean = "Цены поставщиков";
  }
  return clean;
}

function formatRubles(kopeks: number) {
  if (!kopeks) return "по запросу";
  return `${new Intl.NumberFormat("ru-RU").format(Math.round(kopeks / 100))} ₽`;
}

function formatBalanceRubles(kopeks: number) {
  return `${new Intl.NumberFormat("ru-RU").format(Math.round((kopeks || 0) / 100))} ₽`;
}

function selectionRequirementsText(requirements: unknown): string {
  if (typeof requirements === "string") return requirements.trim();
  if (typeof requirements === "number" || typeof requirements === "boolean") return String(requirements);
  if (Array.isArray(requirements)) {
    return requirements.map((item) => selectionRequirementsText(item)).filter(Boolean).join(" · ");
  }
  if (!requirements || typeof requirements !== "object") return "";

  const record = requirements as Record<string, unknown>;
  const label = selectionRequirementsText(record.param_name ?? record.label ?? record.name ?? record.parameter);
  const value = selectionRequirementsText(record.tz_requirement ?? record.requirement ?? record.value ?? record.description);
  if (label && value) return `${label}: ${value}`;
  if (value) return value;
  if (label) return label;

  return Object.values(record)
    .map((item) => selectionRequirementsText(item))
    .filter(Boolean)
    .join(" · ");
}

function positionSelectionForJob(job: CustomerJob): PositionSelection | null | undefined {
  return job.mode === "price_monitoring" ? job.position_selection : job.exact_product_selection;
}

function isAwaitingPositionSelection(job: CustomerJob): boolean {
  const isExact = job.status === "awaiting_exact_selection";
  const isMonitoring = job.mode === "price_monitoring" && job.status === "awaiting_position_selection";
  return (isExact || isMonitoring) && Boolean(positionSelectionForJob(job)) && !positionSelectionForJob(job)?.confirmed;
}

function supplierStrategyRowCount(job: CustomerJob): number {
  const categories = job.multi_item_details?.items || [];
  const declaredRows = job.multi_item_details?.total_items;
  const includedRows = categories.reduce((total, item) => total + Math.max(1, item.included_sub_items?.length || 0), 0);
  // Older responses call the category count total_items; never let it hide source rows.
  return Math.max(declaredRows || 0, includedRows);
}

function balanceValue(counter?: BalanceCounter) {
  if (!counter) return "0";
  return counter.available === null ? "без лимита" : String(counter.available);
}

function accessValue(counter?: BalanceCounter) {
  return balanceValue(counter);
}

function priceOrAccessValue(counter?: BalanceCounter) {
  if (counter?.price_kopeks) return formatRubles(counter.price_kopeks);
  return accessValue(counter);
}

function extraSupplierPriceOrAccessValue(balance?: SessionPayload["balance"]) {
  if (balance?.effective_prices?.supplier_search_extra?.price_kopeks) {
    return formatRubles(balance.effective_prices.supplier_search_extra.price_kopeks);
  }
  if (balance?.supplier_search_extra?.price_kopeks) {
    return formatRubles(balance.supplier_search_extra.price_kopeks);
  }
  if (balance?.supplier_search?.price_kopeks) {
    const p = balance.supplier_search.price_kopeks;
    return formatRubles(p === 9900 ? 4900 : Math.round(p * 0.5));
  }
  return accessValue(balance?.supplier_search_extra);
}

function tariffDisplayName(tariff: Tariff) {
  if (tariff.kind === "procurement_report") {
    return `${tariff.units} ${pluralizeRu(tariff.units, ["анализ закупки", "анализа закупки", "анализов закупки"])}`;
  }
  if (tariff.kind === "supplier_search") {
    return `${tariff.units} ${pluralizeRu(tariff.units, ["поиск поставщиков", "поиска поставщиков", "поисков поставщиков"])}`;
  }
  return tariff.name;
}

function modeDisplayName(job: CustomerJob) {
  if (job.is_custom_batch_report) return "Экспресс-оценка";
  const policy = (job as unknown as { supplier_search_policy?: string }).supplier_search_policy;
  const policyLabel =
    policy === "registry_only" || policy === "minprom_registry_only"
      ? "Только реестр"
      : policy === "registry_priority" || policy === "minprom_registry_priority"
      ? "Реестр в приоритете"
      : "Обычный";

  if (job.mode === "exact_product") return "Подбор товара и аналогов";
  if (job.mode === "price_monitoring") return "Мониторинг цен";
  if (job.mode === "procurement_report") return "Анализ документации";
  if (job.mode === "analysis_and_suppliers") return `Анализ + поиск (${policyLabel})`;
  return `Поиск поставщиков (${policyLabel})`;
}

function pluralizeRu(value: number, [one, few, many]: [string, string, string]) {
  const mod10 = Math.abs(value) % 10;
  const mod100 = Math.abs(value) % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

function formatCleanJobTitle(job: CustomerJob): string {
  let title = String(job.human_title || "").trim();
  if (!title) return modeDisplayName(job);

  // Clean truncated batch titles: "Экспресс-оценка (10 зак.): Выгрузка" / legacy "Пакетный анализ 3 зак"
  const batchWithTail = title.match(/^(?:Экспресс-оценка|Пакетный анализ)\s*\(?(\d+)\s*зак\.?\)?\s*[:—-]\s*(.+)$/i);
  if (batchWithTail) {
    const n = Number(batchWithTail[1]);
    const word = pluralizeRu(n, ["закупка", "закупки", "закупок"]);
    return `Экспресс-оценка · ${n} ${word}: ${batchWithTail[2].trim()}`;
  }
  const batchOnly = title.match(/^(?:Экспресс-оценка|Пакетный анализ)\s*\(?(\d+)\s*зак\.?\)?$/i);
  if (batchOnly) {
    const n = Number(batchOnly[1]);
    const word = pluralizeRu(n, ["закупка", "закупки", "закупок"]);
    return `Экспресс-оценка · ${n} ${word}`;
  }

  // Deduplicate stacked prefixes like "Анализ закупки: Анализ - Анализ закупки Поставка..."
  const leadPrefix = /^(Анализ закупки|Поиск поставщиков|Подбор товара и аналогов|Мониторинг цен|Анализ \+ поиск)\s*[:—-]\s*/i;
  const firstMatch = title.match(leadPrefix);
  if (firstMatch) {
    const canonical = firstMatch[1];
    let rest = title.slice(firstMatch[0].length).trim();
    const redundant = /^(?:Анализ закупки|Анализ|Закупка|Поиск поставщиков|Подбор товара и аналогов|Подбор товара)\s*(?:[:—-]\s*|\s+(?=[А-ЯЁA-Z0-9«"]))+/i;
    let guard = 0;
    while (guard < 4 && redundant.test(rest)) {
      const next = rest.replace(redundant, "").trim();
      if (!next || next === rest) break;
      rest = next;
      guard++;
    }
    if (rest) {
      title = `${canonical}: ${rest}`;
    }
  }
  return title;
}

function formatCleanJobMessage(message?: string | null): string {
  const raw = String(message || "").trim();
  if (!raw) return "";
  return raw.replace(/(\d+)\s*зак\.?(?=$|[\s.,;)])/gi, (_m, nStr: string) => {
    const n = Number(nStr);
    return `${n} ${pluralizeRu(n, ["закупка", "закупки", "закупок"])}`;
  });
}

function formatStatusLabel(label?: string | null): string {
  const raw = String(label || "").trim();
  if (!raw) return "";
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

function parseError(raw: string, options?: { isUpload?: boolean }) {
  const str = String(raw || "").trim();
  if (str.includes("502 Bad Gateway")) {
    return "Сервер временно обновляется или перезагружается (502 Bad Gateway). Пожалуйста, подождите пару секунд и повторите.";
  }
  if (str.includes("504 Gateway Time-out") || str.includes("504 Gateway Timeout")) {
    return options?.isUpload
      ? "Время ожидания ответа сервера истекло (504 Gateway Timeout). Попробуйте разбить файл на части или повторите попытку."
      : "Сервер не успел ответить вовремя (504 Gateway Timeout). Пожалуйста, повторите попытку через пару секунд.";
  }
  if (str.includes("500 Internal Server Error")) {
    return "Внутренняя ошибка сервера (500). Пожалуйста, повторите попытку позже.";
  }
  try {
    const parsed = JSON.parse(str);
    if (typeof parsed?.detail === "string") return parsed.detail;
  } catch {
    if (/<html|<!DOCTYPE|<head|<body/i.test(str)) {
      return "Ошибка связи с сервером. Пожалуйста, повторите попытку через несколько секунд.";
    }
    return str || "Ошибка запроса";
  }
  return str || "Ошибка запроса";
}

function filenameFromResponse(response: Response, fallback: string) {
  const header = response.headers.get("content-disposition") || "";
  const utf = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf?.[1]) return decodeURIComponent(utf[1]);
  const plain = header.match(/filename="?([^";]+)"?/i);
  return plain?.[1] || fallback;
}

async function readJson<T>(response: Response, options?: { isUpload?: boolean }): Promise<T> {
  const text = await response.text();
  if (!response.ok) throw new Error(parseError(text, options));
  return text ? (JSON.parse(text) as T) : ({} as T);
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatInlineMarkdown(value: string) {
  return escapeHtml(value)
    .replace(/&lt;br\s*\/?&gt;/gi, "<br />")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/__(.*?)__/g, "<strong>$1</strong>");
}

function extractQuoteTableItems(markdown: string): Array<{ index: number; name: string }> {
  const lines = String(markdown || "").split(/\r?\n/);
  const tableRows: string[][] = [];
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith("|")) {
      let combined = trimmed;
      while (!combined.endsWith("|") && i + 1 < lines.length && lines[i + 1].trim()) {
        i++;
        combined += " <br> " + lines[i].trim();
      }
      const compact = combined.replace(/\|/g, "").replace(/:/g, "").replace(/-/g, "").trim();
      if (!compact) continue;
      tableRows.push(combined.slice(1, -1).split("|").map((cell) => cell.trim()));
    }
  }
  if (tableRows.length < 2) return [];
  const [header, ...body] = normalizeQuoteTableRows(tableRows);
  const nameIdx = quoteColumnIndex(header, ["наименование", "товар", "позиция", "предмет"]);
  if (nameIdx < 0) return [];
  return body.map((row, i) => ({
    index: i,
    name: quoteCell(row, nameIdx) || `Позиция ${i + 1}`,
  })).filter((item) => Boolean(item.name));
}

function quoteMarkdownToHtml(markdown: string, selectedRowIndexes?: number[] | null) {
  const value = String(markdown || "").trim();
  if (!value) return "<p></p>";
  const lines = value.split(/\r?\n/);
  const html: string[] = [];
  let tableRows: string[][] = [];
  let listItems: string[] = [];

  const flushList = () => {
    if (!listItems.length) return;
    html.push(`<ul>${listItems.map((item) => `<li>${formatInlineMarkdown(item)}</li>`).join("")}</ul>`);
    listItems = [];
  };

  const flushTable = () => {
    if (!tableRows.length) return;
    const [header, ...body] = normalizeQuoteTableRows(tableRows);
    let filteredBody = body;
    if (Array.isArray(selectedRowIndexes) && selectedRowIndexes.length > 0) {
      const allowed = new Set(selectedRowIndexes);
      filteredBody = body
        .filter((_, idx) => allowed.has(idx))
        .map((row, newIdx) => row.map((cell, cellIdx) => (cellIdx === 0 ? String(newIdx + 1) : cell)));
    }
    html.push(
      `<div style="overflow-x:auto;margin:14px 0;"><table style="width:100%;border-collapse:collapse;font-size:12px;font-family:system-ui,-apple-system,sans-serif;border:1px solid #CBD5E1;background-color:#FFFFFF;">` +
      `<thead style="background-color:#F1F5F9;"><tr style="border-bottom:2px solid #CBD5E1;">` +
      header.map((cell) => `<th style="padding:9px 12px;text-align:left;font-weight:700;color:#0F172A;border:1px solid #CBD5E1;">${formatInlineMarkdown(cell)}</th>`).join("") +
      `</tr></thead><tbody>` +
      filteredBody.map((row) => `<tr style="border-bottom:1px solid #E2E8F0;">` + row.map((cell) => `<td style="padding:9px 12px;color:#334155;border:1px solid #E2E8F0;vertical-align:top;">${formatInlineMarkdown(cell)}</td>`).join("") + `</tr>`).join("") +
      `</tbody></table></div>`
    );
    tableRows = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith("|")) {
      flushList();
      let combined = trimmed;
      while (!combined.endsWith("|") && i + 1 < lines.length && lines[i + 1].trim()) {
        i++;
        combined += " <br> " + lines[i].trim();
      }
      const compact = combined.replace(/\|/g, "").replace(/:/g, "").replace(/-/g, "").trim();
      if (!compact) continue;
      tableRows.push(combined.slice(1, -1).split("|").map((cell) => cell.trim()));
      continue;
    }
    flushTable();
    if (!trimmed) continue;
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      listItems.push(trimmed.slice(2));
      continue;
    }
    flushList();
    if (trimmed.startsWith("### ")) {
      html.push(`<h3>${formatInlineMarkdown(trimmed.slice(4))}</h3>`);
    } else if (trimmed.startsWith("## ")) {
      html.push(`<h2>${formatInlineMarkdown(trimmed.slice(3))}</h2>`);
    } else if (trimmed.startsWith("# ")) {
      html.push(`<h2>${formatInlineMarkdown(trimmed.slice(2))}</h2>`);
    } else if (trimmed.toUpperCase() === "ЗАПРОС КП" || trimmed.toUpperCase() === "ЗАПРОС КОММЕРЧЕСКОГО ПРЕДЛОЖЕНИЯ") {
      html.push(`<h2>${formatInlineMarkdown("Запрос коммерческого предложения")}</h2>`);
    } else {
      html.push(`<p>${formatInlineMarkdown(trimmed)}</p>`);
    }
  }
  flushTable();
  flushList();
  return html.join("");
}

function cellsText(row: HTMLTableRowElement) {
  return Array.from(row.querySelectorAll("th,td")).map((cell) => {
    const clone = cell.cloneNode(true) as HTMLElement;
    clone.querySelectorAll("br").forEach((br) => br.replaceWith("\n"));
    return (clone.textContent || "").replace(/[ \t]+/g, " ").trim();
  });
}

function cellsForMarkdownTable(row: HTMLTableRowElement) {
  return Array.from(row.querySelectorAll("th,td")).map((cell) => {
    const clone = cell.cloneNode(true) as HTMLElement;
    clone.querySelectorAll("br").forEach((br) => br.replaceWith(" <br> "));
    clone.querySelectorAll("p, div, li").forEach((el) => {
      if (el !== clone.firstElementChild) {
        el.before(" <br> ");
      }
    });
    const raw = clone.textContent || "";
    return raw
      .replace(/[\r\n]+/g, " <br> ")
      .replace(/[ \t]+/g, " ")
      .replace(/\|/g, "/")
      .replace(/(?:\s*<br>\s*)+/gi, "<br>")
      .trim();
  });
}

function quotePlainText(value: string | null | undefined) {
  return String(value || "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
}

function quoteHeaderKey(value: string) {
  return quotePlainText(value).toLowerCase().replace("ед. изм.", "ед.изм.").replace("ед изм", "ед.изм.");
}

function quoteColumnIndex(header: string[], aliases: string[]) {
  return header.findIndex((cell) => aliases.some((alias) => quoteHeaderKey(cell).includes(alias)));
}

function normalizeQuoteTableRows(rows: string[][]) {
  if (!rows.length) return rows;
  const header = rows[0];
  const dropIndexes = new Set<number>();
  header.forEach((cell, index) => {
    const key = quoteHeaderKey(cell);
    if (key.includes("примечан") || key.includes("комментар")) {
      dropIndexes.add(index);
    }
  });
  if (!dropIndexes.size) return rows;
  return rows.map((row) => row.filter((_, index) => !dropIndexes.has(index)));
}

function quoteCell(row: string[], index: number) {
  return index >= 0 && index < row.length ? quotePlainText(row[index]) : "";
}

function quoteTableToReadableText(table: Element) {
  const rows = normalizeQuoteTableRows(
    Array.from(table.querySelectorAll("tr"))
      .map((row) => cellsText(row as HTMLTableRowElement))
      .filter((row) => row.some(Boolean)),
  );
  if (!rows.length) return "";
  const [header, ...body] = rows;
  const indexes = {
    num: quoteColumnIndex(header, ["№", "номер", "n"]),
    name: quoteColumnIndex(header, ["наименование", "товар", "позиция", "предмет"]),
    characteristics: quoteColumnIndex(header, ["характерист", "описание", "требован"]),
    unit: quoteColumnIndex(header, ["ед.изм.", "единица"]),
    quantity: quoteColumnIndex(header, ["кол-во", "количество", "объем"]),
  };
  if (indexes.name < 0) {
    return body.map((row) => row.map(quotePlainText).filter(Boolean).join("; ")).filter(Boolean).join("\n\n");
  }
  return body
    .map((row, rowIndex) => {
      const number = quoteCell(row, indexes.num) || `${rowIndex + 1}`;
      const name = quoteCell(row, indexes.name);
      if (!name) return "";
      const lines = [`${number}. ${name}`];
      const characteristics = quoteCell(row, indexes.characteristics);
      const unit = quoteCell(row, indexes.unit);
      const quantity = quoteCell(row, indexes.quantity);
      if (characteristics) lines.push(`Характеристики: ${characteristics}`);
      if (unit) lines.push(`Ед. изм.: ${unit}`);
      if (quantity) lines.push(`Кол-во: ${quantity}`);
      return lines.join("\n");
    })
    .filter(Boolean)
    .join("\n\n");
}

function quoteHtmlToMarkdown(root: HTMLElement | null) {
  if (!root) return "";
  const lines: string[] = [];
  const appendText = (value: string) => {
    const cleaned = value.replace(/\s+/g, " ").trim();
    if (cleaned) lines.push(cleaned);
  };
  Array.from(root.children).forEach((child) => {
    const tag = child.tagName.toLowerCase();
    const tableEl = tag === "table" ? child : child.querySelector("table");
    if (tableEl) {
      const rows = normalizeQuoteTableRows(
        Array.from(tableEl.querySelectorAll("tr"))
          .map((row) => cellsForMarkdownTable(row as HTMLTableRowElement))
          .filter((row) => row.some(Boolean)),
      );
      if (rows.length) {
        lines.push(`| ${rows[0].join(" | ")} |`);
        lines.push(`| ${rows[0].map(() => "---").join(" | ")} |`);
        rows.slice(1).forEach((row) => lines.push(`| ${row.join(" | ")} |`));
      }
    } else if (tag === "ul" || tag === "ol") {
      Array.from(child.querySelectorAll("li")).forEach((item) => appendText(`- ${item.textContent || ""}`));
    } else if (tag === "h3") {
      appendText(`### ${child.textContent || ""}`);
    } else if (tag === "h2" || tag === "h1") {
      appendText(child.textContent || "");
    } else {
      appendText(child.textContent || "");
    }
    if (lines[lines.length - 1] !== "") lines.push("");
  });
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function quoteHtmlToReadableText(root: HTMLElement | null) {
  if (!root) return "";
  const blocks: string[] = [];
  const appendBlock = (value: string) => {
    const cleaned = String(value || "").replace(/[ \t]+\n/g, "\n").replace(/\n[ \t]+/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
    if (cleaned) blocks.push(cleaned);
  };
  Array.from(root.children).forEach((child) => {
    const tag = child.tagName.toLowerCase();
    const tableEl = tag === "table" ? child : child.querySelector("table");
    if (tableEl) {
      appendBlock(quoteTableToReadableText(tableEl));
    } else if (tag === "ul" || tag === "ol") {
      appendBlock(Array.from(child.querySelectorAll("li")).map((item) => quotePlainText(item.textContent)).filter(Boolean).join("\n"));
    } else {
      appendBlock(quotePlainText(child.textContent));
    }
  });
  return blocks.join("\n\n").replace(/\n{3,}/g, "\n\n").trim();
}

async function writeClipboardText(text: string, htmlText?: string) {
  if (htmlText && navigator.clipboard && typeof ClipboardItem !== "undefined") {
    try {
      const htmlBlob = new Blob([htmlText], { type: "text/html" });
      const textBlob = new Blob([text], { type: "text/plain" });
      await navigator.clipboard.write([
        new ClipboardItem({
          "text/html": htmlBlob,
          "text/plain": textBlob,
        }),
      ]);
      return;
    } catch (err) {
      console.warn("Rich HTML clipboard copy fallback to text:", err);
    }
  }
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.style.position = "fixed";
  textArea.style.left = "-999999px";
  textArea.style.top = "-999999px";
  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();
  const copied = document.execCommand("copy");
  textArea.remove();
  if (!copied) throw new Error("Не удалось скопировать текст.");
}

function playNotificationChime() {
  if (typeof window === "undefined") return;
  try {
    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }
    const now = ctx.currentTime;

    // First tone (E5 - ~659Hz)
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = "sine";
    osc1.frequency.setValueAtTime(659.25, now);
    gain1.gain.setValueAtTime(0, now);
    gain1.gain.linearRampToValueAtTime(0.18, now + 0.02);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.36);

    // Second tone (A5 - 880Hz)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = "sine";
    osc2.frequency.setValueAtTime(880, now + 0.12);
    gain2.gain.setValueAtTime(0, now + 0.12);
    gain2.gain.linearRampToValueAtTime(0.22, now + 0.14);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.65);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.12);
    osc2.stop(now + 0.66);
  } catch (err) {
    console.warn("Notification chime error:", err);
  }
}

function DeliveryPriorityControl({ geoRadiusEnabled, deliveryCity, geoRadiusKm, setGeoRadiusEnabled, setDeliveryCity, setGeoRadiusKm, surchargePct, idPrefix = "" }: {
  geoRadiusEnabled: boolean; deliveryCity: string; geoRadiusKm: number;
  setGeoRadiusEnabled: (value: boolean) => void; setDeliveryCity: (value: string) => void;
  setGeoRadiusKm: (value: number) => void; surchargePct: number; idPrefix?: string;
}) {
  return (
            <section className="tl-geo-filter p-3 bg-slate-50 border border-slate-200/90 rounded-xl space-y-2.5" aria-label="Логистический фильтр">
              <div className="tl-geo-filter__heading flex items-center justify-between gap-3">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={geoRadiusEnabled}
                    onChange={(e) => setGeoRadiusEnabled(e.target.checked)}
                    className="w-4 h-4 text-teal-600 rounded border-slate-300 focus:ring-teal-500"
                  />
                  <span className="text-xs font-bold text-slate-800">
                    Приоритет в радиусе доставки
                  </span>
                </label>
                <span className="tl-geo-filter__badge text-[11px] font-semibold text-teal-700 bg-teal-50 border border-teal-200/80 px-2 py-0.5 rounded-full">
                  +{surchargePct}% к стоимости задачи
                </span>
              </div>

              {geoRadiusEnabled ? (
                <div className="tl-geo-filter__fields pt-2 border-t border-slate-200/80 grid grid-cols-1 sm:grid-cols-3 gap-2.5 items-end">
                  <div className="tl-geo-filter__city sm:col-span-2">
                    <label htmlFor={`${idPrefix}delivery-city`} className="block text-[11px] font-bold text-slate-700 mb-1">
                      Город объекта или поставки
                    </label>
                    <input
                      id={`${idPrefix}delivery-city`}
                      type="text"
                      pattern=".*\S.*"
                      value={deliveryCity}
                      onChange={(e) => setDeliveryCity(e.target.value)}
                      placeholder="например, Каменск-Шахтинский или Ростов-на-Дону"
                      required={geoRadiusEnabled}
                      aria-describedby={`${idPrefix}delivery-radius-help`}
                      className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500 placeholder:text-slate-400"
                    />
                  </div>
                  <div className="tl-geo-filter__radius">
                    <label htmlFor={`${idPrefix}delivery-radius`} className="block text-[11px] font-bold text-slate-700 mb-1">
                      Радиус поиска
                    </label>
                    <div className="relative">
                      <input
                        id={`${idPrefix}delivery-radius`}
                        type="number"
                        min={10}
                        max={5000}
                        required={geoRadiusEnabled}
                        step={1}
                        value={geoRadiusKm || ""}
                        onChange={(e) => {
                          const val = e.target.value === "" ? 0 : Number(e.target.value);
                          setGeoRadiusKm(val);
                        }}
                        placeholder="300"
                        className="w-full text-xs px-3 py-2 pr-9 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500 font-semibold text-slate-800"
                      />
                      <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs font-semibold text-slate-400 pointer-events-none">
                        км
                      </span>
                    </div>
                  </div>
                  <div id={`${idPrefix}delivery-radius-help`} className="tl-geo-filter__helper sm:col-span-3 text-[11px] text-slate-500 leading-tight">
                    Ближайшие поставщики идут первыми. Варианты вне радиуса и с неподтверждённым адресом помечаются отдельно. Расстояние приблизительное; склад и сроки уточняются у поставщика.
                  </div>
                </div>
              ) : null}
            </section>
  );
}

function CustomerJobChat({
  job,
  csrf,
  onJobUpdated,
}: {
  job: CustomerJob;
  csrf: string;
  onJobUpdated: (updatedJob: CustomerJob) => void;
}) {
  const hasMessages = Boolean(job.chat_messages && job.chat_messages.length > 0) || Boolean(job.admin_comment);
  const [isOpen, setIsOpen] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [replyFiles, setReplyFiles] = useState<File[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && job.unread_admin_messages_count && job.unread_admin_messages_count > 0) {
      fetch(`/api/customer/jobs/${job.id}/chat/read`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      })
        .then(() => {
          onJobUpdated({
            ...job,
            unread_admin_messages_count: 0,
            chat_messages: job.chat_messages?.map((m) =>
              m.sender_role === "admin" ? { ...m, is_read_by_client: true } : m
            ),
          });
        })
        .catch(() => {});
    }
  }, [isOpen, job.id, job.unread_admin_messages_count, csrf]);

  async function handleSendReply(e: React.FormEvent) {
    e.preventDefault();
    const text = replyText.trim();
    if (!text && replyFiles.length === 0) return;

    setSending(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("message", text);
      replyFiles.forEach((f) => formData.append("files", f));
      if (replyFiles[0]) formData.append("file", replyFiles[0]);

      const res = await fetch(`/api/customer/jobs/${job.id}/chat`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
        body: formData,
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || "Ошибка отправки ответа");
      }

      const data = await res.json();
      setReplyText("");
      setReplyFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";

      onJobUpdated({
        ...job,
        chat_messages: data.messages || job.chat_messages,
        unread_admin_messages_count: 0,
      });
    } catch (err: any) {
      setError(err.message || "Не удалось отправить сообщение");
    } finally {
      setSending(false);
    }
  }

  const messages =
    job.chat_messages && job.chat_messages.length > 0
      ? job.chat_messages
      : job.admin_comment
      ? [
          {
            id: "initial-comment",
            job_id: job.id,
            client_id: job.client_id || "",
            sender_role: "admin" as const,
            message: job.admin_comment,
            attachments: [],
            is_read_by_client: true,
            is_read_by_admin: true,
            created_at: job.admin_supplement_at || job.updated_at || job.created_at,
          },
        ]
      : [];

  if (!isOpen) {
    if (!hasMessages) {
      return null;
    }

    const lastMsg = messages[messages.length - 1];
    return (
      <div className="col-span-12 mt-1.5 px-3 py-2 rounded-xl bg-[#f4f8ef] border border-[#cde0be] flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-3 text-xs">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-5 h-5 rounded-full bg-[#174b3f] text-white flex items-center justify-center shrink-0">
            <Sparkles size={11} aria-hidden="true" />
          </div>
          <span className="font-bold text-[#103a31] text-xs shrink-0">Переписка:</span>
          <span className="text-slate-600 truncate min-w-0">
            {lastMsg?.message || "Экспертные материалы подготовлены"}
          </span>
          {Boolean(job.unread_admin_messages_count) && (
            <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-600 text-white shrink-0">
              Новый ответ
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => {
              window.dispatchEvent(
                new CustomEvent("open_tenderlex_chat", {
                  detail: {
                    jobId: job.id,
                    jobNumber: job.job_number,
                    jobTitle: formatCleanJobTitle(job),
                  },
                })
              );
            }}
            className="tl-btn-primary inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] cursor-pointer"
          >
            <MessageSquare size={12} />
            <span>Открыть в чате</span>
          </button>
          <button
            type="button"
            onClick={() => setIsOpen(true)}
            className="text-slate-600 hover:text-slate-900 text-[11px] font-semibold flex items-center gap-0.5 cursor-pointer"
            title="Показать историю на карточке"
          >
            <span>История ({messages.length})</span>
            <ChevronDown size={12} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="col-span-12 mt-2 p-3.5 rounded-xl bg-[#f4f8ef] border border-[#cde0be] text-slate-800 text-xs">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-full bg-[#174b3f] text-white flex items-center justify-center shrink-0">
            <Sparkles size={11} aria-hidden="true" />
          </div>
          <span className="font-bold text-[#103a31] text-xs">
            Переписка со специалистом TenderLex
          </span>
          {Boolean(job.unread_admin_messages_count) && (
            <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-600 text-white">
              Новый ответ
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => {
              window.dispatchEvent(
                new CustomEvent("open_tenderlex_chat", {
                  detail: {
                    jobId: job.id,
                    jobNumber: job.job_number,
                    jobTitle: formatCleanJobTitle(job),
                  },
                })
              );
            }}
            className="text-[#174b3f] hover:text-[#103a31] text-[11px] font-semibold flex items-center gap-1 cursor-pointer"
          >
            <MessageSquare size={12} />
            <span>Открыть в едином чате</span>
          </button>
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            className="text-slate-500 hover:text-slate-800 text-[11px] font-medium flex items-center gap-1 cursor-pointer"
          >
            <span>Свернуть</span>
            <ChevronDown size={13} className="rotate-180" />
          </button>
        </div>
      </div>

      {isOpen && (
        <div className="space-y-3 mt-2">
          <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
            {messages.map((m, idx) => {
              const isAdmin = m.sender_role === "admin";
              return (
                <div
                  key={m.id || idx}
                  className={`flex flex-col ${isAdmin ? "items-start" : "items-end"}`}
                >
                  <div className="flex items-center gap-1.5 mb-1 text-[10px] text-slate-500">
                    <span
                      className={`font-semibold ${isAdmin ? "text-teal-800" : "text-slate-700"}`}
                    >
                      {isAdmin ? "Специалист TenderLex" : "Вы"}
                    </span>
                    {m.created_at && (
                      <>
                        <span>·</span>
                        <span>{formatDate(m.created_at)}</span>
                      </>
                    )}
                  </div>

                  <div
                    className={`p-2.5 rounded-xl max-w-[92%] leading-relaxed ${
                      isAdmin
                        ? "bg-white border border-teal-200/90 text-slate-800 shadow-2xs"
                        : "bg-teal-600 text-white border border-teal-700 shadow-2xs"
                    }`}
                  >
                    <p className="whitespace-pre-wrap font-normal m-0">{m.message}</p>

                    {m.attachments && m.attachments.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-100 flex flex-wrap gap-1.5">
                        {m.attachments.map((att) => (
                          <a
                            key={att.index}
                            href={att.customer_url || att.url}
                            target="_blank"
                            rel="noreferrer"
                            download
                            className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-semibold transition-colors ${
                              isAdmin
                                ? "bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200"
                                : "bg-teal-700 hover:bg-teal-800 text-white border border-teal-800"
                            }`}
                          >
                            <Download size={11} />
                            <span>{att.name}</span>
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <form onSubmit={handleSendReply} className="pt-2 border-t border-teal-100 space-y-2">
            {error && (
              <div className="p-2 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-[11px]">
                {error}
              </div>
            )}

            {replyFiles.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {replyFiles.map((f, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] bg-teal-100 text-teal-800 font-medium"
                  >
                    <Paperclip size={10} />
                    <span>{f.name}</span>
                    <button
                      type="button"
                      onClick={() =>
                        setReplyFiles((prev) => prev.filter((_, idx) => idx !== i))
                      }
                      className="ml-0.5 text-teal-800 hover:text-teal-950 font-bold"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}

            <div className="flex gap-2 items-end">
              <div className="flex-1">
                <textarea
                  rows={2}
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Ответьте специалисту (укажите ваш телефон или уточните требования)..."
                  className="w-full p-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-1 focus:ring-teal-500 focus:border-teal-500 bg-white resize-y"
                />
              </div>

              <div className="flex flex-col gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  title="Прикрепить файл"
                  className="inline-flex items-center justify-center p-2 rounded-lg border border-slate-300 bg-white text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  <Paperclip size={14} />
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    className="hidden"
                    accept=".xlsx,.xls,.docx,.doc,.pdf,.zip,.png,.jpg,.jpeg"
                    onChange={(e) => {
                      if (e.target.files) {
                        setReplyFiles(Array.from(e.target.files));
                      }
                    }}
                  />
                </button>

                <button
                  type="submit"
                  disabled={sending || (!replyText.trim() && replyFiles.length === 0)}
                  className="inline-flex items-center justify-center gap-1 px-3 py-2 rounded-lg bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white font-semibold text-xs transition-colors shadow-2xs"
                >
                  {sending ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                  <span>Ответить</span>
                </button>
              </div>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

export function CabinetClient({ initialTrialBalanceRub = 495 }: { initialTrialBalanceRub?: number }) {
  const [nowTs, setNowTs] = useState(() => Date.now());
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [telegramVerifying, setTelegramVerifying] = useState(false);
  const [jobs, setJobs] = useState<CustomerJob[]>([]);
  const [jobsPage, setJobsPage] = useState(1);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [jobsPageSize, setJobsPageSize] = useState<number>(() => {
    if (typeof window === "undefined") return DEFAULT_CUSTOMER_JOBS_PAGE_SIZE;
    try {
      const saved = localStorage.getItem("tenderlex_customer_jobs_page_size");
      if (saved) {
        const num = parseInt(saved, 10);
        if (num === 15 || num === 25 || num === 50 || num === 100) return num;
      }
    } catch {}
    return DEFAULT_CUSTOMER_JOBS_PAGE_SIZE;
  });

  function handleJobsPageSizeChange(size: number) {
    setJobsPageSize(size);
    setJobsPage(1);
    try {
      localStorage.setItem("tenderlex_customer_jobs_page_size", String(size));
    } catch {}
  }

  const [cabinetSection, setCabinetSection] = useState<"workspace" | "jobs">("workspace");
  const [showAllWorkspaceJobs, setShowAllWorkspaceJobs] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);
  const [chatUnreadCount, setChatUnreadCount] = useState(0);
  const [jobSearchQuery, setJobSearchQuery] = useState("");
  const [debouncedJobSearch, setDebouncedJobSearch] = useState("");
  const [jobModeFilter, setJobModeFilter] = useState("");
  const [jobPolicyFilter, setJobPolicyFilter] = useState("");
  const [jobStatusFilter, setJobStatusFilter] = useState<"" | "active" | "attention" | "completed">("");
  const [authMode, setAuthMode] = useState<"login" | "register" | "reset" | "new_password">("register");
  const [resetToken, setResetToken] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [registerPasswordConfirm, setRegisterPasswordConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [changeNewPassword, setChangeNewPassword] = useState("");
  const [changeNewPasswordConfirm, setChangeNewPasswordConfirm] = useState("");
  const [changePasswordBusy, setChangePasswordBusy] = useState(false);
  const [changePasswordError, setChangePasswordError] = useState("");
  const [changePasswordSuccess, setChangePasswordSuccess] = useState("");
  const [deleteAccountConfirm, setDeleteAccountConfirm] = useState(false);
  const [deleteAccountBusy, setDeleteAccountBusy] = useState(false);
  const [name, setName] = useState("");
  const [registerPhone, setRegisterPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [website, setWebsite] = useState("");
  const [challengeToken, setChallengeToken] = useState("");
  const isSubmittingJobRef = useRef(false);
  const lastJobSubmitRef = useRef<{ signature: string; ts: number }>({ signature: "", ts: 0 });

  useEffect(() => {
    const isAuthed = Boolean(session?.authenticated && session.user);
    if (authMode !== "register" || sessionLoading || isAuthed) return;
    let cancelled = false;
    fetch("/api/public/auth/challenge", { credentials: "same-origin", cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data?.token) setChallengeToken(String(data.token));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [authMode, sessionLoading, session?.authenticated, session?.user]);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [personalDataConsent, setPersonalDataConsent] = useState(false);
  const [emailDraft, setEmailDraft] = useState("");
  const [emailEditOpen, setEmailEditOpen] = useState(false);
  const [scenario, setScenario] = useState<Scenario>("procurement_report");
  const [supplierSearchPolicy, setSupplierSearchPolicy] = useState<SupplierSearchPolicy>("normal");
  const [geoScope, setGeoScope] = useState<GeoScope>("ru");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("tenderlex_geo_scope");
      if (saved === "ru" || saved === "cis" || saved === "world") {
        setGeoScope(saved as GeoScope);
      }
    } catch {}
  }, []);

  const handleSetSupplierSearchPolicy = (policy: SupplierSearchPolicy) => {
    setSupplierSearchPolicy(policy);
    if (policy === "minprom_registry_only" || policy === "minprom_registry_priority") {
      setGeoScope("ru");
    }
  };

  const handleSetGeoScope = (scope: GeoScope) => {
    setGeoScope(scope);
    try {
      localStorage.setItem("tenderlex_geo_scope", scope);
    } catch {}
    if (scope !== "ru" && supplierSearchPolicy === "minprom_registry_only") {
      setSupplierSearchPolicy("normal");
    }
  };

  const [multiItemMode, setMultiItemMode] = useState<"balanced" | "per_item">("balanced");
  const [geoRadiusEnabled, setGeoRadiusEnabled] = useState(false);
  const [deliveryCity, setDeliveryCity] = useState("");
  const [geoRadiusKm, setGeoRadiusKm] = useState<number>(300);
  const [text, setText] = useState("");
  const [sourceUrls, setSourceUrls] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [jobsLoading, setJobsLoading] = useState(false);
  const jobsRequestIdRef = useRef(0);
  const jobsForegroundRequestRef = useRef<number | null>(null);
  const jobsBackgroundRequestRef = useRef<number | null>(null);
  const sessionBackgroundRequestRef = useRef(false);
  const [findMoreConfirmJob, setFindMoreConfirmJob] = useState<CustomerJob | null>(null);
  const [findMorePrompt, setFindMorePrompt] = useState("");
  const [startSupplierSearchConfirmJob, setStartSupplierSearchConfirmJob] = useState<CustomerJob | null>(null);
  const [startSupplierSearchPolicy, setStartSupplierSearchPolicy] = useState<SupplierSearchPolicy>("normal");
  const [startSupplierSearchMultiItemMode, setStartSupplierSearchMultiItemMode] = useState<"balanced" | "per_item">("balanced");
  const [startSupplierSearchAlternatives, setStartSupplierSearchAlternatives] = useState<boolean>(true);
  const [startSupplierSearchPrompt, setStartSupplierSearchPrompt] = useState<string>("");
  const [startSupplierGeoEnabled, setStartSupplierGeoEnabled] = useState(false);
  const [startSupplierCity, setStartSupplierCity] = useState("");
  const [startSupplierRadius, setStartSupplierRadius] = useState(300);
  const [retryConfirmJob, setRetryConfirmJob] = useState<CustomerJob | null>(null);
  const [retryPolicy, setRetryPolicy] = useState<SupplierSearchPolicy>("normal");
  const [retryMultiItemMode, setRetryMultiItemMode] = useState<"balanced" | "per_item">("balanced");
  const [strategyConfirmJob, setStrategyConfirmJob] = useState<CustomerJob | null>(null);
  const [selectedStrategyMode, setSelectedStrategyMode] = useState<"balanced" | "per_item">("balanced");
  const [selectedStrategyItemIds, setSelectedStrategyItemIds] = useState<string[]>([]);
  const [strategyError, setStrategyError] = useState<string>("");
  const [strategySubmittingJobId, setStrategySubmittingJobId] = useState<string | null>(null);
  const dismissedStrategyJobIdsRef = useRef<Set<string>>(new Set());
  const [exactSelectionJob, setExactSelectionJob] = useState<CustomerJob | null>(null);
  const [selectedExactItemIds, setSelectedExactItemIds] = useState<string[]>([]);
  const [exactSelectionError, setExactSelectionError] = useState("");
  const [exactSelectionSubmittingJobId, setExactSelectionSubmittingJobId] = useState<string | null>(null);
  const dismissedExactSelectionJobIdsRef = useRef<Set<string>>(new Set());
  const exactSelectionStateRef = useRef<Map<string, string[]>>(new Map());
  const [selectionSearchQuery, setSelectionSearchQuery] = useState("");
  const [selectionVisibleLimit, setSelectionVisibleLimit] = useState(50);

  function markStrategyDismissed(jobId: string) {
    dismissedStrategyJobIdsRef.current.add(jobId);
    try {
      const raw = sessionStorage.getItem("tenderlex_dismissed_strategy_jobs");
      const list: string[] = raw ? JSON.parse(raw) : [];
      if (!list.includes(jobId)) {
        list.push(jobId);
        sessionStorage.setItem("tenderlex_dismissed_strategy_jobs", JSON.stringify(list));
      }
    } catch {}
  }

  function unmarkStrategyDismissed(jobId: string) {
    dismissedStrategyJobIdsRef.current.delete(jobId);
    try {
      const raw = sessionStorage.getItem("tenderlex_dismissed_strategy_jobs");
      if (raw) {
        const list: string[] = JSON.parse(raw);
        const filtered = list.filter((id) => id !== jobId);
        sessionStorage.setItem("tenderlex_dismissed_strategy_jobs", JSON.stringify(filtered));
      }
    } catch {}
  }

  function openStrategyConfirmModal(job: CustomerJob) {
    const items = job.multi_item_details?.items || [];
    const allIds = items.map((it, idx) => it.id || `item-${idx}`);
    setSelectedStrategyMode("balanced");
    setSelectedStrategyItemIds(allIds);
    setStrategyError("");
    setStrategyConfirmJob(job);
  }

  function exactSelectionKey(job: CustomerJob) {
    return `${job.id}:${positionSelectionForJob(job)?.revision || ""}`;
  }

  function openExactSelectionModal(job: CustomerJob) {
    const selection = positionSelectionForJob(job);
    if (!selection) return;
    const key = exactSelectionKey(job);
    const itemIds = new Set(selection.items.map((item) => item.id));
    const remembered = exactSelectionStateRef.current.get(key);
    const initial = (remembered || selection.selected_ids || []).filter((id) => itemIds.has(id));
    setSelectedExactItemIds(initial);
    setExactSelectionError("");
    setSelectionSearchQuery("");
    setSelectionVisibleLimit(50);
    setExactSelectionJob(job);
  }

  function dismissExactSelectionModal() {
    if (!exactSelectionJob) return;
    dismissedExactSelectionJobIdsRef.current.add(exactSelectionKey(exactSelectionJob));
    setExactSelectionJob(null);
  }

  function toggleExactSelectionItem(job: CustomerJob, itemId: string) {
    const selection = positionSelectionForJob(job);
    const isUncapped = job.mode === "exact_product" || job.mode === "price_monitoring" || selection?.pricing_mode === "per_position" || selection?.pricing_mode === "per_found_position";
    const maxPositions = isUncapped ? (selection?.items.length || 100) : (selection?.max_positions || 5);
    setSelectedExactItemIds((current) => {
      const hasItem = current.includes(itemId);
      if (hasItem) {
        const next = current.filter((id) => id !== itemId);
        exactSelectionStateRef.current.set(exactSelectionKey(job), next);
        setExactSelectionError("");
        return next;
      }
      if (current.length >= maxPositions) {
        setExactSelectionError(`Можно выбрать не более ${maxPositions} позиций.`);
        return current;
      }
      const next = [...current, itemId];
      exactSelectionStateRef.current.set(exactSelectionKey(job), next);
      setExactSelectionError("");
      return next;
    });
  }

  function toggleExactSelectionGroup(job: CustomerJob, itemIds: string[], groupName: string) {
    const selection = positionSelectionForJob(job);
    if (!selection || itemIds.length === 0) return;
    const isUncapped = job.mode === "exact_product" || job.mode === "price_monitoring" || selection.pricing_mode === "per_position" || selection.pricing_mode === "per_found_position";
    const maxPositions = isUncapped ? selection.items.length : (selection.max_positions || selection.items.length);
    setSelectedExactItemIds((current) => {
      const groupSet = new Set(itemIds);
      const allSelected = itemIds.every((itemId) => current.includes(itemId));
      const next = allSelected ? current.filter((itemId) => !groupSet.has(itemId)) : Array.from(new Set([...current, ...itemIds]));
      if (!allSelected && next.length > maxPositions) {
        setExactSelectionError(`Категория «${groupName}» содержит ${itemIds.length} позиций. С текущим выбором это превысит лимит ${maxPositions}; выберите позиции вручную.`);
        return current;
      }
      exactSelectionStateRef.current.set(exactSelectionKey(job), next);
      setExactSelectionError("");
      return next;
    });
  }

  async function confirmExactSelection(job: CustomerJob) {
    const selection = positionSelectionForJob(job);
    if (!csrf || !selection) return;
    const isPriceMonitoring = job.mode === "price_monitoring";
    const isUncapped = job.mode === "exact_product" || isPriceMonitoring || selection.pricing_mode === "per_position" || selection.pricing_mode === "per_found_position";
    const maxPositions = isUncapped ? selection.items.length : (selection.max_positions || selection.items.length);
    if (selectedExactItemIds.length === 0) {
      setExactSelectionError(`Выберите хотя бы одну позицию для ${isPriceMonitoring ? "мониторинга цен" : "подбора"}.`);
      return;
    }
    if (selectedExactItemIds.length > maxPositions) {
      setExactSelectionError(`Можно выбрать не более ${maxPositions} позиций.`);
      return;
    }
    setExactSelectionSubmittingJobId(job.id);
    setExactSelectionError("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/${isPriceMonitoring ? "position-selection" : "exact-selection"}`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf, "content-type": "application/json" },
        body: JSON.stringify({ revision: selection.revision, selected_item_ids: selectedExactItemIds }),
      });
      const payload = await readJson<{ message?: string }>(response);
      exactSelectionStateRef.current.delete(exactSelectionKey(job));
      dismissedExactSelectionJobIdsRef.current.add(exactSelectionKey(job));
      setExactSelectionJob(null);
      setMessage(payload.message || `Выбрано позиций: ${selectedExactItemIds.length}. ${isPriceMonitoring ? "Начинаем мониторинг цен." : "Начинаем подбор."}`);
      await loadSession();
      await loadJobs();
    } catch (err) {
      setExactSelectionError(err instanceof Error ? err.message : String(err));
    } finally {
      setExactSelectionSubmittingJobId(null);
    }
  }

  async function retryExactPosition(job: CustomerJob, positionId?: string) {
    const selection = job.exact_product_selection;
    if (!csrf || !selection || !positionId) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/exact-selection/retry`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf, "content-type": "application/json" },
        body: JSON.stringify({ revision: selection.revision, selected_item_ids: [positionId] }),
      });
      const payload = await readJson<{ message?: string }>(response);
      setMessage(payload.message || "Создан новый подбор для выбранной позиции. Подтвердите его в списке задач.");
      setJobsPage(1);
      await loadSession();
      await loadJobs(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function skipOrDismissStrategyModal() {
    if (!strategyConfirmJob) return;
    markStrategyDismissed(strategyConfirmJob.id);
    const otherPending = jobs.filter(
      (j) =>
        j.id !== strategyConfirmJob.id &&
        j.awaiting_customer_confirmation &&
        j.confirmation_kind === "multi_item_strategy" &&
        !dismissedStrategyJobIdsRef.current.has(j.id)
    );
    if (otherPending.length > 0) {
      openStrategyConfirmModal(otherPending[0]);
    } else {
      setStrategyConfirmJob(null);
    }
  }

  function fillDemoExample() {
    selectScenario("supplier_search");
    setError("");
    setText(
      "Поставка промышленной трубопроводной арматуры:\n" +
      "1. Задвижка стальная клиновая фланцевая 30с41нж Ду100 Ру16 — 12 шт.\n" +
      "2. Клапан обратный поворотный фланцевый 19с53нж Ду100 Ру16 — 8 шт.\n" +
      "3. Кран шаровой стальной фланцевый 11с67п Ду50 Ру16 — 25 шт.\n" +
      "4. Фланец плоский приварной стальной ГОСТ 33259-2015 Ду100 Ру16 — 24 шт."
    );
    clearSelectedFiles();
    const launcher = document.getElementById("new-job");
    if (launcher) {
      launcher.scrollIntoView({ behavior: "smooth" });
    }
    setMessage("Демонстрационное ТЗ загружено в форму. Нажмите кнопку «Запустить поиск поставщиков».");
  }

  function getClientEffectiveTaskPrice(): number | null {
    const eff = session?.balance?.effective_prices?.supplier_search?.price_rub;
    if (typeof eff === "number" && eff > 0) return eff;
    const s = session?.balance?.supplier_search?.price_rub;
    if (typeof s === "number" && s > 0) return s;
    return null;
  }
  const [quoteRequestModal, setQuoteRequestModal] = useState<QuoteRequestModal | null>(null);
  const [quoteItemSearch, setQuoteItemSearch] = useState("");
  const [batchPreview, setBatchPreview] = useState<BatchRegistryPreviewData | null>(null);
  const [batchSelectedIds, setBatchSelectedIds] = useState<string[]>([]);
  const [batchBusy, setBatchBusy] = useState(false);
  const [batchModalError, setBatchModalError] = useState("");
  const [batchReaderData, setBatchReaderData] = useState<BatchReportReaderData | null>(null);
  const [batchReaderActiveIdx, setBatchReaderActiveIdx] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [showTariffs, setShowTariffs] = useState(false);
  const [mobileToolsOpen, setMobileToolsOpen] = useState(false);
  const [showTopUpModal, setShowTopUpModal] = useState(false);
  const [topUpTab, setTopUpTab] = useState<"card" | "b2b">("card");
  const [selectedTopUpPackage, setSelectedTopUpPackage] = useState<DepositPackage | null>(null);
  const [customTopUpRub, setCustomTopUpRub] = useState<number>(5000);
  const [topUpCopied, setTopUpCopied] = useState(false);
  const [isPayingOnline, setIsPayingOnline] = useState(false);
  const [onlinePayError, setOnlinePayError] = useState("");
  const [payerPhone, setPayerPhone] = useState("");
  const [payerTelegram, setPayerTelegram] = useState("");
  const [paymentSuccessNotice, setPaymentSuccessNotice] = useState<{
    amountRub: number;
    bonusRub: number;
    totalCreditRub: number;
  } | null>(null);
  const [checkingPaymentStatus, setCheckingPaymentStatus] = useState(false);

  // B2B Invoice state
  const [invoiceInn, setInvoiceInn] = useState("");
  const [invoiceKpp, setInvoiceKpp] = useState("");
  const [invoiceName, setInvoiceName] = useState("");
  const [invoiceAddress, setInvoiceAddress] = useState("");
  const [invoiceEmail, setInvoiceEmail] = useState("");
  const [invoiceLoadingInn, setInvoiceLoadingInn] = useState(false);
  const [invoiceInnFound, setInvoiceInnFound] = useState(false);
  const [invoiceInnError, setInvoiceInnError] = useState("");
  const [invoiceSubmitting, setInvoiceSubmitting] = useState(false);
  const [invoiceSubmitError, setInvoiceSubmitError] = useState("");
  const [invoiceCreated, setInvoiceCreated] = useState<{
    id: string;
    invoice_number: string;
    amount_rub: number;
    bonus_rub: number;
    total_credit_rub: number;
    buyer_name: string;
    buyer_inn: string;
    buyer_kpp?: string;
    buyer_address?: string;
    buyer_email: string;
    tariff_name: string;
    created_at?: string;
    status?: string;
    proof_submitted_at?: string | null;
  } | null>(null);
  const [invoiceEmailSending, setInvoiceEmailSending] = useState(false);
  const [invoiceEmailSent, setInvoiceEmailSent] = useState(false);
  const [invoiceEmailError, setInvoiceEmailError] = useState("");
  const [invoiceDetailsCopied, setInvoiceDetailsCopied] = useState(false);
  const [customerInvoices, setCustomerInvoices] = useState<CustomerInvoice[]>([]);
  const invoiceRequestVersion = useRef(0);
  const [customerInvoicesTotal, setCustomerInvoicesTotal] = useState(0);
  const [customerInvoicesPage, setCustomerInvoicesPage] = useState(1);
  const CUSTOMER_INVOICES_PER_PAGE = 5;
  const [invoiceProofUploading, setInvoiceProofUploading] = useState<string | null>(null);
  const [invoiceProofMessage, setInvoiceProofMessage] = useState<string | null>(null);
  const [showHelpModal, setShowHelpModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [historyModalTab, setHistoryModalTab] = useState<"transactions" | "invoices">("transactions");
  const [historyOpFilter, setHistoryOpFilter] = useState<"all" | "debit" | "grant" | "release">("all");
  const [invoiceCopiedId, setInvoiceCopiedId] = useState<string | null>(null);
  const [invoiceEmailSendingId, setInvoiceEmailSendingId] = useState<string | null>(null);
  const [invoiceEmailSentId, setInvoiceEmailSentId] = useState<string | null>(null);
  const [invoiceCardEmailError, setInvoiceCardEmailError] = useState("");
  const [showCurrentPwd, setShowCurrentPwd] = useState(false);
  const [showNewPwd, setShowNewPwd] = useState(false);
  const [showReferralModal, setShowReferralModal] = useState(false);
  const [referralCopiedKey, setReferralCopiedKey] = useState<string | null>(null);
  const [historyTransactions, setHistoryTransactions] = useState<CustomerBillingTransaction[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [showScenarioHint, setShowScenarioHint] = useState(false);
  const [helpModalTab, setHelpModalTab] = useState<string>("workflow");
  const [showApiModal, setShowApiModal] = useState(false);
  const [apiModalTab, setApiModalTab] = useState<"key" | "methods" | "ai_prompt" | "mcp">("key");
  const [apiKeys, setApiKeys] = useState<Array<{
    id: string;
    key_prefix: string;
    raw_key?: string | null;
    name: string;
    created_at: string | null;
    is_active: boolean;
    last_used_at: string | null;
    total_spent: number;
  }>>([]);
  const [loadingApiKeys, setLoadingApiKeys] = useState(false);
  const [generatingApiKey, setGeneratingApiKey] = useState(false);
  const [revokingKeyId, setRevokingKeyId] = useState<string | null>(null);
  const [confirmRevokeKeyId, setConfirmRevokeKeyId] = useState<string | null>(null);
  const [newlyGeneratedKey, setNewlyGeneratedKey] = useState<string | null>(null);
  const [apiCopiedField, setApiCopiedField] = useState<string | null>(null);

  async function loadCustomerApiKeys() {
    setLoadingApiKeys(true);
    try {
      const res = await fetch("/api/customer/api-keys", { credentials: "same-origin" });
      if (res.ok) {
        const data = await res.json();
        setApiKeys(data.keys || []);
      }
    } catch (err) {
      console.error("loadCustomerApiKeys failed:", err);
    } finally {
      setLoadingApiKeys(false);
    }
  }

  async function createCustomerApiKey() {
    if (!csrf) return;
    setGeneratingApiKey(true);
    try {
      const res = await fetch("/api/customer/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        credentials: "same-origin",
      });
      if (res.ok) {
        const data = await res.json();
        setNewlyGeneratedKey(data.raw_key);
        await loadCustomerApiKeys();
      }
    } catch (err) {
      console.error("createCustomerApiKey failed:", err);
    } finally {
      setGeneratingApiKey(false);
    }
  }

  async function revokeCustomerApiKey(keyId: string) {
    if (!csrf) return;
    setRevokingKeyId(keyId);
    try {
      const res = await fetch(`/api/customer/api-keys/${keyId}/revoke`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        credentials: "same-origin",
      });
      if (res.ok) {
        setNewlyGeneratedKey(null);
        setConfirmRevokeKeyId(null);
        await loadCustomerApiKeys();
      }
    } catch (err) {
      console.error("revokeCustomerApiKey failed:", err);
    } finally {
      setRevokingKeyId(null);
    }
  }

  function copyApiText(text: string, fieldId: string) {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        setApiCopiedField(fieldId);
        setTimeout(() => setApiCopiedField(null), 2500);
      });
    }
  }
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const notificationsEnabledRef = useRef(notificationsEnabled);
  notificationsEnabledRef.current = notificationsEnabled;
  const [viewedJobIds, setViewedJobIds] = useState<string[]>([]);
  const [activeToast, setActiveToast] = useState<ActiveToast | null>(null);
  const prevJobStatusesRef = useRef<Map<string, string>>(new Map());
  const hasInitializedJobsRef = useRef(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const quoteEditorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedJobSearch(jobSearchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [jobSearchQuery]);

  useEffect(() => {
    setJobsPage(1);
  }, [debouncedJobSearch, jobModeFilter, jobPolicyFilter, jobStatusFilter]);

  const hasActiveJobFilters = Boolean(jobSearchQuery.trim() || jobModeFilter || jobPolicyFilter || jobStatusFilter);

  function resetJobFilters() {
    setJobSearchQuery("");
    setDebouncedJobSearch("");
    setJobModeFilter("");
    setJobPolicyFilter("");
    setJobStatusFilter("");
    setJobsPage(1);
  }

  const csrf = session?.csrf_token || "";
  const authenticated = Boolean(session?.authenticated && session.user);
  const hasSeparateCustomBatchTab = Boolean(
    session?.user?.allowed_custom_batch_report && session?.user?.custom_report_separate_tab
  );
  const isInlineCustomBatchMode = Boolean(
    session?.user?.allowed_custom_batch_report && !session?.user?.custom_report_separate_tab
  );
  const isCustomBatchScenario =
    scenario === "custom_batch_report" ||
    (scenario === "procurement_report" && isInlineCustomBatchMode);
  const selectedCopy =
    scenario === "procurement_report" && isInlineCustomBatchMode
      ? modeCopy.custom_batch_report
      : modeCopy[scenario];
  const selectedMode = selectedCopy.mode;
  const acceptsSources = Boolean(selectedCopy.sourceLabel);
  const acceptsText = Boolean(selectedCopy.textLabel);
  const maxFiles = session?.limits?.max_files_per_batch || 20;
  const targetQuota = session?.limits?.default_supplier_target || 25;
  const emailVerified = session?.user?.is_email_verified !== false;
  const supplierMultiFileWarning = scenario === "supplier_search" && selectedFiles.length > 1;
  const activeJobs = useMemo(
    () => jobs.filter((job) => ["pending", "running", "awaiting_customer_confirmation", "awaiting_exact_selection", "awaiting_position_selection"].includes(job.status)).length,
    [jobs],
  );
  const attentionJobsCount = useMemo(
    () => jobs.filter((job) => job.awaiting_customer_confirmation || isAwaitingPositionSelection(job)).length,
    [jobs],
  );
  const pendingInvoicesCount = useMemo(
    () => customerInvoices.filter((inv) => inv.status === "issued" || inv.status === "rejected").length,
    [customerInvoices],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const initial = Number((window as unknown as { __tenderlexChatUnread?: number }).__tenderlexChatUnread || 0);
    if (initial > 0) setChatUnreadCount(initial);
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ count?: number }>).detail;
      setChatUnreadCount(Math.max(0, Number(detail?.count || 0)));
    };
    window.addEventListener("tenderlex_chat_unread", handler);
    return () => window.removeEventListener("tenderlex_chat_unread", handler);
  }, []);

  useEffect(() => {
    if (!profileMenuOpen) return;
    const onMouseDown = (event: globalThis.MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target as Node)) {
        setProfileMenuOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setProfileMenuOpen(false);
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [profileMenuOpen]);

  const activeScenarioPricingHint = useMemo(() => {
    const eff = session?.balance?.effective_prices;
    const fn = session?.function_prices;
    const reportPrice = Math.round(eff?.procurement_report?.price_rub ?? fn?.procurement_report?.price_rub ?? 99);
    const batchPrice = Math.round(eff?.custom_batch_report?.price_rub ?? fn?.custom_batch_report?.price_rub ?? 30);
    const batchMax = session?.user?.batch_report_max_items ?? 30;
    const supplierPrice = Math.round(eff?.supplier_search?.price_rub ?? fn?.supplier_search?.price_rub ?? 99);
    const exactPrice = Math.round(eff?.exact_product?.price_rub ?? fn?.exact_product?.price_rub ?? 99);
    const pmPrice = Math.round(eff?.price_monitoring?.price_rub ?? 50);
    const geoPct = session?.user?.geo_radius_surcharge_pct ?? 30;
    const geoNote = geoRadiusEnabled && session?.user?.allowed_geo_radius ? ` (+${geoPct}% приоритет доставки)` : "";

    if (isCustomBatchScenario) {
      return `${batchPrice} ₽ за каждую обработанную закупку (до ${batchMax} шт. за запуск) — за закрытые площадки 0 ₽`;
    }
    if (scenario === "procurement_report") {
      return `${reportPrice} ₽ с баланса — списание только по готовому отчёту`;
    }
    if (scenario === "supplier_search") {
      return `${supplierPrice} ₽ с баланса${geoNote} — списание только за найденных поставщиков`;
    }
    if (scenario === "analysis_and_suppliers") {
      return `${reportPrice + supplierPrice} ₽ с баланса (анализ ${reportPrice} ₽ + поставщики ${supplierPrice} ₽${geoNote}) — оплата по результату`;
    }
    if (scenario === "exact_product") {
      return `${exactPrice} ₽ за позицию — выбор позиций и суммы перед запуском`;
    }
    if (scenario === "price_monitoring") {
      return `${pmPrice} ₽ за найденную позицию${geoNote} — если цена не найдена, 0 ₽`;
    }
    return "";
  }, [session, scenario, isCustomBatchScenario, geoRadiusEnabled]);
  const hasTickingJobs = useMemo(
    () => jobs.some((job) => job.status === "pending" || job.status === "running"),
    [jobs],
  );
  useEffect(() => {
    if (!hasTickingJobs) return;
    setNowTs(Date.now());
    const timer = setInterval(() => {
      if (typeof document === "undefined" || !document.hidden) {
        setNowTs(Date.now());
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [hasTickingJobs]);
  const jobsPageCount = Math.max(1, Math.ceil(jobsTotal / jobsPageSize));
  const jobsStart = jobsTotal ? (jobsPage - 1) * jobsPageSize + 1 : 0;
  const jobsEnd = Math.min(jobsTotal, jobsPage * jobsPageSize);
  const WORKSPACE_RECENT_LIMIT = 5;
  const isWorkspaceCollapsed =
    cabinetSection === "workspace" &&
    jobsPage === 1 &&
    !hasActiveJobFilters &&
    !showAllWorkspaceJobs &&
    jobs.length > WORKSPACE_RECENT_LIMIT;
  const visibleJobs = isWorkspaceCollapsed ? jobs.slice(0, WORKSPACE_RECENT_LIMIT) : jobs;
  const hasFindMoreSuppliers = jobs.some((job) => job.can_find_more_suppliers);

  async function loadSession(options?: { background?: boolean }) {
    const background = Boolean(options?.background);
    if (background && sessionBackgroundRequestRef.current) return null;
    if (background) sessionBackgroundRequestRef.current = true;
    try {
      const response = await fetch("/api/customer/auth/session", { credentials: "same-origin", cache: "no-store" });
      if (response.status === 401 || response.status === 404) {
        setSession(null);
        invoiceRequestVersion.current++;
        setCustomerInvoices([]);
        setCustomerInvoicesTotal(0);
        return null;
      }
      if (!response.ok && response.status >= 500) {
        if (background || session) return session;
        throw new Error("Сервер временно обновляется. Повторите попытку через пару секунд.");
      }
      const payload = await readJson<SessionPayload>(response);
      setSession(payload.authenticated ? payload : null);
      if (payload.authenticated) {
        if (!background) {
          loadCustomerInvoices();
        }
        if (payload.user?.phone) {
          setPayerPhone((cur) => cur || formatPhoneRu(payload.user?.phone || ""));
        }
        if (payload.user?.telegram_username) {
          setPayerTelegram((cur) => cur || (payload.user?.telegram_username ? (payload.user.telegram_username.startsWith("@") ? payload.user.telegram_username : `@${payload.user.telegram_username}`) : ""));
        }
      } else {
        invoiceRequestVersion.current++;
        setCustomerInvoices([]);
        setCustomerInvoicesTotal(0);
      }
      return payload;
    } catch (err) {
      if (background) return null;
      throw err;
    } finally {
      if (background) sessionBackgroundRequestRef.current = false;
      setSessionLoading(false);
    }
  }

  const HISTORY_PAGE_SIZE = 12;

  async function loadHistoryTransactions(page = 1) {
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const offset = Math.max(0, (page - 1) * HISTORY_PAGE_SIZE);
      const response = await fetch(`/api/customer/billing/transactions?limit=${HISTORY_PAGE_SIZE}&offset=${offset}`, {
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error("Не удалось загрузить историю операций");
      }
      const data = await readJson<{ items: CustomerBillingTransaction[]; total: number }>(response);
      setHistoryTransactions(Array.isArray(data?.items) ? data.items : []);
      setHistoryTotal(typeof data?.total === "number" ? data.total : 0);
      setHistoryPage(page);
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : "Ошибка загрузки истории операций");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function loadCustomerInvoices() {
    const version = ++invoiceRequestVersion.current;
    try {
      const response = await fetch(`/api/customer/invoices?limit=100&offset=0`, { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) return;
      const data = await readJson<{ invoices?: CustomerInvoice[]; total?: number }>(response);
      if (version !== invoiceRequestVersion.current) return;
      const next = Array.isArray(data.invoices) ? data.invoices : [];
      setCustomerInvoices(next);
      setCustomerInvoicesTotal(typeof data.total === "number" ? data.total : next.length);
    } catch {
      // Invoice history is supplementary; keep the cabinet usable if unavailable.
    }
  }

  async function uploadInvoiceProof(invoiceId: string, file: File) {
    setInvoiceProofUploading(invoiceId);
    setInvoiceProofMessage(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const csrf = session?.csrf_token || "";
      const response = await fetch(`/api/customer/invoices/${invoiceId}/proof`, {
        method: "POST",
        credentials: "same-origin",
        headers: csrf ? { "x-csrf-token": csrf } : {},
        body,
      });
      const data = await readJson<{ detail?: string; invoice?: CustomerInvoice }>(response);
      if (!response.ok) throw new Error(data.detail || "Не удалось отправить платёжку");
      setInvoiceProofMessage("Платёжка отправлена. Начисление будет выполнено после проверки оплаты.");
      await loadCustomerInvoices();
    } catch (err) {
      setInvoiceProofMessage(err instanceof Error ? err.message : "Не удалось отправить платёжку");
    } finally {
      setInvoiceProofUploading(null);
    }
  }

  async function handleStartOnlinePayment() {
    if (!customTopUpRub || customTopUpRub < 500) {
      setOnlinePayError("Минимальная сумма пополнения — 500 ₽");
      return;
    }
    const rawDigits = payerPhone.replace(/\D/g, "");
    if (!rawDigits || rawDigits.length < 10) {
      setOnlinePayError("Укажите контактный номер телефона для связи");
      return;
    }
    const matchedPkg =
      selectedTopUpPackage && selectedTopUpPackage.price_rub === customTopUpRub
        ? selectedTopUpPackage
        : null;
    setIsPayingOnline(true);
    setOnlinePayError("");
    try {
      const res = await fetch("/api/customer/payments/yookassa/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(session?.csrf_token ? { "X-CSRF-Token": session.csrf_token } : {}),
        },
        credentials: "same-origin",
        body: JSON.stringify({
          amount_rub: customTopUpRub,
          package_id: matchedPkg?.id || null,
          phone: payerPhone.trim(),
          telegram_username: payerTelegram.trim().replace(/^@/, ""),
        }),
      });

      const data = await readJson<{ detail?: string; confirmation_url?: string }>(res);
      if (!res.ok) {
        throw new Error(data?.detail || "Не удалось создать платёж в ЮKassa");
      }

      if (data?.confirmation_url) {
        trackGoal("checkout_started");
        window.location.href = data.confirmation_url;
      } else {
        throw new Error("Не получена ссылка для перехода на оплату");
      }
    } catch (err: any) {
      setIsPayingOnline(false);
      setOnlinePayError(err?.message || "Ошибка перехода к оплате");
    }
  }

  async function loadJobs(
    page = jobsPage,
    query = debouncedJobSearch,
    mode = jobModeFilter,
    policy = jobPolicyFilter,
    pageSize = jobsPageSize,
    background = false,
    statusFilter = jobStatusFilter,
  ) {
    if (!authenticated) return;
    if (background && (jobsForegroundRequestRef.current !== null || jobsBackgroundRequestRef.current !== null)) return;
    const requestId = ++jobsRequestIdRef.current;
    if (background) {
      jobsBackgroundRequestRef.current = requestId;
    } else {
      jobsForegroundRequestRef.current = requestId;
      setJobsLoading(true);
    }
    try {
      const offset = (page - 1) * pageSize;
      const params = new URLSearchParams({
        limit: String(pageSize),
        offset: String(offset),
        include_pagination: "true",
      });
      if (query.trim()) params.set("q", query.trim());
      if (mode) params.set("mode", mode);
      if (policy) params.set("policy", policy);
      if (statusFilter) params.set("status", statusFilter);

      const response = await fetch(
        `/api/customer/jobs?${params.toString()}`,
        CUSTOMER_JOB_FETCH_OPTIONS,
      );
      const payload = await readJson<CustomerJobsResponse | CustomerJob[]>(response);
      if (requestId !== jobsRequestIdRef.current) return;
      const rawItems = Array.isArray(payload) ? payload : (payload?.items || (payload as { jobs?: CustomerJob[] })?.jobs || []);
      const incomingItems: CustomerJob[] = Array.isArray(rawItems) ? rawItems : [];

      if (!hasInitializedJobsRef.current) {
        const map = new Map<string, string>();
        incomingItems.forEach((j) => map.set(j.id, j.status));
        prevJobStatusesRef.current = map;
        hasInitializedJobsRef.current = true;
      } else {
        const newlyFinished: CustomerJob[] = [];
        incomingItems.forEach((j) => {
          const prev = prevJobStatusesRef.current.get(j.id);
          const isDone = j.status === "done" || (j.has_result && j.status !== "pending" && j.status !== "running");
          const wasRunning = prev === "pending" || prev === "running";
          if (isDone && wasRunning) {
            newlyFinished.push(j);
          }
          prevJobStatusesRef.current.set(j.id, j.status);
        });

        if (newlyFinished.length > 0) {
          const latest = newlyFinished[0];
          if (notificationsEnabledRef.current) {
            playNotificationChime();
            setActiveToast({
              id: `${latest.id}-${Date.now()}`,
              jobId: latest.id,
              title: latest.human_title || latest.mode_label || "Задача выполнена",
              modeLabel: latest.mode_label,
            });
          }
        }
      }

      if (Array.isArray(payload)) {
        setJobs(payload);
        setJobsTotal(payload.length);
        return;
      }
      const total = typeof payload?.total === "number" ? payload.total : incomingItems.length;
      const limit = typeof payload?.limit === "number" && payload.limit > 0 ? payload.limit : 15;
      const nextPageCount = Math.max(1, Math.ceil(total / limit));
      setJobsTotal(total);
      if (page > nextPageCount) {
        setJobsPage(nextPageCount);
        return;
      }
      setJobs(incomingItems);
    } catch (err) {
      if (!background && requestId === jobsRequestIdRef.current) setError(err instanceof Error ? err.message : String(err));
    } finally {
      if (jobsBackgroundRequestRef.current === requestId) jobsBackgroundRequestRef.current = null;
      if (jobsForegroundRequestRef.current === requestId) {
        jobsForegroundRequestRef.current = null;
        setJobsLoading(false);
      }
    }
  }

  function syncSelectedFiles(files: File[]) {
    setSelectedFiles(files);
    if (!fileInputRef.current) return;
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    fileInputRef.current.files = transfer.files;
  }

  async function inspectBatchRegistryFile(
    file: File,
    requestedSheets?: string[],
    targetMode: "custom_batch_report" | "procurement_report" = "custom_batch_report"
  ) {
    if (!csrf) return;
    setBatchBusy(true);
    setBatchModalError("");
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("target_mode", targetMode);
      if (requestedSheets && requestedSheets.length > 0) {
        form.append("sheet_names_json", JSON.stringify(requestedSheets));
      }
      const res = await fetch("/api/customer/jobs/batch-report/preview", {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
        body: form,
      });
      const data = await readJson<{
        target_mode?: "custom_batch_report" | "procurement_report";
        is_registry: boolean;
        filename: string;
        sheet_name: string;
        sheet_names: string[];
        selected_sheets?: string[];
        requires_sheet_selection?: boolean;
        items: BatchRegistryPreviewItem[];
        max_items?: number;
        unit_price_kopeks: number;
        unit_price_rub: number;
        available_kopeks: number;
        available_rub: number;
      }>(res, { isUpload: true });
      const resolvedTargetMode = data.target_mode || targetMode;
      const minItemsToOpenModal =
        resolvedTargetMode === "procurement_report" && !(requestedSheets && requestedSheets.length > 0) ? 2 : 1;
      if (data.requires_sheet_selection && data.sheet_names.length > 1) {
        setBatchPreview({
          ...data,
          target_mode: resolvedTargetMode,
          file,
          items: [],
          requires_sheet_selection: true,
        });
        setBatchSelectedIds([]);
      } else if (data.is_registry && data.items.length >= minItemsToOpenModal) {
        const defaultCap =
          resolvedTargetMode === "procurement_report"
            ? 10
            : session?.user?.batch_report_max_items || 30;
        const limitCap = Math.max(1, data.max_items || defaultCap);
        setBatchPreview({
          ...data,
          target_mode: resolvedTargetMode,
          file,
          requires_sheet_selection: false,
        });
        setBatchSelectedIds(data.items.slice(0, limitCap).map((it) => it.id));
        clearSelectedFiles();
      } else if (requestedSheets && requestedSheets.length > 0) {
        setBatchModalError(
          "В выбранных вкладках не найдено таблицы с номерами извещений. Выберите другие вкладки или закройте окно, чтобы запустить файл как документацию одной закупки."
        );
      }
    } catch (err) {
      if (requestedSheets && requestedSheets.length > 0) {
        setBatchModalError(err instanceof Error ? err.message : String(err));
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setBatchBusy(false);
    }
  }

  async function inspectBatchTextNotices(
    rawText: string,
    targetMode: "custom_batch_report" | "procurement_report" = "custom_batch_report"
  ) {
    if (!csrf) return null;
    const form = new FormData();
    form.append("text_notices", rawText);
    form.append("target_mode", targetMode);
    const res = await fetch("/api/customer/jobs/batch-report/preview", {
      method: "POST",
      credentials: "same-origin",
      headers: { "x-csrf-token": csrf },
      body: form,
    });
    return await readJson<{
      target_mode?: "custom_batch_report" | "procurement_report";
      is_registry: boolean;
      filename: string;
      sheet_name: string;
      sheet_names: string[];
      selected_sheets?: string[];
      requires_sheet_selection?: boolean;
      items: BatchRegistryPreviewItem[];
      max_items?: number;
      unit_price_kopeks: number;
      unit_price_rub: number;
      available_kopeks: number;
      available_rub: number;
    }>(res);
  }

  async function confirmBatchReportLaunch() {
    if (!csrf || !batchPreview) return;
    const chosenSet = new Set(batchSelectedIds);
    const selectedItems = batchPreview.items.filter((it) => chosenSet.has(it.id));
    if (selectedItems.length === 0) {
      setBatchModalError("Отметьте хотя бы одну закупку галочкой.");
      return;
    }
    const isFullAnalysis = batchPreview.target_mode === "procurement_report";
    setBatchBusy(true);
    setBatchModalError("");
    try {
      const endpoint = isFullAnalysis
        ? "/api/customer/jobs/procurement-report/batch-create"
        : "/api/customer/jobs/batch-report/create";
      const res = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "x-csrf-token": csrf },
        body: JSON.stringify({
          filename: batchPreview.filename,
          items: selectedItems,
        }),
      });
      await readJson(res);
      trackGoal("task_started", { module: isFullAnalysis ? "procurement_report" : "custom_batch_report" });
      setBatchPreview(null);
      setBatchSelectedIds([]);
      setSourceUrls("");
      clearSelectedFiles();
      setMessage(
        isFullAnalysis
          ? `Запущено анализов документации: ${selectedItems.length} шт.`
          : `Запущена экспресс-оценка: ${selectedItems.length} зак.`
      );
      setJobsPage(1);
      await loadSession({ background: true });
      await loadJobs(1).catch(() => {});
    } catch (err) {
      setBatchModalError(err instanceof Error ? err.message : String(err));
    } finally {
      setBatchBusy(false);
    }
  }

  async function openBatchReportReader(jobId: string, resetIndex = true) {
    try {
      const res = await fetch(`/api/customer/jobs/${jobId}/batch-report`, CUSTOMER_JOB_FETCH_OPTIONS);
      const data = await readJson<BatchReportReaderData>(res);
      setBatchReaderData(data);
      if (resetIndex) {
        const firstReady = data.items.findIndex((it) => it.status === "completed");
        setBatchReaderActiveIdx(firstReady >= 0 ? firstReady : 0);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function downloadBatchItemDocx(jobId: string, itemIndex: number, fallbackFilename: string) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        `/api/customer/jobs/${jobId}/batch-report/download/${itemIndex}`,
        CUSTOMER_JOB_FETCH_OPTIONS
      );
      if (!response.ok) throw new Error(parseError(await response.text()));
      downloadBlob(
        await response.blob(),
        filenameFromResponse(response, fallbackFilename || "Анализ_закупки.docx")
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!batchReaderData) return;
    if (batchReaderData.status !== "pending" && batchReaderData.status !== "running") return;
    const timer = window.setInterval(() => {
      void openBatchReportReader(batchReaderData.job_id, false);
    }, 4000);
    return () => window.clearInterval(timer);
  }, [batchReaderData?.job_id, batchReaderData?.status]);

  function filesFromList(fileList: FileList | null) {
    const files = Array.from(fileList || []);
    const limited = selectedCopy.multipleFiles ? files.slice(0, maxFiles) : files.slice(0, 1);
    syncSelectedFiles(limited);
    const registryTargetMode: "custom_batch_report" | "procurement_report" | null =
      Boolean(session?.user?.allowed_custom_batch_report) &&
      (scenario === "custom_batch_report" ||
        (scenario === "procurement_report" && !session?.user?.custom_report_separate_tab))
        ? "custom_batch_report"
        : scenario === "procurement_report"
          ? "procurement_report"
          : null;
    if (registryTargetMode && limited.length === 1) {
      const ext = limited[0].name.toLowerCase();
      const isInspectable = [
        ".xlsx",
        ".xls",
        ".csv",
        ".docx",
        ".doc",
        ".pdf",
        ".txt",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
      ].some((suffix) => ext.endsWith(suffix));
      if (isInspectable) {
        void inspectBatchRegistryFile(limited[0], undefined, registryTargetMode);
      }
    }
  }

  function clearSelectedFiles() {
    setSelectedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function selectScenario(next: Scenario, options?: { preserveInput?: boolean }) {
    const prevScenario = scenario;
    const preserve = Boolean(options?.preserveInput);
    const sourceTargetModes: Scenario[] = ["procurement_report", "analysis_and_suppliers", "custom_batch_report"];
    const textTargetModes: Scenario[] = ["supplier_search", "exact_product", "price_monitoring"];

    setCabinetSection("workspace");
    setScenario(next);
    if (typeof window !== "undefined") {
      try {
        sessionStorage.removeItem("tenderlex_pending_launcher_scenario");
        localStorage.setItem("tenderlex_cabinet_launcher_scenario", next);
      } catch {}
    }
    if (!preserve) {
      setGeoRadiusEnabled(false);
      setDeliveryCity("");
      setGeoRadiusKm(300);
      setText("");
      setSourceUrls("");
      clearSelectedFiles();
    } else if (sourceTargetModes.includes(prevScenario) && textTargetModes.includes(next)) {
      if (!text.trim() && sourceUrls.trim()) {
        setText(sourceUrls.trim());
        setSourceUrls("");
      }
    } else if (textTargetModes.includes(prevScenario) && sourceTargetModes.includes(next)) {
      if (!sourceUrls.trim() && text.trim()) {
        setSourceUrls(text.trim());
        setText("");
      }
    }
    if (next === "procurement_report") setSupplierSearchPolicy("normal");
  }

  function handleFileInput(event: ChangeEvent<HTMLInputElement>) {
    filesFromList(event.currentTarget.files);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragActive(false);
    filesFromList(event.dataTransfer.files);
  }

  useEffect(() => {
    const authEvent = window.location.hash.slice(1);
    if (authEvent === "registration_success" || authEvent === "login_success") {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }

    const params = new URLSearchParams(window.location.search);
    const scenarioParam = params.get("scenario") || params.get("mode");
    const validScenarios: Scenario[] = ["procurement_report", "supplier_search", "analysis_and_suppliers", "exact_product", "price_monitoring", "custom_batch_report"];
    if (scenarioParam === "doc_analysis") {
      setScenario("procurement_report");
      if (typeof window !== "undefined") {
        try {
          sessionStorage.setItem("tenderlex_pending_launcher_scenario", "procurement_report");
          localStorage.setItem("tenderlex_cabinet_launcher_scenario", "procurement_report");
        } catch {}
      }
    } else if (scenarioParam && validScenarios.includes(scenarioParam as Scenario)) {
      setScenario(scenarioParam as Scenario);
      if (typeof window !== "undefined") {
        try {
          sessionStorage.setItem("tenderlex_pending_launcher_scenario", scenarioParam);
          localStorage.setItem("tenderlex_cabinet_launcher_scenario", scenarioParam);
        } catch {}
      }
    } else if (typeof window !== "undefined") {
      try {
        const pendingScenario = sessionStorage.getItem("tenderlex_pending_launcher_scenario");
        const savedScenario = pendingScenario || localStorage.getItem("tenderlex_cabinet_launcher_scenario");
        if (pendingScenario) sessionStorage.removeItem("tenderlex_pending_launcher_scenario");
        if (savedScenario && validScenarios.includes(savedScenario as Scenario)) {
          setScenario(savedScenario as Scenario);
        }
      } catch {}
    }
    const textParam = params.get("text") || params.get("q");
    if (textParam) {
      setText(textParam.trim());
    }
    const refParam = params.get("ref");
    if (refParam && typeof window !== "undefined") {
      localStorage.setItem("tenderlex_ref", refParam.trim());
    }
    const utmSourceParam = (params.get("utm_source") || "").trim().toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 40);
    const utmCampaignParam = (params.get("utm_campaign") || "").trim().replace(/[^a-zA-Z0-9_.:-]/g, "").slice(0, 80);
    if (utmSourceParam && typeof window !== "undefined") {
      try {
        if (window.localStorage.getItem(ANALYTICS_CONSENT_KEY) === "granted") {
          sessionStorage.setItem("tenderlex_utm_source", utmSourceParam);
          if (utmCampaignParam) sessionStorage.setItem("tenderlex_utm_campaign", utmCampaignParam);
        }
      } catch {}
    }
    const hashStr = typeof window !== "undefined" && window.location.hash ? window.location.hash.replace(/^#/, "") : "";
    const hashParams = new URLSearchParams(hashStr);

    const tgAuthResult = hashParams.get("tgAuthResult") || params.get("tgAuthResult");
    const tgId = hashParams.get("id") || params.get("id");
    const tgHash = hashParams.get("hash") || params.get("hash");

    if (tgAuthResult || (tgId && tgHash)) {
      setBusy(true);
      setTelegramVerifying(true);
      setSessionLoading(true);

      const payload: Record<string, string> = {};
      if (tgAuthResult) {
        payload.tgAuthResult = tgAuthResult;
      } else {
        const source = tgId && hashParams.get("id") ? hashParams : params;
        source.forEach((val, key) => {
          payload[key] = val;
        });
      }
      if (typeof window !== "undefined") {
        const storedRef = localStorage.getItem("tenderlex_ref");
        if (storedRef) payload.ref = storedRef;
      }

      fetch("/api/customer/auth/telegram/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then(async (res) => {
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Ошибка верификации Telegram");
          }
          return res.json();
        })
        .then((respData: { is_new?: boolean; success?: boolean }) => {
          if (respData.success) trackGoal(respData.is_new ? "registration_success" : "login_success");
          window.history.replaceState(null, "", window.location.pathname + (params.toString() ? `?${params.toString()}` : ""));
          return loadSession();
        })
        .catch((err) => {
          window.history.replaceState(null, "", window.location.pathname + (params.toString() ? `?${params.toString()}` : ""));
          setError(err instanceof Error ? err.message : "Не удалось подтвердить авторизацию через Telegram.");
          setSessionLoading(false);
        })
        .finally(() => {
          setBusy(false);
          setTelegramVerifying(false);
        });
    } else {
      loadSession().then((payload) => {
        if (payload?.authenticated && (authEvent === "registration_success" || authEvent === "login_success")) trackGoal(authEvent);
      }).catch((err) => setError(err instanceof Error ? err.message : String(err)));
    }

    const verified = params.get("email_verified");
    const verifyToken = params.get("email_verify_token");
    const resetTokenParam = params.get("reset_token");
    const authError = params.get("auth_error");
    const modeParam = params.get("mode") || (window.location.hash === "#login" ? "login" : window.location.hash === "#register" ? "register" : null);
    if (modeParam === "login" || modeParam === "register" || modeParam === "reset") {
      setAuthMode(modeParam);
    }
    if (verified === "1") setMessage("Email подтверждён. Теперь можно запускать задачи.");
    if (verified === "0") setError("Ссылка подтверждения недействительна или устарела.");
    if (authError === "yandex_declined") {
      setError("Вход через Яндекс ID был отменён.");
      params.delete("auth_error");
    } else if (authError === "telegram_invalid" || authError === "telegram_no_data") {
      setError("Не удалось подтвердить авторизацию через Telegram. Попробуйте войти снова.");
      params.delete("auth_error");
    } else if (authError === "invalid_state") {
      setError("Сессия авторизации устарела. Попробуйте войти снова.");
      params.delete("auth_error");
    } else if (authError === "fetch_failed" || authError === "user_creation_failed" || authError === "no_code") {
      setError("Не удалось войти через выбранный сервис. Попробуйте ещё раз или используйте email.");
      params.delete("auth_error");
    }
    if (verifyToken) {
      confirmEmailToken(verifyToken).catch((err) => setError(err instanceof Error ? err.message : String(err)));
      params.delete("email_verify_token");
    }
    if (resetTokenParam) {
      setResetToken(resetTokenParam);
      setAuthMode("new_password");
      setError("");
      setMessage("Задайте новый пароль для входа в кабинет.");
      params.delete("reset_token");
    }
    if (verified) {
      params.delete("email_verified");
    }
    if (verified || verifyToken || authError || resetTokenParam) {
      const nextQuery = params.toString();
      window.history.replaceState(null, "", `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`);
    }
  }, []);

  useEffect(() => {
    if (session?.user?.email && !emailEditOpen) setEmailDraft(session.user.email);
  }, [emailEditOpen, session?.user?.email]);

  useEffect(() => {
    if (authenticated) loadJobs(jobsPage, debouncedJobSearch, jobModeFilter, jobPolicyFilter, jobsPageSize, false, jobStatusFilter);
    else setJobsLoading(false);
    return () => {
      // Responses from the previous page, filters or session must never replace current tasks.
      jobsRequestIdRef.current += 1;
      jobsForegroundRequestRef.current = null;
      jobsBackgroundRequestRef.current = null;
    };
  }, [authenticated, jobsPage, debouncedJobSearch, jobModeFilter, jobPolicyFilter, jobsPageSize, jobStatusFilter]);

  useEffect(() => {
    if (!authenticated) return;
    const timer = window.setInterval(() => {
      if (typeof document !== "undefined" && document.hidden) return;
      loadJobs(jobsPage, debouncedJobSearch, jobModeFilter, jobPolicyFilter, jobsPageSize, true, jobStatusFilter);
      if (activeJobs) loadSession({ background: true }).catch(() => {});
    }, activeJobs ? 3000 : 7000);
    return () => window.clearInterval(timer);
  }, [authenticated, jobsPage, debouncedJobSearch, jobModeFilter, jobPolicyFilter, jobsPageSize, activeJobs, jobStatusFilter]);

  useEffect(() => {
    if (!findMoreConfirmJob) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setFindMoreConfirmJob(null);
      }
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [findMoreConfirmJob]);

  useEffect(() => {
    try {
      const savedViewed = localStorage.getItem("tenderlex_viewed_job_ids");
      if (savedViewed) {
        const parsed = JSON.parse(savedViewed);
        if (Array.isArray(parsed)) setViewedJobIds(parsed);
      }
      const savedNotif = localStorage.getItem("tenderlex_notifications_enabled");
      if (savedNotif !== null) {
        setNotificationsEnabled(savedNotif === "true");
      }
      const savedDismissed = sessionStorage.getItem("tenderlex_dismissed_strategy_jobs");
      if (savedDismissed) {
        const list = JSON.parse(savedDismissed);
        if (Array.isArray(list)) {
          list.forEach((id) => dismissedStrategyJobIdsRef.current.add(String(id)));
        }
      }
    } catch {
      // ignore
    }
  }, []);

  // Auto-open strategy modal when specification needs customer decision
  useEffect(() => {
    if (strategyConfirmJob) return;
    const pendingJob = jobs.find(
      (j) =>
        j.awaiting_customer_confirmation &&
        j.confirmation_kind === "multi_item_strategy" &&
        !dismissedStrategyJobIdsRef.current.has(j.id)
    );
    if (pendingJob) {
      openStrategyConfirmModal(pendingJob);
    }
  }, [jobs, strategyConfirmJob]);

  useEffect(() => {
    if (exactSelectionJob) return;
    const pendingJob = jobs.find((job) => {
      return isAwaitingPositionSelection(job) && !dismissedExactSelectionJobIdsRef.current.has(exactSelectionKey(job));
    });
    if (pendingJob) openExactSelectionModal(pendingJob);
  }, [jobs, exactSelectionJob]);

  useEffect(() => {
    if (!exactSelectionJob) return;
    const refreshedJob = jobs.find((job) => job.id === exactSelectionJob.id);
    if (!refreshedJob || !isAwaitingPositionSelection(refreshedJob)) {
      setExactSelectionJob(null);
    } else if (positionSelectionForJob(refreshedJob)?.revision !== positionSelectionForJob(exactSelectionJob)?.revision) {
      openExactSelectionModal(refreshedJob);
    }
  }, [jobs, exactSelectionJob]);

  // Close modal on Escape
  useEffect(() => {
    if (!strategyConfirmJob) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        skipOrDismissStrategyModal();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [strategyConfirmJob]);

  useEffect(() => {
    if (!exactSelectionJob) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") dismissExactSelectionModal();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [exactSelectionJob]);

  useEffect(() => {
    if (!activeToast) return;
    const timer = setTimeout(() => setActiveToast(null), 15000);
    return () => clearTimeout(timer);
  }, [activeToast]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const paymentStatus = params.get("payment_status");
    const paymentId = params.get("tenderlex_payment_id") || params.get("payment_id");

    if (paymentStatus === "check" && paymentId) {
      setCheckingPaymentStatus(true);
      const cleanUrl = () => {
        const url = new URL(window.location.href);
        url.searchParams.delete("payment_status");
        url.searchParams.delete("tenderlex_payment_id");
        url.searchParams.delete("payment_id");
        window.history.replaceState({}, document.title, url.pathname + (url.search || ""));
      };

      async function verifyPayment(retries = 3) {
        try {
          const res = await fetch(`/api/customer/payments/${paymentId}/status`, {
            credentials: "same-origin",
            cache: "no-store",
          });
          if (res.ok) {
            const data = await readJson<{
              status?: string;
              amount_rub?: number;
              bonus_rub?: number;
              total_credit_rub?: number;
            }>(res);
            if (data?.status === "succeeded") {
              setPaymentSuccessNotice({
                amountRub: data.amount_rub || 0,
                bonusRub: data.bonus_rub || 0,
                totalCreditRub: data.total_credit_rub || 0,
              });
              await loadSession();
              cleanUrl();
              setCheckingPaymentStatus(false);
              return;
            }
          }
          if (retries > 0) {
            setTimeout(() => void verifyPayment(retries - 1), 2500);
          } else {
            setCheckingPaymentStatus(false);
            cleanUrl();
          }
        } catch {
          setCheckingPaymentStatus(false);
          cleanUrl();
        }
      }

      void verifyPayment();
    }
  }, []);

  function toggleNotifications() {
    setNotificationsEnabled((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("tenderlex_notifications_enabled", String(next));
      } catch {}
      return next;
    });
  }

  function markJobAsViewed(jobId: string) {
    setViewedJobIds((prev) => {
      if (prev.includes(jobId)) return prev;
      const next = [jobId, ...prev].slice(0, 500);
      try {
        localStorage.setItem("tenderlex_viewed_job_ids", JSON.stringify(next));
      } catch {}
      return next;
    });
  }

  function scrollToJob(jobId: string) {
    markJobAsViewed(jobId);
    const el = document.getElementById(`job-${jobId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("ring-2", "ring-teal-500", "bg-teal-50/70");
      setTimeout(() => {
        el.classList.remove("ring-2", "ring-teal-500", "bg-teal-50/70");
      }, 2500);
    }
  }

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (authMode === "new_password") {
        if (!resetToken) {
          setError("Ссылка сброса пароля недействительна. Запросите новую ссылку.");
          return;
        }
        if (password.length < 10) {
          setError("Пароль должен содержать не менее 10 символов.");
          return;
        }
        if (password !== newPasswordConfirm) {
          setError("Пароли не совпадают.");
          return;
        }
        const response = await fetch("/api/customer/auth/password-reset/confirm", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: resetToken, new_password: password }),
        });
        const payload = await readJson<SessionPayload>(response);
        setSession(payload);
        if (payload.authenticated) trackGoal("login_success");
        setPassword("");
        setNewPasswordConfirm("");
        setResetToken("");
        setAuthMode("login");
        setMessage(payload.message || "Пароль успешно обновлён. Вы вошли в личный кабинет.");
        return;
      }
      if (authMode === "register") {
        if (password.length < 10) {
          setError("Пароль должен содержать не менее 10 символов.");
          return;
        }
        if (password !== registerPasswordConfirm) {
          setError("Пароли не совпадают.");
          return;
        }
      }
      if (authMode === "reset") {
        const response = await fetch("/api/customer/auth/password-reset/request", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        const payload = await readJson<{ message?: string }>(response);
        setMessage(payload.message || "Мы отправили ссылку для сброса пароля на ваш email.");
        return;
      }
      if (authMode === "register") await pendingSeoEntry();
      let tokenToSend = challengeToken;
      if (authMode === "register" && !tokenToSend) {
        try {
          const chRes = await fetch("/api/public/auth/challenge", { credentials: "same-origin", cache: "no-store" });
          if (chRes.ok) {
            const chData = await chRes.json();
            if (chData?.token) {
              tokenToSend = String(chData.token);
              setChallengeToken(tokenToSend);
            }
          }
        } catch {}
      }
      const response = await fetch(`/api/customer/auth/${authMode}`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          name,
          phone: authMode === "register" ? registerPhone : "",
          website: authMode === "register" ? website : "",
          challenge_token: authMode === "register" ? tokenToSend : "",
          ref: authMode === "register" ? (typeof window !== "undefined" ? localStorage.getItem("tenderlex_ref") || "" : "") : "",
          utm_source: authMode === "register" ? (typeof window !== "undefined" ? sessionStorage.getItem("tenderlex_utm_source") || "" : "") : "",
          utm_campaign: authMode === "register" ? (typeof window !== "undefined" ? sessionStorage.getItem("tenderlex_utm_campaign") || "" : "") : "",
          terms_accepted: termsAccepted,
          personal_data_consent: personalDataConsent,
          legal_version: "2026-07-17",
        }),
      });
      const payload = await readJson<SessionPayload>(response);
      setSession(payload);
      if (payload.authenticated) trackGoal(authMode === "register" ? "registration_success" : "login_success");
      setPassword("");
      setRegisterPasswordConfirm("");
      setWebsite("");
      setMessage(
        authMode === "register"
          ? (payload.message || "Вы можете сразу запустить первую пробную задачу или демо-пример. Для следующих задач подтвердите email по ссылке из письма.")
          : "",
      );
    } catch (err) {
      if (authMode === "register") {
        fetch("/api/public/auth/challenge", { credentials: "same-origin", cache: "no-store" })
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (data?.token) setChallengeToken(String(data.token));
          })
          .catch(() => {});
      }
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function waitForSearchEntryBeforeOAuth(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
    const pending = pendingSeoEntry();
    if (!pending) return;
    event.preventDefault();
    const destination = event.currentTarget.href;
    void pending.then(() => window.location.assign(destination));
  }

  function handleSwitchAuthMode(mode: "login" | "register" | "reset") {
    setError("");
    setMessage("");
    setPassword("");
    setRegisterPasswordConfirm("");
    setNewPasswordConfirm("");
    setShowPassword(false);
    setShowConfirmPassword(false);
    setEmail("");
    setName("");
    setAuthMode(mode);
  }

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setChangePasswordError("");
    setChangePasswordSuccess("");
    if (!currentPassword) {
      setChangePasswordError("Введите текущий пароль.");
      return;
    }
    if (changeNewPassword.length < 10) {
      setChangePasswordError("Новый пароль должен содержать не менее 10 символов.");
      return;
    }
    if (changeNewPassword !== changeNewPasswordConfirm) {
      setChangePasswordError("Новые пароли не совпадают.");
      return;
    }
    setChangePasswordBusy(true);
    try {
      const res = await fetch("/api/customer/auth/change-password", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "x-csrf-token": csrf,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: changeNewPassword,
        }),
      });
      const data = await readJson<{ ok?: boolean; message?: string }>(res);
      setChangePasswordSuccess(data.message || "Пароль успешно изменён.");
      setCurrentPassword("");
      setChangeNewPassword("");
      setChangeNewPasswordConfirm("");
      setTimeout(() => {
        setChangePasswordOpen(false);
        setChangePasswordSuccess("");
      }, 1500);
    } catch (err) {
      setChangePasswordError(err instanceof Error ? err.message : String(err));
    } finally {
      setChangePasswordBusy(false);
    }
  }

  async function logout() {
    if (!csrf) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/customer/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      await readJson(response);
      setSession(null);
      invoiceRequestVersion.current++;
      setCustomerInvoices([]);
      setCustomerInvoicesTotal(0);
      setJobs([]);
      setJobsPage(1);
      setJobsTotal(0);
      setFindMoreConfirmJob(null);
      setBatchPreview(null);
      setBatchSelectedIds([]);
      setBatchReaderData(null);
      // Clean all user data from memory/form inputs
      setName("");
      setEmail("");
      setPassword("");
      setRegisterPasswordConfirm("");
      setNewPasswordConfirm("");
      setResetToken("");
      setText("");
      setSourceUrls("");
      setSelectedFiles([]);
      setDeliveryCity("");
      setTermsAccepted(false);
      setPersonalDataConsent(false);
      setShowPassword(false);
      setShowConfirmPassword(false);
      setAuthMode("login");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteAccount() {
    if (!csrf || deleteAccountBusy) return;
    setDeleteAccountBusy(true);
    setChangePasswordError("");
    try {
      const response = await fetch("/api/customer/account/delete", {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      await readJson(response);
      setChangePasswordOpen(false);
      setDeleteAccountConfirm(false);
      setSession(null);
      invoiceRequestVersion.current++;
      setCustomerInvoices([]);
      setCustomerInvoicesTotal(0);
      setJobs([]);
      setJobsPage(1);
      setJobsTotal(0);
      setAuthMode("login");
      setMessage("Аккаунт и персональные данные удалены.");
    } catch (err) {
      setChangePasswordError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeleteAccountBusy(false);
    }
  }

  async function resendVerification() {
    if (!csrf) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch("/api/customer/auth/verify-email/request", {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      const payload = await readJson<{ message?: string }>(response);
      setMessage(payload.message || "Письмо отправлено. Проверьте почту.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirmEmailToken(token: string) {
    if (!token) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch("/api/customer/auth/verify-email/confirm", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const payload = await readJson<{ user?: SessionPayload["user"] }>(response);
      if (payload.user) {
        setSession((current) => (current ? { ...current, user: payload.user } : current));
      }
      setMessage("Email подтверждён. Теперь можно запускать задачи.");
      trackGoal("email_verified");
      await loadSession();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function changeAccountEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrf) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch("/api/customer/auth/email", {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "x-csrf-token": csrf },
        body: JSON.stringify({ email: emailDraft }),
      });
      const payload = await readJson<SessionPayload>(response);
      setSession(payload);
      setEmailEditOpen(false);
      setMessage(payload.message || "Email обновлён. Проверьте письмо для подтверждения.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (session?.authenticated && scenario === "custom_batch_report" && !hasSeparateCustomBatchTab) {
      setScenario("procurement_report");
    }
  }, [session?.authenticated, scenario, hasSeparateCustomBatchTab]);

  async function submitJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrf) return;
    if (isSubmittingJobRef.current) return;
    const nonFailedOrCancelledCount = jobs.filter((j) => j.status !== "failed" && j.status !== "cancelled").length;
    if (!emailVerified && nonFailedOrCancelledCount > 0) {
      setError("Подтвердите email по ссылке из письма, чтобы запускать следующие задачи.");
      return;
    }
    const useCustomBatchFlow = isCustomBatchScenario;
    const filesSig = selectedFiles.map((file) => `${file.name}:${file.size}:${file.lastModified}`).join("|");
    const submitSignature = `${selectedMode}::${useCustomBatchFlow ? "custom" : "std"}::${supplierSearchPolicy}::${geoScope}::${multiItemMode}::${acceptsText ? text.trim() : ""}::${acceptsSources ? sourceUrls.trim() : ""}::${filesSig}`;
    const now = Date.now();
    if (lastJobSubmitRef.current.signature === submitSignature && now - lastJobSubmitRef.current.ts < 4000) {
      return;
    }
    isSubmittingJobRef.current = true;
    lastJobSubmitRef.current = { signature: submitSignature, ts: now };
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (useCustomBatchFlow && selectedFiles.length === 0 && sourceUrls.trim()) {
        const previewData = await inspectBatchTextNotices(sourceUrls, "custom_batch_report");
        if (previewData && previewData.is_registry && previewData.items.length > 0) {
          const singleItem = previewData.items.length === 1 ? previewData.items[0] : null;
          const isSingleStandardEis = Boolean(
            singleItem &&
            (/^\d{11}$|^\d{19}$/.test(singleItem.notice_number.trim()) || singleItem.eis_url)
          );
          if (previewData.items.length > 1 || !isSingleStandardEis) {
            const limitCap = Math.max(1, previewData.max_items || session?.user?.batch_report_max_items || 30);
            setBatchPreview({
              ...previewData,
              target_mode: "custom_batch_report",
              file: null,
              requires_sheet_selection: false,
            });
            setBatchSelectedIds(previewData.items.slice(0, limitCap).map((it) => it.id));
            setBatchModalError("");
            lastJobSubmitRef.current = { signature: "", ts: 0 };
            return;
          }
        }
      } else if (!useCustomBatchFlow && selectedMode === "procurement_report" && selectedFiles.length === 0 && sourceUrls.trim()) {
        const candidateTokens = sourceUrls
          .split(/[\r\n,;|\t ]+/)
          .map((t) => t.trim())
          .filter((t) => /\d{6,}/.test(t) || /^https?:\/\//i.test(t));
        if (candidateTokens.length >= 2) {
          const previewData = await inspectBatchTextNotices(sourceUrls, "procurement_report");
          if (previewData && previewData.is_registry && previewData.items.length >= 2) {
            const limitCap = Math.max(1, previewData.max_items || 10);
            setBatchPreview({
              ...previewData,
              target_mode: "procurement_report",
              file: null,
              requires_sheet_selection: false,
            });
            setBatchSelectedIds(previewData.items.slice(0, limitCap).map((it) => it.id));
            setBatchModalError("");
            lastJobSubmitRef.current = { signature: "", ts: 0 };
            return;
          }
        }
      }

      const form = new FormData();
      form.append("mode", selectedMode);
      form.append("supplier_search_policy", selectedMode === "procurement_report" ? "normal" : supplierSearchPolicy);
      if (useCustomBatchFlow && selectedMode === "procurement_report") {
        form.append("use_custom_prompt", "true");
      }
      const isMinpromPolicy = supplierSearchPolicy === "minprom_registry_only" || supplierSearchPolicy === "minprom_registry_priority";
      const effectiveGeoScope = isMinpromPolicy ? "ru" : geoScope;
      form.append("geo_scope", effectiveGeoScope);
      form.append("multi_item_mode", multiItemMode);
      if (geoRadiusEnabled && session?.user?.allowed_geo_radius && ["supplier_search", "analysis_and_suppliers", "price_monitoring"].includes(selectedMode)) {
        if (!deliveryCity.trim() || !Number.isInteger(geoRadiusKm) || geoRadiusKm < 10 || geoRadiusKm > 5000) {
          throw new Error("Укажите город и целый радиус от 10 до 5000 км.");
        }
        form.append("delivery_city", deliveryCity.trim());
        form.append("geo_radius_km", String(geoRadiusKm));
      }
      form.append("text", acceptsText ? text : "");
      form.append("source_urls", acceptsSources ? sourceUrls : "");
      form.append("target_suppliers", "0");
      selectedFiles.forEach((file) => form.append("files", file));
      const response = await fetch("/api/customer/jobs", {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
        body: form,
      });
      const payload = await readJson<{ batch: boolean; count: number }>(response, { isUpload: true });
      trackGoal("task_started", { module: selectedMode });
      setText("");
      setSourceUrls("");
      setDeliveryCity("");
      setGeoRadiusEnabled(false);
      clearSelectedFiles();
      setMessage(payload.batch ? `Запущено задач: ${payload.count}.` : "Задача запущена.");
      setJobsPage(1);
      await loadSession({ background: true });
      await loadJobs(1).catch(() => {});
    } catch (err) {
      lastJobSubmitRef.current = { signature: "", ts: 0 };
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      isSubmittingJobRef.current = false;
      setBusy(false);
    }
  }

  async function downloadJob(job: CustomerJob) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/download`, CUSTOMER_JOB_FETCH_OPTIONS);
      if (!response.ok) throw new Error(parseError(await response.text()));
      downloadBlob(await response.blob(), filenameFromResponse(response, `${job.human_title || "result"}.zip`));
      trackGoal("result_downloaded", { module: job.mode });
      await loadSession();
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function downloadJobFile(job: CustomerJob, file: CustomerJob["result_files"][number]) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/download/${encodeURIComponent(file.kind)}`, CUSTOMER_JOB_FETCH_OPTIONS);
      if (!response.ok) throw new Error(parseError(await response.text()));
      downloadBlob(await response.blob(), filenameFromResponse(response, file.filename || `${job.human_title || "result"}`));
      trackGoal("result_downloaded", { module: job.mode });
      await loadSession();
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function openQuoteRequest(job: CustomerJob, file: CustomerJob["result_files"][number]) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/quote-request`, CUSTOMER_JOB_FETCH_OPTIONS);
      const payload = await readJson<{ content: string; filename: string }>(response);
      const raw = payload.content || "";
      const tableItems = extractQuoteTableItems(raw);
      const allIndexes = tableItems.map((it) => it.index);
      setQuoteItemSearch("");
      setQuoteRequestModal({
        job,
        html: quoteMarkdownToHtml(raw, allIndexes),
        filename: payload.filename || file.filename || "Запрос коммерческого предложения.docx",
        copied: false,
        rawMarkdown: raw,
        items: tableItems,
        selectedItemIndexes: allIndexes,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function applyQuoteRequestItemIndexes(safeIndexes: number[]) {
    if (!quoteRequestModal) return;
    const raw = quoteRequestModal.rawMarkdown || "";
    const nextHtml = quoteMarkdownToHtml(raw, safeIndexes);
    if (quoteEditorRef.current) {
      quoteEditorRef.current.innerHTML = nextHtml;
    }
    setQuoteRequestModal({
      ...quoteRequestModal,
      html: nextHtml,
      selectedItemIndexes: safeIndexes,
      copied: false,
    });
  }

  function toggleQuoteRequestItem(index: number) {
    if (!quoteRequestModal) return;
    const current = quoteRequestModal.selectedItemIndexes;
    const nextIndexes = current.includes(index)
      ? current.filter((i) => i !== index)
      : [...current, index].sort((a, b) => a - b);
    const safeIndexes = nextIndexes.length > 0 ? nextIndexes : [index];
    applyQuoteRequestItemIndexes(safeIndexes);
  }

  function toggleAllQuoteRequestItems(selectAll: boolean) {
    if (!quoteRequestModal) return;
    const items = quoteRequestModal.items || [];
    const safeIndexes = selectAll ? items.map((it) => it.index) : (items.length > 0 ? [items[0].index] : []);
    applyQuoteRequestItemIndexes(safeIndexes);
  }

  function selectFirstNQuoteRequestItems(count: number) {
    if (!quoteRequestModal) return;
    const items = quoteRequestModal.items || [];
    const safeIndexes = items.slice(0, count).map((it) => it.index);
    applyQuoteRequestItemIndexes(safeIndexes.length > 0 ? safeIndexes : (items.length > 0 ? [items[0].index] : []));
  }

  function invertQuoteRequestItems() {
    if (!quoteRequestModal) return;
    const items = quoteRequestModal.items || [];
    const current = new Set(quoteRequestModal.selectedItemIndexes);
    const inverted = items.filter((it) => !current.has(it.index)).map((it) => it.index);
    applyQuoteRequestItemIndexes(inverted.length > 0 ? inverted : items.map((it) => it.index));
  }

  function selectMatchingQuoteRequestItems(matchingIndexes: number[]) {
    if (!quoteRequestModal) return;
    const items = quoteRequestModal.items || [];
    const current = new Set(quoteRequestModal.selectedItemIndexes);
    matchingIndexes.forEach((idx) => current.add(idx));
    const next = items.filter((it) => current.has(it.index)).map((it) => it.index);
    applyQuoteRequestItemIndexes(next.length > 0 ? next : (items.length > 0 ? [items[0].index] : []));
  }

  async function downloadEditedQuoteRequest() {
    if (!csrf || !quoteRequestModal) return;
    const content = quoteHtmlToMarkdown(quoteEditorRef.current);
    setBusy(true);
    setError("");
    try {
      const items = quoteRequestModal.items || [];
      const selected = quoteRequestModal.selectedItemIndexes;
      let targetFilename = quoteRequestModal.filename || "Запрос коммерческого предложения.docx";
      if (selected.length === 1 && items[selected[0]]) {
        targetFilename = `Запрос КП - ${items[selected[0]].name.slice(0, 50).replace(/[\\/*?:"<>|]/g, "_")}.docx`;
      } else if (selected.length < items.length) {
        targetFilename = `Запрос КП - ${selected.length} поз.docx`;
      }
      const response = await fetch(`/api/customer/jobs/${quoteRequestModal.job.id}/quote-request/docx`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "x-csrf-token": csrf },
        body: JSON.stringify({ content, filename: targetFilename }),
      });
      if (!response.ok) throw new Error(parseError(await response.text()));
      downloadBlob(await response.blob(), filenameFromResponse(response, targetFilename));
      trackGoal("result_downloaded", { module: "supplier_search" });
      await loadSession();
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function copyQuoteRequestText() {
    if (!quoteRequestModal) return;
    const textContent = quoteHtmlToReadableText(quoteEditorRef.current);
    const htmlContent = quoteEditorRef.current?.innerHTML || "";
    try {
      await writeClipboardText(textContent, htmlContent);
      setQuoteRequestModal({ ...quoteRequestModal, copied: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function cancelJob(job: CustomerJob) {
    if (!csrf) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/cancel`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      await readJson(response);
      setMessage("Задача отменена.");
      await loadSession();
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function acceptPartial(job: CustomerJob) {
    if (!csrf) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/accept-partial`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      if (!response.ok) throw new Error(parseError(await response.text()));
      await readJson(response);
      setMessage(job.confirmation_kind === "admin_supplement_offer" ? "Дополненный отчёт успешно принят и оплачен. Файлы готовы к скачиванию." : "Отчёт принят. Результат можно скачать в строке задачи.");
      await loadSession();
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function declinePartial(job: CustomerJob) {
    if (!csrf) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/decline-partial`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      if (!response.ok) throw new Error(parseError(await response.text()));
      await readJson(response);
      setMessage(job.confirmation_kind === "admin_supplement_offer" ? "Вы отказались от предложения. Списание средств не производилось." : "Отказ зафиксирован.");
      await loadSession();
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function chooseStrategy(job: CustomerJob, mode: "balanced" | "per_item", itemIds?: string[]) {
    if (!csrf) return;
    setStrategySubmittingJobId(job.id);
    setStrategyError("");
    dismissedStrategyJobIdsRef.current.add(job.id);
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/choose-strategy`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "x-csrf-token": csrf,
          "content-type": "application/json",
        },
        body: JSON.stringify({
          multi_item_mode: mode,
          selected_item_ids: mode === "per_item" ? itemIds : undefined,
        }),
      });
      if (!response.ok) throw new Error(parseError(await response.text()));
      await readJson(response);
      const countLabel = mode === "per_item" && itemIds?.length ? ` (${itemIds.length} поз.)` : "";

      // Check if there are other pending strategy jobs in the queue
      const otherPending = jobs.filter(
        (j) =>
          j.id !== job.id &&
          j.awaiting_customer_confirmation &&
          j.confirmation_kind === "multi_item_strategy" &&
          !dismissedStrategyJobIdsRef.current.has(j.id)
      );

      if (otherPending.length > 0) {
        setMessage(`Стратегия для «${job.human_title || "ТЗ"}» сохранена (${mode === "balanced" ? "Сбалансированный" : `Попозиционный${countLabel}`}).`);
        openStrategyConfirmModal(otherPending[0]);
      } else {
        setStrategyConfirmJob(null);
        setMessage(`Стратегия поиска сохранена (${mode === "balanced" ? "Сбалансированный поиск" : `Попозиционный поиск${countLabel}`}). Поиск поставщиков продолжается.`);
      }

      await loadSession();
      await loadJobs();
    } catch (err) {
      setStrategyError(err instanceof Error ? err.message : String(err));
    } finally {
      setStrategySubmittingJobId(null);
    }
  }

  async function findMoreSuppliers(job: CustomerJob) {
    if (!csrf) return;
    setBusy(true);
    setError("");
    setMessage("");
    const promptToSend = findMorePrompt.trim();
    setFindMoreConfirmJob(null);
    setFindMorePrompt("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/find-more-suppliers`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "x-csrf-token": csrf,
          "content-type": "application/json",
        },
        body: JSON.stringify({ additional_prompt: promptToSend }),
      });
      const payload = await readJson<{ message?: string; job?: CustomerJob }>(response);
      trackGoal("task_started", { module: "supplier_search" });
      setMessage(payload.message || "Запущен дополнительный поиск поставщиков.");
      setJobsPage(1);
      await loadSession();
      await loadJobs(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function startSupplierSearchFromExact(job: CustomerJob) {
    if (!csrf) return;
    setBusy(true);
    setError("");
    setMessage("");
    const policyToSend = startSupplierSearchPolicy;
    const multiItemToSend = startSupplierSearchMultiItemMode;
    const includeAlts = startSupplierSearchAlternatives;
    const promptToSend = startSupplierSearchPrompt.trim();
    if (startSupplierGeoEnabled && (!startSupplierCity.trim() || !Number.isInteger(startSupplierRadius) || startSupplierRadius < 10 || startSupplierRadius > 5000)) {
      setError("Укажите город и целый радиус от 10 до 5000 км.");
      setBusy(false);
      return;
    }
    setStartSupplierSearchConfirmJob(null);
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/start-supplier-search`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "x-csrf-token": csrf,
          "content-type": "application/json",
        },
        body: JSON.stringify({
          supplier_search_policy: policyToSend,
          multi_item_mode: multiItemToSend,
          include_alternatives: includeAlts,
          additional_prompt: promptToSend,
          ...(startSupplierGeoEnabled && session?.user?.allowed_geo_radius ? { delivery_city: startSupplierCity.trim(), geo_radius_km: startSupplierRadius } : {}),
        }),
      });
      const payload = await readJson<{ message?: string; job?: CustomerJob }>(response);
      trackGoal("task_started", { module: "supplier_search" });
      setMessage(payload.message || "Поиск поставщиков успешно запущен на основе подобранных товаров и аналогов.");
      setJobsPage(1);
      await loadSession();
      await loadJobs(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function retryJob(job: CustomerJob, policy?: string, multiItemModeParam?: string) {
    try {
      setBusy(true);
      setError("");
      setMessage("");
      const params = new URLSearchParams();
      if (policy) params.set("policy", policy);
      if (multiItemModeParam) params.set("multi_item_mode", multiItemModeParam);
      const qs = params.toString() ? `?${params.toString()}` : "";
      const url = `/api/customer/jobs/${job.id}/retry${qs}`;
      const res = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: csrf ? { "x-csrf-token": csrf } : {},
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || "Не удалось перезапустить задачу");
      }
      setMessage(data.message || "Задача успешно перезапущена");
      await loadJobs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ошибка перезапуска задачи");
    } finally {
      setBusy(false);
      setRetryConfirmJob(null);
    }
  }

  if (sessionLoading) {
    return (
      <main className="tl-cabinet tl-cabinet-loading cabinet-page min-h-screen bg-slate-50/70 flex flex-col items-center justify-center p-4 sm:p-8 font-sans text-slate-900">
        <header className="tl-cabinet-auth-header w-full max-w-5xl mx-auto flex items-center justify-between pb-6 mb-8 border-b border-slate-200/80">
          <a className="flex items-center gap-3 font-extrabold text-slate-900 text-xl hover:text-teal-700 transition-colors" href="/">
            <Image src="/tenderlex-logo.png" alt="TenderLex" width={36} height={36} priority />
            <span>TenderLex</span>
          </a>
          <a className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-700 hover:text-teal-700 transition-colors bg-slate-100 hover:bg-slate-200 px-4 py-2 rounded-xl border border-slate-200 shadow-2xs" href="/">
            На главную
          </a>
        </header>

        <section className="w-full max-w-md bg-white p-8 sm:p-10 rounded-3xl border border-slate-200/90 shadow-xl flex flex-col items-center justify-center text-center space-y-4 my-auto">
          <Loader2 size={40} className="animate-spin text-teal-600" aria-hidden="true" />
          <div className="space-y-1.5">
            <h2 className="text-base sm:text-lg font-bold text-slate-900">
              {telegramVerifying ? "Вход через Telegram..." : "Загрузка кабинета..."}
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 leading-relaxed">
              {telegramVerifying
                ? "Проверяем данные авторизации и открываем сессию"
                : "Синхронизируем данные вашего аккаунта"}
            </p>
          </div>
        </section>
      </main>
    );
  }

  if (!authenticated) {
    return (
      <main className="tl-cabinet tl-cabinet-auth cabinet-page min-h-screen bg-slate-50/70 flex flex-col items-center justify-center p-4 sm:p-8 font-sans text-slate-900">
        <header className="tl-cabinet-auth-header w-full max-w-5xl mx-auto flex items-center justify-between pb-6 mb-8 border-b border-slate-200/80">
          <a className="flex items-center gap-3 font-extrabold text-slate-900 text-xl hover:text-teal-700 transition-colors" href="/">
            <Image src="/tenderlex-logo.png" alt="TenderLex" width={36} height={36} priority />
            <span>TenderLex</span>
          </a>
          <a className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-700 hover:text-teal-700 transition-colors bg-slate-100 hover:bg-slate-200 px-4 py-2 rounded-xl border border-slate-200 shadow-2xs" href="/">
            На главную
          </a>
        </header>

        <section className="tl-cabinet-auth-card w-full max-w-5xl grid lg:grid-cols-12 gap-8 items-stretch bg-white p-6 sm:p-10 rounded-3xl border border-slate-200/90 shadow-xl">
          <div className="lg:col-span-7 flex flex-col justify-between space-y-6 pr-0 lg:pr-4">
            <div className="space-y-4">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 leading-tight">
                {authMode === "register" ? "Проверьте первое ТЗ бесплатно" : "Работайте с закупками прямо на сайте"}
              </h1>
              <p className="text-sm text-slate-600 leading-relaxed">
                {authMode === "register"
                  ? initialTrialBalanceRub > 0
                    ? `Создайте кабинет за 15 секунд — дарим ${initialTrialBalanceRub.toLocaleString("ru-RU")} ₽ на баланс для бесплатного тестирования на ваших спецификациях. Без привязки карты.`
                    : "Создайте кабинет за 15 секунд, чтобы запускать анализ закупок и поиск поставщиков на ваших спецификациях."
                  : "Войдите в кабинет, чтобы запускать анализ закупок, искать поставщиков и скачивать готовые результаты."}
              </p>
            </div>

            <div className="space-y-3 pt-2">
              <article className="flex items-start gap-4 p-4 bg-slate-50/80 border border-slate-200/80 rounded-2xl text-left">
                <div className="w-10 h-10 rounded-xl bg-teal-100/80 text-teal-700 flex items-center justify-center shrink-0 border border-teal-200/60 mt-0.5">
                  <Search size={20} aria-hidden="true" />
                </div>
                <div className="space-y-0.5">
                  <strong className="text-sm font-bold text-slate-900 block">Поиск поставщиков</strong>
                  <span className="text-xs text-slate-500 leading-normal block">контакты прямых производителей и поставщиков для запроса КП</span>
                </div>
              </article>

              <article className="flex items-start gap-4 p-4 bg-slate-50/80 border border-slate-200/80 rounded-2xl text-left">
                <div className="w-10 h-10 rounded-xl bg-teal-100/80 text-teal-700 flex items-center justify-center shrink-0 border border-teal-200/60 mt-0.5">
                  <Layers size={20} aria-hidden="true" />
                </div>
                <div className="space-y-0.5">
                  <strong className="text-sm font-bold text-slate-900 block">Подбор товара и аналогов</strong>
                  <span className="text-xs text-slate-500 leading-normal block">российские аналоги по ТЗ и сверка с реестром Минпромторга / ЕАЭС</span>
                </div>
              </article>

              <article className="flex items-start gap-4 p-4 bg-slate-50/80 border border-slate-200/80 rounded-2xl text-left">
                <div className="w-10 h-10 rounded-xl bg-teal-100/80 text-teal-700 flex items-center justify-center shrink-0 border border-teal-200/60 mt-0.5">
                  <FileText size={20} aria-hidden="true" />
                </div>
                <div className="space-y-0.5">
                  <strong className="text-sm font-bold text-slate-900 block">Анализ документации</strong>
                  <span className="text-xs text-slate-500 leading-normal block">разбор условий закупки, выявление скрытых рисков, сроков и штрафов</span>
                </div>
              </article>

              <div className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-teal-50 border border-teal-200/80 text-xs font-semibold text-teal-800">
                <CheckCircle2 size={15} className="text-teal-600 shrink-0" />
                <span>Оплата для юрлиц по счёту с УПД через Диадок / СБИС</span>
              </div>
            </div>
          </div>

          <form className="tl-cabinet-auth-form lg:col-span-5 bg-slate-50/70 p-6 sm:p-8 rounded-2xl border border-slate-200/80 space-y-4 flex flex-col justify-center" onSubmit={submitAuth}>
            {authMode === "reset" ? (
              <div className="space-y-1 pb-2 border-b border-slate-200/80 mb-2">
                <h2 className="text-lg font-bold text-slate-900">Восстановить доступ</h2>
                <p className="text-xs text-slate-500">Укажите email кабинета. Мы пришлём ссылку для сброса пароля.</p>
              </div>
            ) : authMode === "new_password" ? (
              <div className="space-y-1 pb-2 border-b border-slate-200/80 mb-2">
                <h2 className="text-lg font-bold text-slate-900">Новый пароль</h2>
                <p className="text-xs text-slate-500">Задайте новый пароль для входа в кабинет TenderLex.</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 p-1.5 bg-slate-200/70 rounded-xl mb-3 text-xs font-bold" role="tablist" aria-label="Режим входа">
                <button
                  type="button"
                  className={`py-2 px-3 rounded-lg transition-all cursor-pointer flex items-center justify-center text-center ${authMode === "register" ? "bg-white text-teal-800 shadow-2xs font-extrabold" : "text-slate-600 hover:text-slate-900"}`}
                  onClick={() => handleSwitchAuthMode("register")}
                >
                  Регистрация
                </button>
                <button
                  type="button"
                  className={`py-2 px-3 rounded-lg transition-all cursor-pointer flex items-center justify-center text-center ${authMode === "login" ? "bg-white text-slate-900 shadow-2xs font-extrabold" : "text-slate-600 hover:text-slate-900"}`}
                  onClick={() => handleSwitchAuthMode("login")}
                >
                  Вход
                </button>
              </div>
            )}

            {authMode !== "reset" && authMode !== "new_password" ? (
              <div className="space-y-2.5 pt-1">
                <a
                  href="/api/customer/auth/telegram/login"
                  onClick={waitForSearchEntryBeforeOAuth}
                  className="w-full min-h-[46px] py-2.5 px-4 bg-[#24A1DE] hover:bg-[#1f93cc] active:bg-[#1a83b7] text-white rounded-xl font-bold text-sm shadow-2xs transition-all flex items-center justify-center text-center gap-3 cursor-pointer select-none group"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="shrink-0" aria-hidden="true">
                    <circle cx="12" cy="12" r="12" fill="#FFFFFF" />
                    <path fill="#24A1DE" d="M17.5 7.5L6.5 11.75C5.75 12.05 5.75 12.47 6.36 12.65L9.18 13.53L15.71 9.41C16.02 9.22 16.3 9.33 16.07 9.53L10.78 14.3L10.59 17.15C10.87 17.15 11 17.02 11.16 16.86L12.53 15.53L15.38 17.63C15.91 17.92 16.29 17.77 16.42 17.14L18.29 8.33C18.48 7.57 18 7.22 17.5 7.5Z" />
                  </svg>
                  <span>{authMode === "login" ? "Войти через Telegram" : "Создать кабинет через Telegram в 1 клик"}</span>
                </a>

                <a
                  href="/api/customer/auth/yandex/login"
                  onClick={waitForSearchEntryBeforeOAuth}
                  className="w-full min-h-[46px] py-2.5 px-4 bg-white hover:bg-slate-50 active:bg-slate-100 text-slate-800 hover:text-slate-950 border border-slate-300 rounded-xl font-bold text-sm shadow-2xs transition-all flex items-center justify-center text-center gap-3 cursor-pointer select-none group"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="shrink-0" aria-hidden="true">
                    <circle cx="12" cy="12" r="12" fill="#FC3F1D" />
                    <path fill="#FFFFFF" d="M13.32 7.02h-1.63c-1.39 0-2.19.74-2.19 1.86 0 1.15.58 1.8 1.48 2.5l-1.84 5.6h1.75l1.67-5.07h.76v5.07h1.66V7.02zm-1.55 3.53h-.45c-.56 0-.89-.34-.89-.88 0-.52.33-.87.89-.87h.45v1.75z" />
                  </svg>
                  <span>{authMode === "login" ? "Войти с Яндекс ID" : "Создать кабинет через Яндекс ID"}</span>
                </a>

                <p className="text-[11px] leading-snug text-slate-500 text-center px-1">
                  Продолжая через Telegram или Яндекс ID, вы принимаете{" "}
                  <a className="text-teal-700 underline hover:text-teal-900 font-medium" href="/terms" target="_blank" rel="noreferrer">
                    публичную оферту
                  </a>
                  , даёте{" "}
                  <a className="text-teal-700 underline hover:text-teal-900 font-medium" href="/personal-data" target="_blank" rel="noreferrer">
                    согласие на обработку ПДн
                  </a>{" "}
                  и ознакомлены с{" "}
                  <a className="text-teal-700 underline hover:text-teal-900 font-medium" href="/privacy" target="_blank" rel="noreferrer">
                    Политикой конфиденциальности
                  </a>
                  .
                </p>

                {authMode === "register" && initialTrialBalanceRub > 0 ? (
                  <div className="flex items-center justify-center gap-2 text-xs text-teal-900 font-semibold bg-teal-50 border border-teal-200/80 rounded-xl py-2 px-3 text-center">
                    <Gift size={14} className="text-teal-700 shrink-0" aria-hidden="true" />
                    <span>Стартовый баланс {initialTrialBalanceRub.toLocaleString("ru-RU")} ₽ зачисляется сразу при создании кабинета</span>
                  </div>
                ) : null}

                <div className="relative flex py-1 items-center">
                  <div className="flex-grow border-t border-slate-200" />
                  <span className="shrink mx-3 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">или по email</span>
                  <div className="flex-grow border-t border-slate-200" />
                </div>
              </div>
            ) : null}

            {authMode === "register" ? (
              <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-700 w-full">
                <span>Имя</span>
                <input
                  className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 shadow-2xs"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  autoComplete="name"
                  placeholder="Ваше имя"
                />
              </label>
            ) : null}

            {authMode === "register" ? (
              <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-700 w-full">
                <span className="flex items-center justify-between">
                  <span>Телефон / WhatsApp</span>
                  <span className="text-[11px] font-normal text-slate-400">для связи по расчетам (необязательно)</span>
                </span>
                <input
                  className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 shadow-2xs"
                  value={registerPhone}
                  onChange={(event) => setRegisterPhone(event.target.value)}
                  type="tel"
                  autoComplete="tel"
                  placeholder="+7 (___) ___-__-__"
                />
              </label>
            ) : null}

            {authMode === "register" ? (
              <label className="hidden" aria-hidden="true">
                Сайт
                <input value={website} onChange={(event) => setWebsite(event.target.value)} tabIndex={-1} autoComplete="off" />
              </label>
            ) : null}

            {authMode !== "new_password" ? (
              <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-700 w-full">
                <span>Email</span>
                <input
                  className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 shadow-2xs"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  type="email"
                  autoComplete="email"
                  placeholder="name@company.ru"
                  required
                />
              </label>
            ) : null}

            {authMode === "new_password" ? (
              <>
                <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-700 w-full">
                  <span>Новый пароль</span>
                  <div className="relative w-full">
                    <input
                      className="w-full pl-3.5 pr-10 py-2.5 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 shadow-2xs"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      minLength={10}
                      placeholder="Не менее 10 символов"
                      required
                    />
                    <button
                      type="button"
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 cursor-pointer"
                      onClick={() => setShowPassword((prev) => !prev)}
                      tabIndex={-1}
                      aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </label>
                <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-700 w-full">
                  <span>Повторите новый пароль</span>
                  <div className="relative w-full">
                    <input
                      className="w-full pl-3.5 pr-10 py-2.5 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 shadow-2xs"
                      value={newPasswordConfirm}
                      onChange={(event) => setNewPasswordConfirm(event.target.value)}
                      type={showConfirmPassword ? "text" : "password"}
                      autoComplete="new-password"
                      minLength={10}
                      placeholder="Повторите новый пароль"
                      required
                    />
                    <button
                      type="button"
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 cursor-pointer"
                      onClick={() => setShowConfirmPassword((prev) => !prev)}
                      tabIndex={-1}
                      aria-label={showConfirmPassword ? "Скрыть пароль" : "Показать пароль"}
                    >
                      {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </label>
              </>
            ) : authMode === "register" ? (
              <>
                <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-700 w-full">
                  <span>Пароль (не менее 10 символов)</span>
                  <div className="relative w-full">
                    <input
                      className="w-full pl-3.5 pr-10 py-2.5 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 shadow-2xs"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      minLength={10}
                      placeholder="Не менее 10 символов"
                      required
                    />
                    <button
                      type="button"
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 cursor-pointer"
                      onClick={() => setShowPassword((prev) => !prev)}
                      tabIndex={-1}
                      aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </label>
                <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-700 w-full">
                  <span>Повторите пароль</span>
                  <div className="relative w-full">
                    <input
                      className="w-full pl-3.5 pr-10 py-2.5 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 shadow-2xs"
                      value={registerPasswordConfirm}
                      onChange={(event) => setRegisterPasswordConfirm(event.target.value)}
                      type={showConfirmPassword ? "text" : "password"}
                      autoComplete="new-password"
                      minLength={10}
                      placeholder="Повторите пароль"
                      required
                    />
                    <button
                      type="button"
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 cursor-pointer"
                      onClick={() => setShowConfirmPassword((prev) => !prev)}
                      tabIndex={-1}
                      aria-label={showConfirmPassword ? "Скрыть пароль" : "Показать пароль"}
                    >
                      {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </label>
              </>
            ) : authMode === "login" ? (
              <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-700 w-full">
                <span>Пароль</span>
                <div className="relative w-full">
                  <input
                    className="w-full pl-3.5 pr-10 py-2.5 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 shadow-2xs"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="••••••••"
                    required
                  />
                  <button
                    type="button"
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 cursor-pointer"
                    onClick={() => setShowPassword((prev) => !prev)}
                    tabIndex={-1}
                    aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </label>
            ) : null}

            {authMode === "register" ? (
              <div className="space-y-2.5 pt-2 border-t border-slate-200/60">
                <label className="flex items-start gap-2.5 text-xs text-slate-700 font-medium leading-snug cursor-pointer select-none">
                  <input
                    className="sr-only"
                    type="checkbox"
                    checked={termsAccepted}
                    onChange={(event) => setTermsAccepted(event.target.checked)}
                    required
                  />
                  <div
                    className={`w-4 h-4 rounded border flex items-center justify-center transition-all shrink-0 mt-0.5 ${
                      termsAccepted
                        ? "bg-emerald-600 border-emerald-600 text-white shadow-2xs"
                        : "bg-white border-slate-300 hover:border-emerald-500"
                    }`}
                  >
                    {termsAccepted ? <Check size={11} strokeWidth={3.5} className="text-white" /> : null}
                  </div>
                  <span>
                    Я принимаю <a className="text-teal-700 underline font-semibold hover:text-teal-900" href="/terms" target="_blank" rel="noreferrer">публичную оферту</a>.
                  </span>
                </label>
                <label className="flex items-start gap-2.5 text-xs text-slate-700 font-medium leading-snug cursor-pointer select-none">
                  <input
                    className="sr-only"
                    type="checkbox"
                    checked={personalDataConsent}
                    onChange={(event) => setPersonalDataConsent(event.target.checked)}
                    required
                  />
                  <div
                    className={`w-4 h-4 rounded border flex items-center justify-center transition-all shrink-0 mt-0.5 ${
                      personalDataConsent
                        ? "bg-emerald-600 border-emerald-600 text-white shadow-2xs"
                        : "bg-white border-slate-300 hover:border-emerald-500"
                    }`}
                  >
                    {personalDataConsent ? <Check size={11} strokeWidth={3.5} className="text-white" /> : null}
                  </div>
                  <span>
                    Даю согласие на <a className="text-teal-700 underline font-semibold hover:text-teal-900" href="/personal-data" target="_blank" rel="noreferrer">обработку персональных данных</a> и ознакомлен с <a className="text-teal-700 underline font-semibold hover:text-teal-900" href="/privacy" target="_blank" rel="noreferrer">политикой</a>.
                  </span>
                </label>
              </div>
            ) : null}

            {error ? <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs font-bold text-rose-700">{error}</div> : null}
            {message ? <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-bold text-emerald-800">{message}</div> : null}

            <button
              className="w-full px-8 py-3.5 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white text-sm font-bold rounded-xl shadow-md transition-all flex items-center justify-center gap-2.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed mt-2"
              type="submit"
              disabled={busy}
            >
              {busy ? <Loader2 size={18} className="animate-spin" aria-hidden="true" /> : null}
              <span>
                {authMode === "reset"
                  ? "Отправить ссылку на почту"
                  : authMode === "new_password"
                  ? "Сохранить новый пароль и войти"
                  : authMode === "login"
                  ? "Войти"
                  : initialTrialBalanceRub > 0
                  ? `Создать кабинет и получить ${initialTrialBalanceRub.toLocaleString("ru-RU")} ₽`
                  : "Создать кабинет"}
              </span>
            </button>

            {authMode === "new_password" ? (
              <button
                className="w-full text-center text-xs font-bold text-teal-700 hover:text-teal-900 transition-colors py-2 border-t border-slate-200/60 mt-2 block cursor-pointer"
                type="button"
                onClick={() => {
                  setResetToken("");
                  handleSwitchAuthMode("login");
                }}
              >
                Отмена / Ко входу
              </button>
            ) : authMode === "login" ? (
              <button
                className="w-full text-center text-xs font-bold text-teal-700 hover:text-teal-900 transition-colors py-2 border-t border-slate-200/60 mt-2 block cursor-pointer"
                type="button"
                onClick={() => handleSwitchAuthMode("reset")}
              >
                Не помню пароль
              </button>
            ) : authMode === "reset" ? (
              <button
                className="w-full text-center text-xs font-bold text-teal-700 hover:text-teal-900 transition-colors py-2 border-t border-slate-200/60 mt-2 block cursor-pointer"
                type="button"
                onClick={() => handleSwitchAuthMode("login")}
              >
                Вернуться ко входу
              </button>
            ) : (
              <button
                className="w-full text-center text-xs font-bold text-slate-600 hover:text-teal-800 transition-colors py-2 border-t border-slate-200/60 mt-2 block cursor-pointer"
                type="button"
                onClick={() => handleSwitchAuthMode("login")}
              >
                Уже есть кабинет? <span className="text-teal-700 underline font-semibold">Войти</span>
              </button>
            )}
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="tl-cabinet cabinet-page min-h-screen font-sans text-slate-900">
      <aside className={`tl-cabinet-sidebar ${mobileToolsOpen ? "tl-cabinet-sidebar--open" : ""}`} aria-label="Навигация личного кабинета">
        {/* Compact Mobile Top Bar (< 1024px) */}
        <div className="tl-mobile-brand-row">
          <a className="inline-flex items-center gap-2 font-extrabold text-base text-slate-900" href="/">
            <Image src="/tenderlex-logo.png" alt="TenderLex" width={26} height={26} priority />
            <span>TenderLex</span>
          </a>
          <a
            href="/"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-xs font-semibold text-slate-600 hover:text-slate-900"
          >
            <span>На сайт</span>
          </a>
        </div>

        {/* Primary Workspace Tools & Results Navigation */}
        <div className="tl-sidebar-panel">
          <a className="tl-sidebar-brand" href="/">
            <Image src="/tenderlex-logo.png" alt="TenderLex" width={28} height={28} priority />
            <span>TenderLex</span>
          </a>

          <div className="tl-sidebar-group">
            <div className="tl-sidebar-group-label">Инструменты</div>
            {(() => {
              const coreTools: Array<{ id: Scenario; label: string; icon: LucideIcon }> = scenarioOptions.map(({ id, label, icon }) => ({
                id,
                label,
                icon,
              }));
              const extraTools: Array<{ id: Scenario; label: string; icon: LucideIcon }> = [
                ...(session?.user?.allowed_price_monitoring
                  ? [{ id: "price_monitoring" as const, label: "Мониторинг цен", icon: Coins }]
                  : []),
                ...(hasSeparateCustomBatchTab
                  ? [{ id: "custom_batch_report" as const, label: "Экспресс-оценка", icon: FileSpreadsheet }]
                  : []),
              ];
              const renderSidebarTool = (item: { id: Scenario; label: string; icon: LucideIcon }) => {
                const ItemIcon = item.icon;
                const isSelected = cabinetSection === "workspace" && scenario === item.id;
                return (
                  <div
                    key={item.id}
                    role="tab"
                    tabIndex={0}
                    aria-selected={isSelected}
                    className="tl-sidebar-item"
                    onClick={() => selectScenario(item.id)}
                    onKeyDown={(event) => {
                      if (event.target !== event.currentTarget) return;
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        selectScenario(item.id);
                      }
                    }}
                  >
                    <span className="tl-sidebar-item__main">
                      <ItemIcon size={15} className="tl-sidebar-item__icon" aria-hidden="true" />
                      <span className="tl-sidebar-item__label">{item.label}</span>
                    </span>
                    <button
                      type="button"
                      className="tl-sidebar-item__help"
                      title={`Справка: как работает «${item.label}»`}
                      aria-label={`Справка: как работает «${item.label}»`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setHelpModalTab(item.id);
                        setShowHelpModal(true);
                      }}
                    >
                      <HelpCircle size={13} aria-hidden="true" />
                    </button>
                  </div>
                );
              };
              return (
                <div className="tl-sidebar-tools-list" role="tablist" aria-label="Рабочие инструменты">
                  {coreTools.map(renderSidebarTool)}
                  {extraTools.length > 0 ? (
                    <>
                      <div className="tl-sidebar-divider" role="presentation">
                        <span>Специнструменты</span>
                      </div>
                      {extraTools.map(renderSidebarTool)}
                    </>
                  ) : null}
                </div>
              );
            })()}
          </div>

          <div className="tl-sidebar-group pt-1 border-t border-slate-100">
            <div className="tl-sidebar-group-label">Результаты</div>
            <button
              type="button"
              className={`tl-sidebar-item ${cabinetSection === "jobs" ? "is-active" : ""}`}
              onClick={() => {
                setCabinetSection("jobs");
                if (typeof window !== "undefined") {
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }
              }}
            >
              <span className="tl-sidebar-item__main">
                <History size={15} className="tl-sidebar-item__icon" aria-hidden="true" />
                <span className="tl-sidebar-item__label">Мои задачи</span>
              </span>
              <span className="inline-flex items-center gap-1 shrink-0">
                {attentionJobsCount > 0 ? (
                  <span
                    className="tl-sidebar-badge-attention"
                    title={`Ждут вашего решения: ${attentionJobsCount}`}
                  >
                    {attentionJobsCount}
                  </span>
                ) : null}
                <span className="tl-sidebar-count">
                  {activeJobs > 0 ? (
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 inline-block" aria-hidden="true" />
                  ) : null}
                  <span>{jobsTotal}</span>
                </span>
              </span>
            </button>
          </div>
        </div>

        {/* Mobile Account Drawer Toggle (< 1024px) */}
        <button
          type="button"
          className="tl-cabinet-tools-toggle"
          aria-expanded={mobileToolsOpen}
          aria-controls="cabinet-account-tools"
          onClick={() => setMobileToolsOpen((open) => !open)}
        >
          <span className="tl-num">Баланс {formatBalanceRubles(session?.balance?.money?.available_kopeks || 0)}</span>
          <span className="inline-flex items-center gap-1.5">
            <span>{mobileToolsOpen ? "Скрыть меню" : "Меню кабинета"}</span>
            <ChevronDown size={15} className={`transition-transform ${mobileToolsOpen ? "rotate-180" : ""}`} aria-hidden="true" />
          </span>
        </button>

        {/* Balance, Tariffs, Billing & Support Block */}
        <div id="cabinet-account-tools" className="tl-cabinet-account-tools">
          <section className="tl-sidebar-panel tl-cabinet-toolbar" aria-label="Счёт и настройки">
            <button
              type="button"
              onClick={() => {
                const pkgs = session?.deposit_packages?.length ? session.deposit_packages : DEFAULT_DEPOSIT_PACKAGES;
                const defPkg = pkgs.find((p) => p.price_rub === 5000) || pkgs[2] || pkgs[0];
                setSelectedTopUpPackage(defPkg);
                setCustomTopUpRub(defPkg?.price_rub || 5000);
                setShowTopUpModal(true);
              }}
              className="tl-balance-box"
              title="Баланс аккаунта. Нажмите, чтобы пополнить"
            >
              <div>
                <span className="tl-balance-box__label">Баланс кабинета</span>
                <strong className="tl-balance-box__amount">
                  {formatBalanceRubles(session?.balance?.money?.available_kopeks || 0)}
                </strong>
              </div>
              <span className="tl-balance-box__cta">
                <PlusCircle size={12} aria-hidden="true" />
                <span>Пополнить</span>
              </span>
            </button>

            <div className="tl-sidebar-group">
              <button
                type="button"
                className={`tl-sidebar-item ${showTariffs ? "is-active" : ""}`}
                onClick={() => setShowTariffs((v) => !v)}
                aria-expanded={showTariffs}
                aria-controls="cabinet-tariffs"
              >
                <span className="tl-sidebar-item__main">
                  <Sliders size={15} className="tl-sidebar-item__icon" aria-hidden="true" />
                  <span className="tl-sidebar-item__label">Тарифы и пакеты</span>
                </span>
                <ChevronDown size={14} className={`text-slate-400 transition-transform ${showTariffs ? "rotate-180 text-teal-800" : ""}`} aria-hidden="true" />
              </button>

              <button
                type="button"
                className="tl-sidebar-item"
                onClick={() => {
                  setHistoryModalTab("transactions");
                  setShowHistoryModal(true);
                  loadHistoryTransactions(1);
                  loadCustomerInvoices();
                }}
                title="История операций и списаний"
              >
                <span className="tl-sidebar-item__main">
                  <Receipt size={15} className="tl-sidebar-item__icon" aria-hidden="true" />
                  <span className="tl-sidebar-item__label">Счета и операции</span>
                </span>
                {pendingInvoicesCount > 0 ? (
                  <span
                    className="tl-sidebar-badge-attention"
                    title={`Счетов к оплате: ${pendingInvoicesCount}`}
                  >
                    {pendingInvoicesCount}
                  </span>
                ) : null}
              </button>

              <button
                type="button"
                className="tl-sidebar-item"
                onClick={() => {
                  setShowApiModal(true);
                  loadCustomerApiKeys();
                }}
                title="API и интеграции (CRM, 1С, ИИ-ассистенты, MCP)"
              >
                <span className="tl-sidebar-item__main">
                  <Key size={15} className="tl-sidebar-item__icon" aria-hidden="true" />
                  <span className="tl-sidebar-item__label">API и интеграции</span>
                </span>
              </button>

              <button
                type="button"
                className="tl-sidebar-item"
                onClick={() => setShowReferralModal(true)}
                title="Пригласить коллегу: +1 000 ₽ на баланс за рекомендацию"
              >
                <span className="tl-sidebar-item__main">
                  <Gift size={15} className="tl-sidebar-item__icon" aria-hidden="true" />
                  <span className="tl-sidebar-item__label">Пригласить коллегу</span>
                </span>
                <span className="px-1.5 py-0.5 rounded bg-emerald-50 border border-emerald-200 text-emerald-900 font-bold text-[10px] leading-none whitespace-nowrap shrink-0 tl-num">
                  +1 000 ₽
                </span>
              </button>

              <button
                type="button"
                className="tl-sidebar-item"
                onClick={() => {
                  setHelpModalTab("workflow");
                  setShowHelpModal(true);
                }}
                title="Справка: подробное описание 4 функций и пошаговый алгоритм работы"
              >
                <span className="tl-sidebar-item__main">
                  <BookOpen size={15} className="tl-sidebar-item__icon" aria-hidden="true" />
                  <span className="tl-sidebar-item__label">Справка по функциям</span>
                </span>
              </button>
            </div>

            <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-0.5 text-[11px] text-slate-600">
              <button
                type="button"
                onClick={() => {
                  if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("open_tenderlex_chat"));
                    (window as unknown as { openTenderlexChat?: () => void }).openTenderlexChat?.();
                  }
                }}
                className="inline-flex items-center gap-1 py-1 px-1.5 rounded-md hover:bg-slate-100 text-slate-700 font-semibold cursor-pointer transition-colors"
                title="Онлайн-чат поддержки"
              >
                <MessageCircle size={13} className="text-[#174b3f] shrink-0" aria-hidden="true" />
                <span>Чат</span>
                {chatUnreadCount > 0 ? (
                  <span className="tl-sidebar-badge-unread" aria-label={`Новых сообщений: ${chatUnreadCount}`}>
                    {chatUnreadCount}
                  </span>
                ) : null}
              </button>

              {session?.contacts?.telegram_url ? (
                <a
                  href={session.contacts.telegram_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 py-1 px-1.5 rounded-md hover:bg-slate-100 text-slate-700 font-semibold transition-colors"
                  title="Написать в Telegram"
                >
                  <Send size={12} className="text-[#174b3f] shrink-0" aria-hidden="true" />
                  <span>Telegram</span>
                </a>
              ) : null}

              <a
                href={`mailto:${session?.contacts?.email || "info@tenderlex.ru"}`}
                className="inline-flex items-center gap-1 py-1 px-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors"
                title={`Написать на почту: ${session?.contacts?.email || "info@tenderlex.ru"}`}
              >
                <Mail size={12} className="shrink-0" aria-hidden="true" />
                <span>Почта</span>
              </a>
            </div>
          </section>
        </div>
      </aside>

      <div className="tl-cabinet-content">
        <header className="tl-cabinet-header">
          <div className="flex items-center gap-2 min-w-0 text-xs">
            <span className="text-slate-400 font-medium hidden sm:inline">
              {cabinetSection === "jobs" ? "Результаты" : "Инструмент"}
            </span>
            <span className="text-slate-300 hidden sm:inline" aria-hidden="true">/</span>
            <strong className="font-bold text-slate-800 truncate">
              {cabinetSection === "jobs" ? "Мои задачи" : selectedCopy.title}
            </strong>
            {activeJobs > 0 ? (
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-900 text-[11px] font-semibold shrink-0 tl-num">
                <Loader2 size={11} className="animate-spin text-amber-700" aria-hidden="true" />
                <span>В работе: {activeJobs}</span>
              </span>
            ) : null}
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              className={`inline-flex items-center justify-center w-8 h-8 rounded-lg border transition-colors cursor-pointer ${
                notificationsEnabled
                  ? "bg-slate-50 hover:bg-slate-100 text-teal-800 border-slate-200"
                  : "bg-slate-50 hover:bg-slate-100 text-slate-400 border-slate-200"
              }`}
              onClick={toggleNotifications}
              title={notificationsEnabled ? "Звуковые уведомления включены (нажмите, чтобы выключить)" : "Уведомления выключены (нажмите, чтобы включить)"}
              aria-label={notificationsEnabled ? "Выключить звуковые уведомления" : "Включить звуковые уведомления"}
            >
              {notificationsEnabled ? (
                <Bell size={14} aria-hidden="true" />
              ) : (
                <BellOff size={14} aria-hidden="true" />
              )}
            </button>

            <div className="relative" ref={profileMenuRef}>
              <button
                type="button"
                className={`inline-flex items-center gap-1.5 px-2 sm:px-2.5 h-8 rounded-lg border text-xs font-semibold transition-colors cursor-pointer max-w-[190px] sm:max-w-[260px] ${
                  profileMenuOpen
                    ? "bg-[#e7efe0] border-[#cde0be] text-[#103a31]"
                    : "bg-slate-50 hover:bg-slate-100 border-slate-200 text-slate-700"
                }`}
                onClick={() => setProfileMenuOpen((open) => !open)}
                aria-expanded={profileMenuOpen}
                aria-haspopup="menu"
                aria-label="Меню аккаунта"
                title={session?.user?.email || "Аккаунт"}
              >
                <User size={13} className="text-slate-500 shrink-0" aria-hidden="true" />
                <span className="truncate hidden sm:inline">{session?.user?.email}</span>
                <ChevronDown
                  size={13}
                  className={`text-slate-400 shrink-0 transition-transform ${profileMenuOpen ? "rotate-180 text-[#174b3f]" : ""}`}
                  aria-hidden="true"
                />
              </button>

              {profileMenuOpen ? (
                <div className="tl-profile-menu" role="menu" aria-label="Настройки аккаунта">
                  <div className="px-2.5 py-2 border-b border-slate-100 mb-1">
                    {session?.user?.name ? (
                      <div className="text-xs font-bold text-slate-900 truncate">{session.user.name}</div>
                    ) : null}
                    <div className="text-[11px] text-slate-500 truncate">{session?.user?.email}</div>
                  </div>

                  {session?.user?.has_telegram ? (
                    <div className="px-2.5 py-1.5 mb-1 rounded-lg bg-[#f4f8ef] border border-[#dfe5dc] text-[11px] text-[#103a31] flex items-center gap-1.5">
                      <CheckCircle2 size={13} className="text-[#174b3f] shrink-0" aria-hidden="true" />
                      <span className="truncate font-medium">
                        Telegram подключён{session.user.telegram_username ? ` (@${session.user.telegram_username})` : ""}
                      </span>
                    </div>
                  ) : (
                    <a
                      href="/api/customer/auth/telegram/login"
                      role="menuitem"
                      className="tl-profile-menu__item"
                      onClick={() => setProfileMenuOpen(false)}
                    >
                      <Send size={13} className="text-[#24A1DE] shrink-0" aria-hidden="true" />
                      <span>Привязать Telegram-бот</span>
                    </a>
                  )}

                  <button
                    type="button"
                    role="menuitem"
                    className="tl-profile-menu__item"
                    onClick={() => {
                      setProfileMenuOpen(false);
                      setChangePasswordOpen(true);
                      setChangePasswordError("");
                      setChangePasswordSuccess("");
                      setCurrentPassword("");
                      setChangeNewPassword("");
                      setChangeNewPasswordConfirm("");
                    }}
                  >
                    <Key size={13} className="text-slate-500 shrink-0" aria-hidden="true" />
                    <span>Сменить пароль</span>
                  </button>

                  <div className="my-1 border-t border-slate-100" role="separator" />

                  <button
                    type="button"
                    role="menuitem"
                    className="tl-profile-menu__item tl-profile-menu__item--danger"
                    onClick={() => {
                      setProfileMenuOpen(false);
                      logout();
                    }}
                    disabled={busy}
                    aria-label="Выйти"
                  >
                    <LogOut size={13} className="shrink-0" aria-hidden="true" />
                    <span>Выйти из кабинета</span>
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>

        {changePasswordOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4" onClick={() => !changePasswordBusy && setChangePasswordOpen(false)}>
            <section
              role="dialog"
              aria-modal="true"
              aria-labelledby="change-password-title"
              className="bg-white rounded-2xl shadow-xl border border-slate-200 max-w-md w-full p-5 sm:p-6 space-y-4 font-sans"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-3 pb-3 border-b border-slate-100">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-[#f4f8ef] border border-[#cde0be] text-[#174b3f] shrink-0">
                    <Key size={18} aria-hidden="true" />
                  </div>
                  <div>
                    <h2 id="change-password-title" className="text-base font-extrabold text-slate-900 leading-tight">
                      Смена пароля
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Обновите пароль для входа в личный кабинет
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  aria-label="Закрыть окно"
                  className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer shrink-0"
                  onClick={() => !changePasswordBusy && setChangePasswordOpen(false)}
                >
                  <X size={18} aria-hidden="true" />
                </button>
              </div>

              <form onSubmit={handleChangePassword} className="space-y-3.5">
                <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-700">
                  <span>Текущий пароль</span>
                  <div className="relative">
                    <input
                      type={showCurrentPwd ? "text" : "password"}
                      className="w-full px-3.5 py-2.5 pr-10 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f] shadow-2xs"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowCurrentPwd((v) => !v)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-700 cursor-pointer"
                      aria-label={showCurrentPwd ? "Скрыть текущий пароль" : "Показать текущий пароль"}
                    >
                      {showCurrentPwd ? <EyeOff size={15} aria-hidden="true" /> : <Eye size={15} aria-hidden="true" />}
                    </button>
                  </div>
                </label>
                <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-700">
                  <span>Новый пароль</span>
                  <div className="relative">
                    <input
                      type={showNewPwd ? "text" : "password"}
                      minLength={10}
                      className="w-full px-3.5 py-2.5 pr-10 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f] shadow-2xs"
                      value={changeNewPassword}
                      onChange={(e) => setChangeNewPassword(e.target.value)}
                      placeholder="Не менее 10 символов"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowNewPwd((v) => !v)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-700 cursor-pointer"
                      aria-label={showNewPwd ? "Скрыть новый пароль" : "Показать новый пароль"}
                    >
                      {showNewPwd ? <EyeOff size={15} aria-hidden="true" /> : <Eye size={15} aria-hidden="true" />}
                    </button>
                  </div>
                </label>
                <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-700">
                  <span>Повторите новый пароль</span>
                  <input
                    type={showNewPwd ? "text" : "password"}
                    minLength={10}
                    className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f] shadow-2xs"
                    value={changeNewPasswordConfirm}
                    onChange={(e) => setChangeNewPasswordConfirm(e.target.value)}
                    placeholder="Повторите новый пароль"
                    required
                  />
                </label>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] font-semibold pt-0.5">
                  <span className={`inline-flex items-center gap-1 ${changeNewPassword.length >= 10 ? "text-emerald-700" : "text-slate-400"}`}>
                    <CheckCircle2 size={12} aria-hidden="true" />
                    <span>Минимум 10 символов</span>
                  </span>
                  <span className={`inline-flex items-center gap-1 ${changeNewPassword.length > 0 && changeNewPassword === changeNewPasswordConfirm ? "text-emerald-700" : "text-slate-400"}`}>
                    <CheckCircle2 size={12} aria-hidden="true" />
                    <span>Пароли совпадают</span>
                  </span>
                </div>

                {changePasswordError && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs font-bold text-rose-700">
                    {changePasswordError}
                  </div>
                )}
                {changePasswordSuccess && (
                  <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-bold text-emerald-800">
                    {changePasswordSuccess}
                  </div>
                )}

                <div className="flex gap-2.5 pt-2">
                  <button
                    type="button"
                    className="w-1/2 py-2.5 px-4 rounded-xl border border-slate-300 text-slate-700 font-bold text-xs hover:bg-slate-50 cursor-pointer"
                    onClick={() => setChangePasswordOpen(false)}
                    disabled={changePasswordBusy}
                  >
                    Отмена
                  </button>
                  <button
                    type="submit"
                    className="tl-btn-primary w-1/2 py-2.5 px-4 rounded-xl text-xs shadow-2xs cursor-pointer disabled:opacity-50 flex items-center justify-center gap-1.5"
                    disabled={changePasswordBusy || deleteAccountBusy}
                  >
                    {changePasswordBusy && <Loader2 size={14} className="animate-spin" />}
                    <span>Сохранить</span>
                  </button>
                </div>
              </form>

              <div className="pt-3.5 border-t border-slate-200/80 space-y-2">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Управление аккаунтом
                </div>
                {!deleteAccountConfirm ? (
                  <button
                    type="button"
                    onClick={() => setDeleteAccountConfirm(true)}
                    disabled={changePasswordBusy || deleteAccountBusy}
                    className="w-full text-left text-[11px] font-semibold text-slate-500 hover:text-rose-700 transition-colors cursor-pointer"
                  >
                    Удалить аккаунт и отозвать согласие на обработку персональных данных…
                  </button>
                ) : (
                  <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 space-y-2.5">
                    <p className="text-[11px] text-rose-900 leading-relaxed font-medium">
                      Вы уверены? Все активные сессии будут завершены, а персональные данные обезличены (при отсутствии активных задач в очереди).
                    </p>
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setDeleteAccountConfirm(false)}
                        disabled={deleteAccountBusy}
                        className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 font-bold text-xs cursor-pointer"
                      >
                        Отмена
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDeleteAccount()}
                        disabled={deleteAccountBusy}
                        className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs cursor-pointer disabled:opacity-50 inline-flex items-center gap-1.5"
                      >
                        {deleteAccountBusy ? <Loader2 size={13} className="animate-spin" /> : null}
                        <span>Подтвердить удаление</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </section>
          </div>
        )}

        {/* Collapsible tariff content belongs to the work column, not the sidebar. */}
        {showTariffs ? (() => {
          const supplierPriceKopeks =
            session?.balance?.effective_prices?.supplier_search?.price_kopeks ??
            (session?.tariff_groups?.supplier_search?.[0]?.price_kopeks ?? 9900);
          const supplierIsOverride = session?.balance?.effective_prices?.supplier_search?.source === "client_override";

          const extraPriceKopeks =
            session?.balance?.effective_prices?.supplier_search_extra?.price_kopeks ??
            (session?.tariff_groups?.supplier_search_extra?.[0]?.price_kopeks ?? 4900);
          const extraIsOverride = session?.balance?.effective_prices?.supplier_search_extra?.source === "client_override";

          const exactPriceKopeks =
            session?.balance?.effective_prices?.exact_product?.price_kopeks ??
            (session?.tariff_groups?.exact_product?.[0]?.price_kopeks ?? 9900);
          const exactIsOverride = session?.balance?.effective_prices?.exact_product?.source === "client_override";

          const reportPriceKopeks =
            session?.balance?.effective_prices?.procurement_report?.price_kopeks ??
            (session?.tariff_groups?.procurement_report?.[0]?.price_kopeks ?? 9900);
          const reportIsOverride = session?.balance?.effective_prices?.procurement_report?.source === "client_override";

          const comboPriceKopeks = supplierPriceKopeks + reportPriceKopeks;
          const depositPkgs = session?.deposit_packages?.length ? session.deposit_packages : DEFAULT_DEPOSIT_PACKAGES;
          const maxBonusPercent = Math.max(0, ...depositPkgs.map((pkg) => pkg.price_rub > 0 ? Math.round(pkg.bonus_rub / pkg.price_rub * 100) : 0));
          const popularPkgId =
            depositPkgs.find((p) => p.price_rub === 5000)?.id ||
            depositPkgs.find((p) => p.badge && /хит|популяр/i.test(p.badge))?.id ||
            null;
          const baseTaskRateRub = Math.max(1, Math.round(supplierPriceKopeks / 100));
          const geoSurchargePct = session?.user?.geo_radius_surcharge_pct ?? 30;
          const hasPriceMonitoring = Boolean(session?.user?.allowed_price_monitoring);
          const hasBatchAnalysis = Boolean(session?.user?.allowed_custom_batch_report);

          return (
            <section id="cabinet-tariffs" className="tl-cabinet-tariffs space-y-3" aria-label="Тарифы и пополнение баланса">
              <div className="flex items-center justify-between gap-2 pb-2.5 border-b border-[#e5e9e2]">
                <div>
                  <h2 className="text-sm sm:text-base font-extrabold text-slate-900">Тарифы и пакеты пополнения</h2>
                  <p className="text-[11px] text-slate-500">Единый бессрочный баланс на все инструменты кабинета и Telegram-бота</p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowTariffs(false)}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold cursor-pointer shrink-0"
                >
                  <X size={13} aria-hidden="true" />
                  <span>Скрыть</span>
                </button>
              </div>
              <div className="grid md:grid-cols-2 gap-3">
                {/* Column 1: Списание за операции по прайсу (Strict 3-module order) */}
                <div className="space-y-1.5 bg-[#f8faf6] p-3 rounded-xl border border-[#dfe5dc] flex flex-col justify-between">
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center justify-between gap-1 pb-1.5 border-b border-[#e5e9e2]">
                      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                        Списание за задачи с баланса
                      </span>
                      <span className="text-[10px] text-slate-400">без подписок и скрытых условий</span>
                    </div>
                    <div className="space-y-1.5 pt-0.5 tl-num">
                      <div className={`px-2.5 py-1.5 ${supplierIsOverride ? "bg-amber-50/80 border-amber-200 text-amber-950" : "bg-white border-[#e5e9e2] text-slate-800"} border rounded-lg flex items-center justify-between gap-2 text-xs font-medium`}>
                        <span className="min-w-0 leading-snug font-semibold text-slate-800">1. Поиск поставщиков</span>
                        <b className="font-extrabold text-slate-900 shrink-0 whitespace-nowrap">
                          {formatRubles(supplierPriceKopeks)}
                        </b>
                      </div>
                      <div className={`px-2.5 py-1.5 ${extraIsOverride ? "bg-amber-50/80 border-amber-200 text-amber-950" : "bg-[#f4f8ef] border-[#d7e5cd] text-[#103a31]"} border rounded-lg flex items-center justify-between gap-2 text-xs font-medium`}>
                        <span className={`min-w-0 leading-snug font-semibold ${extraIsOverride ? "text-amber-900" : "text-[#174b3f]"}`}>
                          ↳ Добор поставщиков (по тому же ТЗ)
                        </span>
                        <b className={`font-extrabold ${extraIsOverride ? "text-amber-900" : "text-[#174b3f]"} shrink-0 whitespace-nowrap`}>
                          {formatRubles(extraPriceKopeks)}
                        </b>
                      </div>
                      <div className={`px-2.5 py-1.5 ${exactIsOverride ? "bg-amber-50/80 border-amber-200 text-amber-950" : "bg-white border-[#e5e9e2] text-slate-800"} border rounded-lg flex items-center justify-between gap-2 text-xs font-medium`}>
                        <span className="min-w-0 leading-snug font-semibold text-slate-800">2. Подбор товара и аналогов</span>
                        <b className="font-extrabold text-slate-900 shrink-0 whitespace-nowrap">
                          {formatRubles(exactPriceKopeks)} / поз.
                        </b>
                      </div>
                      <div className={`px-2.5 py-1.5 ${reportIsOverride ? "bg-amber-50/80 border-amber-200 text-amber-950" : "bg-white border-[#e5e9e2] text-slate-800"} border rounded-lg flex items-center justify-between gap-2 text-xs font-medium`}>
                        <span className="min-w-0 leading-snug font-semibold text-slate-800">3. Анализ документации</span>
                        <b className="font-extrabold text-slate-900 shrink-0 whitespace-nowrap">
                          {formatRubles(reportPriceKopeks)}
                        </b>
                      </div>
                      <div className="px-2.5 py-1.5 bg-slate-100/80 border border-[#dfe5dc] rounded-lg flex items-center justify-between gap-2 text-xs font-medium text-slate-800">
                        <span className="min-w-0 leading-snug font-semibold text-slate-700">4. Анализ + поиск (комбо)</span>
                        <b className="font-extrabold text-slate-900 shrink-0 whitespace-nowrap">
                          {formatRubles(comboPriceKopeks)}
                        </b>
                      </div>
                      {hasPriceMonitoring ? (() => {
                        const pmPriceKopeks =
                          session?.balance?.effective_prices?.price_monitoring?.price_kopeks ?? 5000;
                        const pmIsOverride = session?.balance?.effective_prices?.price_monitoring?.source === "client_override";
                        return (
                          <div className={`px-2.5 py-1.5 ${pmIsOverride ? "bg-amber-50/80 border-amber-200 text-amber-950" : "bg-white border-[#e5e9e2] text-slate-800"} border rounded-lg flex items-center justify-between gap-2 text-xs font-medium`}>
                            <span className="min-w-0 leading-snug font-semibold text-slate-800">5. Мониторинг цен (за найденную)</span>
                            <b className="font-extrabold text-slate-900 shrink-0 whitespace-nowrap">
                              {formatRubles(pmPriceKopeks)}
                            </b>
                          </div>
                        );
                      })() : null}
                      {hasBatchAnalysis ? (() => {
                        const batchPriceKopeks =
                          session?.balance?.effective_prices?.custom_batch_report?.price_kopeks ??
                          session?.function_prices?.custom_batch_report?.price_kopeks ??
                          3000;
                        const batchIsOverride =
                          session?.balance?.effective_prices?.custom_batch_report?.source === "client_override";
                        return (
                          <div className={`px-2.5 py-1.5 ${batchIsOverride ? "bg-amber-50/80 border-amber-200 text-amber-950" : "bg-white border-[#e5e9e2] text-slate-800"} border rounded-lg flex items-center justify-between gap-2 text-xs font-medium`}>
                            <span className="min-w-0 leading-snug font-semibold text-slate-800">
                              {hasPriceMonitoring ? "6" : "5"}. Экспресс-оценка закупок (за закупку)
                            </span>
                            <b className="font-extrabold text-slate-900 shrink-0 whitespace-nowrap">
                              {formatRubles(batchPriceKopeks)}
                            </b>
                          </div>
                        );
                      })() : null}
                    </div>
                  </div>
                  {session?.user?.allowed_geo_radius ? (
                    <p className="text-[11px] text-slate-500 pt-2 mt-1.5 border-t border-[#e5e9e2] leading-snug">
                      Опция «Приоритет в радиусе доставки»: +{geoSurchargePct}% к стоимости поиска или мониторинга.
                    </p>
                  ) : null}
                </div>

                {/* Column 2: Пакеты пополнения баланса */}
                <div className="space-y-1.5 bg-[#f8faf6] p-3 rounded-xl border border-[#dfe5dc]">
                  <div className="flex flex-wrap items-center justify-between gap-1 pb-1.5 border-b border-[#e5e9e2]">
                    <span className="text-[10px] font-bold text-[#174b3f] uppercase tracking-wider">
                      {maxBonusPercent > 0 ? "Пакеты пополнения с бонусом" : "Пакеты пополнения баланса"}
                    </span>
                    {maxBonusPercent > 0 ? (
                      <span className="text-[10px] font-bold text-[#174b3f] bg-[#e7efe0] px-1.5 py-0.5 rounded">
                        до +{maxBonusPercent}% на счёт
                      </span>
                    ) : null}
                  </div>
                  <div className="space-y-1.5 pt-0.5 tl-num">
                    {depositPkgs.map((pkg) => {
                      const isPopular = pkg.id === popularPkgId;
                      const effectiveTaskRub =
                        pkg.total_rub > 0 ? Math.round(baseTaskRateRub * (pkg.price_rub / pkg.total_rub)) : baseTaskRateRub;
                      return (
                        <div
                          key={pkg.id}
                          className={`tl-topup-package px-2.5 py-2 rounded-lg flex items-center justify-between gap-2 text-xs font-medium text-slate-800 transition-colors border ${
                            isPopular
                              ? "bg-[#f4f8ef] border-[#9ec089]"
                              : "bg-white border-[#e5e9e2] hover:border-[#b7c9af]"
                          }`}
                        >
                          <div className="tl-topup-package__amounts min-w-0 space-y-0.5">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-bold text-slate-900">{pkg.name}</span>
                              {isPopular ? (
                                <span className="px-1.5 py-0.5 rounded bg-[#174b3f] text-white text-[10px] font-bold leading-none">
                                  Хит
                                </span>
                              ) : null}
                              {pkg.bonus_rub > 0 ? (
                                <span className="text-[10px] text-slate-500 whitespace-nowrap">
                                  ~{effectiveTaskRub} ₽/задача
                                </span>
                              ) : null}
                            </div>
                            <div className="flex items-center gap-1.5 flex-wrap text-[11px]">
                              <span className="font-bold text-slate-700 whitespace-nowrap">{pkg.price_rub.toLocaleString("ru-RU")} ₽</span>
                              <span className="text-slate-400">→</span>
                              <span className="font-extrabold text-[#174b3f] whitespace-nowrap">{pkg.total_rub.toLocaleString("ru-RU")} ₽ на баланс</span>
                            </div>
                          </div>
                          <div className="tl-topup-package__action flex items-center gap-1.5 shrink-0">
                            {pkg.bonus_rub > 0 ? (
                              <span className="px-1.5 py-0.5 rounded bg-[#e7efe0] text-[#103a31] text-[10px] font-bold whitespace-nowrap">
                                +{pkg.bonus_rub.toLocaleString("ru-RU")} ₽
                              </span>
                            ) : (
                              <span className="text-[10px] text-slate-400 font-medium whitespace-nowrap">без бонуса</span>
                            )}
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedTopUpPackage(pkg);
                                setCustomTopUpRub(pkg.price_rub);
                                setTopUpTab("card");
                                setShowTopUpModal(true);
                                setShowTariffs(false);
                              }}
                              className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-colors cursor-pointer whitespace-nowrap ${
                                isPopular
                                  ? "tl-btn-primary"
                                  : "bg-white hover:bg-[#f4f8ef] text-[#174b3f] border border-[#b7c9af] hover:border-[#174b3f]"
                              }`}
                            >
                              Купить
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Action Banner inside Tariffs */}
              <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 bg-[#f8faf6] rounded-xl border border-[#dfe5dc] text-xs">
                <span className="text-slate-600 text-[11px]">
                  Средства на балансе не сгорают, расходуются только по факту выполненных задач.
                </span>
                <div className="flex flex-wrap items-center gap-2 ml-auto">
                  <button
                    type="button"
                    onClick={() => {
                      const defPkg = depositPkgs.find((p) => p.price_rub === 5000) || depositPkgs[2] || depositPkgs[0];
                      setSelectedTopUpPackage(defPkg);
                      setCustomTopUpRub(defPkg?.price_rub || 5000);
                      setTopUpTab("b2b");
                      setShowTopUpModal(true);
                      setShowTariffs(false);
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-[#f4f8ef] text-[#174b3f] border border-[#b7c9af] rounded-lg text-xs font-bold transition-colors cursor-pointer"
                  >
                    <Building2 size={13} aria-hidden="true" />
                    <span>Выставить счёт юрлицу</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const defPkg = depositPkgs.find((p) => p.price_rub === 5000) || depositPkgs[2] || depositPkgs[0];
                      setSelectedTopUpPackage(defPkg);
                      setCustomTopUpRub(defPkg?.price_rub || 5000);
                      setTopUpTab("card");
                      setShowTopUpModal(true);
                      setShowTariffs(false);
                    }}
                    className="tl-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer"
                  >
                    <PlusCircle size={13} aria-hidden="true" />
                    <span>Пополнить баланс с бонусом</span>
                  </button>
                </div>
              </div>
            </section>
          );
        })() : null}
      {!emailVerified ? (
        <div className="p-2.5 bg-amber-50 border border-amber-200/90 rounded-xl text-xs font-medium text-amber-900 flex flex-wrap items-center justify-between gap-2 shadow-2xs">
          <div className="flex items-center gap-2">
            <Mail size={15} className="text-amber-700 shrink-0" aria-hidden="true" />
            <span>
              <strong>Подтвердите email.</strong> Вы можете сразу запустить первую пробную задачу или демо-пример. Для следующих задач подтвердите email по ссылке из письма.
            </span>
          </div>
          <button
            type="button"
            className="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-bold transition-all shadow-2xs cursor-pointer"
            onClick={resendVerification}
            disabled={busy}
          >
            Отправить письмо повторно
          </button>
        </div>
      ) : null}

      {(message || (error && cabinetSection !== "workspace")) ? (
        <div className={`p-2.5 rounded-xl border text-xs font-bold flex items-center gap-2 ${error && !message ? "bg-rose-50 border-rose-200 text-rose-800" : "bg-emerald-50 border-emerald-200 text-emerald-800"}`}>
          {error && !message ? <XCircle size={15} aria-hidden="true" /> : <CheckCircle2 size={15} aria-hidden="true" />}
          <span>{message || error}</span>
        </div>
      ) : null}

      {session?.user?.is_trial ? (
        <div className="p-3 sm:p-4 bg-gradient-to-r from-teal-50 via-white to-sky-50 border border-teal-200/90 rounded-xl shadow-2xs">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-teal-700 text-white flex items-center justify-center shrink-0 shadow-2xs mt-0.5">
              <Sparkles size={16} aria-hidden="true" />
            </div>
            <div className="space-y-0.5 text-xs">
              <div className="flex items-center gap-2">
                <h2 className="font-bold text-slate-900 text-xs sm:text-sm">
                  Тестовый доступ активен
                </h2>
                <span className="text-[10px] font-bold text-teal-800 bg-teal-100/90 px-2 py-0.5 rounded border border-teal-300 shrink-0">
                  пробный период
                </span>
              </div>
              <p className="text-slate-600 leading-relaxed text-[12px] sm:text-[13px]">
                Вам начислен стартовый баланс для проверки поиска поставщиков, подбора товара и аналогов или анализа документации по вашим ТЗ. Если для тестирования требуется больше запусков — напишите нам по кнопкам контактов ниже, и мы начислим дополнительные лимиты.
              </p>
              {jobsTotal === 0 ? (
                <div className="pt-2 flex flex-wrap items-center gap-2.5">
                  <button
                    type="button"
                    onClick={fillDemoExample}
                    className="px-3.5 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs shadow-xs transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <Sparkles size={14} />
                    <span>Попробовать на демо-ТЗ в 1 клик</span>
                  </button>
                  <span className="text-[11px] text-slate-500">
                    Заполнит форму тестовой спецификацией (арматура / краны / фланцы) для мгновенного запуска.
                  </span>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {/* Main Task Launch Form — Single Focused Tool Composer (Hidden when viewing Full Tasks Archive) */}
      {cabinetSection === "workspace" ? (
        <section className="tl-cabinet-launcher">
          <form id="new-job" className="space-y-3.5" onSubmit={submitJob}>
            {/* 1. Focused Tool Header */}
            <div className="flex items-start justify-between gap-3 pb-3 border-b border-slate-100">
              <div className="min-w-0 space-y-0.5">
                <h1 className="text-lg sm:text-xl font-extrabold text-slate-900 tracking-tight leading-snug">
                  {selectedCopy.title}
                </h1>
                <p className="text-xs sm:text-[13px] text-slate-600 leading-relaxed max-w-3xl">
                  {selectedCopy.formSubtitle}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setHelpModalTab(scenario);
                  setShowHelpModal(true);
                }}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold shrink-0 cursor-pointer transition-colors"
                title={`Справка: как работает «${selectedCopy.title}»`}
              >
                <HelpCircle size={13} className="text-teal-700" aria-hidden="true" />
                <span className="hidden sm:inline">Как работает</span>
              </button>
            </div>

            {error ? (
              <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-800 flex items-center gap-2">
                <XCircle size={15} className="text-rose-600 shrink-0" aria-hidden="true" />
                <span>{error}</span>
              </div>
            ) : null}

            {batchBusy && !batchPreview ? (
              <div className="p-2.5 bg-teal-50 border border-teal-200 rounded-xl text-xs font-semibold text-teal-900 flex items-center gap-2">
                <Loader2 size={15} className="animate-spin text-teal-700 shrink-0" />
                <span>Читаем перечень закупок из файла и подготавливаем окно выбора...</span>
              </div>
            ) : null}

            {/* Hidden File Input Shared Across Dropzones */}
            <input
              ref={fileInputRef}
              className="hidden"
              type="file"
              multiple
              accept=".pdf,.docx,.doc,.txt,.xlsx,.xls,.csv,.zip,.rar,.7z,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"
              onChange={handleFileInput}
            />

            {/* 2A. EIS / Procurement Documentation Composer (Distinct Document-First Layout) */}
            {acceptsSources ? (
              <div className="space-y-2.5">
                <div className="p-3 sm:p-3.5 rounded-xl bg-slate-50/70 border border-slate-200/90 space-y-2">
                  <label className="block text-xs font-bold text-slate-800" htmlFor="eis-source-input">
                    {selectedCopy.sourceLabel}
                  </label>
                  <div className="flex flex-col sm:flex-row items-stretch gap-2">
                    <div className="relative flex-1 min-w-0">
                      {!isCustomBatchScenario && scenario !== "procurement_report" ? (
                        <Globe size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" aria-hidden="true" />
                      ) : null}
                      {isCustomBatchScenario || scenario === "procurement_report" ? (
                        <textarea
                          id="eis-source-input"
                          className={`w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-[13px] text-slate-900 resize-y ${
                            isCustomBatchScenario ? "min-h-[68px]" : "min-h-[44px]"
                          }`}
                          rows={isCustomBatchScenario ? 2 : 1}
                          value={sourceUrls}
                          onChange={(event) => setSourceUrls(event.target.value)}
                          placeholder={selectedCopy.sourcePlaceholder}
                        />
                      ) : (
                        <input
                          id="eis-source-input"
                          className="w-full pl-9 pr-3 h-[42px] bg-white border border-slate-300 rounded-lg text-[13px] text-slate-900 tl-num"
                          value={sourceUrls}
                          onChange={(event) => setSourceUrls(event.target.value)}
                          placeholder={selectedCopy.sourcePlaceholder}
                        />
                      )}
                    </div>
                    <button
                      className={`tl-btn-primary px-5 h-[42px] ${isCustomBatchScenario || scenario === "procurement_report" ? "sm:self-start" : ""} rounded-lg text-xs sm:text-[13px] flex items-center justify-center gap-2 cursor-pointer shrink-0 whitespace-nowrap`}
                      type="submit"
                      disabled={busy}
                    >
                      {busy ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : null}
                      <span>
                        {selectedFiles.length > 0
                          ? `${selectedCopy.submit} (${selectedFiles.length} ${declensionFiles(selectedFiles.length)})`
                          : selectedCopy.submit}
                      </span>
                      {!busy ? <ArrowRight size={14} aria-hidden="true" /> : null}
                    </button>
                  </div>

                  {activeScenarioPricingHint ? (
                    <div className="tl-cost-hint pt-0.5">
                      <Wallet size={12} className="text-[#174b3f] shrink-0" aria-hidden="true" />
                      <span>{activeScenarioPricingHint}</span>
                    </div>
                  ) : null}

                  {isCustomBatchScenario ? (
                    <div className="px-3 py-2 rounded-lg bg-[#f4f8ef] border border-[#d6e4c9] text-xs text-slate-700 flex flex-wrap items-center justify-between gap-2">
                      <span>
                        Нужен полный разбор всех позиций ТЗ, нацрежима (ПП № 1875) и готовый Запрос КП перед подачей?
                      </span>
                      <button
                        type="button"
                        onClick={() => selectScenario("procurement_report", { preserveInput: true })}
                        className="px-2.5 py-1 rounded-md bg-white border border-[#b7c9af] font-bold text-[#174b3f] hover:bg-[#174b3f] hover:text-white transition-colors cursor-pointer text-[11px] shrink-0"
                      >
                        Перейти в «Анализ документации» →
                      </button>
                    </div>
                  ) : null}

                  {(() => {
                    const trimmedSource = sourceUrls.trim();
                    const looksLikeProductText =
                      trimmedSource.length >= 4 &&
                      !isCustomBatchScenario &&
                      !/\d{11,19}/.test(trimmedSource) &&
                      !/zakupki\.gov\.ru|https?:\/\//i.test(trimmedSource) &&
                      /[а-яА-ЯёЁa-zA-Z]{3,}/.test(trimmedSource);
                    if (!looksLikeProductText) return null;
                    return (
                      <div className="px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-950 flex flex-wrap items-center justify-between gap-2">
                        <span>Похоже на название товара, а не номер закупки ЕИС. Перенести запрос в нужный инструмент?</span>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            type="button"
                            onClick={() => selectScenario("supplier_search", { preserveInput: true })}
                            className="px-2.5 py-1 rounded-md bg-white border border-amber-300 font-bold text-teal-900 hover:border-teal-600 cursor-pointer text-[11px]"
                          >
                            В «Поиск поставщиков» →
                          </button>
                          <button
                            type="button"
                            onClick={() => selectScenario("exact_product", { preserveInput: true })}
                            className="px-2.5 py-1 rounded-md bg-white border border-amber-300 font-bold text-slate-800 hover:border-teal-600 cursor-pointer text-[11px]"
                          >
                            В «Подбор аналогов» →
                          </button>
                        </div>
                      </div>
                    );
                  })()}
                </div>

                {/* Secondary Compact Document Drop Bar */}
                <div
                  className={`border border-dashed rounded-xl px-3.5 py-2.5 cursor-pointer transition-colors flex flex-wrap items-center justify-between gap-2.5 ${
                    dragActive ? "border-teal-600 bg-teal-50/70" : "border-slate-300 hover:border-teal-600 bg-white hover:bg-slate-50/70"
                  }`}
                  role="button"
                  tabIndex={0}
                  aria-label="Выбрать файлы для задачи"
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDragActive(true);
                  }}
                  onDragLeave={() => setDragActive(false)}
                  onDrop={(event) => {
                    event.preventDefault();
                    setDragActive(false);
                    filesFromList(event.dataTransfer.files);
                  }}
                  onClick={() => fileInputRef.current?.click()}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      fileInputRef.current?.click();
                    }
                  }}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Paperclip size={15} className="text-teal-700 shrink-0" aria-hidden="true" />
                    <div className="min-w-0">
                      <span className="text-xs font-bold text-slate-800">{selectedCopy.uploadTitle}</span>
                      <span className="hidden md:inline text-xs text-slate-500 ml-2">— {selectedCopy.uploadText}</span>
                    </div>
                  </div>
                  <span className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-800 rounded-md text-xs font-semibold shrink-0">
                    Выбрать файлы
                  </span>
                </div>
                {batchBusy && !batchPreview ? (
                  <div className="px-3 py-2 rounded-lg bg-teal-50 border border-teal-200 text-xs font-semibold text-teal-900 flex items-center gap-2">
                    <Loader2 size={14} className="animate-spin text-teal-700 shrink-0" aria-hidden="true" />
                    <span>Распознаём файл и проверяем, есть ли в нём список закупок...</span>
                  </div>
                ) : null}
              </div>
            ) : null}

            {/* 2B. Product / Specification Composer (Unified File + Text Workspace) */}
            {acceptsText ? (
              <div className="rounded-xl border border-slate-300 bg-white overflow-hidden">
                <div
                  className={`px-3.5 py-2.5 border-b border-slate-200/90 cursor-pointer transition-colors flex flex-wrap items-center justify-between gap-2.5 ${
                    dragActive ? "bg-teal-50/80" : "bg-slate-50/80 hover:bg-slate-100/70"
                  }`}
                  role="button"
                  tabIndex={0}
                  aria-label="Выбрать файлы для задачи"
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDragActive(true);
                  }}
                  onDragLeave={() => setDragActive(false)}
                  onDrop={(event) => {
                    event.preventDefault();
                    setDragActive(false);
                    filesFromList(event.dataTransfer.files);
                  }}
                  onClick={() => fileInputRef.current?.click()}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      fileInputRef.current?.click();
                    }
                  }}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Upload size={15} className="text-teal-700 shrink-0" aria-hidden="true" />
                    <strong className="text-xs font-bold text-slate-900">{selectedCopy.uploadTitle}</strong>
                    <span className="hidden md:inline text-xs text-slate-500 truncate">{selectedCopy.uploadText}</span>
                  </div>
                  <span className="px-2.5 py-1 bg-white border border-slate-300 text-slate-800 rounded-md text-xs font-semibold shrink-0">
                    Выбрать файл
                  </span>
                </div>

                <div className="p-3 space-y-2">
                  <label className="block text-[11px] font-semibold text-slate-500" htmlFor="spec-text-input">
                    {selectedCopy.textLabel}
                  </label>
                  <textarea
                    id="spec-text-input"
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-[13px] text-slate-900 resize-y min-h-[76px] leading-relaxed"
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    rows={3}
                    placeholder={selectedCopy.textPlaceholder}
                  />

                  {(() => {
                    const trimmedText = text.trim();
                    const looksLikeEisNotice =
                      /zakupki\.gov\.ru/i.test(trimmedText) || /^\d{11}$|^\d{19}$/.test(trimmedText);
                    if (!looksLikeEisNotice) return null;
                    return (
                      <div className="px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-950 flex flex-wrap items-center justify-between gap-2">
                        <span>Вы вставили номер или ссылку ЕИС. Перенести в разбор закупки с сохранением данных?</span>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            type="button"
                            onClick={() => selectScenario("analysis_and_suppliers", { preserveInput: true })}
                            className="px-2.5 py-1 rounded-md bg-white border border-amber-300 font-bold text-teal-900 hover:border-teal-600 cursor-pointer text-[11px]"
                          >
                            Анализ + поиск →
                          </button>
                          <button
                            type="button"
                            onClick={() => selectScenario("procurement_report", { preserveInput: true })}
                            className="px-2.5 py-1 rounded-md bg-white border border-amber-300 font-bold text-slate-800 hover:border-teal-600 cursor-pointer text-[11px]"
                          >
                            Анализ документации →
                          </button>
                        </div>
                      </div>
                    );
                  })()}
                </div>

                <div className="px-3.5 py-2.5 bg-slate-50/70 border-t border-slate-200/80 flex flex-wrap items-center justify-between gap-2.5">
                  <div className="space-y-0.5 min-w-0">
                    {activeScenarioPricingHint ? (
                      <div className="tl-cost-hint text-slate-700 font-medium">
                        <Wallet size={12} className="text-[#174b3f] shrink-0" aria-hidden="true" />
                        <span>{activeScenarioPricingHint}</span>
                      </div>
                    ) : null}
                    <span className="text-[11px] text-slate-500 block">
                      {selectedCopy.hint}
                    </span>
                  </div>
                  <button
                    className="tl-btn-primary px-5 h-[38px] rounded-lg text-xs sm:text-[13px] flex items-center justify-center gap-2 cursor-pointer ml-auto shrink-0"
                    type="submit"
                    disabled={busy}
                  >
                    {busy ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : null}
                    <span>
                      {selectedFiles.length > 0
                        ? `${selectedCopy.submit} (${selectedFiles.length} ${declensionFiles(selectedFiles.length)})`
                        : selectedCopy.submit}
                    </span>
                    {!busy ? <ArrowRight size={14} aria-hidden="true" /> : null}
                  </button>
                </div>
              </div>
            ) : null}

            {/* Selected Files List */}
            {selectedFiles.length ? (
              <div className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl space-y-1.5">
                <div className="flex items-center justify-between text-xs font-bold text-slate-700">
                  <span>Прикреплённые файлы ({selectedFiles.length}):</span>
                  <button
                    type="button"
                    className="px-2 py-0.5 text-[11px] font-semibold text-rose-700 hover:bg-rose-50 rounded cursor-pointer"
                    onClick={clearSelectedFiles}
                  >
                    Очистить
                  </button>
                </div>
                <ul className="flex flex-wrap gap-1.5">
                  {selectedFiles.map((file, idx) => (
                    <li key={`${file.name}-${idx}`} className="inline-flex items-center gap-2 text-xs bg-white px-2.5 py-1 rounded-md border border-slate-200 text-slate-800 max-w-full">
                      <FileText size={12} className="text-teal-700 shrink-0" aria-hidden="true" />
                      <span className="truncate max-w-[260px] font-medium">{file.name}</span>
                      <span className="text-[10px] text-slate-400 tl-num shrink-0">{(file.size / 1024).toFixed(1)} KB</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {/* 3. Compact Single-Row Search Parameters (Registry & Geography) */}
            {scenario === "supplier_search" || scenario === "analysis_and_suppliers" || scenario === "price_monitoring" ? (
              <div className="pt-1 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
                {scenario === "supplier_search" || scenario === "analysis_and_suppliers" ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-slate-600">Реестр:</span>
                    <div className="tl-seg-group" role="group" aria-label="Фильтр по реестру Минпромторга">
                      {supplierPolicyOptions.map((opt) => (
                        <button
                          key={opt.id}
                          type="button"
                          title={opt.description}
                          className={`tl-seg-btn ${supplierSearchPolicy === opt.id ? "is-active" : ""}`}
                          onClick={() => handleSetSupplierSearchPolicy(opt.id)}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold text-slate-600">География:</span>
                  <div className="tl-seg-group" role="group" aria-label="География поиска">
                    {geoScopeOptions.map((opt) => {
                      const isLockedByMinprom =
                        (supplierSearchPolicy === "minprom_registry_only" || supplierSearchPolicy === "minprom_registry_priority") &&
                        opt.id !== "ru";
                      const isSelected = isLockedByMinprom ? false : geoScope === opt.id;
                      return (
                        <button
                          key={opt.id}
                          type="button"
                          disabled={isLockedByMinprom}
                          title={isLockedByMinprom ? "При поиске по реестру Минпромторга доступна только территория РФ" : opt.description}
                          className={`tl-seg-btn ${isSelected ? "is-active" : ""}`}
                          onClick={() => !isLockedByMinprom && handleSetGeoScope(opt.id)}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : null}

            {/* 4. Optional Logistics Radius Strip */}
            {(scenario === "supplier_search" || scenario === "analysis_and_suppliers" || scenario === "price_monitoring") && session?.user?.allowed_geo_radius ? (
              <DeliveryPriorityControl
                geoRadiusEnabled={geoRadiusEnabled}
                deliveryCity={deliveryCity}
                geoRadiusKm={geoRadiusKm}
                setGeoRadiusEnabled={setGeoRadiusEnabled}
                setDeliveryCity={setDeliveryCity}
                setGeoRadiusKm={setGeoRadiusKm}
                surchargePct={session?.user?.geo_radius_surcharge_pct ?? 30}
              />
            ) : null}
          </form>
        </section>
      ) : null}

      {activeJobs > 0 && !session?.user?.has_telegram ? (
        <aside className="p-3 bg-white border border-slate-200 rounded-xl flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 text-xs text-slate-800">
            <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200 text-teal-800 flex items-center justify-center shrink-0">
              <BellRing size={15} aria-hidden="true" />
            </div>
            <div>
              <strong className="block text-slate-900 font-bold text-xs tl-num">
                {activeJobs} {declensionTasks(activeJobs)} в обработке (~2–3 мин)
              </strong>
              <span className="text-slate-600 text-[11px] leading-tight block">
                Привяжите Telegram-бота — пришлём готовый отчёт прямо в мессенджер, можно не ждать на сайте
              </span>
            </div>
          </div>
          <a
            href="/api/customer/auth/telegram/login"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-[#24A1DE] hover:bg-[#1f93cc] text-white text-xs font-bold rounded-lg transition-colors shrink-0 cursor-pointer"
          >
            <Send size={13} aria-hidden="true" />
            <span>Привязать Telegram</span>
          </a>
        </aside>
      ) : null}

      {/* Jobs History Table */}
      <section id="jobs" className="tl-cabinet-jobs space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2.5 pb-2.5 border-b border-slate-100">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h2 className="text-base sm:text-lg font-extrabold text-slate-900 tracking-tight">
              {cabinetSection === "workspace" ? "Последние задачи" : "Мои задачи"}
            </h2>
            <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2.5 py-0.5 rounded-md tl-num">
              {jobsTotal
                ? isWorkspaceCollapsed
                  ? `1–${visibleJobs.length} из ${jobsTotal}`
                  : `${jobsStart}–${jobsEnd} из ${jobsTotal}`
                : "0 задач"}
            </span>

            {/* Quick Status Filter Segmented Bar */}
            <div className="tl-seg-group" role="group" aria-label="Фильтр по статусу задач">
              {[
                { id: "" as const, label: "Все" },
                { id: "active" as const, label: "В работе" },
                { id: "attention" as const, label: "Ждут решения" },
                { id: "completed" as const, label: "Готовые" },
              ].map((tab) => (
                <button
                  key={tab.id || "all"}
                  type="button"
                  className={`tl-seg-btn ${jobStatusFilter === tab.id ? "is-active" : ""}`}
                  onClick={() => {
                    setJobStatusFilter(tab.id);
                    setJobsPage(1);
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {cabinetSection === "jobs" ? (
              <button
                type="button"
                onClick={() => {
                  setCabinetSection("workspace");
                  if (typeof window !== "undefined") {
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }
                }}
                className="tl-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer"
              >
                <PlusCircle size={13} aria-hidden="true" />
                <span>Новая задача</span>
              </button>
            ) : null}

            {jobsTotal > jobsPageSize ? (
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700 tl-num" aria-label="Навигация по задачам">
                <button
                  type="button"
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
                  onClick={() => setJobsPage((page) => Math.max(1, page - 1))}
                  disabled={jobsPage <= 1 || jobsLoading}
                >
                  Назад
                </button>
                <span className="px-1.5 text-xs font-medium text-slate-600">
                  Страница {jobsPage} из {jobsPageCount}
                </span>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
                  onClick={() => setJobsPage((page) => Math.min(jobsPageCount, page + 1))}
                  disabled={jobsPage >= jobsPageCount || jobsLoading}
                >
                  Вперёд
                </button>
              </div>
            ) : null}
            <select
              value={jobsPageSize}
              onChange={(e) => handleJobsPageSizeChange(Number(e.target.value))}
              className="py-1.5 px-2.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 cursor-pointer tl-num"
              title="Количество задач на странице"
            >
              <option value={15}>По 15</option>
              <option value={25}>По 25</option>
              <option value={50}>По 50</option>
              <option value={100}>По 100</option>
            </select>
          </div>
        </div>

        {/* Search and Filters Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-12 gap-2 items-center">
          {/* Search Input */}
          <div className="relative sm:col-span-2 md:col-span-6">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={14} />
            <input
              type="text"
              value={jobSearchQuery}
              onChange={(e) => setJobSearchQuery(e.target.value)}
              placeholder="Поиск по названию или номеру #..."
              className="w-full pl-9 pr-8 py-1.5 min-h-[36px] bg-white border border-slate-200 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 font-medium"
            />
            {jobSearchQuery ? (
              <button
                type="button"
                onClick={() => setJobSearchQuery("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5 rounded cursor-pointer"
                title="Очистить поиск"
              >
                <X size={14} />
              </button>
            ) : null}
          </div>

          {/* Mode Filter (Тип поиска) */}
          <div className="sm:col-span-1 md:col-span-3">
            <select
              aria-label="Тип задачи в истории"
              value={jobModeFilter}
              onChange={(e) => {
                setJobModeFilter(e.target.value);
                setJobsPage(1);
              }}
              className="w-full py-1.5 min-h-[36px] px-3 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 cursor-pointer"
            >
              <option value="">Все типы</option>
              <option value="procurement_report">Анализ документации</option>
              <option value="supplier_search">Поиск поставщиков</option>
              <option value="analysis_and_suppliers">Анализ + поиск</option>
              <option value="exact_product">Подбор товара и аналогов</option>
              {session?.user?.allowed_price_monitoring ? (
                <option value="price_monitoring">Мониторинг цен</option>
              ) : null}
              {session?.user?.allowed_custom_batch_report || jobs.some((j) => j.is_custom_batch_report) ? (
                <option value="custom_batch_report">Экспресс-оценка</option>
              ) : null}
            </select>
          </div>

          {/* Policy Filter (Режим поиска по реестру) */}
          <div className="sm:col-span-1 md:col-span-3 flex items-center gap-1.5">
            <select
              aria-label="Режим поиска в истории"
              value={jobPolicyFilter}
              onChange={(e) => {
                setJobPolicyFilter(e.target.value);
                setJobsPage(1);
              }}
              className="w-full py-1.5 min-h-[36px] px-3 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 cursor-pointer"
            >
              <option value="">Все режимы</option>
              <option value="normal">Обычный поиск</option>
              <option value="minprom_registry_only">Только реестр (Минпромторг)</option>
              <option value="minprom_registry_priority">Реестр в приоритете (Минпромторг)</option>
            </select>

            {hasActiveJobFilters ? (
              <button
                type="button"
                onClick={resetJobFilters}
                className="px-2.5 min-h-[36px] text-xs font-bold text-slate-600 hover:text-rose-700 bg-slate-100 hover:bg-rose-50 border border-slate-200 hover:border-rose-200 rounded-lg transition-colors cursor-pointer shrink-0"
                title="Сбросить все фильтры"
              >
                Сброс
              </button>
            ) : null}
          </div>
        </div>

        <div className="w-full space-y-2 font-sans">
          {visibleJobs.length > 0 ? (
            <div className="hidden md:grid grid-cols-12 gap-4 pb-2 border-b border-slate-200 text-xs font-semibold text-slate-500 px-3.5">
              <span className="col-span-5">Задача и параметры</span>
              <span className="col-span-3">Статус</span>
              <span className="col-span-4 text-right">Результаты и действия</span>
            </div>
          ) : null}

          {visibleJobs.length ? (
            visibleJobs.map((job) => {
              const offer = (job as unknown as { result_offer?: { kind?: string; charge_amount_rub?: number; new_count?: number; prior_count?: number; delta_units?: number; can_accept?: boolean; can_decline?: boolean; comment?: string } }).result_offer;
              const isFailed = job.status === "failed" || job.status === "error";
              const isCancelledOrDeclined = job.status === "cancelled" || job.status === "customer_declined";
              const isExpired = job.status === "confirmation_expired" || job.status === "delivery_expired";
              const isPending = job.status === "pending" || job.status === "running";
              const isAwaiting = job.status === "awaiting_customer_confirmation";
              const isAwaitingExactSelection = isAwaitingPositionSelection(job);
              const jobPositionSelection = positionSelectionForJob(job);
              const isCompletedWithResult = job.status === "done" || (Boolean(job.result_files?.length) && !isPending && !isFailed);
              const jobCreatedTs = job.created_at ? new Date(apiDateValue(job.created_at)).getTime() : 0;
              const isCreatedAfterFeature = !Number.isNaN(jobCreatedTs) && jobCreatedTs >= NOTIFICATION_FEATURE_START_TS;
              const isUnviewed = isCreatedAfterFeature && isCompletedWithResult && !viewedJobIds.includes(job.id);
              const durationText = formatJobDuration(job, nowTs);
              const cleanTitle = formatCleanJobTitle(job);
              const cleanStatusLabel = formatStatusLabel(job.status_label);
              const cleanMessage = formatCleanJobMessage(job.message);
              const hasJobMessages = Boolean(job.chat_messages && job.chat_messages.length > 0) || Boolean(job.admin_comment);

              return (
                <article
                  key={job.id}
                  id={`job-${job.id}`}
                  onClick={() => {
                    if (isUnviewed) markJobAsViewed(job.id);
                  }}
                  className={`tl-job-row p-3.5 space-y-2.5 md:space-y-0 md:grid md:grid-cols-12 md:gap-4 md:items-center text-xs font-medium text-slate-800 ${
                    isUnviewed ? "is-unviewed" : ""
                  }`}
                >
                  {/* Column 1: Task Title & Consolidated Metadata (5/12 = 42%) */}
                  <div className="col-span-12 md:col-span-5 flex flex-col gap-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {job.job_number ? (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold bg-slate-100 border border-slate-200 text-slate-700 select-all shrink-0 tl-num" title={`Номер задачи: #${job.job_number}`}>
                          #{job.job_number}
                        </span>
                      ) : null}
                      <strong className="font-bold text-[13px] text-slate-900 leading-snug break-words">{cleanTitle}</strong>
                      {isUnviewed ? (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-700 text-white shrink-0">
                          <Sparkles size={10} aria-hidden="true" />
                          <span>Новая</span>
                        </span>
                      ) : null}
                      {job.has_admin_supplement ? (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 border border-emerald-300 text-emerald-900 shrink-0">
                          <Sparkles size={10} aria-hidden="true" />
                          <span>Дополнено экспертом</span>
                        </span>
                      ) : null}
                    </div>
                    <div className="flex items-center gap-1.5 flex-wrap text-[11px] text-slate-500 tl-num">
                      <span className="font-semibold text-slate-700">{modeDisplayName(job)}</span>
                      <span className="text-slate-300" aria-hidden="true">·</span>
                      <span>{formatDate(job.created_at)}{durationText ? ` · ${durationText}` : ""}</span>
                      {job.file_count > 0 ? (
                        <>
                          <span className="text-slate-300" aria-hidden="true">·</span>
                          <span>файлов: {job.file_count}</span>
                        </>
                      ) : null}
                      {job.delivery_city ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-teal-900 bg-teal-50 border border-teal-200 px-1.5 py-0.5 rounded">
                          <MapPin size={10} aria-hidden="true" />
                          <span>{job.delivery_city}{job.geo_radius_km ? ` (до ${job.geo_radius_km} км)` : ""}</span>
                        </span>
                      ) : null}
                      {job.geo_scope && job.geo_scope !== "ru" ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-slate-700 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded">
                          <Globe size={10} aria-hidden="true" />
                          <span>{job.geo_scope === "cis" ? "РФ и СНГ (ЕАЭС)" : "Весь мир"}</span>
                        </span>
                      ) : null}
                    </div>
                  </div>

                  {/* Column 2: Honest Status & Live Progress ONLY When Active (3/12 = 25%) */}
                  <div className="col-span-12 md:col-span-3 flex flex-col items-start gap-1 min-w-0">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold border whitespace-nowrap leading-tight w-max max-w-full ${
                        job.status_label === "нет в реестре" || job.status_label === "не найдено в Минпромторге"
                          ? "bg-slate-100 text-slate-700 border-slate-300"
                          : isFailed
                          ? "bg-rose-50 text-rose-800 border-rose-200"
                          : isCancelledOrDeclined
                          ? "bg-slate-100 text-slate-600 border-slate-200"
                          : isExpired
                          ? "bg-amber-50 text-amber-800 border-amber-200"
                          : isPending
                          ? "bg-amber-50 text-amber-900 border-amber-300"
                          : isAwaiting || isAwaitingExactSelection
                          ? "bg-sky-50 text-sky-900 border-sky-200"
                          : "bg-emerald-50 text-emerald-900 border-emerald-200"
                      }`}
                    >
                      {isPending ? <Loader2 size={11} className="animate-spin text-amber-700 shrink-0" aria-hidden="true" /> : null}
                      <span>{cleanStatusLabel}</span>
                    </span>

                    {isPending ? (
                      <div className="w-full space-y-1">
                        <JobStageSteps progress={job.progress} />
                        <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden" aria-label={`Прогресс ${job.progress}%`}>
                          <i
                            className="block h-full transition-all rounded-full bg-teal-700"
                            style={{ width: `${Math.max(4, Math.min(100, job.progress))}%` }}
                          />
                        </div>
                        <span className="text-[11px] text-slate-600 leading-snug block truncate tl-num">
                          {cleanMessage || `${job.progress}%`}
                        </span>
                      </div>
                    ) : job.error && job.status_label !== "нет в реестре" && job.status_label !== "не найдено в Минпромторге" ? (
                      <small className="text-rose-700 text-[11px] leading-snug block break-words">
                        {job.error}
                      </small>
                    ) : cleanMessage && cleanMessage.toLowerCase() !== cleanStatusLabel.toLowerCase() && cleanMessage !== "Готово" ? (
                      <span className="text-[11px] text-slate-500 leading-snug block truncate tl-num" title={cleanMessage}>
                        {cleanMessage}
                      </span>
                    ) : null}
                  </div>

                  {/* Column 3: Result Files & Actions (4/12 = 33%) */}
                  <div className="col-span-12 md:col-span-4 flex flex-wrap items-center gap-1.5 md:justify-end min-w-0">
                    {isFailed || isExpired || isCancelledOrDeclined ? (
                      <>
                        {job.mode === "supplier_search" && (job.supplier_search_policy === "minprom_registry_only" || job.error?.toLowerCase().includes("реестр") || job.message?.toLowerCase().includes("реестр")) ? (
                          <button
                            type="button"
                            className="tl-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer shrink-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              setRetryConfirmJob(job);
                              setRetryPolicy("normal");
                              setRetryMultiItemMode(normalizeMultiItemMode(job.multi_item_mode));
                            }}
                            disabled={busy}
                          >
                            <Search size={14} aria-hidden="true" />
                            <span>Найти обычным поиском</span>
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-amber-50 text-amber-800 border border-amber-300 rounded-lg text-xs font-semibold transition-colors cursor-pointer shrink-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              setRetryConfirmJob(job);
                              setRetryPolicy(normalizeSupplierSearchPolicy(job.supplier_search_policy));
                              setRetryMultiItemMode(normalizeMultiItemMode(job.multi_item_mode));
                            }}
                            disabled={busy}
                          >
                            <RotateCcw size={14} className="text-amber-700" aria-hidden="true" />
                            <span>{job.mode === "exact_product" ? "Повторить подбор" : job.mode === "price_monitoring" ? "Повторить мониторинг" : job.mode === "procurement_report" ? "Повторить анализ" : "Повторить поиск"}</span>
                          </button>
                        )}
                      </>
                    ) : null}

                    {isAwaitingExactSelection ? (
                      <div className="flex items-center gap-2 flex-wrap">
                        <button
                          type="button"
                          className="tl-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer"
                          onClick={(event) => {
                            event.stopPropagation();
                            dismissedExactSelectionJobIdsRef.current.delete(exactSelectionKey(job));
                            openExactSelectionModal(job);
                          }}
                        >
                          <CheckCircle2 size={14} aria-hidden="true" />
                          <span>Выбрать позиции ({jobPositionSelection?.items.length || 0})</span>
                        </button>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                          onClick={(event) => {
                            event.stopPropagation();
                            void cancelJob(job);
                          }}
                          disabled={busy}
                        >
                          <XCircle size={14} aria-hidden="true" />
                          <span>Отменить</span>
                        </button>
                      </div>
                    ) : job.awaiting_customer_confirmation ? (
                      job.confirmation_kind === "multi_item_strategy" ? (
                        (() => {
                          const items = job.multi_item_details?.items || [];
                          return (
                            <div className="flex items-center gap-2 flex-wrap">
                              <button
                                type="button"
                                className="tl-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  unmarkStrategyDismissed(job.id);
                                  openStrategyConfirmModal(job);
                                }}
                              >
                                <Sliders size={14} aria-hidden="true" />
                                <span>Выбрать стратегию{items.length > 0 ? ` (${items.length} ${pluralizeRu(items.length, ["категория", "категории", "категорий"])})` : ""}</span>
                              </button>
                              <button
                                type="button"
                                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  void cancelJob(job);
                                }}
                                disabled={busy}
                              >
                                <XCircle size={14} className="text-rose-600" aria-hidden="true" />
                                <span>Отменить</span>
                              </button>
                            </div>
                          );
                        })()
                      ) : (
                        <>
                          {!offer || offer.can_accept ? (
                            <button
                              type="button"
                              className="tl-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer"
                              onClick={(e) => {
                                e.stopPropagation();
                                markJobAsViewed(job.id);
                                acceptPartial(job);
                              }}
                              disabled={busy}
                            >
                              <CheckCircle2 size={15} aria-hidden="true" />
                              <span>{offer?.kind === "registry_fallback" ? "Получить без реестра" : offer?.kind === "admin_supplement_offer" ? `Принять и оплатить (${offer.charge_amount_rub || 0} ₽)` : "Получить и списать"}</span>
                            </button>
                          ) : null}
                          {!offer || offer.can_decline ? (
                            <button
                              type="button"
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                              onClick={(e) => {
                                e.stopPropagation();
                                markJobAsViewed(job.id);
                                declinePartial(job);
                              }}
                              disabled={busy}
                            >
                              <XCircle size={15} className="text-rose-600" aria-hidden="true" />
                              <span>Отказаться</span>
                            </button>
                          ) : null}
                        </>
                      )
                    ) : (
                      <>
                        {job.can_cancel ? (
                          <button
                            type="button"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 rounded-lg text-xs font-semibold transition-colors cursor-pointer shrink-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              void cancelJob(job);
                            }}
                            disabled={busy}
                          >
                            <XCircle size={14} className="text-rose-600" aria-hidden="true" />
                            <span>Отменить</span>
                          </button>
                        ) : null}
                        {job.is_custom_batch_report && job.status !== "cancelled" && job.status !== "failed" ? (
                          <button
                            type="button"
                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors cursor-pointer shrink-0 border ${
                              isUnviewed || isPending
                                ? "tl-btn-primary"
                                : "bg-white hover:bg-slate-50 text-slate-800 border-slate-300 hover:border-slate-400 font-semibold"
                            }`}
                            onClick={(e) => {
                              e.stopPropagation();
                              markJobAsViewed(job.id);
                              void openBatchReportReader(job.id, true);
                            }}
                            disabled={busy}
                          >
                            <Eye size={14} className={isUnviewed || isPending ? "" : "text-[#174b3f]"} aria-hidden="true" />
                            <span>{job.status === "running" || job.status === "pending" ? "Смотреть ход разбора" : "Открыть ответы ИИ"}</span>
                          </button>
                        ) : null}
                        {job.result_files?.length ? (
                          job.result_files.map((file, fileIdx) => {
                            const isQuoteRequest = file.kind === "quote_request";
                            const isSuppliers = file.kind === "suppliers_excel" || file.kind === "suppliers" || file.filename?.endsWith(".xlsx") || (file.label && file.label.toLowerCase().includes("поставщик"));
                            const isAdminSupplement = file.kind === "admin_supplement" || file.is_admin_supplement;
                            const isPrimaryDownload = !job.is_custom_batch_report && !isQuoteRequest && fileIdx === 0 && isUnviewed;
                            return (
                                <button
                                key={`${job.id}-${file.kind}`}
                                type="button"
                                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors cursor-pointer shrink-0 border ${
                                  isAdminSupplement
                                    ? "bg-emerald-700 hover:bg-emerald-800 text-white border-emerald-700 font-bold"
                                    : isPrimaryDownload
                                    ? "tl-btn-primary font-bold"
                                    : "bg-white hover:bg-slate-50 text-slate-800 border-slate-300 hover:border-slate-400 font-semibold"
                                }`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  markJobAsViewed(job.id);
                                  if (isQuoteRequest) openQuoteRequest(job, file);
                                  else downloadJobFile(job, file);
                                }}
                                disabled={busy}
                              >
                                {isAdminSupplement || isPrimaryDownload ? (
                                  <Download size={14} aria-hidden="true" />
                                ) : isQuoteRequest ? (
                                  <FileText size={14} className="text-slate-600" aria-hidden="true" />
                                ) : isSuppliers ? (
                                  <FileSpreadsheet size={14} className="text-teal-800" aria-hidden="true" />
                                ) : (
                                  <FileText size={14} className="text-teal-800" aria-hidden="true" />
                                )}
                                <span>{formatArtifactLabel(file.label)}</span>
                              </button>
                            );
                          })
                        ) : null}
                        {job.can_find_more_suppliers ? (
                          <button
                            type="button"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-teal-50/50 text-teal-900 border border-slate-200 hover:border-teal-300 rounded-lg text-xs font-semibold transition-colors cursor-pointer shrink-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              markJobAsViewed(job.id);
                              setFindMoreConfirmJob(job);
                            }}
                            disabled={busy}
                          >
                            <Search size={14} className="text-teal-700" aria-hidden="true" />
                            <span>Найти ещё</span>
                          </button>
                        ) : null}
                        {job.can_start_supplier_search || (job.mode === "exact_product" && isCompletedWithResult) ? (
                          <button
                            type="button"
                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer shrink-0 border ${
                              isUnviewed
                                ? "bg-teal-50 hover:bg-teal-100/80 text-teal-950 border-teal-300"
                                : "tl-btn-primary"
                            }`}
                            onClick={(e) => {
                              e.stopPropagation();
                              markJobAsViewed(job.id);
                              setStartSupplierSearchConfirmJob(job);
                              setStartSupplierSearchPolicy("normal");
                              setStartSupplierSearchMultiItemMode(normalizeMultiItemMode(job.multi_item_mode));
                              setStartSupplierSearchAlternatives(true);
                              setStartSupplierSearchPrompt("");
                              setStartSupplierGeoEnabled(false);
                              setStartSupplierCity("");
                              setStartSupplierRadius(300);
                            }}
                            disabled={busy}
                            title="Найти поставщиков по подобранным товарам и аналогам"
                          >
                            <Search size={14} aria-hidden="true" />
                            <span>Найти поставщиков</span>
                          </button>
                        ) : null}
                        {(() => {
                          if (job.mode !== "analysis_and_suppliers" || !isFailed) {
                            return null;
                          }
                          const hasAnalysisResult = job.result_files?.some(f => f.kind === "procurement_report" || f.kind === "report" || (f.label && f.label.toLowerCase().includes("анализ")));
                          const hasSupplierResult = job.result_files?.some(f => f.kind === "suppliers_excel" || f.kind === "suppliers" || (f.label && f.label.toLowerCase().includes("поставщик")));

                          if (hasAnalysisResult && !hasSupplierResult) {
                            return (
                              <button
                                type="button"
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200/90 hover:border-slate-300 rounded-md text-xs font-medium shadow-xs transition-colors cursor-pointer shrink-0"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setRetryConfirmJob(job);
                                  setRetryPolicy(normalizeSupplierSearchPolicy(job.supplier_search_policy));
                                  setRetryMultiItemMode(normalizeMultiItemMode(job.multi_item_mode));
                                }}
                                disabled={busy}
                                title="Продолжить поиск поставщиков"
                              >
                                <RotateCcw size={14} aria-hidden="true" />
                                <span>Продолжить поиск</span>
                              </button>
                            );
                          }
                          return null;
                        })()}
                        {isCompletedWithResult && (job.mode === "supplier_search" || job.mode === "analysis_and_suppliers") ? (
                          <button
                            type="button"
                            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200/90 hover:border-slate-300 rounded-lg text-xs font-medium transition-colors cursor-pointer shrink-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              setRetryConfirmJob(job);
                              setRetryPolicy(normalizeSupplierSearchPolicy(job.supplier_search_policy));
                              setRetryMultiItemMode(normalizeMultiItemMode(job.multi_item_mode));
                            }}
                            disabled={busy}
                            title="Повторить поиск с другими параметрами (квота, реестр Минпромторга)"
                          >
                            <RotateCcw size={13} aria-hidden="true" />
                            <span>Повторить</span>
                          </button>
                        ) : null}
                      </>
                    )}
                    {!hasJobMessages ? (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          window.dispatchEvent(
                            new CustomEvent("open_tenderlex_chat", {
                              detail: {
                                jobId: job.id,
                                jobNumber: job.job_number,
                                jobTitle: cleanTitle,
                              },
                            })
                          );
                        }}
                        className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs font-medium text-slate-500 hover:text-[#174b3f] hover:bg-slate-100 border border-transparent hover:border-slate-200 transition-colors cursor-pointer shrink-0"
                        title="Написать специалисту TenderLex по задаче"
                        aria-label="Написать специалисту TenderLex по задаче"
                      >
                        <MessageCircle size={13} aria-hidden="true" />
                        <span>Вопрос</span>
                      </button>
                    ) : null}
                  </div>
                  {job.mode === "exact_product" && job.exact_product_positions?.length ? (
                    <div className="col-span-12 mt-2 p-2.5 rounded-xl bg-slate-50/90 border border-slate-200/90 text-xs">
                      <details className="group">
                        <summary className="flex items-center justify-between gap-2 cursor-pointer list-none select-none">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-bold text-[11px] bg-teal-50 text-teal-800 border border-teal-200">
                              <CheckCircle2 size={12} aria-hidden="true" />
                              Результаты по позициям
                            </span>
                            <span className="text-slate-600 font-medium text-[11px]">
                              {job.exact_product_positions.length} {pluralizeRu(job.exact_product_positions.length, ["позиция", "позиции", "позиций"])}
                            </span>
                          </div>
                          <span className="text-teal-700 text-[11px] font-semibold flex items-center gap-1">
                            <span className="group-open:hidden">Показать</span>
                            <span className="hidden group-open:inline">Скрыть</span>
                            <ChevronDown size={13} className="group-open:rotate-180 transition-transform duration-200" aria-hidden="true" />
                          </span>
                        </summary>
                        <div className="mt-2.5 pt-2 border-t border-slate-200 space-y-2">
                          {job.exact_product_positions.map((position, index) => (
                            <div key={position.id || `${position.position_no || index}-${position.name}`} className="rounded-lg bg-white border border-slate-200 p-2.5 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <p className="font-bold text-slate-900">
                                  {position.position_no || index + 1}. {position.name}
                                </p>
                                <p className="mt-0.5 text-[11px] text-slate-600">
                                  {({ found: "Модель подтверждена", needs_clarification: "Требуется уточнение характеристик", not_found: "Модель не найдена", error: "Ошибка проверки" } as Record<string, string>)[position.status || ""] || position.status || (position.model ? "Подобрана модель" : "Требуется проверка")}
                                  {position.model ? ` · ${position.model}` : ""}
                                  {position.manufacturer ? ` · ${position.manufacturer}` : ""}
                                </p>
                                {position.error ? <p className="mt-1 text-[11px] text-amber-800">{position.error}</p> : null}
                                {position.source_url ? <a className="mt-1 inline-flex text-[11px] font-semibold text-teal-700 hover:text-teal-900 underline" href={position.source_url} target="_blank" rel="noreferrer">Источник для проверки</a> : null}
                              </div>
                              {position.can_retry_position && position.id && job.exact_product_selection ? (
                                <button
                                  type="button"
                                  className="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-white hover:bg-amber-50 text-amber-800 border border-amber-300 rounded-md text-[11px] font-bold transition-colors cursor-pointer disabled:opacity-50"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void retryExactPosition(job, position.id);
                                  }}
                                  disabled={busy}
                                >
                                  <RotateCcw size={13} aria-hidden="true" />
                                  Новый подбор
                                </button>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      </details>
                    </div>
                  ) : null}

                  {job.awaiting_customer_confirmation && job.confirmation_kind === "admin_supplement_offer" && offer ? (
                    <div className="col-span-12 my-2.5 p-4 rounded-xl bg-gradient-to-r from-teal-50 via-emerald-50/70 to-teal-50 border border-teal-200 shadow-xs">
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-teal-700 text-white">
                              <Sparkles size={12} aria-hidden="true" />
                              <span>Предложение эксперта</span>
                            </span>
                            <span className="font-bold text-sm text-slate-800">
                              Готов пересчитанный отчёт
                            </span>
                          </div>
                          <p className="text-xs text-slate-700 leading-relaxed">
                            {offer.new_count && offer.new_count > 0 ? (
                              <>
                                Найдено <strong>{offer.new_count}</strong> позиций (ранее было {offer.prior_count || 0}).
                                {offer.delta_units && offer.delta_units > 0 ? ` Дополнительно подобрано +${offer.delta_units} поз.` : ""}
                              </>
                            ) : (
                              "Эксперты TenderLex подготовили доработанный отчёт по вашей спецификации."
                            )}
                            {offer.charge_amount_rub && offer.charge_amount_rub > 0 ? (
                              <> Стоимость доплаты с баланса: <strong className="text-teal-800 font-bold">{offer.charge_amount_rub} ₽</strong>.</>
                            ) : (
                              " Доплата не требуется."
                            )}
                          </p>
                          {offer.comment ? (
                            <p className="text-xs text-slate-600 italic border-l-2 border-teal-400 pl-2.5 mt-1.5">
                              «{offer.comment}»
                            </p>
                          ) : null}
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            type="button"
                            className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-xs font-bold shadow-xs transition-colors cursor-pointer"
                            onClick={(e) => {
                              e.stopPropagation();
                              markJobAsViewed(job.id);
                              acceptPartial(job);
                            }}
                            disabled={busy}
                          >
                            <CheckCircle2 size={15} aria-hidden="true" />
                            <span>Принять и оплатить ({offer.charge_amount_rub || 0} ₽)</span>
                          </button>

                          <button
                            type="button"
                            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                            onClick={(e) => {
                              e.stopPropagation();
                              markJobAsViewed(job.id);
                              declinePartial(job);
                            }}
                            disabled={busy}
                          >
                            <XCircle size={15} className="text-rose-600" aria-hidden="true" />
                            <span>Отказаться</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : null}

                  <CustomerJobChat
                    job={job}
                    csrf={csrf}
                    onJobUpdated={(updated) => {
                      setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
                    }}
                  />

                  {job.awaiting_customer_confirmation && job.confirmation_kind === "multi_item_strategy" ? (
                    <div className="col-span-12 mt-2 p-3 sm:p-3.5 rounded-2xl bg-gradient-to-r from-amber-50 to-teal-50/40 border border-amber-300 text-amber-950 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-2xs">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="w-8 h-8 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center shrink-0" aria-hidden="true">
                          <Sliders size={15} />
                        </span>
                        <div className="space-y-0.5 text-xs min-w-0">
                          <strong className="font-extrabold text-slate-900 block truncate">
                            В спецификации найдено {job.multi_item_details?.items?.length || 0} {pluralizeRu(job.multi_item_details?.items?.length || 0, ["позиция", "позиции", "позиций"])}: выберите стратегию поиска
                          </strong>
                          <p className="text-slate-600 text-[11px] leading-relaxed">
                            Стандартный сбалансированный поиск по всей спецификации выполняется в рамках вашего тарифа (без доплат).
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0 w-full sm:w-auto">
                        <button
                          type="button"
                          className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white rounded-xl text-xs font-bold shadow-xs transition-colors cursor-pointer"
                          onClick={(e) => {
                            e.stopPropagation();
                            void chooseStrategy(job, "balanced");
                          }}
                          disabled={busy || strategySubmittingJobId === job.id}
                        >
                          <CheckCircle2 size={14} aria-hidden="true" />
                          <span>Продолжить (без доплат)</span>
                        </button>
                        <button
                          type="button"
                          className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-100 text-slate-800 border border-slate-300 rounded-xl text-xs font-bold shadow-2xs transition-colors cursor-pointer"
                          onClick={(e) => {
                            e.stopPropagation();
                            unmarkStrategyDismissed(job.id);
                            openStrategyConfirmModal(job);
                          }}
                          disabled={busy}
                        >
                          <Sliders size={14} aria-hidden="true" />
                          <span>Настроить</span>
                        </button>
                      </div>
                    </div>
                  ) : null}

                  {(!job.awaiting_customer_confirmation || job.confirmation_kind !== "multi_item_strategy") &&
                  job.multi_item_details?.items &&
                  job.multi_item_details.items.length > 1 ? (
                    <div className="col-span-12 mt-2 p-2.5 rounded-xl bg-slate-50/90 border border-slate-200/90 text-xs">
                      <details className="group">
                        <summary className="flex items-center justify-between cursor-pointer list-none select-none">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-bold text-[11px] bg-teal-50 text-teal-800 border border-teal-200">
                              <Sliders size={11} aria-hidden="true" />
                              <span>{job.multi_item_mode === "per_item" ? "Попозиционный поиск" : "Сбалансированный поиск"}</span>
                            </span>
                            <span className="text-slate-600 font-medium text-[11px]">
                              Категорий: <strong>{job.multi_item_details.items.length}</strong> · Товарных строк: <strong>{supplierStrategyRowCount(job)}</strong>
                            </span>
                          </div>
                          <span className="text-teal-700 text-[11px] font-semibold flex items-center gap-1 cursor-pointer">
                            <span className="group-open:hidden">Показать позиции</span>
                            <span className="hidden group-open:inline">Скрыть позиции</span>
                            <ChevronDown size={13} className="group-open:rotate-180 transition-transform duration-200" aria-hidden="true" />
                          </span>
                        </summary>
                        <div className="mt-2.5 pt-2 border-t border-slate-200 flex flex-wrap gap-1.5">
                          {job.multi_item_details.items.map((it, idx) => (
                            <span
                              key={it.id || idx}
                              className="inline-flex items-center gap-1 px-2.5 py-1 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 shadow-2xs"
                            >
                              <span className="font-bold text-slate-400">{idx + 1}.</span>
                              <span className="font-medium">{it.name}</span>
                              {it.quantity ? (
                                <span className="text-slate-400 text-[10px]">
                                  ({it.quantity} {it.unit || "шт."})
                                </span>
                              ) : null}
                            </span>
                          ))}
                        </div>
                      </details>
                    </div>
                  ) : null}
                </article>
              );
            })
          ) : (
            hasActiveJobFilters ? (
              <div className="p-8 text-center bg-slate-50 rounded-2xl border border-slate-200/60 text-slate-500 text-xs space-y-2">
                <p>По заданным фильтрам ничего не найдено.</p>
                <button
                  type="button"
                  onClick={resetJobFilters}
                  className="px-3 py-1.5 bg-white hover:bg-slate-100 text-teal-700 border border-slate-200 rounded-lg text-xs font-bold transition-colors cursor-pointer"
                >
                  Сбросить фильтры
                </button>
              </div>
            ) : (
              <div className="p-8 sm:p-10 text-center bg-gradient-to-br from-teal-50/60 via-slate-50 to-white rounded-2xl border-2 border-dashed border-teal-200 text-slate-700 text-xs space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-teal-100 text-teal-700 flex items-center justify-center mx-auto shadow-2xs">
                  <Sparkles size={24} />
                </div>
                <div className="max-w-md mx-auto space-y-1">
                  <h3 className="text-sm sm:text-base font-extrabold text-slate-900">
                    У вас пока нет выполненных задач
                  </h3>
                  <p className="text-slate-500 text-xs leading-relaxed">
                    Загрузите ваше техническое задание в форму выше или проверьте точность подбора поставщиков на готовом примере за 1 клик.
                  </p>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-3 pt-1">
                  <button
                    type="button"
                    onClick={fillDemoExample}
                    className="tl-btn-primary px-4 py-2 rounded-lg text-xs flex items-center gap-1.5 cursor-pointer"
                  >
                    <Sparkles size={14} />
                    <span>Попробовать на демо-ТЗ в 1 клик</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const launcher = document.getElementById("new-job");
                      if (launcher) launcher.scrollIntoView({ behavior: "smooth" });
                    }}
                    className="px-4 py-2 rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 font-bold text-xs transition-all cursor-pointer"
                  >
                    Перейти к загрузке ТЗ
                  </button>
                </div>
              </div>
            )
          )}

          {isWorkspaceCollapsed ? (
            <div className="tl-workspace-more-bar">
              <span className="tl-num">
                Показаны {visibleJobs.length} последних задач из {jobsTotal}
              </span>
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => setShowAllWorkspaceJobs(true)}
                  className="px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 text-xs font-semibold transition-colors cursor-pointer tl-num"
                >
                  Показать ещё {jobs.length - visibleJobs.length} на странице
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCabinetSection("jobs");
                    if (typeof window !== "undefined") {
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }
                  }}
                  className="tl-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer tl-num"
                >
                  <span>Открыть все {jobsTotal} {declensionTasks(jobsTotal)}</span>
                  <ArrowRight size={13} aria-hidden="true" />
                </button>
              </div>
            </div>
          ) : null}
        </div>

        {jobsTotal > jobsPageSize ? (
          <div className="flex items-center justify-center gap-1.5 pt-3 border-t border-slate-100 text-xs font-bold text-slate-700" aria-label="Навигация по задачам (нижняя)">
            <button
              type="button"
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-bold transition-colors cursor-pointer disabled:opacity-50"
              onClick={() => {
                setJobsPage((page) => Math.max(1, page - 1));
                const el = document.getElementById("jobs");
                if (el) el.scrollIntoView({ behavior: "smooth" });
              }}
              disabled={jobsPage <= 1 || jobsLoading}
            >
              Назад
            </button>
            <span className="px-2 text-xs font-medium text-slate-600">
              Страница {jobsPage} из {jobsPageCount}
            </span>
            <button
              type="button"
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-bold transition-colors cursor-pointer disabled:opacity-50"
              onClick={() => {
                setJobsPage((page) => Math.min(jobsPageCount, page + 1));
                const el = document.getElementById("jobs");
                if (el) el.scrollIntoView({ behavior: "smooth" });
              }}
              disabled={jobsPage >= jobsPageCount || jobsLoading}
            >
              Вперёд
            </button>
          </div>
        ) : null}
      </section>

      {batchPreview && batchPreview.requires_sheet_selection && batchPreview.sheet_names.length > 1 ? (
        <BatchSheetSelectorModal
          preview={batchPreview}
          busy={batchBusy}
          error={batchModalError}
          onConfirmSheets={(chosenSheets) => {
            if (batchPreview.file) {
              void inspectBatchRegistryFile(
                batchPreview.file,
                chosenSheets,
                batchPreview.target_mode || "custom_batch_report"
              );
            }
          }}
          onClose={() => {
            if (!batchBusy) {
              setBatchPreview(null);
              setBatchSelectedIds([]);
              setBatchModalError("");
            }
          }}
        />
      ) : batchPreview ? (
        <BatchSelectionModal
          preview={batchPreview}
          selectedIds={batchSelectedIds}
          busy={batchBusy}
          error={batchModalError}
          onToggleItem={(id) =>
            setBatchSelectedIds((prev) =>
              prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
            )
          }
          onSelectAllVisible={(visibleIds) => {
            const fallbackCap =
              batchPreview.target_mode === "procurement_report"
                ? 10
                : session?.user?.batch_report_max_items || 30;
            const maxItems = Math.max(1, batchPreview.max_items || fallbackCap);
            setBatchSelectedIds((prev) => Array.from(new Set([...prev, ...visibleIds])).slice(0, maxItems));
          }}
          onClearAll={() => setBatchSelectedIds([])}
          onOpenSheetSelector={() => {
            setBatchModalError("");
            setBatchPreview((prev) => (prev ? { ...prev, requires_sheet_selection: true } : null));
          }}
          onConfirm={() => void confirmBatchReportLaunch()}
          onClose={() => {
            if (!batchBusy) {
              setBatchPreview(null);
              setBatchSelectedIds([]);
              setBatchModalError("");
            }
          }}
        />
      ) : null}

      {batchReaderData ? (
        <BatchResultsReaderModal
          data={batchReaderData}
          activeIndex={batchReaderActiveIdx}
          onSelectIndex={setBatchReaderActiveIdx}
          onDownloadItemDocx={(jobId, idx, fname) => void downloadBatchItemDocx(jobId, idx, fname)}
          onDownloadAllZip={(jobId) => {
            const found = jobs.find((j) => j.id === jobId);
            if (found) void downloadJob(found);
          }}
          onOpenDetailedAnalysis={(noticeNum) => {
            setBatchReaderData(null);
            setCabinetSection("workspace");
            selectScenario("procurement_report");
            setSourceUrls(noticeNum);
            if (typeof window !== "undefined") {
              window.scrollTo({ top: 0, behavior: "smooth" });
            }
          }}
          onClose={() => setBatchReaderData(null)}
        />
      ) : null}

      {quoteRequestModal ? (
        <div
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 overflow-y-auto"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setQuoteRequestModal(null);
              setQuoteItemSearch("");
            }
          }}
        >
          <section className="bg-white rounded-2xl p-6 sm:p-8 max-w-3xl w-full shadow-2xl border border-slate-200 space-y-5 max-h-[92vh] flex flex-col font-sans" role="dialog" aria-modal="true" aria-labelledby="quote-request-title">
            <header className="flex items-center justify-between pb-3.5 border-b border-slate-200 shrink-0">
              <div>
                <h2 id="quote-request-title" className="text-lg font-extrabold text-slate-900">Запрос коммерческого предложения</h2>
                <span className="text-xs text-slate-500 font-medium">{quoteRequestModal.job.human_title}</span>
              </div>
              <button
                type="button"
                className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-colors shrink-0 cursor-pointer"
                onClick={() => {
                  setQuoteRequestModal(null);
                  setQuoteItemSearch("");
                }}
                disabled={busy}
                aria-label="Закрыть"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </header>
            {quoteRequestModal.items && quoteRequestModal.items.length > 1 ? (() => {
              const query = quoteItemSearch.trim().toLowerCase();
              const filteredItems = query
                ? quoteRequestModal.items.filter(
                    (it) =>
                      it.name.toLowerCase().includes(query) ||
                      String(it.index + 1).includes(query)
                  )
                : quoteRequestModal.items;
              const matchingIndexes = filteredItems.map((it) => it.index);
              return (
                <div className="bg-slate-50 p-3 sm:p-3.5 rounded-2xl border border-slate-200/90 space-y-2.5 shrink-0">
                  <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-800">
                        Позиции для запроса КП:
                      </span>
                      <span className="px-2 py-0.5 bg-teal-100 text-teal-800 font-bold rounded-full text-[11px]">
                        {quoteRequestModal.selectedItemIndexes.length} из {quoteRequestModal.items.length}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 text-[11px] flex-wrap">
                      <button
                        type="button"
                        onClick={() => toggleAllQuoteRequestItems(true)}
                        className="px-2.5 py-0.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-md font-semibold cursor-pointer shadow-2xs"
                      >
                        Выбрать все
                      </button>
                      {quoteRequestModal.items.length >= 10 && (
                        <button
                          type="button"
                          onClick={() => selectFirstNQuoteRequestItems(10)}
                          className="px-2.5 py-0.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-md font-semibold cursor-pointer shadow-2xs"
                        >
                          Первые 10
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => invertQuoteRequestItems()}
                        className="px-2.5 py-0.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-md font-semibold cursor-pointer shadow-2xs"
                      >
                        Инвертировать
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleAllQuoteRequestItems(false)}
                        className="px-2.5 py-0.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-md font-semibold cursor-pointer shadow-2xs"
                      >
                        Сброс
                      </button>
                    </div>
                  </div>

                  {quoteRequestModal.items.length > 4 && (
                    <div className="flex items-center gap-2">
                      <div className="relative flex-1">
                        <input
                          type="text"
                          value={quoteItemSearch}
                          onChange={(e) => setQuoteItemSearch(e.target.value)}
                          placeholder="Поиск по названию или номеру позиции..."
                          className="w-full pl-8 pr-7 py-1 text-xs bg-white border border-slate-200 rounded-lg focus:outline-hidden focus:border-teal-500 focus:ring-1 focus:ring-teal-500 text-slate-800 placeholder-slate-400"
                        />
                        <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" aria-hidden="true" />
                        {quoteItemSearch && (
                          <button
                            type="button"
                            onClick={() => setQuoteItemSearch("")}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
                            aria-label="Очистить поиск"
                          >
                            <X size={12} />
                          </button>
                        )}
                      </div>
                      {quoteItemSearch && (
                        <button
                          type="button"
                          onClick={() => selectMatchingQuoteRequestItems(matchingIndexes)}
                          disabled={matchingIndexes.length === 0}
                          className="px-2.5 py-1 text-[11px] font-semibold bg-teal-50 text-teal-800 hover:bg-teal-100 disabled:opacity-50 border border-teal-200 rounded-lg shrink-0 cursor-pointer"
                        >
                          Выбрать найденные ({matchingIndexes.length})
                        </button>
                      )}
                    </div>
                  )}

                  <div className="flex flex-wrap gap-1.5 max-h-[130px] overflow-y-auto pr-1">
                    {filteredItems.length === 0 ? (
                      <div className="text-xs text-slate-400 py-2 text-center w-full">
                        Ничего не найдено по запросу «{quoteItemSearch}»
                      </div>
                    ) : (
                      filteredItems.map((item) => {
                        const isSelected = quoteRequestModal.selectedItemIndexes.includes(item.index);
                        return (
                          <button
                            key={item.index}
                            type="button"
                            title={item.name}
                            onClick={() => toggleQuoteRequestItem(item.index)}
                            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-all cursor-pointer text-left max-w-full ${
                              isSelected
                                ? "bg-teal-50 border-teal-300 text-teal-900 font-bold shadow-2xs"
                                : "bg-white border-slate-200 text-slate-600 hover:border-slate-300"
                            }`}
                          >
                            <span
                              className={`w-3.5 h-3.5 rounded flex items-center justify-center text-[10px] shrink-0 border ${
                                isSelected ? "bg-teal-600 border-teal-600 text-white" : "border-slate-300 bg-white"
                              }`}
                            >
                              {isSelected ? "✓" : ""}
                            </span>
                            <span className="truncate max-w-[260px]">
                              {item.index + 1}. {item.name}
                            </span>
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              );
            })() : null}
            <div
              ref={quoteEditorRef}
              className="flex-1 overflow-y-auto p-5 bg-white border border-slate-200 rounded-2xl font-sans text-xs text-slate-900 space-y-4 min-h-[220px] max-h-[46vh] shadow-inner leading-relaxed"
              contentEditable
              suppressContentEditableWarning
              onPaste={(event) => {
                event.preventDefault();
                document.execCommand("insertText", false, event.clipboardData.getData("text/plain"));
              }}
              dangerouslySetInnerHTML={{ __html: quoteRequestModal.html }}
              onInput={() => {
                if (quoteRequestModal.copied) {
                  setQuoteRequestModal({ ...quoteRequestModal, html: quoteEditorRef.current?.innerHTML || quoteRequestModal.html, copied: false });
                }
              }}
              aria-label="Текст запроса коммерческого предложения"
            />
            <div className="flex items-center justify-end gap-3 pt-3.5 border-t border-slate-200 shrink-0">
              <button
                type="button"
                className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 font-bold text-xs rounded-xl transition-all cursor-pointer"
                onClick={() => {
                  setQuoteRequestModal(null);
                  setQuoteItemSearch("");
                }}
                disabled={busy}
              >
                Закрыть
              </button>
              <button type="button" className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-300 font-bold text-xs rounded-xl transition-all cursor-pointer" onClick={() => void copyQuoteRequestText()} disabled={busy}>
                <Copy size={16} aria-hidden="true" />
                <span>{quoteRequestModal.copied ? "Скопировано" : "Копировать"}</span>
              </button>
              <button className="tl-btn-primary px-6 py-2.5 text-xs rounded-xl shadow-sm transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50" type="button" onClick={() => void downloadEditedQuoteRequest()} disabled={busy}>
                {busy ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <Download size={16} aria-hidden="true" />}
                <span>Скачать Word</span>
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {findMoreConfirmJob ? (
        <div
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setFindMoreConfirmJob(null);
              setFindMorePrompt("");
            }
          }}
        >
          <section className="bg-white rounded-2xl p-6 max-w-md w-full shadow-2xl border border-slate-200 space-y-4 font-sans text-center" role="dialog" aria-modal="true" aria-labelledby="find-more-confirm-title">
            <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-700 mx-auto flex items-center justify-center border border-amber-200 shadow-2xs mb-2">
              <Search size={20} aria-hidden="true" />
            </div>
            <div className="space-y-1">
              <h2 id="find-more-confirm-title" className="text-base font-extrabold text-slate-900">Найти ещё поставщиков?</h2>
              <p className="text-xs text-slate-600 leading-relaxed">С баланса спишется стоимость добора поставщиков. Уже найденные компании не попадут в новый результат.</p>
              <span className="text-[11px] font-bold text-slate-400 block mt-1">{findMoreConfirmJob.human_title}</span>
            </div>
            {findMoreConfirmJob.multi_item_details?.items && findMoreConfirmJob.multi_item_details.items.length > 1 ? (
              <div className="p-3 rounded-xl bg-teal-50/70 border border-teal-200 text-left text-xs text-slate-700 space-y-1 my-2">
                <div className="flex items-center gap-1.5 font-bold text-teal-900">
                  <span>Режим добора:</span>
                  <span className="font-extrabold text-teal-800">
                    {findMoreConfirmJob.multi_item_mode === "per_item" ? "Попозиционный поиск" : "Сбалансированный поиск"}
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 leading-snug">
                  Поиск новых поставщиков будет продолжен по всем {findMoreConfirmJob.multi_item_details.items.length} позициям ТЗ без дублирования уже найденных компаний.
                </p>
              </div>
            ) : null}
            <div className="text-left space-y-1 pt-1">
              <label htmlFor="dobor-prompt-input" className="block text-[11px] font-semibold text-slate-500">
                Дополнительные критерии (опционально):
              </label>
              <input
                id="dobor-prompt-input"
                type="text"
                value={findMorePrompt}
                onChange={(e) => setFindMorePrompt(e.target.value)}
                placeholder="Например: дистрибьюторы со складом, поставщики аналогов..."
                className="w-full text-xs px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-slate-50 text-slate-800"
              />
            </div>
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 font-bold text-xs rounded-xl transition-all cursor-pointer"
                type="button"
                onClick={() => {
                  setFindMoreConfirmJob(null);
                  setFindMorePrompt("");
                }}
                disabled={busy}
              >
                Отмена
              </button>
              <button
                className="tl-btn-primary px-6 py-2.5 text-xs rounded-xl shadow-sm transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                type="button"
                onClick={() => void findMoreSuppliers(findMoreConfirmJob)}
                disabled={busy}
              >
                {busy ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <Search size={16} aria-hidden="true" />}
                <span>Продолжить</span>
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {startSupplierSearchConfirmJob ? (
        <div
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6 z-50 overflow-y-auto"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setStartSupplierSearchConfirmJob(null);
            }
          }}
        >
          <section
            className="bg-white rounded-2xl max-w-2xl w-full shadow-2xl border border-slate-200 overflow-hidden flex flex-col font-sans text-left my-auto"
            role="dialog"
            aria-modal="true"
            aria-labelledby="start-suppliers-confirm-title"
          >
            {/* Header with Title, Procurement Name and Close Button */}
            <header className="px-6 py-3.5 sm:py-4 border-b border-slate-200/90 flex items-center justify-between bg-gradient-to-r from-slate-50 to-teal-50/40 shrink-0">
              <div className="flex items-center gap-3 min-w-0 pr-2">
                <div className="w-9 h-9 rounded-xl bg-teal-600 text-white flex items-center justify-center shrink-0 shadow-sm">
                  <Search size={18} aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <h2 id="start-suppliers-confirm-title" className="text-sm sm:text-base font-extrabold text-slate-900 leading-tight">
                    Поиск поставщиков по подобранным товарам
                  </h2>
                  <p className="text-[11px] text-slate-500 font-medium truncate mt-0.5 max-w-md sm:max-w-lg">
                    ТЗ: {startSupplierSearchConfirmJob.human_title}
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-xl transition-all shrink-0 cursor-pointer"
                onClick={() => setStartSupplierSearchConfirmJob(null)}
                aria-label="Закрыть"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </header>

            {/* Content Body */}
            <div className="p-5 sm:p-6 space-y-3 sm:space-y-3.5 overflow-y-auto max-h-[75vh]">
              {/* Unified Equipment Card (Primary + Analogs together) */}
              {startSupplierSearchConfirmJob.exact_product_summary ? (
                <div className="bg-teal-50/35 border border-teal-200/80 rounded-2xl p-3 sm:p-3.5 space-y-2">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-teal-600 text-white uppercase tracking-wider shrink-0">
                        <CheckCircle2 size={11} aria-hidden="true" />
                        Точный товар
                      </span>
                      <strong className="text-xs sm:text-sm font-extrabold text-slate-900 leading-snug truncate">
                        {startSupplierSearchConfirmJob.exact_product_summary.primary_product}
                      </strong>
                    </div>
                    {startSupplierSearchConfirmJob.exact_product_summary.total_positions && startSupplierSearchConfirmJob.exact_product_summary.total_positions > 1 ? (
                      <span className="text-[11px] text-teal-800 font-semibold shrink-0">
                        Всего позиций: {startSupplierSearchConfirmJob.exact_product_summary.total_positions}
                      </span>
                    ) : null}
                  </div>

                  {startSupplierSearchConfirmJob.exact_product_summary.alternatives?.length ? (
                    <div className="pt-1.5 border-t border-teal-200/50 flex items-baseline gap-2 flex-wrap">
                      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider shrink-0">
                        Аналоги ({startSupplierSearchConfirmJob.exact_product_summary.alternatives.length}):
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {startSupplierSearchConfirmJob.exact_product_summary.alternatives.map((alt, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-white border border-slate-200/90 text-[11px] font-semibold text-slate-800 shadow-2xs"
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-teal-500 shrink-0" />
                            {alt}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {/* Multi-Item Mode Selection (Only for Multi-Position Specs) */}
              {(startSupplierSearchConfirmJob.exact_product_summary?.total_positions || 0) > 1 ? (
                <div className="space-y-1.5">
                  <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                    Режим для многопозиционных спецификаций:
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setStartSupplierSearchMultiItemMode("balanced")}
                      className={`p-2.5 sm:p-3 rounded-2xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                        startSupplierSearchMultiItemMode === "balanced"
                          ? "bg-teal-50/70 border-teal-500 ring-2 ring-teal-500/20 text-slate-900 shadow-2xs font-bold"
                          : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 text-slate-700"
                      }`}
                    >
                      <div className="flex items-center justify-between w-full mb-0.5">
                        <span className="text-xs font-extrabold">Сбалансированный поиск</span>
                        <span className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 ${startSupplierSearchMultiItemMode === "balanced" ? "border-teal-600 bg-teal-600" : "border-slate-300 bg-white"}`}>
                          {startSupplierSearchMultiItemMode === "balanced" ? <span className="w-1 h-1 rounded-full bg-white" /> : null}
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-500 font-normal leading-snug">Единая квота поставщиков распределяется по всем позициям ТЗ, формируется единый Excel со сворачиваемой структурой (+ / -)</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setStartSupplierSearchMultiItemMode("per_item")}
                      className={`p-2.5 sm:p-3 rounded-2xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                        startSupplierSearchMultiItemMode === "per_item"
                          ? "bg-teal-50/70 border-teal-500 ring-2 ring-teal-500/20 text-slate-900 shadow-2xs font-bold"
                          : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 text-slate-700"
                      }`}
                    >
                      <div className="flex items-center justify-between w-full mb-0.5">
                        <span className="text-xs font-extrabold">Попозиционный глубокий поиск</span>
                        <span className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 ${startSupplierSearchMultiItemMode === "per_item" ? "border-teal-600 bg-teal-600" : "border-slate-300 bg-white"}`}>
                          {startSupplierSearchMultiItemMode === "per_item" ? <span className="w-1 h-1 rounded-full bg-white" /> : null}
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-500 font-normal leading-snug">Глубокий пул поставщиков под каждую позицию спецификации с отдельным анализом</span>
                    </button>
                  </div>
                </div>
              ) : null}

              {/* Policy Selection Cards */}
              <div className="space-y-1.5">
                <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                  Требования к реестру Минпромторга РФ:
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {[
                    {
                      id: "normal",
                      label: "Обычный поиск",
                      desc: "Кандидаты по заданным условиям",
                    },
                    {
                      id: "minprom_registry_priority",
                      label: "Реестр в приоритете",
                      desc: "Производители из ГИСП в приоритете",
                    },
                    {
                      id: "minprom_registry_only",
                      label: "Только реестр",
                      desc: "Строго запись (44-ФЗ)",
                    },
                  ].map((opt) => {
                    const isSelected = startSupplierSearchPolicy === opt.id;
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => setStartSupplierSearchPolicy(opt.id as SupplierSearchPolicy)}
                        className={`p-2.5 sm:p-3 rounded-2xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                          isSelected
                            ? "bg-teal-50/70 border-teal-500 ring-2 ring-teal-500/20 text-slate-900 shadow-2xs"
                            : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 text-slate-700"
                        }`}
                      >
                        <div className="flex items-center justify-between w-full mb-0.5">
                          <span className="text-xs font-extrabold">{opt.label}</span>
                          <span className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 ${isSelected ? "border-teal-600 bg-teal-600" : "border-slate-300 bg-white"}`}>
                            {isSelected ? <span className="w-1 h-1 rounded-full bg-white" /> : null}
                          </span>
                        </div>
                        <span className="text-[11px] text-slate-500 leading-snug">{opt.desc}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Include Alternatives Checkbox Card */}
              <label className="flex items-center gap-2.5 p-2.5 sm:p-3 rounded-xl border border-slate-200/90 bg-slate-50/50 hover:bg-slate-100/60 transition-colors cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={startSupplierSearchAlternatives}
                  onChange={(e) => setStartSupplierSearchAlternatives(e.target.checked)}
                  className="sr-only"
                />
                <div
                  className={`w-4 h-4 rounded-md border flex items-center justify-center transition-all shrink-0 ${
                    startSupplierSearchAlternatives
                      ? "border-teal-600 bg-teal-600 text-white shadow-2xs"
                      : "border-slate-300 bg-white hover:border-slate-400"
                  }`}
                  aria-hidden="true"
                >
                  {startSupplierSearchAlternatives ? <Check size={11} strokeWidth={3.5} className="text-white" /> : null}
                </div>
                <div className="text-xs leading-snug">
                  <span className="text-slate-900 font-bold">Искать поставщиков как основного товара, так и аналогов</span>
                  <span className="text-slate-500 text-[11px] block mt-0.5">Рекомендуется: позволяет сравнить КП нескольких брендов и найти склады с наличием</span>
                </div>
              </label>

              {session?.user?.allowed_geo_radius ? <DeliveryPriorityControl geoRadiusEnabled={startSupplierGeoEnabled}
                deliveryCity={startSupplierCity} geoRadiusKm={startSupplierRadius} setGeoRadiusEnabled={setStartSupplierGeoEnabled}
                setDeliveryCity={setStartSupplierCity} setGeoRadiusKm={setStartSupplierRadius}
                surchargePct={session?.user?.geo_radius_surcharge_pct ?? 30} idPrefix="exact-supplier-" /> : null}

              {/* Additional Wishes Input */}
              <div className="space-y-1">
                <label htmlFor="exact-suppliers-prompt-input" className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                  Дополнительные пожелания к поиску (опционально):
                </label>
                <input
                  id="exact-suppliers-prompt-input"
                  type="text"
                  value={startSupplierSearchPrompt}
                  onChange={(e) => setStartSupplierSearchPrompt(e.target.value)}
                  placeholder="Например: склады в СПб, только официальные дистрибьюторы..."
                  className="w-full text-xs px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-slate-50/50 text-slate-800"
                />
              </div>
            </div>

            {/* Modal Actions Footer with integrated Billing notice */}
            <footer className="px-6 py-3.5 bg-slate-50 border-t border-slate-200/80 flex flex-col sm:flex-row items-center justify-between gap-3 shrink-0">
              <div className="flex items-center gap-2 text-xs text-slate-600 leading-tight">
                <span className="w-5 h-5 rounded-full bg-teal-50 border border-teal-200 text-teal-800 flex items-center justify-center shrink-0">
                  <Sparkles size={11} aria-hidden="true" />
                </span>
                <span>
                  <strong className="text-slate-800 font-bold">{startSupplierSearchMultiItemMode === "per_item" ? "По тарифу попозиционного поиска" : "1 поиск с баланса"}</strong> · Реестр контактов и запрос КП
                </span>
              </div>
              <div className="flex items-center gap-2.5 shrink-0 ml-auto">
                <button
                  type="button"
                  className="px-3.5 py-2 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 transition-all cursor-pointer"
                  onClick={() => setStartSupplierSearchConfirmJob(null)}
                  disabled={busy}
                >
                  Отмена
                </button>
                <button
                  type="button"
                  className="tl-btn-primary px-5 py-2 rounded-xl text-xs shadow-sm transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
                  onClick={() => void startSupplierSearchFromExact(startSupplierSearchConfirmJob)}
                  disabled={busy}
                >
                  {busy ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <Search size={15} aria-hidden="true" />}
                  <span>Запустить поиск поставщиков</span>
                </button>
              </div>
            </footer>
          </section>
        </div>
      ) : null}

      {strategyConfirmJob ? (() => {
        const pendingStrategyJobs = jobs.filter(
          (j) => j.awaiting_customer_confirmation && j.confirmation_kind === "multi_item_strategy"
        );
        const currentJobIndex = pendingStrategyJobs.findIndex((j) => j.id === strategyConfirmJob.id);
        const totalPending = pendingStrategyJobs.length;
        const strategyCategoryCount = strategyConfirmJob.multi_item_details?.items?.length || 0;
        const strategyRowCount = supplierStrategyRowCount(strategyConfirmJob);

        return (
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6 z-50 overflow-y-auto"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                skipOrDismissStrategyModal();
              }
            }}
          >
            <section
              className="bg-white rounded-2xl max-w-2xl w-full shadow-2xl border border-slate-200 overflow-hidden flex flex-col font-sans text-left my-auto"
              role="dialog"
              aria-modal="true"
              aria-labelledby="strategy-confirm-title"
            >
              {/* Header with Title, Procurement Name and Close Button */}
              <header className="px-6 py-4 border-b border-slate-200/90 flex items-center justify-between bg-gradient-to-r from-slate-50 to-teal-50/40 shrink-0">
                <div className="flex items-center gap-3 min-w-0 pr-2">
                  <div className="w-10 h-10 rounded-2xl bg-teal-600 text-white flex items-center justify-center shrink-0 shadow-sm">
                    <Sliders size={20} aria-hidden="true" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h2 id="strategy-confirm-title" className="text-sm sm:text-base font-extrabold text-slate-900 leading-tight">
                        Выбор стратегии поиска поставщиков
                      </h2>
                      {totalPending > 1 && currentJobIndex >= 0 ? (
                        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-extrabold bg-teal-100 text-teal-800 border border-teal-200 shrink-0">
                          Задача {currentJobIndex + 1} из {totalPending}
                        </span>
                      ) : null}
                    </div>
                    <p className="text-[11px] text-slate-500 font-medium truncate mt-0.5 max-w-md sm:max-w-lg">
                      {strategyConfirmJob.job_number ? `#${strategyConfirmJob.job_number} · ` : ""}{strategyConfirmJob.human_title}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-xl transition-all shrink-0 cursor-pointer"
                  onClick={skipOrDismissStrategyModal}
                  aria-label="Закрыть"
                >
                  <X size={18} aria-hidden="true" />
                </button>
              </header>

            {/* Content Body */}
            <div className="p-5 sm:p-6 space-y-4 overflow-y-auto max-h-[75vh]">
              {strategyRowCount >= 10 ? (
                <div className="p-3 rounded-xl bg-amber-50/90 border border-amber-200/90 text-amber-950 text-xs flex items-start gap-2.5 leading-relaxed">
                  <Sparkles size={15} className="text-amber-700 shrink-0 mt-0.5" aria-hidden="true" />
                  <div className="space-y-1">
                    <div className="font-bold text-amber-950">
                      Крупная спецификация ({strategyRowCount} товарных строк)
                    </div>
                    <p className="text-amber-900/90 text-[11px] sm:text-xs">
                      Поставщики специализируются по рынкам сбыта (электрика, вентиляция, металл, отделка). Для максимального отклика рекомендуется <strong>разбивать ТЗ на отдельные файлы по направлениям</strong>. Либо выберите «Сбалансированный поиск» (1 задача) для сводного реестра по ключевым системам.
                    </p>
                  </div>
                </div>
              ) : null}

              {/* Detected Items Card */}
              {strategyConfirmJob.multi_item_details?.items && strategyConfirmJob.multi_item_details.items.length > 0 ? (
                <div className="bg-slate-50 border border-slate-200/90 rounded-2xl p-3.5 space-y-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                      <Sparkles size={14} className="text-teal-600" aria-hidden="true" />
                      <span>Категории и товарные строки:</span>
                      <span className="px-2 py-0.5 rounded-full bg-teal-100 text-teal-800 text-[11px] font-extrabold">
                        {strategyCategoryCount} {pluralizeRu(strategyCategoryCount, ["категория", "категории", "категорий"])} / {strategyRowCount} {pluralizeRu(strategyRowCount, ["товарная строка", "товарные строки", "товарных строк"])}
                      </span>
                    </span>
                    {selectedStrategyMode === "per_item" ? (
                      <div className="flex items-center gap-1.5 text-[11px]">
                        <button
                          type="button"
                          onClick={() => {
                            const allIds = strategyConfirmJob.multi_item_details?.items?.map((it, idx) => it.id || `item-${idx}`) || [];
                            setSelectedStrategyItemIds(allIds);
                          }}
                          className="text-teal-700 hover:text-teal-800 font-bold hover:underline cursor-pointer"
                        >
                          Выбрать все
                        </button>
                        <span className="text-slate-300">·</span>
                        <button
                          type="button"
                          onClick={() => {
                            const coreIds = (strategyConfirmJob.multi_item_details?.items || [])
                              .filter(it => it.is_core !== false && !it.is_auxiliary)
                              .map((it, idx) => it.id || `item-${idx}`);
                            setSelectedStrategyItemIds(coreIds.length > 0 ? coreIds : (strategyConfirmJob.multi_item_details?.items?.map((it, idx) => it.id || `item-${idx}`) || []));
                          }}
                          className="text-teal-700 hover:text-teal-800 font-bold hover:underline cursor-pointer"
                        >
                          Только основные
                        </button>
                      </div>
                    ) : (
                      <span className="text-[11px] text-slate-400 hidden sm:inline">
                        Кластеризовано по пулам поставщиков
                      </span>
                    )}
                  </div>
                  <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
                    {strategyConfirmJob.multi_item_details.items.map((it, idx) => {
                      const itemId = it.id || `item-${idx}`;
                      const isChecked = selectedStrategyItemIds.includes(itemId);
                      const isAuxiliary = Boolean(it.is_auxiliary || it.cost_tier === "auxiliary");
                      return (
                        <div
                          key={itemId}
                          onClick={() => {
                            if (selectedStrategyMode !== "per_item") return;
                            if (isChecked) {
                              setSelectedStrategyItemIds(selectedStrategyItemIds.filter(id => id !== itemId));
                            } else {
                              setSelectedStrategyItemIds([...selectedStrategyItemIds, itemId]);
                            }
                          }}
                          className={`flex flex-col text-xs bg-white p-2.5 rounded-xl border transition-all ${
                            selectedStrategyMode === "per_item"
                              ? isChecked
                                ? "border-teal-400 bg-teal-50/20 shadow-2xs cursor-pointer"
                                : "border-slate-200 opacity-60 hover:opacity-100 hover:border-slate-300 cursor-pointer"
                              : "border-slate-200/70"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              {selectedStrategyMode === "per_item" ? (
                                <div
                                  className={`w-4 h-4 rounded border flex items-center justify-center transition-all shrink-0 ${
                                    isChecked
                                      ? "bg-emerald-600 border-emerald-600 text-white shadow-2xs"
                                      : "bg-white border-slate-300 hover:border-emerald-500"
                                  }`}
                                >
                                  {isChecked && <Check size={11} strokeWidth={3.5} className="text-white" />}
                                </div>
                              ) : null}
                              <span className="font-bold text-slate-800 truncate">
                                {idx + 1}. {it.name}
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              {isAuxiliary ? (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-amber-50 text-amber-800 border border-amber-200/70">
                                  Комплектующие
                                </span>
                              ) : (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-teal-50 text-teal-700 border border-teal-200/70">
                                  Основная
                                </span>
                              )}
                              {it.quantity ? (
                                <span className="text-slate-500 font-medium text-[11px]">
                                  {it.quantity} {it.unit || "шт."}
                                </span>
                              ) : null}
                            </div>
                          </div>
                          {it.included_sub_items && it.included_sub_items.length > 0 ? (
                            <div className="mt-1 text-[11px] text-slate-500 pl-2 sm:pl-6 border-l-2 border-teal-200/70">
                              <span className="font-semibold text-slate-600">Включает позиции ТЗ ({it.included_sub_items.length}): </span>
                              <span>{it.included_sub_items.join(" · ")}</span>
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {/* Mode Selection Cards */}
              <div className="space-y-2">
                <label className="block text-xs font-bold text-slate-700">
                  Выберите стратегию поиска:
                </label>
                <div className="grid grid-cols-1 gap-2.5">
                  <button
                    type="button"
                    onClick={() => setSelectedStrategyMode("balanced")}
                    className={`p-3.5 rounded-2xl border text-left transition-all cursor-pointer flex items-start gap-3 ${
                      selectedStrategyMode === "balanced"
                        ? "bg-teal-50/70 border-teal-500 ring-2 ring-teal-500/20 text-slate-900 shadow-2xs font-bold"
                        : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 text-slate-700"
                    }`}
                  >
                    <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5 ${
                      selectedStrategyMode === "balanced" ? "border-teal-600 bg-teal-600 text-white" : "border-slate-300 bg-white"
                    }`}>
                      {selectedStrategyMode === "balanced" ? <span className="w-1.5 h-1.5 rounded-full bg-white" /> : null}
                    </div>
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center justify-between gap-2">
                        <strong className="text-xs sm:text-sm font-extrabold text-slate-900">
                          Сбалансированный поиск
                        </strong>
                        <span className="text-[11px] font-bold text-teal-700 bg-teal-100/70 px-2 py-0.5 rounded-full shrink-0">
                          1 списание (без доплат)
                        </span>
                      </div>
                      <p className="text-[11px] sm:text-xs text-slate-600 font-normal leading-relaxed">
                        Стандартный консолидированный отчёт по вашему тарифу. Целевая квота поставщиков распределяется между всеми позициями ТЗ. В итоговом Excel формируется единый лист «Сводный реестр» со сворачиваемой структурой строк (+ / -) по каждой позиции. Формируется единый официальный Запрос КП (.docx) со всеми позициями.
                      </p>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedStrategyMode("per_item")}
                    className={`p-3.5 rounded-2xl border text-left transition-all cursor-pointer flex items-start gap-3 ${
                      selectedStrategyMode === "per_item"
                        ? "bg-teal-50/70 border-teal-500 ring-2 ring-teal-500/20 text-slate-900 shadow-2xs font-bold"
                        : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 text-slate-700"
                    }`}
                  >
                    <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5 ${
                      selectedStrategyMode === "per_item" ? "border-teal-600 bg-teal-600 text-white" : "border-slate-300 bg-white"
                    }`}>
                      {selectedStrategyMode === "per_item" ? <span className="w-1.5 h-1.5 rounded-full bg-white" /> : null}
                    </div>
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center justify-between gap-2">
                        <strong className="text-xs sm:text-sm font-extrabold text-slate-900">
                          Попозиционный глубокий поиск
                        </strong>
                        <span className="text-[11px] font-bold text-amber-800 bg-amber-100/70 px-2 py-0.5 rounded-full shrink-0">
                          {selectedStrategyItemIds.length === 0
                            ? "Ничего не выбрано"
                            : selectedStrategyItemIds.length === 1
                            ? "1 категория (1 списание)"
                            : `${selectedStrategyItemIds.length} ${pluralizeRu(selectedStrategyItemIds.length, ["категория", "категории", "категорий"])} (${selectedStrategyItemIds.length} ${pluralizeRu(selectedStrategyItemIds.length, ["списание", "списания", "списаний"])})`}
                        </span>
                      </div>
                      <p className="text-[11px] sm:text-xs text-slate-600 font-normal leading-relaxed">
                        Независимый глубокий поиск поставщиков отдельно по выбранным позициям спецификации (по каждой выбранной категории отдельный детальный сбор пула поставщиков). В итоговом Excel формируется единый лист «Сводный реестр» со сворачиваемой структурой строк (+ / -) по позициям и единый сводный Запрос КП (.docx).
                      </p>
                    </div>
                  </button>
                </div>
              </div>
            </div>

            {/* Error inside modal */}
            {strategyError ? (
              <div className="mx-6 mb-3 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                <AlertTriangle size={15} className="shrink-0" />
                <span>{strategyError}</span>
              </div>
            ) : null}

            {/* Modal Actions Footer */}
            <footer className="px-6 py-3.5 bg-slate-50 border-t border-slate-200/80 flex items-center justify-between gap-3 shrink-0">
              <button
                type="button"
                className="px-3.5 py-2 rounded-xl text-xs font-bold text-rose-600 hover:text-rose-800 hover:bg-rose-50 transition-all cursor-pointer"
                onClick={() => {
                  const jobToCancel = strategyConfirmJob;
                  skipOrDismissStrategyModal();
                  if (jobToCancel) void cancelJob(jobToCancel);
                }}
                disabled={Boolean(strategySubmittingJobId)}
              >
                Отменить задачу
              </button>
              <div className="flex items-center gap-2.5 shrink-0 ml-auto">
                <button
                  type="button"
                  className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 transition-all cursor-pointer"
                  onClick={skipOrDismissStrategyModal}
                  disabled={Boolean(strategySubmittingJobId)}
                >
                  Позже
                </button>
                <button
                  type="button"
                  className="tl-btn-primary px-5 py-2 rounded-xl text-xs shadow-sm transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
                  onClick={() => void chooseStrategy(strategyConfirmJob, selectedStrategyMode, selectedStrategyItemIds)}
                  disabled={
                    strategySubmittingJobId === strategyConfirmJob.id ||
                    (selectedStrategyMode === "per_item" && selectedStrategyItemIds.length === 0)
                  }
                >
                  {strategySubmittingJobId === strategyConfirmJob.id ? (
                    <Loader2 size={15} className="animate-spin" aria-hidden="true" />
                  ) : (
                    <CheckCircle2 size={15} aria-hidden="true" />
                  )}
                  <span>Применить</span>
                </button>
              </div>
            </footer>
          </section>
        </div>
      );
    })() : null}

      {exactSelectionJob && positionSelectionForJob(exactSelectionJob) ? (() => {
        const selection = positionSelectionForJob(exactSelectionJob)!;
        const isPriceMonitoring = exactSelectionJob.mode === "price_monitoring";
        const units = new Set(selection.items.map((item) => item.unit?.trim()).filter(Boolean));
        const itemById = new Map(selection.items.map((item) => [item.id, item]));
        const groupedIds = new Set<string>();
        const selectionGroups = (selection.groups || []).map((group, index) => {
          const items = (group.item_ids || [])
            .filter((itemId) => !groupedIds.has(itemId))
            .map((itemId) => itemById.get(itemId))
            .filter((item): item is PositionSelection["items"][number] => Boolean(item));
          items.forEach((item) => groupedIds.add(item.id));
          return { id: group.id || `group-${index}`, name: group.name || group.label || group.title || `Категория ${index + 1}`, items };
        }).filter((group) => group.items.length > 0);
        const remainingByCategory = new Map<string, PositionSelection["items"]>();
        selection.items.filter((item) => !groupedIds.has(item.id)).forEach((item) => {
          const category = item.category || "Без категории";
          remainingByCategory.set(category, [...(remainingByCategory.get(category) || []), item]);
        });
        remainingByCategory.forEach((items, name) => selectionGroups.push({ id: `category-${name}`, name, items }));
        const groupCount = selectionGroups.length;
        const isExactProduct = exactSelectionJob.mode === "exact_product";
        const isUncapped = isExactProduct || isPriceMonitoring || selection.pricing_mode === "per_position" || selection.pricing_mode === "per_found_position";
        const maxPositions = isUncapped ? selection.items.length : (selection.max_positions || selection.items.length);
        const canSelectAll = selection.items.length <= maxPositions;
        const submitting = exactSelectionSubmittingJobId === exactSelectionJob.id;
        const hasShortPrompt = Boolean(selection.has_short_prompt || selection.items.some((i) => i.is_short_prompt));

        const searchNorm = selectionSearchQuery.trim().toLowerCase();
        const matchesSearch = (item: PositionSelection["items"][number]) => {
          if (!searchNorm) return true;
          if (item.name?.toLowerCase().includes(searchNorm)) return true;
          if (item.source_excerpt?.toLowerCase().includes(searchNorm)) return true;
          const reqText = selectionRequirementsText(item.requirements).toLowerCase();
          return reqText.includes(searchNorm);
        };

        const filteredGroups = selectionGroups
          .map((g) => ({ ...g, items: g.items.filter(matchesSearch) }))
          .filter((g) => g.items.length > 0);

        const totalFilteredItems = filteredGroups.reduce((acc, g) => acc + g.items.length, 0);

        let runningCount = 0;
        const visibleGroups = filteredGroups
          .map((g) => {
            if (runningCount >= selectionVisibleLimit) return null;
            const sliceEnd = Math.min(g.items.length, selectionVisibleLimit - runningCount);
            runningCount += sliceEnd;
            return { ...g, items: g.items.slice(0, sliceEnd) };
          })
          .filter((g): g is NonNullable<typeof g> => g !== null && g.items.length > 0);
        return (
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6 z-50 overflow-y-auto"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) dismissExactSelectionModal();
            }}
          >
            <section
              className="bg-white rounded-2xl max-w-2xl w-full shadow-2xl border border-slate-200 overflow-hidden flex flex-col font-sans text-left my-auto"
              role="dialog"
              aria-modal="true"
              aria-labelledby="exact-selection-title"
              aria-describedby="exact-selection-description"
            >
              <header className="px-6 py-4 border-b border-slate-200/90 flex items-center justify-between bg-gradient-to-r from-slate-50 to-teal-50/40 shrink-0">
                <div className="flex items-center gap-3 min-w-0 pr-2">
                  <div className="w-10 h-10 rounded-2xl bg-teal-600 text-white flex items-center justify-center shrink-0 shadow-sm">
                    <CheckCircle2 size={20} aria-hidden="true" />
                  </div>
                  <div className="min-w-0">
                    <h2 id="exact-selection-title" className="text-sm sm:text-base font-extrabold text-slate-900 leading-tight">Выберите позиции</h2>
                    <p id="exact-selection-description" className="text-[11px] text-slate-500 font-medium truncate mt-0.5 max-w-md sm:max-w-lg">
                      {exactSelectionJob.job_number ? `#${exactSelectionJob.job_number} · ` : ""}{exactSelectionJob.human_title} · {isPriceMonitoring ? "мониторинг цен" : "подбор товара и аналогов"}
                    </p>
                  </div>
                </div>
                <button type="button" className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-xl transition-all shrink-0 cursor-pointer" onClick={dismissExactSelectionModal} aria-label="Закрыть выбор позиций" disabled={submitting}>
                  <X size={18} aria-hidden="true" />
                </button>
              </header>

              <div className="p-5 sm:p-6 space-y-4 overflow-y-auto max-h-[70vh]">
                <div className="rounded-2xl border border-teal-200 bg-teal-50/70 p-3.5 text-xs text-slate-700">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-bold text-slate-900">
                      {isPriceMonitoring
                        ? "Выберите позиции для мониторинга цен."
                        : "Выберите позиции для подбора модели и аналогов."}
                    </p>
                    <span className="px-2 py-0.5 rounded-full bg-white border border-teal-200 text-teal-800 font-extrabold whitespace-nowrap">
                      Выбрано: {selectedExactItemIds.length} из {selection.items.length}
                    </span>
                  </div>
                  <p className="mt-1.5 leading-relaxed">
                    {isPriceMonitoring
                      ? selection.price_kopeks
                        ? `Стоимость рассчитывается по результату: ${formatRubles(selection.price_kopeks)} за позицию с найденной ценой. Максимальная сумма при выборе ${selection.items.length} позиций: ${formatRubles(selection.items.length * selection.price_kopeks)}. Позиции без найденной цены не учитываются.`
                        : "Стоимость рассчитывается только по позициям с найденной ценой."
                      : selection.price_kopeks
                        ? `Стоимость подбора: ${formatRubles(selection.price_kopeks)} за позицию. Выбрано ${selectedExactItemIds.length} ${pluralizeRu(selectedExactItemIds.length, ["позиция", "позиции", "позиций"])} на сумму ${formatRubles(selectedExactItemIds.length * selection.price_kopeks)}.`
                        : "Стоимость рассчитывается по выбранным позициям."}
                    {" "}Перед запуском проверьте требования каждой позиции.
                  </p>
                </div>

                {hasShortPrompt ? (
                  <div className="rounded-2xl border border-amber-300 bg-amber-50/90 p-3.5 text-xs text-amber-950 shadow-xs space-y-1.5">
                    <div className="flex items-start gap-2.5">
                      <AlertTriangle className="text-amber-600 shrink-0 mt-0.5" size={16} aria-hidden="true" />
                      <div className="space-y-1 flex-1">
                        <h4 className="font-extrabold text-amber-950 text-xs">
                          Обнаружен краткий запрос без подробных характеристик
                        </h4>
                        <p className="text-amber-900 leading-relaxed text-[11px]">
                          В исходном задании указано только краткое наименование позиции без подробных технических характеристик (размеров, материалов, ГОСТ, маркировки).
                        </p>
                        <p className="text-amber-900 leading-relaxed font-semibold text-[11px]">
                          Подтвердите поиск по этому наименованию или отмените задачу (списания не произойдёт), если файл был прикреплён ошибочно.
                        </p>
                      </div>
                    </div>
                  </div>
                ) : null}

                {/* Поиск по позициям */}
                {selection.items.length > 8 ? (
                  <div className="relative">
                    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" aria-hidden="true" />
                    <input
                      type="text"
                      value={selectionSearchQuery}
                      onChange={(e) => setSelectionSearchQuery(e.target.value)}
                      placeholder="Быстрый поиск по названию, характеристикам или фрагменту ТЗ..."
                      className="w-full pl-8.5 pr-8 py-2 bg-slate-50 hover:bg-white focus:bg-white border border-slate-200 focus:border-teal-500 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 transition-all"
                    />
                    {selectionSearchQuery ? (
                      <button
                        type="button"
                        onClick={() => setSelectionSearchQuery("")}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs p-1"
                        aria-label="Очистить поиск"
                      >
                        ✕
                      </button>
                    ) : null}
                  </div>
                ) : null}

                <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                  <span className="font-semibold text-slate-600">
                    В ТЗ: {selection.items.length} товарных строк
                    {selectionSearchQuery ? ` · Найдено: ${totalFilteredItems}` : ""}
                    · Единицы: {units.size ? Array.from(units).join(", ") : "не указаны"}
                    {groupCount ? ` · Категорий: ${groupCount}` : ""}
                  </span>
                  <div className="flex items-center gap-2 flex-wrap">
                    {!canSelectAll ? (
                      <>
                        <button
                          type="button"
                          className="font-bold text-teal-700 hover:text-teal-900 underline cursor-pointer disabled:text-slate-400 disabled:no-underline"
                          onClick={() => {
                            const next = selection.items.slice(0, maxPositions).map((item) => item.id);
                            setSelectedExactItemIds(next);
                            exactSelectionStateRef.current.set(exactSelectionKey(exactSelectionJob), next);
                            setExactSelectionError("");
                          }}
                          disabled={submitting}
                          title={`Выбрать первые ${maxPositions} позиций по порядку`}
                        >
                          Выбрать первые {maxPositions}
                        </button>
                        <span className="text-slate-300">·</span>
                      </>
                    ) : null}
                    <button
                      type="button"
                      className="font-bold text-teal-700 hover:text-teal-900 disabled:text-slate-400 disabled:no-underline underline cursor-pointer disabled:cursor-not-allowed"
                      onClick={() => {
                        const next = selection.items.map((item) => item.id);
                        setSelectedExactItemIds(next);
                        exactSelectionStateRef.current.set(exactSelectionKey(exactSelectionJob), next);
                        setExactSelectionError("");
                      }}
                      disabled={submitting}
                      title="Выбрать все позиции"
                    >
                      Выбрать все
                    </button>
                    <span className="text-slate-300">·</span>
                    <button
                      type="button"
                      className="font-bold text-teal-700 hover:text-teal-900 disabled:text-slate-400 underline cursor-pointer disabled:cursor-not-allowed"
                      onClick={() => {
                        setSelectedExactItemIds([]);
                        exactSelectionStateRef.current.set(exactSelectionKey(exactSelectionJob), []);
                        setExactSelectionError("");
                      }}
                      disabled={selectedExactItemIds.length === 0 || submitting}
                    >
                      Очистить
                    </button>
                  </div>
                </div>
                {!canSelectAll ? <p className="-mt-2 text-[11px] text-amber-800">В спецификации больше {maxPositions} позиций, поэтому выберите нужные вручную или нажмите «Выбрать первые {maxPositions}».</p> : null}

                <div className="space-y-3" role="group" aria-label={isPriceMonitoring ? "Позиции для мониторинга цен" : "Позиции для подбора"}>
                  {visibleGroups.map((group) => {
                    const groupItemIds = group.items.map((item) => item.id);
                    const groupSelected = groupItemIds.length > 0 && groupItemIds.every((itemId) => selectedExactItemIds.includes(itemId));
                    const wouldExceedLimit = !groupSelected && new Set([...selectedExactItemIds, ...groupItemIds]).size > maxPositions;
                    return (
                      <section key={group.id} className="rounded-2xl border border-slate-200 bg-slate-50/60 overflow-hidden">
                        <header className="px-3.5 py-2.5 border-b border-slate-200/80 flex flex-wrap items-center justify-between gap-2 bg-white">
                          <div className="min-w-0">
                            <h3 className="text-xs font-extrabold text-slate-900 truncate">{group.name}</h3>
                            <p className="text-[10px] font-medium text-slate-500 mt-0.5">{group.items.length} {pluralizeRu(group.items.length, ["товарная строка", "товарные строки", "товарных строк"])}</p>
                          </div>
                          <button
                            type="button"
                            className="shrink-0 rounded-lg border border-teal-200 bg-teal-50 px-2.5 py-1.5 text-[11px] font-bold text-teal-800 hover:bg-teal-100 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                            onClick={() => toggleExactSelectionGroup(exactSelectionJob, groupItemIds, group.name)}
                            disabled={submitting}
                            title={wouldExceedLimit ? `Выбор категории превысит лимит ${maxPositions}; выберите строки вручную.` : undefined}
                          >
                            {groupSelected ? "Снять категорию" : "Выбрать категорию"}
                          </button>
                        </header>
                        {wouldExceedLimit ? <p className="px-3.5 pt-2 text-[10px] leading-relaxed text-amber-800">Выбор всей категории превысит лимит {maxPositions}; выберите нужные строки вручную.</p> : null}
                        <div className="space-y-2 p-2.5">
                          {group.items.map((item) => {
                            const checked = selectedExactItemIds.includes(item.id);
                            const requirements = selectionRequirementsText(item.requirements);
                            return (
                              <label key={item.id} className={`block rounded-xl border p-3 transition-colors cursor-pointer ${checked ? "border-teal-500 bg-teal-50/50 ring-1 ring-teal-500/20" : "border-slate-200 bg-white hover:border-teal-300"}`}>
                                <span className="flex items-start gap-3">
                                  <input type="checkbox" checked={checked} onChange={() => toggleExactSelectionItem(exactSelectionJob, item.id)} disabled={submitting} className="mt-0.5 h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500" />
                                  <span className="min-w-0 flex-1">
                                    <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                                      <strong className="text-xs text-slate-900">{item.position_no}. {item.name}</strong>
                                      {item.quantity ? <span className="text-[11px] text-slate-500">{item.quantity} {item.unit || ""}</span> : null}
                                    </span>
                                    {requirements ? <span className="mt-1 block text-[11px] leading-relaxed text-slate-600">{requirements}</span> : null}
                                    {item.source_excerpt ? <span className="mt-1.5 block rounded-md bg-slate-50 px-2 py-1 text-[10px] leading-relaxed text-slate-500">Фрагмент ТЗ: {item.source_excerpt}</span> : null}
                                  </span>
                                </span>
                              </label>
                            );
                          })}
                        </div>
                      </section>
                    );
                  })}
                </div>

                {/* Пагинация и подгрузка при большом количестве строк */}
                {totalFilteredItems > runningCount ? (
                  <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-slate-100 rounded-2xl text-xs text-slate-600">
                    <span>Показано {runningCount} из {totalFilteredItems} позиций</span>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        className="px-3 py-1.5 bg-white border border-slate-300 hover:border-teal-500 rounded-lg font-bold text-teal-800 hover:bg-slate-50 cursor-pointer text-xs transition-colors"
                        onClick={() => setSelectionVisibleLimit((v) => v + 50)}
                      >
                        Показать ещё 50
                      </button>
                      <button
                        type="button"
                        className="px-3 py-1.5 bg-white border border-slate-300 hover:border-teal-500 rounded-lg font-bold text-teal-800 hover:bg-slate-50 cursor-pointer text-xs transition-colors"
                        onClick={() => setSelectionVisibleLimit(totalFilteredItems)}
                      >
                        Показать все ({totalFilteredItems})
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>

              {exactSelectionError ? <div role="alert" className="mx-6 mb-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 flex items-center gap-2"><AlertTriangle size={15} aria-hidden="true" /><span>{exactSelectionError}</span></div> : null}

              <footer className="px-6 py-3.5 bg-slate-50 border-t border-slate-200/80 flex items-center justify-between gap-3 shrink-0">
                <div className="flex items-center gap-2">
                  <button type="button" className="px-3.5 py-2 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 transition-all cursor-pointer" onClick={dismissExactSelectionModal} disabled={submitting}>Позже</button>
                  {exactSelectionJob.can_cancel ? (
                    <button
                      type="button"
                      className="px-3 py-2 rounded-xl text-xs font-bold text-rose-600 hover:text-rose-700 hover:bg-rose-50 border border-rose-200 transition-all cursor-pointer"
                      onClick={() => {
                        dismissExactSelectionModal();
                        void cancelJob(exactSelectionJob);
                      }}
                      disabled={submitting}
                      title="Отменить задачу без списания средств"
                    >
                      Отменить задачу (без списания)
                    </button>
                  ) : null}
                </div>
                <button type="button" className="px-5 py-2 rounded-xl text-xs font-extrabold text-white bg-teal-600 hover:bg-teal-700 active:bg-teal-800 shadow-sm transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50" onClick={() => void confirmExactSelection(exactSelectionJob)} disabled={selectedExactItemIds.length === 0 || submitting}>
                  {submitting ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <ArrowRight size={15} aria-hidden="true" />}
                  <span>{hasShortPrompt ? "Подтвердить поиск по наименованию" : "Подтвердить выбор"}</span>
                </button>
              </footer>
            </section>
          </div>
        );
      })() : null}

      {retryConfirmJob ? (
        <div
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6 z-50 overflow-y-auto"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setRetryConfirmJob(null);
            }
          }}
        >
          <section
            className="bg-white rounded-2xl max-w-xl w-full shadow-2xl border border-slate-200 overflow-hidden flex flex-col font-sans text-left my-auto"
            role="dialog"
            aria-modal="true"
            aria-labelledby="retry-job-confirm-title"
          >
            {/* Header */}
            <header className="px-6 py-4 border-b border-slate-200/90 flex items-center justify-between bg-gradient-to-r from-slate-50 to-amber-50/40 shrink-0">
              <div className="flex items-center gap-3 min-w-0 pr-2">
                <div className="w-9 h-9 rounded-xl bg-amber-500 text-white flex items-center justify-center shrink-0 shadow-sm">
                  <RotateCcw size={18} aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <h2 id="retry-job-confirm-title" className="text-sm sm:text-base font-extrabold text-slate-900 leading-tight">
                    {retryConfirmJob.mode === "exact_product"
                      ? "Повторить подбор товара и аналогов?"
                      : retryConfirmJob.mode === "procurement_report"
                      ? "Повторить анализ документации?"
                      : retryConfirmJob.mode === "price_monitoring"
                      ? "Повторить мониторинг цен?"
                      : "Повторить поиск поставщиков?"}
                  </h2>
                  <p className="text-[11px] text-slate-500 font-medium truncate mt-0.5 max-w-md">
                    {retryConfirmJob.job_number ? `#${retryConfirmJob.job_number} · ` : ""}{retryConfirmJob.human_title}
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-xl transition-all shrink-0 cursor-pointer"
                onClick={() => setRetryConfirmJob(null)}
                aria-label="Закрыть"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </header>

            {/* Content Body */}
            <div className="p-5 sm:p-6 space-y-4 overflow-y-auto max-h-[75vh]">
              {retryConfirmJob.mode === "supplier_search" || retryConfirmJob.mode === "analysis_and_suppliers" ? (
                <>
                  {/* Multi-Item Mode Choice */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <label className="font-bold text-slate-700 text-xs flex items-center gap-1.5">
                        <span>Режим для многопозиционных спецификаций:</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500 font-normal">
                          много товаров в ТЗ
                        </span>
                      </label>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => setRetryMultiItemMode("balanced")}
                        className={`p-3 rounded-2xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                          retryMultiItemMode === "balanced"
                            ? "bg-teal-50/70 border-teal-500 ring-2 ring-teal-500/20 text-slate-900 shadow-2xs font-bold"
                            : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 text-slate-700"
                        }`}
                      >
                        <div className="flex items-center justify-between w-full mb-1">
                          <span className="text-xs font-extrabold text-slate-900">Сбалансированный поиск</span>
                          <span className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 ${retryMultiItemMode === "balanced" ? "border-teal-600 bg-teal-600" : "border-slate-300 bg-white"}`}>
                            {retryMultiItemMode === "balanced" ? <span className="w-1 h-1 rounded-full bg-white" /> : null}
                          </span>
                        </div>
                        <span className="text-[11px] text-slate-500 font-normal leading-snug">
                          Единая квота поставщиков распределяется между всеми позициями ТЗ. В Excel формируется единый лист со сворачиваемой структурой строк (+ / -) по каждой позиции.
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setRetryMultiItemMode("per_item")}
                        className={`p-3 rounded-2xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                          retryMultiItemMode === "per_item"
                            ? "bg-teal-50/70 border-teal-500 ring-2 ring-teal-500/20 text-slate-900 shadow-2xs font-bold"
                            : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 text-slate-700"
                        }`}
                      >
                        <div className="flex items-center justify-between w-full mb-1">
                          <span className="text-xs font-extrabold text-slate-900">Попозиционный глубокий поиск</span>
                          <span className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 ${retryMultiItemMode === "per_item" ? "border-teal-600 bg-teal-600" : "border-slate-300 bg-white"}`}>
                            {retryMultiItemMode === "per_item" ? <span className="w-1 h-1 rounded-full bg-white" /> : null}
                          </span>
                        </div>
                        <span className="text-[11px] text-slate-500 font-normal leading-snug">
                          Глубокий пул поставщиков по каждой позиции спецификации с отдельным детальным анализом сайтов и контактов.
                        </span>
                      </button>
                    </div>
                  </div>

                  {/* Policy Selection Cards */}
                  <div className="space-y-1.5">
                    <label className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                      Требования к реестру Минпромторга РФ:
                    </label>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      {[
                        {
                          id: "normal",
                          label: "Обычный поиск",
                          desc: "Кандидаты по заданным условиям",
                        },
                        {
                          id: "minprom_registry_priority",
                          label: "Реестр в приоритете",
                          desc: "Производители из ГИСП в приоритете",
                        },
                        {
                          id: "minprom_registry_only",
                          label: "Только реестр",
                          desc: "Строго запись (44-ФЗ)",
                        },
                      ].map((opt) => {
                        const isSelected = retryPolicy === opt.id;
                        return (
                          <button
                            key={opt.id}
                            type="button"
                            onClick={() => setRetryPolicy(opt.id as SupplierSearchPolicy)}
                            className={`p-2.5 sm:p-3 rounded-2xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                              isSelected
                                ? "bg-teal-50/70 border-teal-500 ring-2 ring-teal-500/20 text-slate-900 shadow-2xs font-bold"
                                : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 text-slate-700"
                            }`}
                          >
                            <div className="flex items-center justify-between w-full mb-0.5">
                              <span className="text-xs font-extrabold">{opt.label}</span>
                              <span className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 ${isSelected ? "border-teal-600 bg-teal-600" : "border-slate-300 bg-white"}`}>
                                {isSelected ? <span className="w-1 h-1 rounded-full bg-white" /> : null}
                              </span>
                            </div>
                            <span className="text-[11px] text-slate-500 font-normal leading-snug">{opt.desc}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </>
              ) : retryConfirmJob.mode === "exact_product" ? (
                <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 text-xs text-slate-700 space-y-2">
                  <div className="flex items-center gap-2 font-bold text-slate-900">
                    <Sparkles size={16} className="text-teal-600 shrink-0" aria-hidden="true" />
                    <span>Повторный подбор точного товара и аналогов</span>
                  </div>
                  <p className="text-slate-600 leading-relaxed font-normal">
                    Система заново проверит техническое задание, нормативные требования (ГОСТ/ТУ) и сформирует готовый отчёт в формате Word (.docx).
                  </p>
                </div>
              ) : retryConfirmJob.mode === "price_monitoring" ? (
                <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 text-xs text-slate-700 space-y-2">
                  <div className="flex items-center gap-2 font-bold text-slate-900">
                    <Sparkles size={16} className="text-teal-600 shrink-0" aria-hidden="true" />
                    <span>Повторный мониторинг цен поставщиков</span>
                  </div>
                  <p className="text-slate-600 leading-relaxed font-normal">
                    Система заново выделит позиции спецификации и откроет окно выбора строк для мониторинга цен.
                  </p>
                </div>
              ) : (
                <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 text-xs text-slate-700 space-y-2">
                  <div className="flex items-center gap-2 font-bold text-slate-900">
                    <Sparkles size={16} className="text-teal-600 shrink-0" aria-hidden="true" />
                    <span>Повторный анализ документации</span>
                  </div>
                  <p className="text-slate-600 leading-relaxed font-normal">
                    Система заново проанализирует технические требования, условия контракта, риски и нормативные ограничения закупки.
                  </p>
                </div>
              )}
            </div>

            {/* Modal Actions Footer */}
            <footer className="px-6 py-3.5 bg-slate-50 border-t border-slate-200/80 flex items-center justify-between gap-3 shrink-0">
              <span className="text-xs text-slate-500 hidden sm:inline">
                Параметры будут применены к перезапуску
              </span>
              <div className="flex items-center gap-2.5 shrink-0 ml-auto">
                <button
                  type="button"
                  className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 transition-all cursor-pointer"
                  onClick={() => setRetryConfirmJob(null)}
                  disabled={busy}
                >
                  Отмена
                </button>
                <button
                  type="button"
                  className="px-5 py-2 rounded-xl text-xs font-extrabold text-white bg-amber-600 hover:bg-amber-700 active:bg-amber-800 shadow-sm transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
                  onClick={() => void retryJob(retryConfirmJob, retryPolicy, retryMultiItemMode)}
                  disabled={busy}
                >
                  {busy ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <RotateCcw size={15} aria-hidden="true" />}
                  <span>Перезапустить задачу</span>
                </button>
              </div>
            </footer>
          </section>
        </div>
      ) : null}

      {/* Floating Bottom-Center Task Notification Toast (Minimalist Light Pill) */}
      {activeToast ? (
        <div
          role="status"
          aria-live="polite"
          className="tenderlex-toast-slide-up fixed bottom-5 left-1/2 z-[9999] flex items-center gap-2.5 bg-white/95 text-slate-900 backdrop-blur-md px-4 py-1.5 rounded-full shadow-xl border border-teal-300/80 ring-1 ring-slate-900/5 text-xs font-medium max-w-[92vw] pointer-events-auto"
        >
          <span className="relative flex h-2 w-2 shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-500 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-600" />
          </span>
          <span className="text-[11px] font-extrabold text-teal-700 shrink-0">Готово:</span>
          <span className="text-[11px] font-semibold text-slate-800 truncate max-w-[160px] sm:max-w-xs">
            {activeToast.title}
          </span>
          <button
            type="button"
            className="px-2.5 py-0.5 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white rounded-full text-[10px] font-bold transition-all shrink-0 cursor-pointer shadow-xs active:scale-95"
            onClick={() => {
              scrollToJob(activeToast.jobId);
              setActiveToast(null);
            }}
          >
            Смотреть
          </button>
          <button
            type="button"
            className="p-0.5 text-slate-400 hover:text-slate-700 rounded-full transition-colors cursor-pointer ml-0.5"
            onClick={() => setActiveToast(null)}
            aria-label="Закрыть оповещение"
          >
            <X size={12} aria-hidden="true" />
          </button>
        </div>
      ) : null}

      {/* YooKassa Payment Status Checking Toast */}
      {checkingPaymentStatus ? (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[9999] flex items-center gap-2.5 bg-slate-900/95 text-white backdrop-blur-md px-5 py-2.5 rounded-full shadow-2xl text-xs font-semibold max-w-[92vw] pointer-events-auto border border-white/10"
        >
          <Loader2 size={16} className="animate-spin text-emerald-400" />
          <span>Проверяем зачисление оплаты через ЮKassa...</span>
        </div>
      ) : null}

      {/* YooKassa Payment Success Banner Toast */}
      {paymentSuccessNotice ? (
        <div
          role="status"
          aria-live="polite"
          className="fixed top-5 left-1/2 -translate-x-1/2 z-[9999] flex items-center gap-3 bg-gradient-to-r from-emerald-600 to-teal-700 text-white px-5 py-3 rounded-2xl shadow-2xl text-xs font-semibold max-w-[92vw] pointer-events-auto border border-white/20 animate-fade-in"
        >
          <CheckCircle2 size={20} className="text-white shrink-0" />
          <div>
            <div className="font-extrabold text-sm">Баланс успешно пополнен!</div>
            <div className="text-[11px] text-emerald-100">
              Зачислено {paymentSuccessNotice.totalCreditRub.toLocaleString("ru-RU")} ₽
              {paymentSuccessNotice.bonusRub > 0 ? ` (+${paymentSuccessNotice.bonusRub.toLocaleString("ru-RU")} ₽ бонус)` : ""}
            </div>
          </div>
          <button
            type="button"
            className="p-1 text-white/80 hover:text-white rounded-full transition-colors cursor-pointer ml-2"
            onClick={() => setPaymentSuccessNotice(null)}
            aria-label="Закрыть"
          >
            <X size={16} />
          </button>
        </div>
      ) : null}
      {/* Function Guide & Workflow Compilation Modal */}
      {showHelpModal ? (() => {
        const showBatchHelpTab = Boolean(hasSeparateCustomBatchTab || session?.user?.allowed_custom_batch_report);
        const showPriceHelpTab = Boolean(session?.user?.allowed_price_monitoring);
        const tabBtnClass = (isActive: boolean) =>
          `py-1.5 px-2.5 rounded-lg font-bold transition-all text-center inline-flex items-center justify-center gap-1 cursor-pointer whitespace-nowrap ${
            isActive
              ? "bg-white text-[#103a31] border border-[#cde0be] shadow-2xs ring-1 ring-[#174b3f]/15"
              : "text-slate-600 hover:text-slate-900 hover:bg-white/70 border border-transparent"
          }`;

        return (
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4 z-50 overflow-y-auto"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) setShowHelpModal(false);
            }}
          >
            <section
              className="bg-white rounded-2xl max-w-5xl w-full max-h-[90vh] shadow-2xl border border-slate-200 overflow-hidden flex flex-col font-sans"
              role="dialog"
              aria-modal="true"
              aria-labelledby="help-modal-title"
            >
              {/* Light Calm Modal Header */}
              <header className="bg-white px-5 sm:px-6 py-4 border-b border-slate-100 flex items-start justify-between gap-3 shrink-0">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-[#f4f8ef] border border-[#cde0be] text-[#174b3f] shrink-0">
                    <BookOpen size={18} aria-hidden="true" />
                  </div>
                  <div>
                    <h2 id="help-modal-title" className="text-base sm:text-lg font-extrabold text-slate-900 leading-tight">
                      Справочник функций и алгоритм работы TenderLex
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Пошаговый порядок подготовки к закупкам и назначение инструментов
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors shrink-0 cursor-pointer"
                  onClick={() => setShowHelpModal(false)}
                  aria-label="Закрыть"
                >
                  <X size={18} aria-hidden="true" />
                </button>
              </header>

              {/* Non-Clipping Flex-Wrap Tab Navigation */}
              <div className="bg-[#f8faf6] px-4 sm:px-5 py-2 border-b border-[#e5e9e2] flex flex-wrap items-center gap-1 text-xs shrink-0">
                <button
                  type="button"
                  onClick={() => setHelpModalTab("workflow")}
                  className={tabBtnClass(helpModalTab === "workflow")}
                >
                  <Compass size={14} className={helpModalTab === "workflow" ? "text-[#174b3f]" : "text-slate-400"} aria-hidden="true" />
                  <span>Маршрут работы</span>
                </button>
                <button
                  type="button"
                  onClick={() => setHelpModalTab("procurement_report")}
                  className={tabBtnClass(helpModalTab === "procurement_report")}
                >
                  <FileText size={14} className={helpModalTab === "procurement_report" ? "text-[#174b3f]" : "text-slate-400"} aria-hidden="true" />
                  <span>Анализ документации</span>
                </button>
                <button
                  type="button"
                  onClick={() => setHelpModalTab("supplier_search")}
                  className={tabBtnClass(helpModalTab === "supplier_search")}
                >
                  <Search size={14} className={helpModalTab === "supplier_search" ? "text-[#174b3f]" : "text-slate-400"} aria-hidden="true" />
                  <span>Поиск поставщиков</span>
                </button>
                <button
                  type="button"
                  onClick={() => setHelpModalTab("analysis_and_suppliers")}
                  className={tabBtnClass(helpModalTab === "analysis_and_suppliers")}
                >
                  <Receipt size={14} className={helpModalTab === "analysis_and_suppliers" ? "text-[#174b3f]" : "text-slate-400"} aria-hidden="true" />
                  <span>Анализ + поиск</span>
                </button>
                <button
                  type="button"
                  onClick={() => setHelpModalTab("exact_product")}
                  className={tabBtnClass(helpModalTab === "exact_product")}
                >
                  <CheckCircle2 size={14} className={helpModalTab === "exact_product" ? "text-[#174b3f]" : "text-slate-400"} aria-hidden="true" />
                  <span>Подбор товара</span>
                </button>
                {showPriceHelpTab ? (
                  <button
                    type="button"
                    onClick={() => setHelpModalTab("price_monitoring")}
                    className={tabBtnClass(helpModalTab === "price_monitoring")}
                  >
                    <Coins size={14} className={helpModalTab === "price_monitoring" ? "text-[#174b3f]" : "text-slate-400"} aria-hidden="true" />
                    <span>Мониторинг цен</span>
                  </button>
                ) : null}
                {showBatchHelpTab ? (
                  <button
                    type="button"
                    onClick={() => setHelpModalTab("custom_batch_report")}
                    className={tabBtnClass(helpModalTab === "custom_batch_report")}
                  >
                    <FileSpreadsheet size={14} className={helpModalTab === "custom_batch_report" ? "text-[#174b3f]" : "text-slate-400"} aria-hidden="true" />
                    <span>Экспресс-оценка</span>
                  </button>
                ) : null}
              </div>

              {/* Modal Body Content */}
              <div className="p-4 sm:p-5 text-slate-800 text-xs sm:text-[13px] space-y-4 overflow-y-auto flex-1">
                {helpModalTab === "workflow" ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between pb-1.5 border-b border-slate-100">
                      <div>
                        <h3 className="font-extrabold text-slate-900 text-sm sm:text-base">
                          Рекомендуемый порядок работы с задачами
                        </h3>
                        <p className="text-xs text-slate-500 mt-0.5">
                          4 основных сценария кабинета: от проверки условий закупки до подбора товара и аналогов
                        </p>
                      </div>
                    </div>

                    {/* 4 Step Cards in Canonical Cabinet Order */}
                    <div className="grid sm:grid-cols-2 gap-3.5">
                      {/* Step 1: Анализ документации */}
                      <div className="bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl p-4 flex flex-col justify-between space-y-3 hover:border-[#9ec089] transition-all">
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="w-6 h-6 rounded-full bg-[#e7efe0] text-[#103a31] font-extrabold text-xs flex items-center justify-center shrink-0">
                              1
                            </span>
                            <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-white text-[#174b3f] border border-[#cde0be]">
                              Оценка рисков
                            </span>
                          </div>
                          <strong className="text-xs sm:text-[13px] font-bold text-slate-900 block">
                            Анализ документации
                          </strong>
                          <p className="text-xs text-slate-600 leading-relaxed">
                            Проверка проекта контракта: сроки, штрафы, обеспечение заявки и условия национального режима по действующей редакции ПП РФ № 1875.
                          </p>
                        </div>
                        <div className="pt-2.5 border-t border-[#e5e9e2] flex items-center justify-between">
                          <span className="text-[11px] text-slate-500 font-medium">Условия для проверки</span>
                          <button
                            type="button"
                            onClick={() => {
                              selectScenario("procurement_report");
                              setShowHelpModal(false);
                            }}
                            className="px-2.5 py-1 bg-white hover:bg-[#174b3f] hover:text-white text-[#174b3f] border border-[#b7c9af] rounded-lg text-xs font-bold transition-colors cursor-pointer"
                          >
                            Выбрать →
                          </button>
                        </div>
                      </div>

                      {/* Step 2: Поиск поставщиков */}
                      <div className="bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl p-4 flex flex-col justify-between space-y-3 hover:border-[#9ec089] transition-all">
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="w-6 h-6 rounded-full bg-[#e7efe0] text-[#103a31] font-extrabold text-xs flex items-center justify-center shrink-0">
                              2
                            </span>
                            <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-white text-[#174b3f] border border-[#cde0be]">
                              Запрос КП
                            </span>
                          </div>
                          <strong className="text-xs sm:text-[13px] font-bold text-slate-900 block">
                            Поиск поставщиков
                          </strong>
                          <p className="text-xs text-slate-600 leading-relaxed">
                            Поиск кандидатов и опубликованных контактов для запроса КП. Наличие товара, цену и полномочия поставщика нужно подтвердить.
                          </p>
                        </div>
                        <div className="pt-2.5 border-t border-[#e5e9e2] flex items-center justify-between">
                          <span className="text-[11px] text-slate-500 font-medium">Запрос цен</span>
                          <button
                            type="button"
                            onClick={() => {
                              selectScenario("supplier_search");
                              setShowHelpModal(false);
                            }}
                            className="px-2.5 py-1 bg-white hover:bg-[#174b3f] hover:text-white text-[#174b3f] border border-[#b7c9af] rounded-lg text-xs font-bold transition-colors cursor-pointer"
                          >
                            Выбрать →
                          </button>
                        </div>
                      </div>

                      {/* Step 3: Анализ + поиск */}
                      <div className="bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl p-4 flex flex-col justify-between space-y-3 hover:border-[#9ec089] transition-all">
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="w-6 h-6 rounded-full bg-[#e7efe0] text-[#103a31] font-extrabold text-xs flex items-center justify-center shrink-0">
                              3
                            </span>
                            <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-white text-[#174b3f] border border-[#cde0be]">
                              Комплексный запуск
                            </span>
                          </div>
                          <strong className="text-xs sm:text-[13px] font-bold text-slate-900 block">
                            Анализ + поиск
                          </strong>
                          <p className="text-xs text-slate-600 leading-relaxed">
                            Совмещает разбор закупочной документации и подбор профильных поставщиков под спецификацию в рамках одного запуска.
                          </p>
                        </div>
                        <div className="pt-2.5 border-t border-[#e5e9e2] flex items-center justify-between">
                          <span className="text-[11px] text-slate-500 font-medium">Аудит + контакты сбыта</span>
                          <button
                            type="button"
                            onClick={() => {
                              selectScenario("analysis_and_suppliers");
                              setShowHelpModal(false);
                            }}
                            className="px-2.5 py-1 bg-white hover:bg-[#174b3f] hover:text-white text-[#174b3f] border border-[#b7c9af] rounded-lg text-xs font-bold transition-colors cursor-pointer"
                          >
                            Выбрать →
                          </button>
                        </div>
                      </div>

                      {/* Step 4: Подбор товара и аналогов */}
                      <div className="bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl p-4 flex flex-col justify-between space-y-3 hover:border-[#9ec089] transition-all">
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="w-6 h-6 rounded-full bg-[#e7efe0] text-[#103a31] font-extrabold text-xs flex items-center justify-center shrink-0">
                              4
                            </span>
                            <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-white text-[#174b3f] border border-[#cde0be]">
                              Подбор аналогов
                            </span>
                          </div>
                          <strong className="text-xs sm:text-[13px] font-bold text-slate-900 block">
                            Подбор товара и аналогов
                          </strong>
                          <p className="text-xs text-slate-600 leading-relaxed">
                            Определение заложенной модели по ТЗ, характеристики для проверки заявки и варианты российских аналогов для сравнения стоимости.
                          </p>
                        </div>
                        <div className="pt-2.5 border-t border-[#e5e9e2] flex items-center justify-between">
                          <span className="text-[11px] text-slate-500 font-medium">Проверка характеристик</span>
                          <button
                            type="button"
                            onClick={() => {
                              selectScenario("exact_product");
                              setShowHelpModal(false);
                            }}
                            className="px-2.5 py-1 bg-white hover:bg-[#174b3f] hover:text-white text-[#174b3f] border border-[#b7c9af] rounded-lg text-xs font-bold transition-colors cursor-pointer"
                          >
                            Выбрать →
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Compact Special Tools Strip when enabled */}
                    {(showPriceHelpTab || showBatchHelpTab) ? (
                      <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/90 space-y-2">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                          Специнструменты для массовой работы
                        </div>
                        <div className="grid sm:grid-cols-2 gap-2.5">
                          {showPriceHelpTab ? (
                            <div className="p-3 rounded-xl bg-white border border-slate-200 flex items-center justify-between gap-2.5">
                              <div className="min-w-0">
                                <div className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                                  <Coins size={13} className="text-[#174b3f] shrink-0" aria-hidden="true" />
                                  <span>Мониторинг цен</span>
                                </div>
                                <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                                  Сбор рыночных цен по спецификации до 1 000 строк, списание только за найденные.
                                </p>
                              </div>
                              <button
                                type="button"
                                onClick={() => setHelpModalTab("price_monitoring")}
                                className="px-2.5 py-1 rounded-lg bg-[#f4f8ef] hover:bg-[#e7efe0] text-[#174b3f] border border-[#cde0be] text-[11px] font-bold shrink-0 cursor-pointer"
                              >
                                Подробнее
                              </button>
                            </div>
                          ) : null}
                          {showBatchHelpTab ? (
                            <div className="p-3 rounded-xl bg-white border border-slate-200 flex items-center justify-between gap-2.5">
                              <div className="min-w-0">
                                <div className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                                  <FileSpreadsheet size={13} className="text-[#174b3f] shrink-0" aria-hidden="true" />
                                  <span>Экспресс-оценка закупок</span>
                                </div>
                                <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                                  Быстрый отбор 1 или сразу нескольких закупок по марже, товару и поставщикам.
                                </p>
                              </div>
                              <button
                                type="button"
                                onClick={() => setHelpModalTab("custom_batch_report")}
                                className="px-2.5 py-1 rounded-lg bg-[#f4f8ef] hover:bg-[#e7efe0] text-[#174b3f] border border-[#cde0be] text-[11px] font-bold shrink-0 cursor-pointer"
                              >
                                Подробнее
                              </button>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {helpModalTab === "procurement_report" ? (
                  <div className="space-y-4">
                    <div className="grid sm:grid-cols-2 gap-4">
                      <div className="p-4 bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl space-y-3">
                        <div>
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Назначение функции:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            Автоматизированный разбор условий закупки по 44-ФЗ и 223-ФЗ: сроки, штрафы, лицензии и обеспечение. Выводы нужно сверять с документами и применимыми нормами; отчет не заменяет юридическое заключение.
                          </p>
                        </div>
                        <div className="pt-2 border-t border-[#e5e9e2]">
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Когда применять:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            Перед подачей заявки для проверки условий и оценки рисков. Отчет не гарантирует допуск, исполнение контракта или отсутствие оснований для РНП.
                          </p>
                        </div>
                      </div>

                      <div className="p-4 bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl space-y-3">
                        <div>
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Что загружать:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            19-значный номер извещения ЕИС, прямую ссылку на zakupki.gov.ru или архив с файлами проекта контракта и ТЗ.
                          </p>
                        </div>
                        <div className="pt-2 border-t border-[#e5e9e2]">
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Что на выходе:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            1) Аналитический отчет Word (DOCX) в фирменном стиле.<br />
                            2) Чек-лист ключевых требований и факторов риска.<br />
                            3) Вопросы и условия для самостоятельной проверки участия и исполнения.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100">
                      <span className="text-xs text-slate-500 font-medium">
                        Совет: сопоставьте отчет с исходными документами. Решение об участии принимает участник закупки.
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          selectScenario("procurement_report");
                          setShowHelpModal(false);
                        }}
                        className="tl-btn-primary px-4 py-2 text-xs rounded-xl cursor-pointer inline-flex items-center gap-1.5 shrink-0"
                      >
                        <span>Выбрать «Анализ документации»</span>
                        <ArrowRight size={14} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                ) : null}

                {helpModalTab === "supplier_search" ? (
                  <div className="space-y-4">
                    <div className="grid sm:grid-cols-2 gap-4">
                      <div className="p-4 bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl space-y-3">
                        <div>
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Назначение функции:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            Поиск производителей, дилеров и дистрибьюторов по заданным условиям. Опубликованные контакты и сведения о компании нужно подтвердить; статус официального дилера не гарантируется.
                          </p>
                        </div>
                        <div className="pt-2 border-t border-[#e5e9e2]">
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Фильтрация по Минпромторгу:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            • <strong>Обычный</strong> — поиск по всем поставщикам РФ.<br />
                            • <strong>Только реестр (ГИСП)</strong> — отбор компаний из реестра; применимость записи проверяется для конкретного товара и закупки.<br />
                            • <strong>Реестр в приоритете</strong> — производители из ГИСП первыми. Соответствие требованиям ПП РФ № 1875 нужно подтвердить отдельно.
                          </p>
                        </div>
                        <div className="pt-2 border-t border-[#e5e9e2]">
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Что загружать:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            Файл технического задания, спецификацию (.pdf, .docx, .xlsx, .zip) или список требуемых позиций текстом.
                          </p>
                        </div>
                      </div>

                      <div className="p-4 bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl space-y-3">
                        <div>
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Что на выходе:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            1) Ведомость поставщиков в Excel (XLSX) с прямыми контактами.<br />
                            2) Официальный файл запроса КП в Word (DOCX).<br />
                            3) Копирование текста запроса КП в 1 клик.
                          </p>
                        </div>
                        <div className="pt-2 border-t border-[#e5e9e2]">
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">География поиска:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            • <strong>Только Россия</strong> — отечественные компании с ИНН РФ (для 44-ФЗ, 223-ФЗ и нацрежима).<br />
                            • <strong>РФ и СНГ (ЕАЭС)</strong> — поставщики и заводы России, Беларуси, Казахстана, Армении, Кыргызстана.<br />
                            • <strong>Весь мир</strong> — прямые зарубежные фабрики и производители мира.
                          </p>
                        </div>
                        <div className="pt-2 border-t border-[#e5e9e2]">
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Приоритет в радиусе доставки:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            Укажите город поставки и радиус (10–5 000 км) — ближайшие поставщики попадут в начало таблицы, а компании из других регионов будут отмечены отдельно.
                          </p>
                        </div>
                      </div>

                      <div className="sm:col-span-2 p-4 bg-[#f4f8ef] border border-[#cde0be] rounded-2xl space-y-1.5">
                        <strong className="text-[#103a31] font-bold block text-xs sm:text-[13px]">
                          Многопозиционные спецификации и ТЗ:
                        </strong>
                        <p className="text-slate-700 leading-relaxed text-xs sm:text-[13px]">
                          Если ваше ТЗ содержит несколько товаров разных категорий (например, ламинат, краска, керамогранит):<br />
                          • <strong>Сбалансированный поиск</strong> — единая квота поставщиков распределяется между всеми позициями ТЗ в рамках 1 задачи. В итоговом Excel-отчете формируется единый лист «Сводный реестр» со сворачиваемой иерархической структурой строк (+ / -) по каждой позиции спецификации, а также единый официальный Запрос КП (.docx).<br />
                          • <strong>Попозиционный глубокий поиск</strong> — независимый глубокий поиск по каждой позиции с отдельным детальным анализом сайтов производителей и списанием по числу позиций.
                        </p>
                      </div>
                    </div>

                    <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100">
                      <span className="text-xs text-slate-500 font-medium">
                        Совет: используйте готовую базу контактов для быстрого сбора ценовых предложений.
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          selectScenario("supplier_search");
                          setShowHelpModal(false);
                        }}
                        className="tl-btn-primary px-4 py-2 text-xs rounded-xl cursor-pointer inline-flex items-center gap-1.5 shrink-0"
                      >
                        <span>Выбрать «Поиск поставщиков»</span>
                        <ArrowRight size={14} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                ) : null}

                {helpModalTab === "analysis_and_suppliers" ? (
                  <div className="space-y-4">
                    <div className="grid sm:grid-cols-2 gap-4">
                      <div className="p-4 bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl space-y-3">
                        <div>
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Назначение функции:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            Совмещенный экспресс-запуск в 1 клик: глубокий аудит рисков контракта плюс автоматический сбор базы заводов и поставщиков по спецификации ТЗ.
                          </p>
                        </div>
                        <div className="pt-2 border-t border-[#e5e9e2]">
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Когда применять:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            Когда нужно быстро получить общую картину по новой закупке: оценить риски и сразу получить контакты поставщиков для расчета цены.
                          </p>
                        </div>
                      </div>

                      <div className="p-4 bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl space-y-3">
                        <div>
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Что загружать:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            19-значный номер извещения ЕИС, ссылку на zakupki.gov.ru или файлы документации закупки.
                          </p>
                        </div>
                        <div className="pt-2 border-t border-[#e5e9e2]">
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Что на выходе:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            1) Аналитический отчет DOCX с факторами риска.<br />
                            2) Таблица поставщиков XLSX с прямыми телефонами и email.<br />
                            3) Готовый файл запроса КП.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100">
                      <span className="text-xs text-slate-500 font-medium">
                        Совет: по сложным позициям ТЗ запустите «Подбор товара» для характеристик заявки.
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          selectScenario("analysis_and_suppliers");
                          setShowHelpModal(false);
                        }}
                        className="tl-btn-primary px-4 py-2 text-xs rounded-xl cursor-pointer inline-flex items-center gap-1.5 shrink-0"
                      >
                        <span>Выбрать «Анализ + поиск»</span>
                        <ArrowRight size={14} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                ) : null}

                {helpModalTab === "exact_product" ? (
                  <div className="space-y-4">
                    <div className="grid sm:grid-cols-2 gap-4">
                      <div className="p-4 bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl space-y-3">
                        <div>
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Назначение функции:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            ИИ детально анализирует технические характеристики ТЗ, предлагает возможную модель и производителя, составляет таблицу параметров и российских аналогов. Соответствие требованиям ТЗ нужно подтвердить по документации производителя.
                          </p>
                        </div>
                        <div className="pt-2 border-t border-[#e5e9e2]">
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Когда применять:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            Когда заказчик не указал бренд в ТЗ или требуется снизить себестоимость заявки с помощью российского аналога из реестра Минпромторга (ГИСП).
                          </p>
                        </div>
                      </div>

                      <div className="p-4 bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl space-y-3">
                        <div>
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Что загружать:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            Файл ТЗ, спецификацию или таблицу характеристик (.pdf, .docx, .xlsx, .zip), либо вставьте фрагмент описания объекта закупки текстом.
                          </p>
                        </div>
                        <div className="pt-2 border-t border-[#e5e9e2]">
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Что на выходе:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs sm:text-[13px] mt-1">
                            1) Рабочий отчет Word (DOCX) с кандидатами и сопоставлением характеристик ТЗ.<br />
                            2) Готовая таблица конкретных показателей для 1-й части заявки.<br />
                            3) Варианты аналогов РФ с попараметрическим сравнением и доступными сведениями реестра ГИСП.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100">
                      <span className="text-xs text-slate-500 font-medium">
                        Совет: после расшифровки модели перейдите к «Поиску поставщиков» для запроса КП.
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          selectScenario("exact_product");
                          setShowHelpModal(false);
                        }}
                        className="tl-btn-primary px-4 py-2 text-xs rounded-xl cursor-pointer inline-flex items-center gap-1.5 shrink-0"
                      >
                        <span>Выбрать «Подбор товара»</span>
                        <ArrowRight size={14} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                ) : null}

                {helpModalTab === "price_monitoring" ? (
                  <div className="space-y-4">
                    <div className="p-4 bg-[#f4f8ef] border border-[#cde0be] rounded-2xl">
                      <h3 className="font-extrabold text-[#103a31] text-sm mb-1">
                        Мониторинг цен поставщиков по спецификации (XLSX)
                      </h3>
                      <p className="text-slate-700 text-xs leading-relaxed">
                        Автоматический сбор актуальных рыночных цен из открытых источников и каталогов поставщиков. До 5 реальных предложений на позицию с контактами, ИНН и ссылками на товар.
                      </p>
                    </div>

                    <div className="grid sm:grid-cols-2 gap-3.5">
                      <div className="p-4 bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl space-y-1.5">
                        <div className="font-bold text-slate-900 text-xs sm:text-[13px]">Оплата только за результат</div>
                        <p className="text-slate-600 text-xs leading-relaxed">
                          Списание с баланса происходит исключительно за те позиции спецификации, по которым фактически найдена и подтверждена цена. Позиции без найденной цены не тарифицируются (0 ₽).
                        </p>
                      </div>
                      <div className="p-4 bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl space-y-1.5">
                        <div className="font-bold text-slate-900 text-xs sm:text-[13px]">Формат выгрузки</div>
                        <p className="text-slate-600 text-xs leading-relaxed">
                          Готовый Excel-отчет (.xlsx) в утвержденном формате: сравнительная сводка по 5 поставщикам, детальный реестр с ценой за единицу, датой, телефоном, почтой и ссылкой.
                        </p>
                      </div>
                    </div>

                    <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100">
                      <span className="text-xs text-slate-500 font-medium">
                        Совет: загружайте спецификацию в формате .xlsx с колонками «Наименование» и «Ед. изм.».
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          selectScenario("price_monitoring");
                          setShowHelpModal(false);
                        }}
                        className="tl-btn-primary px-4 py-2 text-xs rounded-xl cursor-pointer inline-flex items-center gap-1.5 shrink-0"
                      >
                        <span>Выбрать «Мониторинг цен»</span>
                        <ArrowRight size={14} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                ) : null}

                {helpModalTab === "custom_batch_report" ? (
                  <div className="space-y-4">
                    <div className="p-4 bg-[#f4f8ef] border border-[#cde0be] rounded-2xl">
                      <h3 className="font-extrabold text-[#103a31] text-sm mb-1">
                        Экспресс-оценка закупок — быстрый фильтр «стоит ли участвовать»
                      </h3>
                      <p className="text-slate-700 text-xs leading-relaxed">
                        Помогает быстро отсеять невыгодные закупки и найти перспективные до глубокой проработки. Работает как с одной закупкой, так и со списком из выгрузки Excel, CSV или Word.
                      </p>
                    </div>

                    <div className="grid sm:grid-cols-2 gap-3.5">
                      <div className="p-4 bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl space-y-3">
                        <div>
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Что загружать:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs mt-1">
                            Один номер закупки ЕИС, перечень номеров в столбик/через запятую, файл ТЗ или таблицу выгрузки закупок. Для списка откроется предпросмотр, где вы отметите нужные строки и сразу увидите стоимость.
                          </p>
                        </div>
                        <div className="pt-2 border-t border-[#e5e9e2]">
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Чем отличается от «Анализа документации»:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs mt-1">
                            <b>Шаг 1 — Экспресс-оценка:</b> быстрый коммерческий вердикт — какой товар нужен, ориентир рыночной цены, потенциальная маржа, примеры поставщиков и риски.<br />
                            <b>Шаг 2 — Анализ документации:</b> детальный разбор всех позиций ТЗ, требований нацрежима (ПП № 1875), штрафов и готовый Запрос КП перед подачей заявки.
                          </p>
                        </div>
                      </div>

                      <div className="p-4 bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl space-y-3">
                        <div>
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Что на выходе:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs mt-1">
                            1) Удобный просмотр всех ответов ИИ прямо в кабинете с кнопкой «Разобрать детально» для перевода перспективной закупки в полный анализ.<br />
                            2) Отдельный структурированный отчёт по каждой закупке с кликабельными ссылками.<br />
                            3) Выгрузка всех готовых отчётов одним архивом.
                          </p>
                        </div>
                        <div className="pt-2 border-t border-[#e5e9e2]">
                          <strong className="text-slate-900 font-bold block text-xs sm:text-[13px]">Оплата по факту:</strong>
                          <p className="text-slate-600 leading-relaxed text-xs mt-1">
                            Списание выполняется только за те закупки, по которым найдена документация и сформирован результат.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100">
                      <span className="text-xs text-slate-500 font-medium">
                        Совет: после оценки откройте «Открыть ответы ИИ» — любую перспективную закупку можно в один клик отправить в «Анализ документации».
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          selectScenario(hasSeparateCustomBatchTab ? "custom_batch_report" : "procurement_report");
                          setShowHelpModal(false);
                        }}
                        className="tl-btn-primary px-4 py-2 text-xs rounded-xl cursor-pointer inline-flex items-center gap-1.5 shrink-0"
                      >
                        <span>Выбрать «Экспресс-оценку»</span>
                        <ArrowRight size={14} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>

              {/* Modal Footer */}
              <footer className="px-5 sm:px-6 py-3 bg-[#f8faf6] border-t border-[#e5e9e2] flex items-center justify-between shrink-0">
                <span className="text-xs text-slate-500 font-medium hidden sm:inline">
                  TenderLex — ИИ-платформа анализа закупок и подбора поставщиков
                </span>
                <button
                  type="button"
                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold text-xs rounded-xl transition-colors cursor-pointer ml-auto"
                  onClick={() => setShowHelpModal(false)}
                >
                  Закрыть
                </button>
              </footer>
            </section>
          </div>
        );
      })() : null}

      {/* Expenses, Operations History & Legal Entity Invoices Modal */}
      {showHistoryModal ? (() => {
        const historyPageCount = Math.max(1, Math.ceil(historyTotal / HISTORY_PAGE_SIZE));
        const historyStart = historyTotal ? (historyPage - 1) * HISTORY_PAGE_SIZE + 1 : 0;
        const historyEnd = Math.min(historyTotal, historyPage * HISTORY_PAGE_SIZE);
        const filteredHistoryTransactions = historyTransactions.filter((tx) => {
          if (historyOpFilter === "grant") return tx.operation === "grant";
          if (historyOpFilter === "release") return tx.operation === "release";
          if (historyOpFilter === "debit") return tx.operation !== "grant" && tx.operation !== "release";
          return true;
        });
        const historyFilterCounts = {
          all: historyTransactions.length,
          debit: historyTransactions.filter((tx) => tx.operation !== "grant" && tx.operation !== "release").length,
          grant: historyTransactions.filter((tx) => tx.operation === "grant").length,
          release: historyTransactions.filter((tx) => tx.operation === "release").length,
        };
        const invoicesTotalPages = Math.max(1, Math.ceil(customerInvoices.length / CUSTOMER_INVOICES_PER_PAGE));
        const safeInvoicesPage = Math.min(customerInvoicesPage, invoicesTotalPages);
        const invoicesStartIndex = (safeInvoicesPage - 1) * CUSTOMER_INVOICES_PER_PAGE;
        const currentModalInvoices = customerInvoices.slice(invoicesStartIndex, invoicesStartIndex + CUSTOMER_INVOICES_PER_PAGE);

        const closeHistoryModal = () => {
          setShowHistoryModal(false);
          setHistoryOpFilter("all");
          setInvoiceCardEmailError("");
        };

        return (
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4 z-50 overflow-y-auto"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) closeHistoryModal();
            }}
          >
            <section
              className="bg-white rounded-2xl p-5 sm:p-6 max-w-2xl w-full shadow-2xl border border-slate-200 space-y-4 max-h-[88vh] flex flex-col font-sans"
              role="dialog"
              aria-modal="true"
              aria-labelledby="history-modal-title"
            >
              {/* Modal Header */}
              <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3.5 shrink-0">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-[#f4f8ef] border border-[#cde0be] text-[#174b3f] shrink-0">
                    <Receipt size={18} aria-hidden="true" />
                  </div>
                  <div>
                    <h2 id="history-modal-title" className="text-base sm:text-lg font-extrabold text-slate-900 leading-tight">
                      Счета и история операций
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Списания за задачи, пополнения баланса и счета для юридических лиц
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-colors shrink-0 cursor-pointer"
                  onClick={closeHistoryModal}
                  aria-label="Закрыть историю"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Segmented Modal Tabs */}
              <div className="flex items-center justify-between gap-2 flex-wrap shrink-0">
                <div className="tl-seg-group" role="tablist" aria-label="Разделы счетов и операций">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={historyModalTab === "transactions"}
                    onClick={() => setHistoryModalTab("transactions")}
                    className={`tl-seg-btn ${historyModalTab === "transactions" ? "is-active" : ""}`}
                  >
                    История списаний
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={historyModalTab === "invoices"}
                    onClick={() => {
                      setHistoryModalTab("invoices");
                      setInvoiceCardEmailError("");
                      loadCustomerInvoices();
                    }}
                    className={`tl-seg-btn tl-num ${historyModalTab === "invoices" ? "is-active" : ""}`}
                  >
                    Счета для юрлиц{customerInvoices.length > 0 ? ` (${customerInvoices.length})` : ""}
                  </button>
                </div>

                {historyModalTab === "invoices" ? (
                  <button
                    type="button"
                    onClick={() => {
                      const pkgs = session?.deposit_packages?.length ? session.deposit_packages : DEFAULT_DEPOSIT_PACKAGES;
                      const defPkg = pkgs.find((p) => p.price_rub === 5000) || pkgs[2] || pkgs[0];
                      setSelectedTopUpPackage(defPkg);
                      setCustomTopUpRub(defPkg?.price_rub || 5000);
                      closeHistoryModal();
                      setTopUpTab("b2b");
                      setShowTopUpModal(true);
                    }}
                    className="tl-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer"
                  >
                    <PlusCircle size={13} aria-hidden="true" />
                    <span>Выставить счёт</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      const pkgs = session?.deposit_packages?.length ? session.deposit_packages : DEFAULT_DEPOSIT_PACKAGES;
                      const defPkg = pkgs.find((p) => p.price_rub === 5000) || pkgs[2] || pkgs[0];
                      setSelectedTopUpPackage(defPkg);
                      setCustomTopUpRub(defPkg?.price_rub || 5000);
                      closeHistoryModal();
                      setTopUpTab("card");
                      setShowTopUpModal(true);
                    }}
                    className="tl-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer"
                  >
                    <PlusCircle size={13} aria-hidden="true" />
                    <span>Пополнить</span>
                  </button>
                )}
              </div>

              {/* Operation-type filter chips for transactions */}
              {historyModalTab === "transactions" && !historyLoading && !historyError && historyTransactions.length > 0 ? (
                <div className="flex flex-wrap items-center gap-1.5 shrink-0 tl-num">
                  {(
                    [
                      { id: "all", label: "Все", count: historyFilterCounts.all },
                      { id: "debit", label: "Списания", count: historyFilterCounts.debit },
                      { id: "grant", label: "Пополнения", count: historyFilterCounts.grant },
                      { id: "release", label: "Возвраты", count: historyFilterCounts.release },
                    ] as const
                  ).map((chip) => {
                    const active = historyOpFilter === chip.id;
                    return (
                      <button
                        key={chip.id}
                        type="button"
                        onClick={() => setHistoryOpFilter(chip.id)}
                        className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors cursor-pointer ${
                          active
                            ? "bg-[#f4f8ef] border-[#9ec089] text-[#103a31]"
                            : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                        }`}
                      >
                        {chip.label}
                        <span className={`ml-1 text-[10px] ${active ? "text-[#174b3f]" : "text-slate-400"}`}>
                          {chip.count}
                        </span>
                      </button>
                    );
                  })}
                </div>
              ) : null}

              {/* Modal Body */}
              {historyModalTab === "transactions" ? (
                <div className="flex-1 overflow-y-auto space-y-2 pr-1 min-h-[260px]">
                  {historyLoading ? (
                    <div className="py-16 flex flex-col items-center justify-center text-slate-400 space-y-2">
                      <Loader2 size={24} className="animate-spin text-[#174b3f]" />
                      <span className="text-xs font-medium">Загрузка истории операций...</span>
                    </div>
                  ) : historyError ? (
                    <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center justify-between">
                      <span>{historyError}</span>
                      <button
                        type="button"
                        onClick={() => loadHistoryTransactions(historyPage)}
                        className="px-2.5 py-1 bg-rose-100 hover:bg-rose-200 text-rose-900 rounded-lg font-bold transition-colors cursor-pointer"
                      >
                        Повторить
                      </button>
                    </div>
                  ) : historyTransactions.length === 0 ? (
                    <div className="py-16 text-center text-slate-400 space-y-2">
                      <Receipt size={32} className="mx-auto text-slate-300" />
                      <p className="text-sm font-semibold text-slate-600">История операций пока пуста</p>
                      <p className="text-xs text-slate-400 max-w-sm mx-auto">
                        Здесь будут отображаться списания за выполненные задачи и история начислений
                      </p>
                    </div>
                  ) : filteredHistoryTransactions.length === 0 ? (
                    <div className="py-12 text-center text-slate-400 space-y-2.5">
                      <p className="text-xs font-semibold text-slate-600">На этой странице нет операций выбранного типа</p>
                      <button
                        type="button"
                        onClick={() => setHistoryOpFilter("all")}
                        className="px-3 py-1.5 rounded-lg bg-[#f4f8ef] hover:bg-[#e7efe0] border border-[#cde0be] text-[#174b3f] text-xs font-bold cursor-pointer"
                      >
                        Показать все операции
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {filteredHistoryTransactions.map((tx) => {
                        const isGrant = tx.operation === "grant";
                        const isRelease = tx.operation === "release";
                        const hasDistinctTitle = Boolean(
                          tx.title &&
                          tx.title.trim().toLowerCase() !== tx.kind_label.trim().toLowerCase() &&
                          tx.title.trim().toLowerCase() !== tx.operation_label.trim().toLowerCase()
                        );

                        return (
                          <div
                            key={tx.id}
                            className="p-3 bg-slate-50/70 hover:bg-slate-50 border border-slate-200/80 rounded-xl flex items-center justify-between gap-3 transition-colors"
                          >
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-slate-900 truncate">
                                  {tx.kind_label || tx.operation_label}
                                </span>
                                <span className="text-[10px] font-medium text-slate-400 shrink-0 tl-num">
                                  {formatDate(tx.created_at)}
                                </span>
                              </div>
                              {hasDistinctTitle ? (
                                <p className="text-xs text-slate-600 truncate font-normal" title={tx.title}>
                                  {tx.title}
                                </p>
                              ) : null}
                            </div>

                            <div className="text-right shrink-0">
                              <span
                                className={`text-xs sm:text-sm font-extrabold whitespace-nowrap tl-num ${
                                  isGrant
                                    ? "text-emerald-700"
                                    : isRelease
                                    ? "text-[#174b3f]"
                                    : "text-slate-800"
                                }`}
                              >
                                {isGrant
                                  ? `+${formatRubles(tx.amount_kopeks)}`
                                  : isRelease
                                  ? `+${formatRubles(tx.amount_kopeks)} (возврат)`
                                  : tx.amount_kopeks > 0
                                  ? `-${formatRubles(tx.amount_kopeks)}`
                                  : "0 ₽"}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto space-y-2 pr-1 min-h-[260px]">
                  {invoiceProofMessage ? (
                    <div
                      className={`p-2.5 rounded-xl text-xs font-semibold border ${
                        invoiceProofMessage.includes("отправлена")
                          ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                          : "bg-rose-50 border-rose-200 text-rose-800"
                      }`}
                    >
                      {invoiceProofMessage}
                    </div>
                  ) : null}
                  {invoiceCardEmailError ? (
                    <div className="p-2.5 rounded-xl text-xs font-semibold border bg-rose-50 border-rose-200 text-rose-800">
                      {invoiceCardEmailError}
                    </div>
                  ) : null}

                  {customerInvoices.length === 0 ? (
                    <div className="py-14 text-center text-slate-400 space-y-3">
                      <Building2 size={32} className="mx-auto text-slate-300" />
                      <div className="space-y-1">
                        <p className="text-sm font-semibold text-slate-700">Выставленных счетов пока нет</p>
                        <p className="text-xs text-slate-500 max-w-sm mx-auto">
                          Вы можете сформировать счёт по ИНН компании, скачать PDF/Excel и прикрепить платёжное поручение для быстрого зачисления
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          const pkgs = session?.deposit_packages?.length ? session.deposit_packages : DEFAULT_DEPOSIT_PACKAGES;
                          const defPkg = pkgs.find((p) => p.price_rub === 5000) || pkgs[2] || pkgs[0];
                          setSelectedTopUpPackage(defPkg);
                          setCustomTopUpRub(defPkg?.price_rub || 5000);
                          closeHistoryModal();
                          setTopUpTab("b2b");
                          setShowTopUpModal(true);
                        }}
                        className="tl-btn-primary inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs cursor-pointer"
                      >
                        <Building2 size={14} aria-hidden="true" />
                        <span>Выставить счёт для юрлица</span>
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {currentModalInvoices.map((invoice) => {
                        const statusLabel =
                          invoice.status === "paid"
                            ? "Оплачен"
                            : invoice.status === "proof_submitted"
                            ? "Платёжка на проверке"
                            : invoice.status === "rejected"
                            ? "Нужна новая платёжка"
                            : invoice.status === "cancelled"
                            ? "Отменён"
                            : "Ожидает оплаты";
                        const statusClass =
                          invoice.status === "paid"
                            ? "bg-emerald-50 text-emerald-900 border-emerald-200"
                            : invoice.status === "proof_submitted"
                            ? "bg-[#f4f8ef] text-[#174b3f] border-[#cde0be]"
                            : invoice.status === "rejected"
                            ? "bg-rose-50 text-rose-800 border-rose-200"
                            : invoice.status === "cancelled"
                            ? "bg-slate-100 text-slate-600 border-slate-200"
                            : "bg-amber-50 text-amber-900 border-amber-200";
                        const canUpload =
                          invoice.status === "issued" ||
                          invoice.status === "rejected" ||
                          invoice.status === "proof_submitted";
                        const isCopied = invoiceCopiedId === invoice.id;
                        const isSendingEmail = invoiceEmailSendingId === invoice.id;
                        const isSentEmail = invoiceEmailSentId === invoice.id;
                        return (
                          <div
                            key={invoice.id}
                            className="rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-white p-3.5 flex flex-col gap-2 transition-colors"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="text-xs font-extrabold text-slate-900 tl-num">
                                  Счёт № {invoice.invoice_number}
                                </div>
                                <div className="text-[11px] text-slate-500 tl-num">
                                  {invoice.created_at ? new Date(invoice.created_at).toLocaleDateString("ru-RU") : ""}
                                  {invoice.buyer_name ? ` · ${invoice.buyer_name}` : ""}
                                </div>
                              </div>
                              <span className={`text-[11px] font-bold border rounded-full px-2.5 py-0.5 shrink-0 ${statusClass}`}>
                                {statusLabel}
                              </span>
                            </div>

                            <div className="text-xs text-slate-700 font-medium tl-num">
                              <strong className="text-slate-900">{invoice.amount_rub.toLocaleString("ru-RU")} ₽</strong>
                              {invoice.bonus_rub > 0 ? (
                                <span className="text-[#174b3f] font-semibold">
                                  {" "}· +{invoice.bonus_rub.toLocaleString("ru-RU")} ₽ бонус (итого {invoice.total_credit_rub.toLocaleString("ru-RU")} ₽)
                                </span>
                              ) : null}
                            </div>

                            <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                              <a
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white hover:bg-slate-50 border border-slate-200 text-[11px] font-semibold text-slate-800 transition-colors"
                                href={`/api/customer/invoices/${invoice.id}/download?format=pdf`}
                                download
                              >
                                <Download size={12} className="text-[#174b3f]" aria-hidden="true" />
                                <span>PDF</span>
                              </a>
                              <a
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white hover:bg-slate-50 border border-slate-200 text-[11px] font-semibold text-slate-800 transition-colors"
                                href={`/api/customer/invoices/${invoice.id}/download?format=xlsx`}
                                download
                              >
                                <FileSpreadsheet size={12} className="text-[#174b3f]" aria-hidden="true" />
                                <span>Excel</span>
                              </a>
                              <a
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white hover:bg-slate-50 border border-slate-200 text-[11px] font-semibold text-slate-700 transition-colors"
                                href={`/api/customer/invoices/${invoice.id}/html`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                <Printer size={12} className="text-slate-500" aria-hidden="true" />
                                <span>Печать</span>
                              </a>
                              <button
                                type="button"
                                onClick={() => {
                                  const detailsText = `Получатель: ИП Груздев Игорь Вячеславович\nИНН: 352516048881\nР/с: 40802810217430000342\nБанк: АО "АЛЬФА-БАНК"\nБИК: 044525593\nК/с: 30101810200000000593\nСумма: ${invoice.amount_rub} руб.\nНазначение: Оплата по счету № ${invoice.invoice_number} за услуги сервиса TenderLex. Без НДС.`;
                                  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
                                    void navigator.clipboard.writeText(detailsText);
                                  }
                                  setInvoiceCopiedId(invoice.id);
                                  setTimeout(() => setInvoiceCopiedId((cur) => (cur === invoice.id ? null : cur)), 2500);
                                }}
                                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border text-[11px] font-semibold transition-colors cursor-pointer ${
                                  isCopied
                                    ? "bg-[#f4f8ef] border-[#9ec089] text-[#103a31]"
                                    : "bg-white hover:bg-slate-50 border-slate-200 text-slate-700"
                                }`}
                              >
                                {isCopied ? <Check size={12} className="text-[#174b3f]" aria-hidden="true" /> : <Copy size={12} className="text-slate-500" aria-hidden="true" />}
                                <span>{isCopied ? "Скопировано" : "Реквизиты для 1С"}</span>
                              </button>
                              <button
                                type="button"
                                disabled={isSendingEmail}
                                onClick={async () => {
                                  setInvoiceEmailSendingId(invoice.id);
                                  setInvoiceCardEmailError("");
                                  try {
                                    const res = await fetch(`/api/customer/invoices/${invoice.id}/send-email`, {
                                      method: "POST",
                                      credentials: "same-origin",
                                      headers: {
                                        "Content-Type": "application/json",
                                        ...(csrf ? { "x-csrf-token": csrf } : {}),
                                      },
                                      body: JSON.stringify({ email: invoice.buyer_email || session?.user?.email }),
                                    });
                                    const data = await res.json();
                                    if (!res.ok) throw new Error(data.detail || "Ошибка отправки");
                                    setInvoiceEmailSentId(invoice.id);
                                    setTimeout(() => setInvoiceEmailSentId((cur) => (cur === invoice.id ? null : cur)), 3500);
                                  } catch (err: any) {
                                    setInvoiceCardEmailError(err?.message || "Не удалось отправить счёт на почту");
                                  } finally {
                                    setInvoiceEmailSendingId(null);
                                  }
                                }}
                                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border text-[11px] font-semibold transition-colors cursor-pointer disabled:opacity-50 ${
                                  isSentEmail
                                    ? "bg-[#f4f8ef] border-[#9ec089] text-[#103a31]"
                                    : "bg-white hover:bg-slate-50 border-slate-200 text-slate-700"
                                }`}
                              >
                                {isSendingEmail ? (
                                  <Loader2 size={12} className="animate-spin text-[#174b3f]" aria-hidden="true" />
                                ) : isSentEmail ? (
                                  <Check size={12} className="text-[#174b3f]" aria-hidden="true" />
                                ) : (
                                  <Mail size={12} className="text-slate-500" aria-hidden="true" />
                                )}
                                <span>{isSentEmail ? "Отправлено" : "На email"}</span>
                              </button>
                              {canUpload ? (
                                <label className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#f4f8ef] hover:bg-[#e7efe0] border border-[#cde0be] text-[11px] font-bold text-[#103a31] cursor-pointer transition-colors">
                                  <Upload size={12} aria-hidden="true" />
                                  <span>
                                    {invoiceProofUploading === invoice.id
                                      ? "Отправка…"
                                      : invoice.status === "proof_submitted"
                                      ? "Загрузить исправленную платёжку"
                                      : "Прикрепить платёжку"}
                                  </span>
                                  <input
                                    type="file"
                                    className="hidden"
                                    accept="application/pdf,image/jpeg,image/png"
                                    disabled={invoiceProofUploading === invoice.id}
                                    onChange={(event) => {
                                      const file = event.currentTarget.files?.[0];
                                      if (file && file.size <= 10 * 1024 * 1024) {
                                        uploadInvoiceProof(invoice.id, file);
                                      } else if (file) {
                                        setInvoiceProofMessage("Файл должен быть не больше 10 МБ");
                                      }
                                      event.currentTarget.value = "";
                                    }}
                                  />
                                </label>
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Modal Footer with Pagination */}
              <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 shrink-0">
                {historyModalTab === "transactions" ? (
                  <>
                    <span className="text-xs text-slate-500 font-medium tl-num">
                      {historyTotal > 0 ? (
                        <>
                          Показано <strong className="text-slate-700">{historyStart}–{historyEnd}</strong> из <strong className="text-slate-700">{historyTotal}</strong>
                        </>
                      ) : (
                        ""
                      )}
                    </span>

                    {historyPageCount > 1 ? (
                      <div className="flex items-center gap-1.5 tl-num">
                        <button
                          type="button"
                          disabled={historyPage <= 1 || historyLoading}
                          onClick={() => loadHistoryTransactions(historyPage - 1)}
                          className="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 disabled:opacity-40 disabled:pointer-events-none text-slate-700 font-bold text-xs rounded-lg transition-colors cursor-pointer"
                        >
                          Назад
                        </button>
                        <span className="text-xs font-semibold text-slate-600 px-1.5">
                          {historyPage} из {historyPageCount}
                        </span>
                        <button
                          type="button"
                          disabled={historyPage >= historyPageCount || historyLoading}
                          onClick={() => loadHistoryTransactions(historyPage + 1)}
                          className="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 disabled:opacity-40 disabled:pointer-events-none text-slate-700 font-bold text-xs rounded-lg transition-colors cursor-pointer"
                        >
                          Вперёд
                        </button>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <>
                    <span className="text-xs text-slate-500 font-medium tl-num">
                      {customerInvoices.length > 0 ? `Всего счетов: ${customerInvoices.length}` : ""}
                    </span>
                    {invoicesTotalPages > 1 ? (
                      <div className="flex items-center gap-1.5 tl-num">
                        <button
                          type="button"
                          disabled={safeInvoicesPage <= 1}
                          onClick={() => setCustomerInvoicesPage((p) => Math.max(1, p - 1))}
                          className="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 disabled:opacity-40 disabled:pointer-events-none text-slate-700 font-bold text-xs rounded-lg transition-colors cursor-pointer"
                        >
                          Назад
                        </button>
                        <span className="text-xs font-semibold text-slate-600 px-1.5">
                          {safeInvoicesPage} из {invoicesTotalPages}
                        </span>
                        <button
                          type="button"
                          disabled={safeInvoicesPage >= invoicesTotalPages}
                          onClick={() => setCustomerInvoicesPage((p) => Math.min(invoicesTotalPages, p + 1))}
                          className="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 disabled:opacity-40 disabled:pointer-events-none text-slate-700 font-bold text-xs rounded-lg transition-colors cursor-pointer"
                        >
                          Вперёд
                        </button>
                      </div>
                    ) : null}
                  </>
                )}

                <button
                  type="button"
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-lg transition-all cursor-pointer ml-auto"
                  onClick={closeHistoryModal}
                >
                  Закрыть
                </button>
              </div>
            </section>
          </div>
        );
      })() : null}

      {/* Referral Program Modal (Compact, Clean, No Scroll, Design System Cohesive) */}
      {showReferralModal ? (() => {
        const refCode = session?.referral?.referral_code || "ref";
        const webLink = session?.referral?.invite_url_web || `https://tenderlex.ru/cabinet?ref=${refCode}`;
        const botLink = session?.referral?.invite_url_bot || `https://t.me/tenderlex_bot?start=ref_${refCode}`;
        const invited = session?.referral?.invited_count ?? 0;
        const activated = session?.referral?.activated_count ?? 0;
        const earned = session?.referral?.bonus_earned_rub ?? 0;

        const shareMessageBody = `Коллега, держи сервис для подготовки к закупкам и тендерам — TenderLex.
Он помогает:
1. Найти реальных производителей и дилеров по ТЗ с прямыми контактами
2. Подобрать точную модель товара и аналоги под первую часть заявки
3. Сформировать структурированный отчет и анализ требований закупки

По ссылке доступен пробный доступ для проверки первых задач + бонус 1 000 ₽ к первому пополнению баланса:`;
        const shareMessage = `${shareMessageBody}\n${webLink}`;
        const tgShareUrl = `https://t.me/share/url?url=${encodeURIComponent(webLink)}&text=${encodeURIComponent(shareMessageBody)}`;

        function copyLink(textToCopy: string, key: string) {
          if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
            navigator.clipboard.writeText(textToCopy).then(() => {
              setReferralCopiedKey(key);
              setTimeout(() => setReferralCopiedKey(null), 2500);
            });
          }
        }

        return (
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4 z-50 overflow-y-auto"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) setShowReferralModal(false);
            }}
          >
            <section
              className="bg-white rounded-2xl p-5 sm:p-6 max-w-xl w-full shadow-2xl border border-slate-200 space-y-3.5 flex flex-col font-sans my-auto max-h-[92vh] overflow-y-auto"
              role="dialog"
              aria-modal="true"
              aria-labelledby="referral-modal-title"
            >
              {/* Modal Header */}
              <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3 shrink-0">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-[#f4f8ef] border border-[#cde0be] text-[#174b3f] shrink-0">
                    <Gift size={18} aria-hidden="true" />
                  </div>
                  <div>
                    <h2 id="referral-modal-title" className="text-base sm:text-lg font-extrabold text-slate-900 leading-tight">
                      Пригласить коллегу
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Дарите +1 000 ₽ к первому пополнению коллеге и получайте 1 000 ₽ за его первый платёж
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors shrink-0 cursor-pointer"
                  onClick={() => setShowReferralModal(false)}
                  aria-label="Закрыть окно"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Statistics Row */}
              <div className="grid grid-cols-3 gap-2.5 shrink-0 tl-num">
                <div className="p-2.5 rounded-xl bg-[#f8faf6] border border-[#dfe5dc] text-center">
                  <div className="text-lg sm:text-xl font-black text-slate-900">{invited}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">Приглашено</div>
                </div>
                <div className="p-2.5 rounded-xl bg-[#f8faf6] border border-[#dfe5dc] text-center">
                  <div className="text-lg sm:text-xl font-black text-[#174b3f]">{activated}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">Пополнили баланс</div>
                </div>
                <div className="p-2.5 rounded-xl bg-[#f4f8ef] border border-[#cde0be] text-center">
                  <div className="text-lg sm:text-xl font-black text-[#103a31]">{earned.toLocaleString("ru-RU")} ₽</div>
                  <div className="text-[11px] text-[#174b3f] mt-0.5">Начислено бонусов</div>
                </div>
              </div>

              {/* Compact 3-Step Conditions Strip */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 p-2.5 rounded-xl bg-slate-50 border border-slate-200/80 text-[11px] text-slate-600">
                <div className="flex items-start gap-1.5">
                  <span className="w-4 h-4 rounded-full bg-[#e7efe0] text-[#103a31] font-extrabold text-[10px] flex items-center justify-center shrink-0 mt-0.5">1</span>
                  <span>Коллега переходит по вашей ссылке и регистрируется</span>
                </div>
                <div className="flex items-start gap-1.5">
                  <span className="w-4 h-4 rounded-full bg-[#e7efe0] text-[#103a31] font-extrabold text-[10px] flex items-center justify-center shrink-0 mt-0.5">2</span>
                  <span>Совершает первое пополнение баланса</span>
                </div>
                <div className="flex items-start gap-1.5">
                  <span className="w-4 h-4 rounded-full bg-[#e7efe0] text-[#103a31] font-extrabold text-[10px] flex items-center justify-center shrink-0 mt-0.5">3</span>
                  <span>Оба баланса автоматически получают по +1 000 ₽</span>
                </div>
              </div>

              {/* Links Section (Calm Secondary Copy Buttons) */}
              <div className="space-y-2 shrink-0">
                <div>
                  <div className="text-[11px] font-semibold text-slate-600 mb-1">
                    Ссылка для сайта (кабинет):
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      readOnly
                      value={webLink}
                      className="flex-1 min-w-0 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 font-mono select-all focus:outline-hidden"
                    />
                    <button
                      type="button"
                      onClick={() => copyLink(webLink, "web")}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors cursor-pointer shrink-0 ${
                        referralCopiedKey === "web"
                          ? "bg-[#f4f8ef] border-[#9ec089] text-[#103a31]"
                          : "bg-white hover:bg-[#f4f8ef] text-[#174b3f] border-[#b7c9af]"
                      }`}
                    >
                      {referralCopiedKey === "web" ? (
                        <>
                          <Check size={13} aria-hidden="true" />
                          <span>Скопировано</span>
                        </>
                      ) : (
                        <>
                          <Copy size={13} aria-hidden="true" />
                          <span>Скопировать</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                <div>
                  <div className="text-[11px] font-semibold text-slate-600 mb-1">
                    Ссылка для Telegram-бота:
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      readOnly
                      value={botLink}
                      className="flex-1 min-w-0 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 font-mono select-all focus:outline-hidden"
                    />
                    <button
                      type="button"
                      onClick={() => copyLink(botLink, "bot")}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors cursor-pointer shrink-0 ${
                        referralCopiedKey === "bot"
                          ? "bg-[#f4f8ef] border-[#9ec089] text-[#103a31]"
                          : "bg-white hover:bg-[#f4f8ef] text-[#174b3f] border-[#b7c9af]"
                      }`}
                    >
                      {referralCopiedKey === "bot" ? (
                        <>
                          <Check size={13} aria-hidden="true" />
                          <span>Скопировано</span>
                        </>
                      ) : (
                        <>
                          <Copy size={13} aria-hidden="true" />
                          <span>Скопировать</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* Ready-to-send Message Box with Elevated Primary Actions */}
              <div className="p-3 bg-[#f8faf6] rounded-xl border border-[#dfe5dc] space-y-2.5 shrink-0">
                <div className="text-[11px] font-bold text-slate-700">
                  Готовое сообщение для пересылки коллегам:
                </div>
                <div className="text-[11px] text-slate-600 bg-white p-2.5 rounded-lg border border-slate-200/80 leading-relaxed font-sans whitespace-pre-wrap select-all">
                  {shareMessage}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => copyLink(shareMessage, "msg")}
                    className="tl-btn-primary inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-xs cursor-pointer flex-1 sm:flex-initial"
                  >
                    {referralCopiedKey === "msg" ? (
                      <>
                        <Check size={14} aria-hidden="true" />
                        <span>Скопировано!</span>
                      </>
                    ) : (
                      <>
                        <Copy size={14} aria-hidden="true" />
                        <span>Скопировать сообщение</span>
                      </>
                    )}
                  </button>
                  <a
                    href={tgShareUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center justify-center gap-1.5 px-4 py-2 bg-white hover:bg-[#f4f8ef] text-[#174b3f] border border-[#b7c9af] rounded-lg text-xs font-bold transition-colors cursor-pointer flex-1 sm:flex-initial"
                  >
                    <Send size={13} aria-hidden="true" />
                    <span>Поделиться в Telegram</span>
                  </a>
                </div>
              </div>

              {/* Footer */}
              <div className="flex justify-end pt-1 shrink-0">
                <button
                  type="button"
                  onClick={() => setShowReferralModal(false)}
                  className="px-4 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold transition-colors cursor-pointer"
                >
                  Закрыть
                </button>
              </div>
            </section>
          </div>
        );
      })() : null}

      {/* API & MCP Integration Modal */}
      {showApiModal ? (() => {
        const currentApiKey = newlyGeneratedKey || "";
        const effectiveKeyPlaceholder = currentApiKey || "<ВАШ_API_КЛЮЧ>";
        const balanceRub = (session?.balance?.money?.available_kopeks || 0) / 100.0;

        const aiPromptText = `Интегрируй API сервиса TenderLex в нашу систему / CRM.
Базовый URL: https://tenderlex.ru/api/v1/mcp
Авторизация: Header "Authorization: Bearer ${effectiveKeyPlaceholder}"
Для каждой новой операции создавай уникальный Idempotency-Key. При повторе после таймаута используй прежний ключ и то же тело; новый ключ означает новую платную задачу.

Требуемые функции:
1. Поиск прямых поставщиков и заводов по ТЗ / закупке:
   - Метод: POST https://tenderlex.ru/api/v1/mcp/suppliers/search
   - Тело JSON:
     {
       "specification": "<текст технического задания или номер закупки ЕИС>",
       "city": "<город или регион поставки, например: Москва>",
       "target_count": 5
     }
   - Ответ JSON:
     {
       "ok": true,
       "total_found": 5,
       "suppliers": [
         {
           "company_name": "ООО Завод...",
           "inn": "7701234567",
           "status": "производитель",
           "product": "кабель ВВГнг...",
           "site": "https://...",
           "email": "sales@...",
           "phone": "+7 (495)..."
         }
       ]
     }

2. Подбор точной модели товара и аналогов (ГОСТ, реестр Минпромторга):
   - Метод: POST https://tenderlex.ru/api/v1/mcp/products/exact-analogs
   - Тело JSON:
     {
       "specification": "<текст ТЗ>",
       "procurement_title": "<название закупки>"
     }
   - Ответ JSON:
     {
       "ok": true,
       "positions": [...],
       "docx_download_url": "https://tenderlex.ru/api/v1/mcp/downloads/exact_product_....docx"
     }

3. Анализ документации и рисков закупки:
   - Метод: POST https://tenderlex.ru/api/v1/mcp/procurements/analyze
   - Тело JSON:
     {
       "document_text": "<текст проекта контракта или извещения>"
     }
   - Ответ JSON:
     {
       "ok": true,
       "report_markdown": "<подробный аудит рисков>"
     }

4. Файлы, мониторинг цен и выбор исходных позиций:
   - POST /api/v1/mcp/jobs: multipart/form-data; Header Idempotency-Key.
   - mode: supplier_search, analysis_and_suppliers, exact_product, procurement_report, price_monitoring.
   - Передай text / source_urls / files; для геоприоритета город и geo_radius_km вместе (10–5000 км).
   - GET /api/v1/mcp/jobs/{job_id}: статус и исходные позиции.
   - POST /api/v1/mcp/jobs/{job_id}/position-selection: revision, selected_item_ids из полученного списка.
   - POST /api/v1/mcp/jobs/{job_id}/choose-strategy: multi_item_mode, selected_item_ids.
   - POST /api/v1/mcp/jobs/{job_id}/cancel; GET /api/v1/mcp/jobs/{job_id}/download.
   - Мониторинг оплачивается за найденные выбранные позиции; подбор товара и аналогов — по тарифу за каждую выбранную позицию.

5. Проверка остатка баланса:
   - Метод: GET https://tenderlex.ru/api/v1/mcp/balance

Правила списания:
- Перед запуском резервируется стоимость операции. Списание и возврат зависят от результата и тарифа; повтор с прежним Idempotency-Key не создаёт новый поиск.
- При нехватке средств на балансе выведи пользователю уведомление: "Баланс в TenderLex исчерпан. Пополните счёт в личном кабинете tenderlex.ru".`;

        const mcpConfigText = JSON.stringify(
          {
            mcpServers: {
              tenderlex: {
                command: "python3",
                args: [
                  "tenderlex_mcp.py",
                  "--api-key",
                  effectiveKeyPlaceholder,
                ],
              },
            },
          },
          null,
          2
        );

        const curlExampleText = `curl -X POST https://tenderlex.ru/api/v1/mcp/suppliers/search \\
  -H "Authorization: Bearer ${effectiveKeyPlaceholder}" \\
  -H "Idempotency-Key: <УНИКАЛЬНЫЙ_ID_ОПЕРАЦИИ>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "specification": "Кабель ВВГнг-LS 3х2.5 ГОСТ 31996-2012",
    "city": "Москва",
    "target_count": 5
  }'`;

        const baseHeaderSnippet = `BASE_URL: https://tenderlex.ru/api/v1/mcp\nAuthorization: Bearer ${effectiveKeyPlaceholder}`;

        const closeApiModal = () => {
          setShowApiModal(false);
          setConfirmRevokeKeyId(null);
        };

        return (
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4 z-50"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) closeApiModal();
            }}
          >
            <section
              className="bg-white rounded-2xl p-5 sm:p-6 max-w-2xl w-full shadow-2xl border border-slate-200 space-y-4 flex flex-col font-sans max-h-[90vh] overflow-y-auto"
              role="dialog"
              aria-modal="true"
              aria-labelledby="api-modal-title"
            >
              {/* Modal Header */}
              <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3 shrink-0">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-[#f4f8ef] border border-[#cde0be] text-[#174b3f] shrink-0">
                    <Key size={18} aria-hidden="true" />
                  </div>
                  <div>
                    <h2 id="api-modal-title" className="text-base sm:text-lg font-extrabold text-slate-900 leading-tight">
                      API и интеграции TenderLex
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Программный доступ к поиску поставщиков, подбору товара и анализу документации
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={closeApiModal}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer shrink-0"
                  aria-label="Закрыть"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Tabs Navigation */}
              <div className="bg-[#f8faf6] p-1.5 rounded-xl border border-[#e5e9e2] flex flex-wrap sm:grid sm:grid-cols-4 gap-1 text-xs shrink-0 font-bold">
                <button
                  type="button"
                  onClick={() => setApiModalTab("key")}
                  className={`py-2 px-2.5 rounded-lg transition-all text-center flex items-center justify-center gap-1.5 cursor-pointer flex-1 ${
                    apiModalTab === "key"
                      ? "bg-white text-[#103a31] shadow-2xs border border-[#cde0be]"
                      : "text-slate-600 hover:text-slate-900 hover:bg-white/60 border border-transparent"
                  }`}
                >
                  <Key size={13} className={apiModalTab === "key" ? "text-[#174b3f]" : "text-slate-400"} />
                  <span>Ключ и баланс</span>
                </button>

                <button
                  type="button"
                  onClick={() => setApiModalTab("methods")}
                  className={`py-2 px-2.5 rounded-lg transition-all text-center flex items-center justify-center gap-1.5 cursor-pointer flex-1 ${
                    apiModalTab === "methods"
                      ? "bg-white text-[#103a31] shadow-2xs border border-[#cde0be]"
                      : "text-slate-600 hover:text-slate-900 hover:bg-white/60 border border-transparent"
                  }`}
                >
                  <Layers size={13} className={apiModalTab === "methods" ? "text-[#174b3f]" : "text-slate-400"} />
                  <span>Методы API</span>
                </button>

                <button
                  type="button"
                  onClick={() => setApiModalTab("ai_prompt")}
                  className={`py-2 px-2.5 rounded-lg transition-all text-center flex items-center justify-center gap-1.5 cursor-pointer flex-1 ${
                    apiModalTab === "ai_prompt"
                      ? "bg-white text-[#103a31] shadow-2xs border border-[#cde0be]"
                      : "text-slate-600 hover:text-slate-900 hover:bg-white/60 border border-transparent"
                  }`}
                >
                  <Sparkles size={13} className={apiModalTab === "ai_prompt" ? "text-[#174b3f]" : "text-slate-400"} />
                  <span>Для ИИ</span>
                </button>

                <button
                  type="button"
                  onClick={() => setApiModalTab("mcp")}
                  className={`py-2 px-2.5 rounded-lg transition-all text-center flex items-center justify-center gap-1.5 cursor-pointer flex-1 whitespace-nowrap ${
                    apiModalTab === "mcp"
                      ? "bg-white text-[#103a31] shadow-2xs border border-[#cde0be]"
                      : "text-slate-600 hover:text-slate-900 hover:bg-white/60 border border-transparent"
                  }`}
                >
                  <Compass size={13} className={apiModalTab === "mcp" ? "text-[#174b3f]" : "text-slate-400"} />
                  <span>MCP (Claude / Cursor)</span>
                </button>
              </div>

              {/* Tab 1: Ключ и баланс */}
              {apiModalTab === "key" && (
                <div className="space-y-4">
                  {/* Balance Callout */}
                  <div className="bg-[#f4f8ef] border border-[#cde0be] rounded-xl p-3.5">
                    <div className="text-xs font-semibold text-[#174b3f]">Баланс аккаунта</div>
                    <div className="text-lg sm:text-xl font-black text-[#103a31] mt-0.5 tl-num">
                      {formatBalanceRubles(session?.balance?.money?.available_kopeks || 0)}
                    </div>
                    <div className="text-[11px] text-slate-600 mt-0.5">
                      Списание происходит с вашего общего баланса по тарифам аккаунта.
                    </div>
                  </div>

                  {/* Newly Generated Key Alert */}
                  {newlyGeneratedKey && (
                    <div className="bg-[#f4f8ef] border-2 border-[#9ec089] rounded-xl p-3.5 space-y-2 animate-fadeIn">
                      <div className="flex items-center gap-2 text-[#103a31] font-extrabold text-xs">
                        <CheckCircle2 size={16} className="text-[#174b3f] shrink-0" />
                        <span>Ключ успешно создан и готов к работе:</span>
                      </div>
                      <div className="flex items-center gap-2 bg-white border border-[#cde0be] rounded-lg p-2">
                        <code className="text-xs font-mono font-bold text-slate-800 break-all select-all flex-1">
                          {newlyGeneratedKey}
                        </code>
                        <button
                          type="button"
                          onClick={() => copyApiText(newlyGeneratedKey, "new_key")}
                          className="tl-btn-primary px-2.5 py-1.5 rounded-md text-xs cursor-pointer shrink-0 flex items-center gap-1"
                        >
                          {apiCopiedField === "new_key" ? <Check size={13} /> : <Copy size={13} />}
                          <span>{apiCopiedField === "new_key" ? "Скопировано" : "Копировать"}</span>
                        </button>
                      </div>
                      <div className="text-[11px] text-[#174b3f]">
                        Скопируйте и сохраните ключ сейчас: после перезагрузки он не показывается. В этой сессии ключ подставлен в примеры на соседних вкладках.
                      </div>
                    </div>
                  )}

                  {/* Existing Key Management */}
                  {loadingApiKeys ? (
                    <div className="py-8 flex flex-col items-center justify-center gap-2 text-slate-400">
                      <Loader2 size={24} className="animate-spin text-[#174b3f]" />
                      <span className="text-xs">Загрузка ключей доступа...</span>
                    </div>
                  ) : apiKeys.length > 0 ? (
                    <div className="space-y-3">
                      <div className="text-xs font-bold text-slate-700">Ваши активные ключи доступа:</div>
                      <p className="text-[11px] text-slate-600">Полный ключ показывается только после создания. Если он не сохранён, создайте новый; прежний продолжает работать до отзыва.</p>
                      {apiKeys.map((k) => {
                        const isConfirmingRevoke = confirmRevokeKeyId === k.id;
                        return (
                          <div key={k.id} className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 space-y-2.5">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-mono font-bold text-xs text-slate-800 bg-white px-2.5 py-1 rounded border border-slate-200 select-all max-w-[260px] sm:max-w-xs truncate">
                                  {`${k.key_prefix}••••••••••••`}
                                </span>

                                <span className="px-2 py-0.5 rounded bg-[#e7efe0] text-[#103a31] text-[10px] font-bold">
                                  Активен
                                </span>
                              </div>
                              {!isConfirmingRevoke ? (
                                <div className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => setConfirmRevokeKeyId(k.id)}
                                    disabled={revokingKeyId === k.id}
                                    className="inline-flex items-center gap-1 px-2.5 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-md text-xs font-bold transition-colors cursor-pointer"
                                  >
                                    {revokingKeyId === k.id ? <Loader2 size={12} className="animate-spin" /> : <XCircle size={12} />}
                                    <span>Отозвать</span>
                                  </button>
                                </div>
                              ) : null}
                            </div>

                            {isConfirmingRevoke ? (
                              <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 flex flex-wrap items-center justify-between gap-2">
                                <span className="text-[11px] font-semibold text-rose-900">
                                  Отключить ключ? Интеграции с ним сразу перестанут работать.
                                </span>
                                <div className="flex items-center gap-1.5 shrink-0 ml-auto">
                                  <button
                                    type="button"
                                    onClick={() => setConfirmRevokeKeyId(null)}
                                    disabled={revokingKeyId === k.id}
                                    className="px-2.5 py-1 rounded-md bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 text-[11px] font-bold cursor-pointer"
                                  >
                                    Отмена
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => void revokeCustomerApiKey(k.id)}
                                    disabled={revokingKeyId === k.id}
                                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-rose-600 hover:bg-rose-700 text-white text-[11px] font-bold cursor-pointer disabled:opacity-50"
                                  >
                                    {revokingKeyId === k.id ? <Loader2 size={11} className="animate-spin" /> : null}
                                    <span>Да, отозвать</span>
                                  </button>
                                </div>
                              </div>
                            ) : null}

                            <div className="text-[11px] text-slate-500 flex flex-wrap items-center gap-3 tl-num">
                              <span>Создан: {k.created_at ? new Date(k.created_at).toLocaleDateString("ru-RU") : "—"}</span>
                              <span>Всего вызовов: <strong>{k.total_spent || 0}</strong></span>
                              {k.last_used_at && <span>Последний вызов: {new Date(k.last_used_at).toLocaleDateString("ru-RU")}</span>}
                            </div>
                          </div>
                        );
                      })}
                      <div className="pt-1">
                        <button
                          type="button"
                          onClick={createCustomerApiKey}
                          disabled={generatingApiKey}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-[#f4f8ef] text-[#174b3f] border border-[#b7c9af] rounded-lg text-xs font-bold transition-colors cursor-pointer"
                        >
                          {generatingApiKey ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
                          <span>Сгенерировать дополнительный ключ</span>
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-[#f8faf6] border border-[#dfe5dc] rounded-2xl p-6 text-center space-y-3">
                      <div className="w-10 h-10 rounded-full bg-[#e7efe0] text-[#174b3f] flex items-center justify-center mx-auto">
                        <Key size={20} />
                      </div>
                      <div className="space-y-1">
                        <div className="font-extrabold text-sm text-slate-900">У вас пока нет API-ключа</div>
                        <p className="text-xs text-slate-500 max-w-md mx-auto">
                          Создайте ключ в 1 клик, чтобы подключить TenderLex к вашей CRM, боту, скрипту или ИИ-агенту.
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={createCustomerApiKey}
                        disabled={generatingApiKey}
                        className="tl-btn-primary inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs shadow-sm cursor-pointer"
                      >
                        {generatingApiKey ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                        <span>Создать API-ключ</span>
                      </button>
                    </div>
                  )}

                  {/* Policy and Safety notice */}
                  <div className="bg-slate-50 p-3 rounded-xl border border-slate-200/80 text-[11px] text-slate-600 space-y-1 leading-relaxed">
                    <ul className="list-disc list-inside space-y-0.5 text-slate-500">
                      <li>Списание происходит только за выполненные запросы.</li>
                      <li>При нулевом балансе запросы автоматически приостанавливаются — задолженность не образуется.</li>
                      <li>Ключ можно отозвать в любой момент.</li>
                    </ul>
                  </div>
                </div>
              )}

              {/* Tab 2: Методы API */}
              {apiModalTab === "methods" && (
                <div className="space-y-3.5 text-xs text-slate-700">
                  <div className="bg-slate-900 text-slate-100 p-3 rounded-xl font-mono text-[11px] space-y-1">
                    <div className="flex items-center justify-between gap-2 pb-1">
                      <span className="text-slate-400"># Базовый адрес API и авторизация:</span>
                      <button
                        type="button"
                        onClick={() => copyApiText(baseHeaderSnippet, "base_header")}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-slate-200 font-sans text-[11px] font-semibold transition-colors cursor-pointer shrink-0"
                      >
                        {apiCopiedField === "base_header" ? <Check size={11} className="text-emerald-300" /> : <Copy size={11} />}
                        <span>{apiCopiedField === "base_header" ? "Скопировано" : "Скопировать"}</span>
                      </button>
                    </div>
                    <div><span className="text-emerald-300">BASE_URL:</span> https://tenderlex.ru/api/v1/mcp</div>
                    <div className="break-all"><span className="text-emerald-300">HEADER:</span> Authorization: Bearer {effectiveKeyPlaceholder}</div>
                  </div>

                  <div className="space-y-2">
                    <div className="border border-slate-200 rounded-xl p-3 space-y-1.5 bg-white">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className="font-mono font-bold text-[#103a31] bg-[#f4f8ef] px-2 py-0.5 rounded border border-[#cde0be] text-[11px]">
                          POST /suppliers/search
                        </span>
                        <span className="text-slate-500 text-[11px] font-semibold">Поиск поставщиков</span>
                      </div>
                      <p className="text-slate-600 text-[11px]">
                        Поиск проверенных поставщиков и заводов по тексту ТЗ или номеру закупки. Возвращает ИНН, сайт, телефон, email, статус производителя.
                      </p>
                    </div>

                    <div className="border border-slate-200 rounded-xl p-3 space-y-1.5 bg-white">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className="font-mono font-bold text-[#103a31] bg-[#f4f8ef] px-2 py-0.5 rounded border border-[#cde0be] text-[11px]">
                          POST /products/exact-analogs
                        </span>
                        <span className="text-slate-500 text-[11px] font-semibold">Подбор товара и аналогов</span>
                      </div>
                      <p className="text-slate-600 text-[11px]">
                        Определение скрытой модели, эквивалентов по ГОСТ, реестр Минпромторга и прямая ссылка на скачивание отчёта в DOCX.
                      </p>
                    </div>

                    <div className="border border-slate-200 rounded-xl p-3 space-y-1.5 bg-white">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className="font-mono font-bold text-[#103a31] bg-[#f4f8ef] px-2 py-0.5 rounded border border-[#cde0be] text-[11px]">
                          POST /procurements/analyze
                        </span>
                        <span className="text-slate-500 text-[11px] font-semibold">Анализ документации и рисков</span>
                      </div>
                      <p className="text-slate-600 text-[11px]">
                        Выявление скрытых ловушек контракта, штрафов, неоднозначных требований и условий приёмки по 44-ФЗ и 223-ФЗ.
                      </p>
                    </div>

                    <div className="border border-slate-200 rounded-xl p-3 space-y-1.5 bg-white">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className="font-mono font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded border border-slate-200 text-[11px]">
                          GET /balance
                        </span>
                        <span className="text-slate-500 text-[11px] font-semibold">Проверка баланса</span>
                      </div>
                      <p className="text-slate-600 text-[11px]">
                        Проверка текущего рублёвого остатка и статуса авторизации.
                      </p>
                    </div>
                  </div>

                  <div className="rounded-xl border border-[#cde0be] bg-[#f4f8ef] p-3 space-y-1.5 text-slate-700">
                    <strong className="text-[#103a31]">Файлы, мониторинг цен и попозиционный выбор</strong>
                    <p><code>POST /jobs</code>: multipart/form-data, режим, текст или файлы и уникальный <code>Idempotency-Key</code>. Для геоприоритета передайте вместе город и радиус 10–5000 км.</p>
                    <p><code>GET /jobs/&#123;id&#125;</code> возвращает статус и список позиций. Передайте выбранные ID и ревизию в <code>POST /jobs/&#123;id&#125;/position-selection</code>. Результат: <code>GET /jobs/&#123;id&#125;/download</code>.</p>
                    <p>Ближайшие поставщики идут первыми; дальние и неизвестные адреса отмечаются отдельно. Подбор товара формирует отчёт Word.</p>
                    <p>При 429 дождитесь <code>Retry-After</code>. После таймаута сохраняйте ключ той же операции вместо нового платного запуска.</p>
                  </div>

                  {/* cURL snippet */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-800">Пример запроса (cURL):</span>
                      <button
                        type="button"
                        onClick={() => copyApiText(curlExampleText, "curl")}
                        className="inline-flex items-center gap-1 text-[11px] font-bold text-[#174b3f] hover:text-[#103a31] cursor-pointer"
                      >
                        {apiCopiedField === "curl" ? <Check size={12} /> : <Copy size={12} />}
                        <span>{apiCopiedField === "curl" ? "Скопировано!" : "Скопировать cURL"}</span>
                      </button>
                    </div>
                    <pre className="bg-slate-900 text-emerald-300 p-3 rounded-xl font-mono text-[10.5px] overflow-x-auto leading-relaxed">
                      {curlExampleText}
                    </pre>
                  </div>
                </div>
              )}

              {/* Tab 3: Для ИИ и быстрой разработки */}
              {apiModalTab === "ai_prompt" && (
                <div className="space-y-3">
                  <div className="bg-[#f8faf6] border border-[#dfe5dc] rounded-xl p-3 text-xs text-slate-700 leading-relaxed">
                    <strong className="text-slate-900">Инструкция для быстрой разработки и ИИ-ассистентов:</strong> скопируйте текст ниже и отправьте в Cursor, ChatGPT, Claude или вашему программисту. Агент сразу поймёт структуру API и корректно встроит TenderLex в вашу систему или CRM.
                  </div>

                  {!newlyGeneratedKey ? (
                    <div className="px-3 py-2 rounded-lg bg-amber-50/70 border border-amber-200/80 text-[11px] text-amber-950 flex flex-wrap items-center justify-between gap-2">
                      <span>
                        {apiKeys.length === 0
                          ? "В тексте ниже стоит заглушка <ВАШ_API_КЛЮЧ> — создайте ключ, чтобы он подставился автоматически."
                          : "Подставьте ваш сохранённый ключ вместо <ВАШ_API_КЛЮЧ> или создайте новый ключ."}
                      </span>
                      <button
                        type="button"
                        onClick={() => setApiModalTab("key")}
                        className="font-bold text-[#174b3f] hover:text-[#103a31] underline cursor-pointer shrink-0"
                      >
                        Перейти к ключам →
                      </button>
                    </div>
                  ) : null}

                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-800">Готовая задача для нейросети:</span>
                    <button
                      type="button"
                      onClick={() => copyApiText(aiPromptText, "ai_prompt")}
                      className="tl-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer"
                    >
                      {apiCopiedField === "ai_prompt" ? <Check size={13} /> : <Copy size={13} />}
                      <span>{apiCopiedField === "ai_prompt" ? "Скопировано в буфер!" : "Скопировать задачу для ИИ"}</span>
                    </button>
                  </div>

                  <div className="text-[11px] font-mono text-slate-700 bg-slate-50 border border-slate-200 rounded-xl p-3 leading-relaxed whitespace-pre-wrap select-all max-h-60 overflow-y-auto">
                    {aiPromptText}
                  </div>
                </div>
              )}

              {/* Tab 4: MCP (Claude / Cursor) */}
              {apiModalTab === "mcp" && (
                <div className="space-y-3">
                  <div className="bg-[#f4f8ef] border border-[#cde0be] rounded-xl p-3 text-xs text-slate-700 leading-relaxed space-y-2">
                    <div>
                      <strong className="text-[#103a31]">Прямое подключение к Claude Desktop и Cursor по протоколу MCP:</strong> позволяет ИИ-ассистенту напрямую искать поставщиков, подбирать аналоги и анализировать документацию TenderLex из чата.
                    </div>
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <a
                        href="/scripts/tenderlex_mcp.py"
                        download="tenderlex_mcp.py"
                        className="tl-btn-primary inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs cursor-pointer"
                      >
                        <Download size={13} />
                        <span>Скачать tenderlex_mcp.py</span>
                      </a>
                      <span className="text-[11px] text-slate-600">
                        (Автономный Python-скрипт, без сторонних библиотек)
                      </span>
                    </div>
                  </div>

                  {!newlyGeneratedKey ? (
                    <div className="px-3 py-2 rounded-lg bg-amber-50/70 border border-amber-200/80 text-[11px] text-amber-950 flex flex-wrap items-center justify-between gap-2">
                      <span>
                        {apiKeys.length === 0
                          ? "Для запуска MCP нужен API-ключ — создайте его, и он сразу подставится в JSON ниже."
                          : "Подставьте ваш сохранённый ключ вместо <ВАШ_API_КЛЮЧ> или создайте новый."}
                      </span>
                      <button
                        type="button"
                        onClick={() => setApiModalTab("key")}
                        className="font-bold text-[#174b3f] hover:text-[#103a31] underline cursor-pointer shrink-0"
                      >
                        Перейти к ключам →
                      </button>
                    </div>
                  ) : null}

                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-800">Конфиг для claude_desktop_config.json:</span>
                    <button
                      type="button"
                      onClick={() => copyApiText(mcpConfigText, "mcp_cfg")}
                      className="inline-flex items-center gap-1 text-xs font-bold text-[#174b3f] hover:text-[#103a31] cursor-pointer"
                    >
                      {apiCopiedField === "mcp_cfg" ? <Check size={13} /> : <Copy size={13} />}
                      <span>{apiCopiedField === "mcp_cfg" ? "Скопировано!" : "Скопировать JSON"}</span>
                    </button>
                  </div>

                  <pre className="bg-slate-900 text-emerald-300 p-3 rounded-xl font-mono text-[11px] overflow-x-auto leading-relaxed select-all">
                    {mcpConfigText}
                  </pre>

                  <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200/80 text-[11px] text-slate-600 space-y-1">
                    <div className="font-bold text-slate-700">Быстрый запуск за 2 шага:</div>
                    <div className="text-[11px] text-slate-600 space-y-0.5">
                      <div>1. Сохраните скачанный <code>tenderlex_mcp.py</code> в удобную папку.</div>
                      <div>2. В конфиге укажите полный путь к скрипту и добавьте блок в:</div>
                    </div>
                    <div className="font-mono text-[10px] text-slate-500 pt-0.5">
                      • Windows: %APPDATA%\Claude\claude_desktop_config.json<br />
                      • macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
                    </div>
                  </div>
                </div>
              )}

              {/* Footer */}
              <div className="flex justify-end pt-2 border-t border-slate-100 shrink-0">
                <button
                  type="button"
                  onClick={closeApiModal}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-colors cursor-pointer"
                >
                  Закрыть
                </button>
              </div>
            </section>
          </div>
        );
      })() : null}


      {/* Top-Up Balance Modal */}
      {showTopUpModal ? (() => {
        const depositPkgs = session?.deposit_packages?.length ? session.deposit_packages : DEFAULT_DEPOSIT_PACKAGES;
        const popularPkgId =
          depositPkgs.find((p) => p.price_rub === 5000)?.id ||
          depositPkgs.find((p) => p.badge && /хит|популяр/i.test(p.badge))?.id ||
          null;
        const baseTaskRates = [
          session?.balance?.effective_prices?.supplier_search?.price_rub ?? session?.function_prices?.supplier_search?.price_rub,
          session?.balance?.effective_prices?.exact_product?.price_rub ?? session?.function_prices?.exact_product?.price_rub,
          session?.balance?.effective_prices?.procurement_report?.price_rub ?? session?.function_prices?.procurement_report?.price_rub,
        ].filter((v): v is number => typeof v === "number" && v > 0);
        const minTaskRateRub = baseTaskRates.length > 0 ? Math.min(...baseTaskRates) : 99;
        const calc = (() => {
          if (selectedTopUpPackage && selectedTopUpPackage.price_rub === customTopUpRub) {
            return {
              bonusRub: selectedTopUpPackage.bonus_rub,
              totalRub: selectedTopUpPackage.total_rub,
              percent: selectedTopUpPackage.bonus_percent,
            };
          }
          return calculateDepositBonus(customTopUpRub);
        })();
        const approxTasks = Math.floor(calc.totalRub / minTaskRateRub);
        const phoneDigits = payerPhone.replace(/\D/g, "");
        const isPhoneValid = phoneDigits.length >= 10;
        const isAmountValid = customTopUpRub >= 500;
        const matchedPkg =
          selectedTopUpPackage && selectedTopUpPackage.price_rub === customTopUpRub
            ? selectedTopUpPackage
            : null;
        const pkgName = matchedPkg?.name || "Пополнение баланса";
        const tgMsg = encodeURIComponent(
          `Здравствуйте! Хочу пополнить баланс TenderLex на ${customTopUpRub.toLocaleString("ru-RU")} ₽ (пакет «${pkgName}», к зачислению с бонусом: ${calc.totalRub.toLocaleString("ru-RU")} ₽). Мой email в сервисе: ${session?.user?.email || ""}`
        );
        const tgUrl = `${session?.contacts?.telegram_url || "https://t.me/lexelence"}?text=${tgMsg}`;

        const cardValidationHint = !isAmountValid
          ? "Минимальная сумма пополнения — 500 ₽"
          : !isPhoneValid
          ? "Укажите номер телефона (10 цифр) для чека и связи"
          : "";

        const b2bMissingFields: string[] = [];
        if (!isAmountValid) b2bMissingFields.push("сумму от 500 ₽");
        if (!invoiceInn.trim()) b2bMissingFields.push("ИНН");
        if (!invoiceName.trim()) b2bMissingFields.push("наименование компании");
        if (!isPhoneValid) b2bMissingFields.push("телефон");
        const b2bValidationHint = b2bMissingFields.length > 0 ? `Заполните: ${b2bMissingFields.join(", ")}` : "";

        const renderPackageRows = () => (
          <div className="space-y-1.5 tl-num">
            {depositPkgs.map((pkg) => {
              const isSelected = (selectedTopUpPackage?.id === pkg.id) || (!selectedTopUpPackage && customTopUpRub === pkg.price_rub);
              const isPopular = pkg.id === popularPkgId;
              const effectiveTaskRub =
                pkg.total_rub > 0 ? Math.round(minTaskRateRub * (pkg.price_rub / pkg.total_rub)) : Math.round(minTaskRateRub);
              return (
                <button
                  key={pkg.id}
                  type="button"
                  onClick={() => {
                    setSelectedTopUpPackage(pkg);
                    setCustomTopUpRub(pkg.price_rub);
                  }}
                  className={`w-full px-3 py-2 rounded-xl border text-left transition-all cursor-pointer flex items-center justify-between gap-2.5 ${
                    isSelected
                      ? "bg-[#f4f8ef] border-[#174b3f] ring-1 ring-[#174b3f]/25"
                      : "bg-white border-slate-200 hover:bg-slate-50 hover:border-[#b7c9af]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span
                      className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${
                        isSelected ? "border-[#174b3f]" : "border-slate-300"
                      }`}
                    >
                      {isSelected ? <span className="w-2 h-2 rounded-full bg-[#174b3f]" /> : null}
                    </span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-xs font-extrabold text-slate-900">{pkg.name}</span>
                        {isPopular ? (
                          <span className="px-1.5 py-0.5 rounded bg-[#174b3f] text-white font-bold text-[10px] leading-none">
                            Хит
                          </span>
                        ) : null}
                        {pkg.bonus_rub > 0 ? (
                          <span className="text-[10px] text-slate-500 whitespace-nowrap">
                            ~{effectiveTaskRub} ₽/задача
                          </span>
                        ) : null}
                      </div>
                      <div className="text-[11px] text-slate-500 mt-0.5">
                        На баланс:{" "}
                        <strong className="text-[#174b3f] font-bold">
                          {pkg.total_rub.toLocaleString("ru-RU")} ₽
                        </strong>
                      </div>
                    </div>
                  </div>
                  <div className="text-right shrink-0 flex flex-col items-end gap-0.5">
                    <span className="text-xs sm:text-sm font-black text-slate-900 whitespace-nowrap">
                      {pkg.price_rub.toLocaleString("ru-RU")} ₽
                    </span>
                    {pkg.bonus_rub > 0 ? (
                      <span className="px-1.5 py-0.5 rounded bg-[#e7efe0] text-[#103a31] text-[10px] font-bold whitespace-nowrap">
                        +{pkg.bonus_rub.toLocaleString("ru-RU")} ₽
                      </span>
                    ) : (
                      <span className="text-[10px] text-slate-400">без бонуса</span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        );

        return (
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4 z-50 overflow-y-auto"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) setShowTopUpModal(false);
            }}
          >
            <section
              className="bg-white rounded-2xl p-4 sm:p-6 max-w-4xl w-full shadow-2xl border border-slate-200 space-y-3.5 flex flex-col font-sans my-auto max-h-[94vh] overflow-y-auto"
              role="dialog"
              aria-modal="true"
              aria-labelledby="topup-modal-title"
            >
              {/* Modal Header */}
              <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3 shrink-0">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-[#f4f8ef] border border-[#cde0be] text-[#174b3f] shrink-0">
                    <Wallet size={20} aria-hidden="true" />
                  </div>
                  <div>
                    <h2 id="topup-modal-title" className="text-base sm:text-lg font-extrabold text-slate-900 leading-tight">
                      Пополнение баланса
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Единый бессрочный баланс на все инструменты TenderLex. Чем больше сумма — тем выше бонус.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors shrink-0 cursor-pointer"
                  onClick={() => setShowTopUpModal(false)}
                  aria-label="Закрыть окно"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Payment Method Switcher Tabs + Compact Guarantee */}
              <div className="flex flex-col sm:flex-row sm:items-center gap-2.5 shrink-0">
                <div className="flex items-center gap-1 p-1 bg-[#f8faf6] rounded-xl border border-[#dfe5dc] text-xs font-semibold sm:min-w-[360px]">
                  <button
                    type="button"
                    onClick={() => setTopUpTab("card")}
                    className={`flex-1 py-2 px-3 rounded-lg text-center transition-all flex items-center justify-center gap-1.5 cursor-pointer whitespace-nowrap ${
                      topUpTab === "card"
                        ? "bg-white text-[#103a31] font-bold shadow-2xs border border-[#cde0be]"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    <CreditCard size={14} className={topUpTab === "card" ? "text-[#174b3f]" : "text-slate-400"} aria-hidden="true" />
                    <span>Оплата онлайн (Карта, СБП)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setTopUpTab("b2b")}
                    className={`flex-1 py-2 px-3 rounded-lg text-center transition-all flex items-center justify-center gap-1.5 cursor-pointer whitespace-nowrap ${
                      topUpTab === "b2b"
                        ? "bg-white text-[#103a31] font-bold shadow-2xs border border-[#cde0be]"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    <Building2 size={14} className={topUpTab === "b2b" ? "text-[#174b3f]" : "text-slate-400"} aria-hidden="true" />
                    <span>Счёт для юрлиц</span>
                  </button>
                </div>

                <div className="flex items-center gap-2 px-3 py-2 bg-[#f4f8ef] border border-[#cde0be] rounded-xl text-[11px] text-[#103a31] font-medium flex-1">
                  <CheckCircle2 size={14} className="text-[#174b3f] shrink-0" aria-hidden="true" />
                  <span>
                    <strong>Гарантия:</strong> списание только по готовому результату, средства не сгорают.
                  </span>
                </div>
              </div>

              {/* TAB 1: Online Payment (2-Column Above-the-Fold Desktop Layout) */}
              {topUpTab === "card" ? (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
                  {/* Left column: 5-row Package Selector + Custom Amount */}
                  <div className="lg:col-span-7 space-y-2.5">
                    <div className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                      Выберите пакет с бонусом:
                    </div>
                    {renderPackageRows()}

                    <div className="pt-1 space-y-1">
                      <label htmlFor="custom-topup-input" className="text-[11px] font-semibold text-slate-600 block">
                        Или введите другую сумму (от 500 ₽):
                      </label>
                      <div className="relative">
                        <input
                          id="custom-topup-input"
                          type="number"
                          min={500}
                          step={500}
                          value={customTopUpRub || ""}
                          onChange={(e) => {
                            const val = parseInt(e.target.value, 10) || 0;
                            setCustomTopUpRub(val);
                            const match = depositPkgs.find((p) => p.price_rub === val) || null;
                            setSelectedTopUpPackage(match);
                          }}
                          placeholder="5000"
                          className="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f] pr-8 tl-num"
                        />
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-400">
                          ₽
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Right column: Summary + Payment Methods + Contacts + Primary CTA */}
                  <div className="lg:col-span-5 space-y-3">
                    {/* Calculation Summary */}
                    <div className="p-3.5 rounded-xl bg-[#f4f8ef] border border-[#cde0be] space-y-1.5 tl-num">
                      <div className="flex items-center justify-between text-xs font-semibold text-slate-600">
                        <span>Сумма к оплате:</span>
                        <strong className="text-slate-900 font-bold">{customTopUpRub.toLocaleString("ru-RU")} ₽</strong>
                      </div>
                      {calc.bonusRub > 0 ? (
                        <div className="flex items-center justify-between text-xs font-semibold text-[#174b3f]">
                          <span>Бонус сервиса ({calc.percent}%):</span>
                          <strong className="font-extrabold">+{calc.bonusRub.toLocaleString("ru-RU")} ₽</strong>
                        </div>
                      ) : null}
                      <div className="pt-2 border-t border-[#cde0be] flex items-center justify-between">
                        <div>
                          <span className="text-xs font-bold text-slate-900 block">Поступит на баланс:</span>
                          <span className="text-[10px] text-slate-500">
                            {`хватит примерно на ${approxTasks} задач`}
                          </span>
                        </div>
                        <div className="text-lg sm:text-xl font-black text-[#103a31]">
                          {calc.totalRub.toLocaleString("ru-RU")} ₽
                        </div>
                      </div>
                    </div>

                    {/* Compact Online Payment Methods */}
                    <div className="p-2.5 bg-[#f8faf6] border border-[#dfe5dc] rounded-xl space-y-1.5">
                      <div className="text-[10px] font-bold text-slate-600 uppercase tracking-wider flex items-center justify-between">
                        <span>ЮKassa</span>
                        <span className="text-[#174b3f] font-semibold flex items-center gap-1 normal-case">
                          <CheckCircle2 size={11} aria-hidden="true" /> Без комиссии
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-700">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-white border border-slate-200 font-medium">
                          <CreditCard size={12} className="text-[#174b3f]" aria-hidden="true" /> МИР, Visa, MC
                        </span>
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-white border border-slate-200 font-medium">
                          <QrCode size={12} className="text-[#174b3f]" aria-hidden="true" /> СБП (QR)
                        </span>
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-white border border-slate-200 font-medium">
                          SberPay / Mir Pay
                        </span>
                      </div>
                    </div>

                    {/* Contacts */}
                    <div className="p-3 bg-slate-50 border border-slate-200/90 rounded-xl space-y-2">
                      <div className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">
                        Контакты для чека и поддержки
                      </div>
                      <div className="space-y-1">
                        <label htmlFor="topup-phone-input" className="text-xs font-bold text-slate-700 block">
                          Телефон <span className="text-rose-500">*</span>
                        </label>
                        <div className="relative">
                          <input
                            id="topup-phone-input"
                            type="tel"
                            value={payerPhone}
                            onChange={(e) => setPayerPhone(formatPhoneRu(e.target.value))}
                            placeholder="+7 (999) 000-00-00"
                            className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f] pl-8"
                          />
                          <Phone size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                        </div>
                      </div>
                      <div className="space-y-1">
                        <label htmlFor="topup-tg-input" className="text-xs font-semibold text-slate-700 flex items-center justify-between">
                          <span>Ник в Telegram</span>
                          <span className="text-[10px] font-normal text-slate-400">опционально</span>
                        </label>
                        <div className="relative">
                          <input
                            id="topup-tg-input"
                            type="text"
                            value={payerTelegram}
                            onChange={(e) => {
                              let val = e.target.value.trim();
                              if (val.startsWith("https://t.me/")) val = val.replace("https://t.me/", "");
                              if (val.startsWith("t.me/")) val = val.replace("t.me/", "");
                              if (val && !val.startsWith("@")) val = "@" + val;
                              setPayerTelegram(val);
                            }}
                            placeholder="@username"
                            className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f] pl-8"
                          />
                          <MessageCircle size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                        </div>
                      </div>
                    </div>

                    {onlinePayError ? (
                      <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 space-y-1">
                        <div className="font-bold flex items-center gap-1.5">
                          <AlertTriangle size={14} className="text-rose-600 shrink-0" />
                          <span>{onlinePayError}</span>
                        </div>
                        <p className="text-[11px] text-rose-700">
                          Если онлайн-оплата временно недоступна, можно пополнить баланс через менеджера в Telegram.
                        </p>
                      </div>
                    ) : null}

                    {/* Primary CTA + Explicit Validation Hint */}
                    <div className="space-y-1.5">
                      <button
                        type="button"
                        disabled={isPayingOnline || !isAmountValid || !isPhoneValid}
                        onClick={handleStartOnlinePayment}
                        className="tl-btn-primary w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm shadow-sm cursor-pointer tl-num"
                      >
                        {isPayingOnline ? (
                          <>
                            <Loader2 size={16} className="animate-spin" />
                            <span>Переход в ЮKassa...</span>
                          </>
                        ) : (
                          <>
                            <CreditCard size={15} aria-hidden="true" />
                            <span>Оплатить {customTopUpRub.toLocaleString("ru-RU")} ₽ (Карта, СБП)</span>
                          </>
                        )}
                      </button>

                      {cardValidationHint ? (
                        <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200/80 rounded-lg px-2.5 py-1.5 text-center font-medium">
                          {cardValidationHint}
                        </p>
                      ) : null}

                      <div className="flex items-center justify-between gap-2 pt-0.5 text-[11px] text-slate-500">
                        <span className="flex items-center gap-1">
                          <CheckCircle2 size={12} className="text-[#174b3f]" aria-hidden="true" />
                          Моментальное зачисление
                        </span>
                        <a
                          href={tgUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-slate-600 hover:text-slate-900 underline font-medium"
                        >
                          Через Telegram
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}

              {/* TAB 2: Interactive B2B Invoice Generator */}
              {topUpTab === "b2b" ? (
                <div className="space-y-3.5">
                  {!invoiceCreated ? (
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
                      {/* Left Column: Step 1 Package & Amount */}
                      <div className="lg:col-span-5 space-y-2.5">
                        <div className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                          1. Выберите пакет или сумму:
                        </div>
                        {renderPackageRows()}

                        <div className="pt-1 space-y-1">
                          <label htmlFor="b2b-custom-amount" className="text-[11px] font-semibold text-slate-600 block">
                            Или укажите произвольную сумму:
                          </label>
                          <div className="relative">
                            <input
                              id="b2b-custom-amount"
                              type="number"
                              min={500}
                              step={500}
                              value={customTopUpRub || ""}
                              onChange={(e) => {
                                const val = parseInt(e.target.value, 10) || 0;
                                setCustomTopUpRub(val);
                                const match = depositPkgs.find((p) => p.price_rub === val) || null;
                                setSelectedTopUpPackage(match);
                              }}
                              placeholder="5000"
                              className="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f] pr-8 tl-num"
                            />
                            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-400">
                              ₽
                            </span>
                          </div>
                        </div>

                        <div className="p-3 rounded-xl bg-[#f4f8ef] border border-[#cde0be] flex items-center justify-between gap-2 text-xs tl-num">
                          <div>
                            <span className="text-[11px] text-slate-600 block">К оплате по счёту:</span>
                            <strong className="text-slate-900 font-extrabold text-sm">{customTopUpRub.toLocaleString("ru-RU")} ₽</strong>
                            {calc.bonusRub > 0 ? (
                              <span className="block text-[10px] text-[#174b3f] font-bold">
                                +{calc.bonusRub.toLocaleString("ru-RU")} ₽ бонус ({calc.percent}%)
                              </span>
                            ) : null}
                          </div>
                          <div className="text-right">
                            <span className="text-[10px] text-slate-500 block">На баланс:</span>
                            <strong className="text-[#103a31] font-black text-base">{calc.totalRub.toLocaleString("ru-RU")} ₽</strong>
                          </div>
                        </div>
                      </div>

                      {/* Right Column: Step 2 Company Requisites */}
                      <div className="lg:col-span-7 space-y-2.5 bg-[#f8faf6] p-3.5 sm:p-4 rounded-xl border border-[#dfe5dc]">
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-[11px] font-bold text-slate-700 uppercase tracking-wider">
                            2. Реквизиты вашей компании / ИП:
                          </div>
                          {invoiceInnFound ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-bold text-[#103a31] bg-[#e7efe0] px-2 py-0.5 rounded-full">
                              <Check size={12} />
                              <span>Найдено в ФНС</span>
                            </span>
                          ) : null}
                        </div>

                        {/* INN Input with DaData auto-lookup */}
                        <div className="space-y-1">
                          <label htmlFor="b2b-inn-input" className="text-xs font-bold text-slate-700 block">
                            ИНН организации или ИП <span className="text-rose-500">*</span>
                          </label>
                          <div className="relative">
                            <input
                              id="b2b-inn-input"
                              type="text"
                              maxLength={12}
                              value={invoiceInn}
                              onChange={(e) => {
                                const val = e.target.value.replace(/\D/g, "");
                                setInvoiceInn(val);
                                setInvoiceInnFound(false);
                                setInvoiceInnError("");
                                if (val.length === 10 || val.length === 12) {
                                  const handleLookup = async () => {
                                    setInvoiceLoadingInn(true);
                                    try {
                                      const res = await fetch(`/api/customer/dadata/company-by-inn?inn=${val}`);
                                      const data = await res.json();
                                      if (data.found && data.company) {
                                        setInvoiceName(data.company.company_name || data.company.full_name || "");
                                        setInvoiceKpp(data.company.kpp || "");
                                        setInvoiceAddress(data.company.legal_address || "");
                                        setInvoiceInnFound(true);
                                      } else {
                                        setInvoiceInnError(data.message || "Организация не найдена в ФНС");
                                      }
                                    } catch (err) {
                                      // Ignored
                                    } finally {
                                      setInvoiceLoadingInn(false);
                                    }
                                  };
                                  handleLookup();
                                }
                              }}
                              placeholder="Введите 10 цифр для юрлиц или 12 цифр для ИП"
                              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs font-mono font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f] pr-10"
                            />
                            {invoiceLoadingInn ? (
                              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[#174b3f]">
                                <Loader2 size={16} className="animate-spin" />
                              </span>
                            ) : (
                              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
                                <Building2 size={16} />
                              </span>
                            )}
                          </div>
                          {invoiceInnError ? (
                            <p className="text-[11px] text-amber-700">{invoiceInnError}</p>
                          ) : (
                            <p className="text-[10px] text-slate-500">
                              Введите ИНН — название, КПП и адрес подтянутся автоматически из ФНС.
                            </p>
                          )}
                        </div>

                        {/* Company Name */}
                        <div className="space-y-1">
                          <label htmlFor="b2b-company-name" className="text-xs font-bold text-slate-700 block">
                            Наименование организации или ИП <span className="text-rose-500">*</span>
                          </label>
                          <input
                            id="b2b-company-name"
                            type="text"
                            value={invoiceName}
                            onChange={(e) => setInvoiceName(e.target.value)}
                            placeholder="Подставится по ИНН автоматически или введите вручную"
                            className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f]"
                          />
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                          <div className="space-y-1">
                            <label htmlFor="b2b-kpp-input" className="text-xs font-bold text-slate-700 block">
                              КПП <span className="text-[10px] font-normal text-slate-400">(для юрлиц)</span>
                            </label>
                            <input
                              id="b2b-kpp-input"
                              type="text"
                              maxLength={9}
                              value={invoiceKpp}
                              onChange={(e) => setInvoiceKpp(e.target.value)}
                              placeholder="770101001"
                              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f]"
                            />
                          </div>

                          <div className="space-y-1 sm:col-span-2">
                            <label htmlFor="b2b-address-input" className="text-xs font-bold text-slate-700 block">
                              Юридический адрес
                            </label>
                            <input
                              id="b2b-address-input"
                              type="text"
                              value={invoiceAddress}
                              onChange={(e) => setInvoiceAddress(e.target.value)}
                              placeholder="Юридический адрес организации"
                              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f]"
                            />
                          </div>
                        </div>

                        <div className="space-y-1">
                          <label htmlFor="b2b-email-input" className="text-xs font-bold text-slate-700 block">
                            Email для получения счёта и закрывающих документов
                          </label>
                          <input
                            id="b2b-email-input"
                            type="email"
                            value={invoiceEmail || session?.user?.email || ""}
                            onChange={(e) => setInvoiceEmail(e.target.value)}
                            placeholder="buh@company.ru"
                            className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f]"
                          />
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          <div className="space-y-1">
                            <label htmlFor="b2b-phone-input" className="text-xs font-bold text-slate-700 block">
                              Контактный телефон <span className="text-rose-500">*</span>
                            </label>
                            <div className="relative">
                              <input
                                id="b2b-phone-input"
                                type="tel"
                                value={payerPhone}
                                onChange={(e) => setPayerPhone(formatPhoneRu(e.target.value))}
                                placeholder="+7 (999) 000-00-00"
                                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f] pl-8"
                              />
                              <Phone size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                            </div>
                          </div>

                          <div className="space-y-1">
                            <label htmlFor="b2b-tg-input" className="text-xs font-semibold text-slate-700 flex items-center justify-between">
                              <span>Ник в Telegram</span>
                              <span className="text-[10px] font-normal text-slate-400">опционально</span>
                            </label>
                            <div className="relative">
                              <input
                                id="b2b-tg-input"
                                type="text"
                                value={payerTelegram}
                                onChange={(e) => {
                                  let val = e.target.value.trim();
                                  if (val.startsWith("https://t.me/")) val = val.replace("https://t.me/", "");
                                  if (val.startsWith("t.me/")) val = val.replace("t.me/", "");
                                  if (val && !val.startsWith("@")) val = "@" + val;
                                  setPayerTelegram(val);
                                }}
                                placeholder="@username"
                                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#174b3f]/25 focus:border-[#174b3f] pl-8"
                              />
                              <MessageCircle size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                            </div>
                          </div>
                        </div>

                        {invoiceSubmitError ? (
                          <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700">
                            {invoiceSubmitError}
                          </div>
                        ) : null}

                        {/* Submit Button + Inline Missing-Fields Hint */}
                        <div className="space-y-1.5 pt-1">
                          <button
                            type="button"
                            disabled={invoiceSubmitting || !isAmountValid || !invoiceInn.trim() || !invoiceName.trim() || !isPhoneValid}
                            onClick={async () => {
                              if (!customTopUpRub || customTopUpRub < 500) {
                                setInvoiceSubmitError("Минимальная сумма счёта — 500 ₽");
                                return;
                              }
                              if (!invoiceInn.trim()) {
                                setInvoiceSubmitError("Укажите ИНН организации или ИП");
                                return;
                              }
                              if (!invoiceName.trim()) {
                                setInvoiceSubmitError("Укажите наименование компании или ИП");
                                return;
                              }
                              if (!payerPhone.trim() || payerPhone.replace(/\D/g, "").length < 10) {
                                setInvoiceSubmitError("Укажите контактный номер телефона для связи");
                                return;
                              }
                              setInvoiceSubmitting(true);
                              setInvoiceSubmitError("");
                              try {
                                const emailToSend = (invoiceEmail.trim() || session?.user?.email || "").trim();
                                const res = await fetch("/api/customer/invoices", {
                                  method: "POST",
                                  credentials: "same-origin",
                                  headers: {
                                    "Content-Type": "application/json",
                                    ...(csrf ? { "x-csrf-token": csrf } : {}),
                                  },
                                  body: JSON.stringify({
                                    amount_rub: customTopUpRub,
                                    tariff_name: pkgName,
                                    buyer_inn: invoiceInn.replace(/\D/g, "").trim(),
                                    buyer_kpp: invoiceKpp.trim(),
                                    buyer_name: invoiceName.trim(),
                                    buyer_address: invoiceAddress.trim(),
                                    buyer_email: emailToSend,
                                    buyer_phone: payerPhone.trim(),
                                    buyer_telegram: payerTelegram.trim().replace(/^@/, ""),
                                  }),
                                });
                                const data = await res.json();
                                if (!res.ok) {
                                  throw new Error(data.detail || "Не удалось выставить счёт");
                                }
                                setInvoiceCreated(data.invoice);
                                loadCustomerInvoices();
                              } catch (err: any) {
                                setInvoiceSubmitError(err.message || "Ошибка при создании счёта");
                              } finally {
                                setInvoiceSubmitting(false);
                              }
                            }}
                            className="tl-btn-primary w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs sm:text-sm shadow-sm cursor-pointer tl-num"
                          >
                            {invoiceSubmitting ? (
                              <>
                                <Loader2 size={16} className="animate-spin" />
                                <span>Формируем счёт...</span>
                              </>
                            ) : (
                              <>
                                <Receipt size={15} aria-hidden="true" />
                                <span>Сформировать счёт на {customTopUpRub.toLocaleString("ru-RU")} ₽</span>
                              </>
                            )}
                          </button>
                          {b2bValidationHint ? (
                            <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200/80 rounded-lg px-2.5 py-1.5 text-center font-medium">
                              {b2bValidationHint}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  ) : (
                    /* Screen 2: Invoice Successfully Created */
                    <div className="space-y-4 max-w-2xl mx-auto">
                      <div className="p-4 rounded-2xl bg-[#f4f8ef] border border-[#9ec089] space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="inline-flex items-center gap-1.5 text-xs font-extrabold text-[#103a31] bg-[#e7efe0] px-2.5 py-1 rounded-full">
                            <CheckCircle2 size={14} className="text-[#174b3f]" />
                            <span>Счёт сформирован</span>
                          </div>
                          <span className="text-xs font-mono font-bold text-slate-500">
                            {invoiceCreated.created_at ? new Date(invoiceCreated.created_at).toLocaleDateString("ru-RU") : "Сегодня"}
                          </span>
                        </div>

                        <div>
                          <h3 className="text-base sm:text-lg font-black text-slate-900 tl-num">
                            Счёт № {invoiceCreated.invoice_number}
                          </h3>
                          <p className="text-xs text-slate-600 mt-0.5">
                            Плательщик: <b>{invoiceCreated.buyer_name}</b> (ИНН {invoiceCreated.buyer_inn})
                          </p>
                        </div>

                        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[#cde0be] text-xs tl-num">
                          <div>
                            <span className="text-[10px] text-slate-500 block uppercase font-semibold">Сумма к оплате:</span>
                            <strong className="text-base font-black text-slate-900">
                              {invoiceCreated.amount_rub.toLocaleString("ru-RU")} ₽
                            </strong>
                          </div>
                          <div className="text-right">
                            <span className="text-[10px] text-[#174b3f] block uppercase font-semibold">На баланс:</span>
                            <strong className="text-base font-black text-[#103a31]">
                              {invoiceCreated.total_credit_rub.toLocaleString("ru-RU")} ₽
                            </strong>
                            {invoiceCreated.bonus_rub > 0 ? (
                              <span className="text-[10px] text-[#174b3f] block">
                                (+{invoiceCreated.bonus_rub.toLocaleString("ru-RU")} ₽ бонус)
                              </span>
                            ) : null}
                          </div>
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="space-y-2">
                        <div className="text-[11px] font-bold text-slate-700 uppercase tracking-wider">
                          Действия со счётом:
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          <a
                            href={`/api/customer/invoices/${invoiceCreated.id}/download?format=pdf`}
                            download
                            className="tl-btn-primary flex items-center justify-center gap-2 p-2.5 rounded-xl text-xs transition-all cursor-pointer text-center"
                          >
                            <Download size={15} className="shrink-0" />
                            <span>Скачать PDF (.pdf)</span>
                          </a>

                          <label className="flex items-center justify-center gap-2 p-2.5 bg-[#f4f8ef] hover:bg-[#e7efe0] text-[#103a31] border border-[#cde0be] rounded-xl text-xs font-bold transition-all cursor-pointer text-center">
                            <Upload size={15} className="shrink-0" />
                            <span>{invoiceProofUploading === invoiceCreated.id ? "Отправка…" : "Отправить платёжку"}</span>
                            <input
                              type="file"
                              className="hidden"
                              accept="application/pdf,image/jpeg,image/png"
                              disabled={invoiceProofUploading === invoiceCreated.id}
                              onChange={(event) => {
                                const file = event.currentTarget.files?.[0];
                                if (file && file.size <= 10 * 1024 * 1024) {
                                  uploadInvoiceProof(invoiceCreated.id, file);
                                } else if (file) {
                                  setInvoiceProofMessage("Файл должен быть не больше 10 МБ");
                                }
                                event.currentTarget.value = "";
                              }}
                            />
                          </label>

                          <a
                            href={`/api/customer/invoices/${invoiceCreated.id}/download?format=xlsx`}
                            download
                            className="flex items-center justify-center gap-2 p-2.5 bg-white hover:bg-slate-50 border border-slate-300 rounded-xl text-xs font-bold text-slate-900 transition-all shadow-2xs cursor-pointer text-center"
                          >
                            <FileSpreadsheet size={15} className="text-[#174b3f] shrink-0" />
                            <span>Скачать Excel (.xlsx)</span>
                          </a>

                          <a
                            href={`/api/customer/invoices/${invoiceCreated.id}/html`}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center justify-center gap-2 p-2.5 bg-white hover:bg-slate-50 border border-slate-300 rounded-xl text-xs font-bold text-slate-900 transition-all shadow-2xs cursor-pointer text-center"
                          >
                            <Printer size={15} className="text-slate-600 shrink-0" />
                            <span>Печать и просмотр (А4)</span>
                          </a>

                          <button
                            type="button"
                            disabled={invoiceEmailSending}
                            onClick={async () => {
                              setInvoiceEmailSending(true);
                              setInvoiceEmailError("");
                              try {
                                const res = await fetch(`/api/customer/invoices/${invoiceCreated.id}/send-email`, {
                                  method: "POST",
                                  credentials: "same-origin",
                                  headers: {
                                    "Content-Type": "application/json",
                                    ...(csrf ? { "x-csrf-token": csrf } : {}),
                                  },
                                  body: JSON.stringify({ email: invoiceCreated.buyer_email || session?.user?.email }),
                                });
                                const data = await res.json();
                                if (!res.ok) throw new Error(data.detail || "Ошибка отправки");
                                setInvoiceEmailSent(true);
                                setTimeout(() => setInvoiceEmailSent(false), 4000);
                              } catch (err: any) {
                                setInvoiceEmailError(err?.message || "Не удалось отправить счёт на почту");
                              } finally {
                                setInvoiceEmailSending(false);
                              }
                            }}
                            className={`flex items-center justify-center gap-2 p-2.5 border rounded-xl text-xs font-bold transition-all shadow-2xs cursor-pointer text-center ${
                              invoiceEmailSent
                                ? "bg-[#f4f8ef] text-[#103a31] border-[#9ec089]"
                                : "bg-white hover:bg-slate-50 text-slate-900 border-slate-300"
                            }`}
                          >
                            {invoiceEmailSending ? (
                              <Loader2 size={15} className="animate-spin text-[#174b3f]" />
                            ) : invoiceEmailSent ? (
                              <Check size={15} className="text-[#174b3f]" />
                            ) : (
                              <Mail size={15} className="text-[#174b3f]" />
                            )}
                            <span>{invoiceEmailSent ? "Отправлено на почту!" : "Отправить на email"}</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              const detailsText = `Получатель: ИП Груздев Игорь Вячеславович\nИНН: 352516048881\nР/с: 40802810217430000342\nБанк: АО "АЛЬФА-БАНК"\nБИК: 044525593\nК/с: 30101810200000000593\nСумма: ${invoiceCreated.amount_rub} руб.\nНазначение: Оплата по счету № ${invoiceCreated.invoice_number} за услуги сервиса TenderLex. Без НДС.`;
                              navigator.clipboard.writeText(detailsText);
                              setInvoiceDetailsCopied(true);
                              setTimeout(() => setInvoiceDetailsCopied(false), 2500);
                            }}
                            className="sm:col-span-2 flex items-center justify-center gap-2 p-2.5 bg-slate-50 hover:bg-slate-100 border border-slate-300 rounded-xl text-xs font-bold text-slate-800 transition-all cursor-pointer text-center"
                          >
                            {invoiceDetailsCopied ? (
                              <Check size={15} className="text-[#174b3f]" />
                            ) : (
                              <Copy size={15} className="text-slate-600" />
                            )}
                            <span>{invoiceDetailsCopied ? "Реквизиты скопированы!" : "Скопировать реквизиты для банк-клиента / 1С"}</span>
                          </button>
                        </div>
                        {invoiceEmailError ? (
                          <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-xs font-semibold text-rose-800">
                            {invoiceEmailError}
                          </div>
                        ) : null}
                        {invoiceProofMessage ? (
                          <div className={`p-2.5 rounded-xl border text-xs font-semibold ${invoiceProofMessage.includes("отправлена") ? "bg-[#f4f8ef] border-[#cde0be] text-[#103a31]" : "bg-rose-50 border-rose-200 text-rose-800"}`}>
                            {invoiceProofMessage}
                          </div>
                        ) : null}
                      </div>

                      <div className="pt-1 text-center">
                        <button
                          type="button"
                          onClick={() => {
                            setInvoiceCreated(null);
                            setInvoiceInnFound(false);
                            setInvoiceEmailError("");
                          }}
                          className="text-xs text-slate-500 hover:text-slate-800 underline cursor-pointer"
                        >
                          Сформировать другой счёт
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Clean B2B Footer: Back to online payment + Link to centralized Invoices tab */}
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-2.5 border-t border-slate-100">
                    <button
                      type="button"
                      onClick={() => {
                        setTopUpTab("card");
                        setInvoiceCreated(null);
                        setInvoiceEmailError("");
                      }}
                      className="text-xs text-[#174b3f] hover:text-[#103a31] font-semibold underline cursor-pointer"
                    >
                      ← Вернуться к оплате онлайн (Карта, СБП)
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setShowTopUpModal(false);
                        setHistoryModalTab("invoices");
                        setShowHistoryModal(true);
                        loadCustomerInvoices();
                      }}
                      className="inline-flex items-center gap-1.5 text-xs font-bold text-[#174b3f] hover:text-[#103a31] bg-[#f4f8ef] hover:bg-[#e7efe0] border border-[#cde0be] px-3 py-1.5 rounded-lg transition-colors cursor-pointer tl-num"
                    >
                      <Receipt size={13} aria-hidden="true" />
                      <span>
                        {customerInvoices.length > 0
                          ? `Выставленные счета (${customerInvoices.length}) →`
                          : "Счета для юрлиц в истории →"}
                      </span>
                    </button>
                  </div>
                </div>
              ) : null}
            </section>
          </div>
        );
      })() : null}
      </div>
    </main>
  );
}

const activeJobStatuses = new Set(["pending", "running", "awaiting_customer_confirmation"]);
const processingStages = ["Принято", "Анализ", "Поиск", "Готово"];

function JobStageSteps({ progress }: { progress: number }) {
  const boundedProgress = Math.max(0, Math.min(100, progress));
  const currentStep = Math.min(processingStages.length - 1, Math.floor((boundedProgress / 100) * processingStages.length));

  return (
    <div className="flex items-center gap-1 flex-wrap text-[10px] text-slate-500 mt-0.5" aria-label="Этапы обработки задачи">
      {processingStages.map((stage, index) => (
        <span
          key={stage}
          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
            index < currentStep
              ? "bg-teal-50 text-teal-800 border border-teal-200/70"
              : index === currentStep
              ? "bg-amber-100 text-amber-900 border border-amber-300"
              : "bg-slate-100 text-slate-400"
          }`}
        >
          {stage}
        </span>
      ))}
    </div>
  );
}
