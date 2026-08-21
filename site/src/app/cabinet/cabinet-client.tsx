"use client";

import Image from "next/image";
import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";
import {
  ArrowRight,
  Bell,
  BellOff,
  BellRing,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Copy,
  Download,
  Eye,
  FileText,
  Loader2,
  LogOut,
  Mail,
  MessageCircle,
  Paperclip,
  Pencil,
  Receipt,
  RotateCcw,
  Search,
  Sliders,
  Sparkles,
  Upload,
  User,
  X,
  XCircle,
  type LucideIcon,
} from "lucide-react";

type JobMode = "supplier_search" | "procurement_report" | "analysis_and_suppliers";
type Scenario = "supplier_search" | "procurement_report" | "analysis_and_suppliers";
type SupplierSearchPolicy = "normal" | "minprom_registry_only" | "minprom_registry_priority";

type BalanceCounter = {
  label: string;
  available: number | null;
  reserved: number;
  spent: number;
  granted: number;
  low: boolean;
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

type SessionPayload = {
  authenticated: boolean;
  csrf_token?: string;
  user?: {
    email: string;
    name: string;
    is_trial: boolean;
    is_email_verified: boolean;
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
    effective_prices?: Record<string, { label: string; price_kopeks: number; price_rub: number; enabled: boolean; source: string }>;
  };
  limits?: {
    max_upload_mb: number;
    max_files_per_batch: number;
    default_supplier_target: number;
  };
  tariff_groups?: {
    supplier_search: Tariff[];
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
  verification_email_sent?: boolean;
  message?: string;
};

type CustomerJob = {
  id: string;
  mode: JobMode;
  mode_label: string;
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
  result_files: Array<{
    kind: string;
    label: string;
    filename: string;
  }>;
  awaiting_customer_confirmation: boolean;
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

const CUSTOMER_JOBS_PAGE_SIZE = 15;
const CUSTOMER_JOB_FETCH_OPTIONS: RequestInit = {
  credentials: "same-origin",
  cache: "no-store",
};
const NOTIFICATION_FEATURE_START_TS = new Date("2026-08-21T13:30:00Z").getTime();

const scenarioOptions: Array<{ id: Scenario; label: string; description: string; icon: LucideIcon }> = [
  {
    id: "supplier_search",
    label: "Поиск поставщиков",
    description: "техническое задание файлом, текстом или архивом",
    icon: Search,
  },
  {
    id: "procurement_report",
    label: "Анализ документации",
    description: "номер, ссылка или документы закупки",
    icon: FileText,
  },
  {
    id: "analysis_and_suppliers",
    label: "Анализ + поиск",
    description: "анализ закупки и поставщики",
    icon: Receipt,
  },
];

const modeCopy: Record<Scenario, {
  mode: JobMode;
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
  supplier_search: {
    mode: "supplier_search",
    formSubtitle: "Выберите тип работы и загрузите техническое задание (файл/архив) или вставьте текст.",
    uploadTitle: "Загрузить техническое задание",
    uploadText: "Перетащите файлы ТЗ сюда или нажмите для выбора (PDF, DOCX, XLSX, ZIP)",
    multipleFiles: true,
    textLabel: "Или вставьте техническое задание текстом",
    textPlaceholder: "Например: сотовый поликарбонат 10 мм, прозрачный, лист 2,1 x 6 м, количество 120 листов. Нужны поставщики с контактами для запроса коммерческого предложения.",
    hint: "Если одно техническое задание состоит из нескольких файлов, объедините их в архив и загрузите одним файлом. Разные технические задания загружайте отдельными файлами.",
    submit: "Запустить поиск поставщиков",
  },
  procurement_report: {
    mode: "procurement_report",
    formSubtitle: "Выберите тип работы и загрузите документацию закупки или укажите номер извещения / ссылку на закупку ЕИС.",
    uploadTitle: "Загрузить документацию закупки",
    uploadText: "Перетащите файлы документации закупки, проект контракта или архив (PDF, DOCX, XLSX, ZIP)",
    multipleFiles: true,
    sourceLabel: "Номер извещения ЕИС или ссылка на zakupki.gov.ru",
    sourcePlaceholder: "Например: 0173200001424000001 или ссылка на zakupki.gov.ru",
    hint: "Укажите номер извещения ЕИС или прямую ссылку на закупку на ЕИС (zakupki.gov.ru). Ссылки на внешние интернет-магазины и частные площадки не поддерживаются.",
    submit: "Запустить анализ документации",
  },
  analysis_and_suppliers: {
    mode: "analysis_and_suppliers",
    formSubtitle: "Выберите тип работы и загрузите документацию закупки или укажите номер извещения / ссылку на закупку ЕИС.",
    uploadTitle: "Загрузить документацию закупки",
    uploadText: "Перетащите файлы документации закупки, проект контракта или архив (PDF, DOCX, XLSX, ZIP)",
    multipleFiles: true,
    sourceLabel: "Номер извещения ЕИС или ссылка на zakupki.gov.ru",
    sourcePlaceholder: "Например: 0173200001424000001 или ссылка на zakupki.gov.ru",
    hint: "Укажите номер извещения ЕИС или ссылку на закупку на ЕИС (zakupki.gov.ru). Ссылки на сторонние сайты не поддерживаются. В результате вы получите анализ закупки и контакты поставщиков.",
    submit: "Запустить анализ + поиск",
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
    label: "Только реестр",
    description: "для закупок с запретом",
  },
  {
    id: "minprom_registry_priority",
    label: "Реестр в приоритете",
    description: "для закупок с ограничением",
  },
];

const statusClasses: Record<string, string> = {
  pending: "pending",
  running: "running",
  completed: "completed",
  partial: "completed",
  needs_review: "review",
  awaiting_customer_confirmation: "review",
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

function formatRubles(kopeks: number) {
  if (!kopeks) return "по запросу";
  return `${new Intl.NumberFormat("ru-RU").format(Math.round(kopeks / 100))} ₽`;
}

function formatBalanceRubles(kopeks: number) {
  return `${new Intl.NumberFormat("ru-RU").format(Math.round((kopeks || 0) / 100))} ₽`;
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
  const policy = (job as unknown as { supplier_search_policy?: string }).supplier_search_policy;
  const policyLabel =
    policy === "registry_only" || policy === "minprom_registry_only"
      ? "Только реестр"
      : policy === "registry_priority" || policy === "minprom_registry_priority"
      ? "Реестр в приоритете"
      : "Обычный";

  if (job.mode === "procurement_report") return "Анализ закупки";
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

function parseError(raw: string) {
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed?.detail === "string") return parsed.detail;
  } catch {
    return raw;
  }
  return raw || "Ошибка запроса";
}

function filenameFromResponse(response: Response, fallback: string) {
  const header = response.headers.get("content-disposition") || "";
  const utf = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf?.[1]) return decodeURIComponent(utf[1]);
  const plain = header.match(/filename="?([^";]+)"?/i);
  return plain?.[1] || fallback;
}

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!response.ok) throw new Error(parseError(text));
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
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/__(.*?)__/g, "<strong>$1</strong>");
}

function quoteMarkdownToHtml(markdown: string) {
  const value = String(markdown || "").trim();
  if (!value) return "<p></p>";
  if (/^\s*</.test(value)) return value;
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
    html.push(
      `<div style="overflow-x:auto;margin:14px 0;"><table style="width:100%;border-collapse:collapse;font-size:12px;font-family:system-ui,-apple-system,sans-serif;border:1px solid #CBD5E1;background-color:#FFFFFF;">` +
      `<thead style="background-color:#F1F5F9;"><tr style="border-bottom:2px solid #CBD5E1;">` +
      header.map((cell) => `<th style="padding:9px 12px;text-align:left;font-weight:700;color:#0F172A;border:1px solid #CBD5E1;">${formatInlineMarkdown(cell)}</th>`).join("") +
      `</tr></thead><tbody>` +
      body.map((row) => `<tr style="border-bottom:1px solid #E2E8F0;">` + row.map((cell) => `<td style="padding:9px 12px;color:#334155;border:1px solid #E2E8F0;vertical-align:top;">${formatInlineMarkdown(cell)}</td>`).join("") + `</tr>`).join("") +
      `</tbody></table></div>`
    );
    tableRows = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      flushList();
      const compact = trimmed.replace(/\|/g, "").replace(/:/g, "").replace(/-/g, "").trim();
      if (!compact) continue;
      tableRows.push(trimmed.slice(1, -1).split("|").map((cell) => cell.trim()));
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
  return Array.from(row.querySelectorAll("th,td")).map((cell) => (cell.textContent || "").replace(/\s+/g, " ").trim());
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
          .map((row) => cellsText(row as HTMLTableRowElement))
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

export function CabinetClient() {
  const [nowTs, setNowTs] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNowTs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [jobs, setJobs] = useState<CustomerJob[]>([]);
  const [jobsPage, setJobsPage] = useState(1);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [authMode, setAuthMode] = useState<"login" | "register" | "reset">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [website, setWebsite] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(true);
  const [personalDataConsent, setPersonalDataConsent] = useState(true);
  const [emailDraft, setEmailDraft] = useState("");
  const [emailEditOpen, setEmailEditOpen] = useState(false);
  const [scenario, setScenario] = useState<Scenario>("supplier_search");
  const [supplierSearchPolicy, setSupplierSearchPolicy] = useState<SupplierSearchPolicy>("normal");
  const [text, setText] = useState("");
  const [sourceUrls, setSourceUrls] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [findMoreConfirmJob, setFindMoreConfirmJob] = useState<CustomerJob | null>(null);
  const [quoteRequestModal, setQuoteRequestModal] = useState<QuoteRequestModal | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [showTariffs, setShowTariffs] = useState(false);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [viewedJobIds, setViewedJobIds] = useState<string[]>([]);
  const [activeToast, setActiveToast] = useState<ActiveToast | null>(null);
  const prevJobStatusesRef = useRef<Map<string, string>>(new Map());
  const hasInitializedJobsRef = useRef(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const quoteEditorRef = useRef<HTMLDivElement | null>(null);

  const csrf = session?.csrf_token || "";
  const authenticated = Boolean(session?.authenticated && session.user);
  const selectedCopy = modeCopy[scenario];
  const selectedMode = selectedCopy.mode;
  const acceptsSources = Boolean(selectedCopy.sourceLabel);
  const acceptsText = Boolean(selectedCopy.textLabel);
  const maxFiles = session?.limits?.max_files_per_batch || 20;
  const emailVerified = session?.user?.is_email_verified !== false;
  const supplierMultiFileWarning = scenario === "supplier_search" && selectedFiles.length > 1;
  const activeJobs = useMemo(
    () => jobs.filter((job) => ["pending", "running", "awaiting_customer_confirmation"].includes(job.status)).length,
    [jobs],
  );
  const jobsPageCount = Math.max(1, Math.ceil(jobsTotal / CUSTOMER_JOBS_PAGE_SIZE));
  const jobsStart = jobsTotal ? (jobsPage - 1) * CUSTOMER_JOBS_PAGE_SIZE + 1 : 0;
  const jobsEnd = Math.min(jobsTotal, jobsPage * CUSTOMER_JOBS_PAGE_SIZE);
  const hasFindMoreSuppliers = jobs.some((job) => job.can_find_more_suppliers);

  async function loadSession() {
    const response = await fetch("/api/customer/auth/session", { credentials: "same-origin", cache: "no-store" });
    if (response.status === 401 || response.status === 404) {
      setSession(null);
      return;
    }
    const payload = await readJson<SessionPayload>(response);
    setSession(payload.authenticated ? payload : null);
  }

  async function loadJobs(page = jobsPage) {
    if (!authenticated) return;
    setJobsLoading(true);
    try {
      const offset = (page - 1) * CUSTOMER_JOBS_PAGE_SIZE;
      const response = await fetch(
        `/api/customer/jobs?limit=${CUSTOMER_JOBS_PAGE_SIZE}&offset=${offset}&include_pagination=true`,
        CUSTOMER_JOB_FETCH_OPTIONS,
      );
      const payload = await readJson<CustomerJobsResponse | CustomerJob[]>(response);
      const incomingItems = Array.isArray(payload) ? payload : payload.items;

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
          if (notificationsEnabled) {
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
      const nextPageCount = Math.max(1, Math.ceil(payload.total / payload.limit));
      setJobsTotal(payload.total);
      if (page > nextPageCount) {
        setJobsPage(nextPageCount);
        return;
      }
      setJobs(payload.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setJobsLoading(false);
    }
  }

  function syncSelectedFiles(files: File[]) {
    setSelectedFiles(files);
    if (!fileInputRef.current) return;
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    fileInputRef.current.files = transfer.files;
  }

  function filesFromList(fileList: FileList | null) {
    const files = Array.from(fileList || []);
    const limited = selectedCopy.multipleFiles ? files.slice(0, maxFiles) : files.slice(0, 1);
    syncSelectedFiles(limited);
  }

  function clearSelectedFiles() {
    setSelectedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function selectScenario(next: Scenario) {
    setScenario(next);
    if (next === "procurement_report") setSupplierSearchPolicy("normal");
    setText("");
    setSourceUrls("");
    clearSelectedFiles();
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
    loadSession().catch((err) => setError(err instanceof Error ? err.message : String(err)));
    const params = new URLSearchParams(window.location.search);
    const verified = params.get("email_verified");
    const verifyToken = params.get("email_verify_token");
    if (verified === "1") setMessage("Email подтверждён. Теперь можно запускать задачи.");
    if (verified === "0") setError("Ссылка подтверждения недействительна или устарела.");
    if (verifyToken) {
      confirmEmailToken(verifyToken).catch((err) => setError(err instanceof Error ? err.message : String(err)));
      params.delete("email_verify_token");
    }
    if (verified) {
      params.delete("email_verified");
    }
    if (verified || verifyToken) {
      const nextQuery = params.toString();
      window.history.replaceState(null, "", `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`);
    }
  }, []);

  useEffect(() => {
    if (session?.user?.email && !emailEditOpen) setEmailDraft(session.user.email);
  }, [emailEditOpen, session?.user?.email]);

  useEffect(() => {
    if (!authenticated) return;
    loadJobs();
    const timer = window.setInterval(() => {
      loadJobs();
      if (activeJobs) loadSession().catch((err) => setError(err instanceof Error ? err.message : String(err)));
    }, activeJobs ? 3000 : 7000);
    return () => window.clearInterval(timer);
  }, [authenticated, jobsPage, activeJobs]);

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
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (!activeToast) return;
    const timer = setTimeout(() => setActiveToast(null), 15000);
    return () => clearTimeout(timer);
  }, [activeToast]);

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
      if (authMode === "reset") {
        const response = await fetch("/api/customer/auth/password-reset/request", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        const payload = await readJson<{ message?: string }>(response);
        setMessage(payload.message || "Заявка отправлена. Мы поможем восстановить доступ.");
        return;
      }
      const response = await fetch(`/api/customer/auth/${authMode}`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          name,
          website: authMode === "register" ? website : "",
          terms_accepted: termsAccepted,
          personal_data_consent: personalDataConsent,
          legal_version: "2026-07-17",
        }),
      });
      const payload = await readJson<SessionPayload>(response);
      setSession(payload);
      setPassword("");
      setWebsite("");
      setMessage(authMode === "register" ? (payload.message || "Кабинет создан. Подтвердите email, чтобы запускать задачи.") : "");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
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
      setJobs([]);
      setJobsPage(1);
      setJobsTotal(0);
      setFindMoreConfirmJob(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
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

  async function submitJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrf) return;
    if (!emailVerified) {
      setError("Подтвердите email, чтобы запускать задачи.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const form = new FormData();
      form.append("mode", selectedMode);
      form.append("supplier_search_policy", selectedMode === "procurement_report" ? "normal" : supplierSearchPolicy);
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
      const payload = await readJson<{ batch: boolean; count: number }>(response);
      setText("");
      setSourceUrls("");
      clearSelectedFiles();
      setMessage(payload.batch ? `Запущено задач: ${payload.count}.` : "Задача запущена.");
      setJobsPage(1);
      await loadSession();
      await loadJobs(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
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
      setQuoteRequestModal({
        job,
        html: quoteMarkdownToHtml(payload.content || ""),
        filename: payload.filename || file.filename || "Запрос коммерческого предложения.docx",
        copied: false,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function downloadEditedQuoteRequest() {
    if (!csrf || !quoteRequestModal) return;
    const content = quoteHtmlToMarkdown(quoteEditorRef.current);
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/customer/jobs/${quoteRequestModal.job.id}/quote-request/docx`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "x-csrf-token": csrf },
        body: JSON.stringify({ content, filename: quoteRequestModal.filename }),
      });
      if (!response.ok) throw new Error(parseError(await response.text()));
      downloadBlob(await response.blob(), filenameFromResponse(response, quoteRequestModal.filename || "Запрос коммерческого предложения.docx"));
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
      setMessage("Отчёт принят. Результат можно скачать в строке задачи.");
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
      await readJson(response);
      await loadSession();
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function findMoreSuppliers(job: CustomerJob) {
    if (!csrf) return;
    setBusy(true);
    setError("");
    setMessage("");
    setFindMoreConfirmJob(null);
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/find-more-suppliers`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      const payload = await readJson<{ message?: string; job?: CustomerJob }>(response);
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

  async function retryJob(job: CustomerJob) {
    try {
      setBusy(true);
      setError("");
      setMessage("");
      const res = await fetch(`/api/customer/jobs/${job.id}/retry`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Не удалось перезапустить задачу");
      }
      setMessage(data.message || "Задача успешно перезапущена");
      await loadJobs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ошибка перезапуска задачи");
    } finally {
      setBusy(false);
    }
  }

  if (!authenticated) {
    return (
      <main className="min-h-screen bg-slate-50/70 flex flex-col items-center justify-center p-4 sm:p-8 font-sans text-slate-900">
        <header className="w-full max-w-5xl mx-auto flex items-center justify-between pb-6 mb-8 border-b border-slate-200/80">
          <a className="flex items-center gap-3 font-extrabold text-slate-900 text-xl hover:text-teal-700 transition-colors" href="/">
            <Image src="/tenderlex-logo.png" alt="TenderLex" width={36} height={36} priority />
            <span>TenderLex</span>
          </a>
          <a className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-700 hover:text-teal-700 transition-colors bg-slate-100 hover:bg-slate-200 px-4 py-2 rounded-xl border border-slate-200 shadow-2xs" href="/">
            На главную
            <ArrowRight size={16} aria-hidden="true" />
          </a>
        </header>

        <section className="w-full max-w-5xl grid lg:grid-cols-12 gap-8 items-stretch bg-white p-6 sm:p-10 rounded-3xl border border-slate-200/90 shadow-xl">
          <div className="lg:col-span-7 flex flex-col justify-between space-y-6 pr-0 lg:pr-4">
            <div className="space-y-4">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 leading-tight">Работайте с закупками прямо на сайте</h1>
              <p className="text-sm text-slate-600 leading-relaxed">
                Войдите или создайте кабинет, чтобы запускать анализ закупок, искать поставщиков и скачивать готовые результаты.
              </p>
            </div>

            <div className="space-y-3 pt-2">
              <article className="flex items-start gap-4 p-4 bg-slate-50/80 border border-slate-200/80 rounded-2xl text-left">
                <div className="w-10 h-10 rounded-xl bg-teal-100/80 text-teal-700 flex items-center justify-center shrink-0 border border-teal-200/60 mt-0.5">
                  <FileText size={20} aria-hidden="true" />
                </div>
                <div className="space-y-0.5">
                  <strong className="text-sm font-bold text-slate-900 block">Анализ закупки</strong>
                  <span className="text-xs text-slate-500 leading-normal block">условия, риски, сроки, вопросы заказчику</span>
                </div>
              </article>

              <article className="flex items-start gap-4 p-4 bg-slate-50/80 border border-slate-200/80 rounded-2xl text-left">
                <div className="w-10 h-10 rounded-xl bg-teal-100/80 text-teal-700 flex items-center justify-center shrink-0 border border-teal-200/60 mt-0.5">
                  <Search size={20} aria-hidden="true" />
                </div>
                <div className="space-y-0.5">
                  <strong className="text-sm font-bold text-slate-900 block">Поиск поставщиков</strong>
                  <span className="text-xs text-slate-500 leading-normal block">контакты компаний для запроса коммерческого предложения</span>
                </div>
              </article>

              <article className="flex items-start gap-4 p-4 bg-slate-50/80 border border-slate-200/80 rounded-2xl text-left">
                <div className="w-10 h-10 rounded-xl bg-teal-100/80 text-teal-700 flex items-center justify-center shrink-0 border border-teal-200/60 mt-0.5">
                  <CheckCircle2 size={20} aria-hidden="true" />
                </div>
                <div className="space-y-0.5">
                  <strong className="text-sm font-bold text-slate-900 block">Вернуться к результатам</strong>
                  <span className="text-xs text-slate-500 leading-normal block">история задач и скачивание готовых файлов</span>
                </div>
              </article>
            </div>
          </div>

          <form className="lg:col-span-5 bg-slate-50/70 p-6 sm:p-8 rounded-2xl border border-slate-200/80 space-y-4 flex flex-col justify-center" onSubmit={submitAuth}>
            {authMode === "reset" ? (
              <div className="space-y-1 pb-2 border-b border-slate-200/80 mb-2">
                <h2 className="text-lg font-bold text-slate-900">Восстановить доступ</h2>
                <p className="text-xs text-slate-500">Укажите email кабинета. Мы проверим заявку и поможем войти снова.</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 p-1 bg-slate-200/60 rounded-xl mb-3 text-xs font-bold" role="tablist" aria-label="Режим входа">
                <button
                  type="button"
                  className={`py-2 rounded-lg transition-all cursor-pointer ${authMode === "login" ? "bg-white text-slate-900 shadow-2xs font-extrabold" : "text-slate-600 hover:text-slate-900"}`}
                  onClick={() => { setError(""); setMessage(""); setAuthMode("login"); }}
                >
                  Вход
                </button>
                <button
                  type="button"
                  className={`py-2 rounded-lg transition-all cursor-pointer ${authMode === "register" ? "bg-white text-slate-900 shadow-2xs font-extrabold" : "text-slate-600 hover:text-slate-900"}`}
                  onClick={() => { setError(""); setMessage(""); setAuthMode("register"); }}
                >
                  Регистрация
                </button>
              </div>
            )}

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
              <label className="hidden" aria-hidden="true">
                Сайт
                <input value={website} onChange={(event) => setWebsite(event.target.value)} tabIndex={-1} autoComplete="off" />
              </label>
            ) : null}

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

            {authMode !== "reset" ? (
              <label className="flex flex-col gap-1.5 text-xs font-bold text-slate-700 w-full">
                <span>Пароль</span>
                <input
                  className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 shadow-2xs"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  type="password"
                  autoComplete={authMode === "login" ? "current-password" : "new-password"}
                  minLength={8}
                  placeholder="••••••••"
                  required
                />
              </label>
            ) : null}

            {authMode === "register" ? (
              <div className="space-y-2.5 pt-2 border-t border-slate-200/60">
                <label className="flex items-start gap-2.5 text-xs text-slate-700 font-medium leading-snug cursor-pointer select-none">
                  <input
                    className="mt-0.5 rounded border-slate-300 text-teal-600 focus:ring-teal-500 shrink-0"
                    type="checkbox"
                    checked={termsAccepted}
                    onChange={(event) => setTermsAccepted(event.target.checked)}
                    required
                  />
                  <span>
                    Я принимаю <a className="text-teal-700 underline font-semibold hover:text-teal-900" href="/terms" target="_blank" rel="noreferrer">публичную оферту</a>.
                  </span>
                </label>
                <label className="flex items-start gap-2.5 text-xs text-slate-700 font-medium leading-snug cursor-pointer select-none">
                  <input
                    className="mt-0.5 rounded border-slate-300 text-teal-600 focus:ring-teal-500 shrink-0"
                    type="checkbox"
                    checked={personalDataConsent}
                    onChange={(event) => setPersonalDataConsent(event.target.checked)}
                    required
                  />
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
              {busy ? <Loader2 size={18} className="animate-spin" aria-hidden="true" /> : <ArrowRight size={18} aria-hidden="true" />}
              <span>{authMode === "reset" ? "Отправить заявку" : authMode === "login" ? "Войти" : "Создать кабинет"}</span>
            </button>

            {authMode === "login" ? (
              <button
                className="w-full text-center text-xs font-bold text-teal-700 hover:text-teal-900 transition-colors py-2 border-t border-slate-200/60 mt-2 block cursor-pointer"
                type="button"
                onClick={() => {
                  setError("");
                  setMessage("");
                  setAuthMode("reset");
                }}
              >
                Не помню пароль
              </button>
            ) : authMode === "reset" ? (
              <button
                className="w-full text-center text-xs font-bold text-teal-700 hover:text-teal-900 transition-colors py-2 border-t border-slate-200/60 mt-2 block cursor-pointer"
                type="button"
                onClick={() => {
                  setError("");
                  setMessage("");
                  setAuthMode("login");
                }}
              >
                Вернуться ко входу
              </button>
            ) : (
              <button
                className="w-full text-center text-xs font-bold text-slate-600 hover:text-teal-800 transition-colors py-2 border-t border-slate-200/60 mt-2 block cursor-pointer"
                type="button"
                onClick={() => {
                  setError("");
                  setMessage("");
                  setAuthMode("login");
                }}
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
    <main className="min-h-screen bg-slate-50/60 p-3 sm:p-5 max-w-7xl mx-auto space-y-3 font-sans text-slate-900">
      <header className="w-full flex items-center justify-between pb-2.5 border-b border-slate-200/80">
        <a className="flex items-center gap-2 font-extrabold text-slate-900 text-lg hover:text-teal-700 transition-colors" href="/">
          <Image src="/tenderlex-logo.png" alt="TenderLex" width={28} height={28} priority />
          <span>TenderLex</span>
        </a>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-xl border border-slate-200/80 text-xs font-bold text-slate-800 shadow-2xs">
            <User size={14} className="text-teal-600" aria-hidden="true" />
            <span>{session?.user?.email}</span>
            <button
              type="button"
              className="p-0.5 hover:bg-slate-100 text-slate-400 hover:text-rose-600 rounded-lg transition-colors inline-flex items-center justify-center cursor-pointer ml-1"
              onClick={logout}
              disabled={busy}
              aria-label="Выйти"
            >
              <LogOut size={14} aria-hidden="true" />
            </button>
          </div>
        </div>
      </header>

      {!emailVerified ? (
        <div className="p-2.5 bg-amber-50 border border-amber-200/90 rounded-xl text-xs font-medium text-amber-900 flex flex-wrap items-center justify-between gap-2 shadow-2xs">
          <div className="flex items-center gap-2">
            <Mail size={15} className="text-amber-700 shrink-0" aria-hidden="true" />
            <span>
              <strong>Подтвердите email.</strong> Проверьте вашу почту для активирования всех функций уведомлений.
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

      {(message || error) ? (
        <div className={`p-2.5 rounded-xl border text-xs font-bold flex items-center gap-2 shadow-2xs ${error ? "bg-rose-50 border-rose-200 text-rose-800" : "bg-emerald-50 border-emerald-200 text-emerald-800"}`}>
          {error ? <XCircle size={15} aria-hidden="true" /> : <CheckCircle2 size={15} aria-hidden="true" />}
          <span>{error || message}</span>
        </div>
      ) : null}

      {/* Top Dashboard: Compact Header with Balance and All Buttons in 1 Continuous Row */}
      <section className="bg-white border border-slate-200/90 rounded-xl p-2 sm:p-2.5 shadow-2xs font-sans space-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {/* Balance Badge */}
          <div className="flex items-center gap-2 bg-gradient-to-r from-teal-700 to-teal-800 text-white px-2.5 py-1.5 rounded-lg shadow-2xs shrink-0">
            <Receipt size={15} className="text-teal-200" aria-hidden="true" />
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] font-semibold text-teal-100 uppercase tracking-wider">Баланс</span>
              <strong className="text-xs sm:text-sm font-extrabold whitespace-nowrap">
                {formatBalanceRubles(session?.balance?.money?.available_kopeks || 0)}
              </strong>
            </div>
            {session?.user?.is_trial ? (
              <span className="text-[9px] font-bold text-amber-800 bg-amber-100 px-1.5 py-0.5 rounded border border-amber-300 shrink-0 ml-1">
                пробный доступ
              </span>
            ) : null}
          </div>

          {/* All buttons sequentially inline in 1 continuous tight row right next to balance */}
          <button
            type="button"
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg text-xs font-bold transition-all shadow-2xs cursor-pointer shrink-0"
            onClick={() => setShowTariffs((v) => !v)}
          >
            <Sliders size={13} className="text-teal-600 shrink-0" aria-hidden="true" />
            <span>{showTariffs ? "Скрыть тарифы ▲" : "Тарифы и цены ▼"}</span>
          </button>

          <button
            type="button"
            className="inline-flex items-center justify-center gap-1.5 px-2.5 py-1.5 bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200/80 rounded-lg text-xs font-bold transition-colors cursor-pointer shrink-0"
            onClick={() => {
              if (typeof (window as unknown as { openTenderlexChat?: () => void }).openTenderlexChat === "function") {
                (window as unknown as { openTenderlexChat?: () => void }).openTenderlexChat!();
              }
              window.dispatchEvent(new CustomEvent("open_tenderlex_chat"));
            }}
          >
            <MessageCircle size={13} className="text-teal-600 shrink-0" aria-hidden="true" />
            <span>Чат сайта</span>
          </button>

          {session?.contacts?.telegram_url ? (
            <a className="inline-flex items-center justify-center gap-1.5 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg text-xs font-bold transition-colors shrink-0" href={session.contacts.telegram_url} target="_blank" rel="noreferrer">
              <MessageCircle size={13} className="text-sky-500 shrink-0" aria-hidden="true" />
              <span>Telegram</span>
            </a>
          ) : null}

          {session?.contacts?.max_url ? (
            <a className="inline-flex items-center justify-center gap-1.5 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg text-xs font-bold transition-colors shrink-0" href={session.contacts.max_url} target="_blank" rel="noreferrer">
              <MessageCircle size={13} className="text-teal-600 shrink-0" aria-hidden="true" />
              <span>MAX</span>
            </a>
          ) : null}

          {session?.contacts?.email ? (
            <a className="inline-flex items-center justify-center gap-1.5 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg text-xs font-bold transition-colors shrink-0" href={`mailto:${session.contacts.email}`}>
              <Mail size={13} className="text-slate-600 shrink-0" aria-hidden="true" />
              <span>Email</span>
            </a>
          ) : null}

          <button
            type="button"
            className={`inline-flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-bold transition-all border cursor-pointer shrink-0 ${
              notificationsEnabled
                ? "bg-teal-50 hover:bg-teal-100 text-teal-800 border-teal-200/80 shadow-2xs"
                : "bg-slate-100 hover:bg-slate-200 text-slate-500 border-slate-200"
            }`}
            onClick={toggleNotifications}
            title={notificationsEnabled ? "Звуковые уведомления и всплывающие плашки включены" : "Уведомления выключены"}
            aria-label={notificationsEnabled ? "Выключить уведомления" : "Включить уведомления"}
          >
            {notificationsEnabled ? (
              <Bell size={13} className="text-teal-600 shrink-0" aria-hidden="true" />
            ) : (
              <BellOff size={13} className="text-slate-400 shrink-0" aria-hidden="true" />
            )}
            <span>{notificationsEnabled ? "Уведомления: вкл" : "Уведомления: выкл"}</span>
          </button>
        </div>

        {/* Collapsible Tariff Box (Default: Hidden / Collapsed) */}
        {showTariffs ? (() => {
          const extraPriceKopeks =
            session?.balance?.effective_prices?.supplier_search_extra?.price_kopeks ??
            (session?.tariff_groups?.supplier_search_extra?.[0]?.price_kopeks ?? 4900);
          const extraIsOverride = session?.balance?.effective_prices?.supplier_search_extra?.source === "client_override";
          const supplierOverride = session?.balance?.effective_prices?.supplier_search?.source === "client_override" ? session.balance.effective_prices.supplier_search : null;
          const reportOverride = session?.balance?.effective_prices?.procurement_report?.source === "client_override" ? session.balance.effective_prices.procurement_report : null;

          return (
            <div className="grid md:grid-cols-2 gap-2.5 pt-2 border-t border-slate-100 transition-all">
              <div className="space-y-1 bg-slate-50/70 p-2 rounded-lg border border-slate-200/70">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Поиск поставщиков</span>
                <div className="space-y-1 mt-0.5">
                  {supplierOverride ? (
                    <div className="px-2 py-1 bg-amber-50/80 border border-amber-200 rounded-md flex items-center justify-between text-xs font-medium text-amber-950 shadow-2xs">
                      <span className="truncate mr-2 font-semibold text-amber-900 text-xs">1 поиск поставщиков (индивидуально)</span>
                      <b className="font-extrabold text-amber-900 shrink-0 whitespace-nowrap text-xs">{formatRubles(supplierOverride.price_kopeks)}</b>
                    </div>
                  ) : null}
                  {(session?.tariff_groups?.supplier_search || []).slice(0, 3).map((tariff) => (
                    <div key={tariff.id} className="px-2 py-1 bg-white border border-slate-200/80 rounded-md flex items-center justify-between text-xs font-medium text-slate-800 shadow-2xs">
                      <span className="truncate mr-2 font-semibold text-slate-700 text-xs">{tariffDisplayName(tariff)}</span>
                      <b className="font-extrabold text-slate-900 shrink-0 whitespace-nowrap text-xs">{formatRubles(tariff.price_kopeks)}</b>
                    </div>
                  ))}
                  <div className={`px-2 py-1 ${extraIsOverride ? 'bg-amber-50/80 border-amber-200 text-amber-950' : 'bg-teal-50/50 border-teal-200/70 text-teal-950'} border rounded-md flex items-center justify-between text-xs font-medium shadow-2xs`}>
                    <span className={`truncate mr-2 font-semibold ${extraIsOverride ? 'text-amber-900' : 'text-teal-900'} text-xs`}>
                      {extraIsOverride ? '1 добор поставщиков (индивидуально)' : '1 добор поставщиков (по тому же ТЗ)'}
                    </span>
                    <b className={`font-extrabold ${extraIsOverride ? 'text-amber-900' : 'text-teal-900'} shrink-0 whitespace-nowrap text-xs`}>
                      {formatRubles(extraPriceKopeks)}
                    </b>
                  </div>
                </div>
              </div>

              <div className="space-y-1 bg-slate-50/70 p-2 rounded-lg border border-slate-200/70">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Анализ закупки</span>
                <div className="space-y-1 mt-0.5">
                  {reportOverride ? (
                    <div className="px-2 py-1 bg-amber-50/80 border border-amber-200 rounded-md flex items-center justify-between text-xs font-medium text-amber-950 shadow-2xs">
                      <span className="truncate mr-2 font-semibold text-amber-900 text-xs">1 анализ закупки (индивидуально)</span>
                      <b className="font-extrabold text-amber-900 shrink-0 whitespace-nowrap text-xs">{formatRubles(reportOverride.price_kopeks)}</b>
                    </div>
                  ) : null}
                  {(session?.tariff_groups?.procurement_report || []).slice(0, 3).map((tariff) => (
                    <div key={tariff.id} className="px-2 py-1 bg-white border border-slate-200/80 rounded-md flex items-center justify-between text-xs font-medium text-slate-800 shadow-2xs">
                      <span className="truncate mr-2 font-semibold text-slate-700 text-xs">{tariffDisplayName(tariff)}</span>
                      <b className="font-extrabold text-slate-900 shrink-0 whitespace-nowrap text-xs">{formatRubles(tariff.price_kopeks)}</b>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })() : null}
      </section>

      {/* Main Task Launch Form */}
      <section className="bg-white border border-slate-200/90 rounded-xl p-3 sm:p-4 shadow-xs">
        <form id="new-job" className="space-y-2.5" onSubmit={submitJob}>
          <div className="space-y-0.5 pb-2 border-b border-slate-100">
            <h1 className="text-sm sm:text-base font-extrabold text-slate-900">Запуск задачи</h1>
            <p className="text-[11px] text-slate-500">{selectedCopy.formSubtitle}</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-1.5 p-1 bg-slate-100 border border-slate-200/90 rounded-xl" role="tablist" aria-label="Тип задачи">
            {scenarioOptions.map((item) => {
              const ItemIcon = item.icon;
              const isSelected = scenario === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`py-2 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 cursor-pointer border ${
                    isSelected
                      ? "bg-teal-600 border-teal-700 text-white shadow-sm ring-1 ring-teal-500/30"
                      : "bg-white border-slate-200/90 text-slate-700 hover:text-teal-800 hover:border-teal-300 hover:bg-teal-50/20 shadow-2xs"
                  }`}
                  onClick={() => selectScenario(item.id)}
                >
                  <ItemIcon size={14} className={isSelected ? "text-teal-100" : "text-teal-600"} aria-hidden="true" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>

          {scenario !== "procurement_report" ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 p-1.5 bg-slate-50 border border-slate-200/90 rounded-xl">
              {supplierPolicyOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className={`p-2.5 rounded-lg text-left border text-xs transition-all cursor-pointer flex items-start gap-2 ${
                    supplierSearchPolicy === opt.id
                      ? "bg-white border-teal-500 ring-2 ring-teal-500/20 shadow-xs font-bold text-slate-900"
                      : "bg-white border-slate-200/90 text-slate-700 hover:border-teal-300 hover:bg-teal-50/20 shadow-2xs"
                  }`}
                  onClick={() => setSupplierSearchPolicy(opt.id)}
                >
                  <div className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5 ${
                    supplierSearchPolicy === opt.id ? "border-teal-600 bg-teal-600 text-white" : "border-slate-300 bg-white"
                  }`}>
                    {supplierSearchPolicy === opt.id ? <div className="w-1.5 h-1.5 rounded-full bg-white" /> : null}
                  </div>
                  <div className="min-w-0">
                    <strong className="block font-bold text-xs leading-tight text-slate-900 truncate">{opt.label}</strong>
                    <span className="text-[10px] text-slate-500 font-normal leading-tight block mt-0.5">{opt.description}</span>
                  </div>
                </button>
              ))}
            </div>
          ) : null}

          <div className="space-y-2">
            <div
              className={`border-2 border-dashed rounded-xl px-4 py-2.5 cursor-pointer transition-all flex flex-wrap items-center justify-between gap-3 min-h-[46px] ${
                dragActive ? "border-teal-500 bg-teal-50/70 shadow-xs" : "border-teal-400/80 hover:border-teal-500 bg-teal-50/25 hover:bg-teal-50/50"
              }`}
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
            >
              <input
                ref={fileInputRef}
                className="hidden"
                type="file"
                multiple
                accept=".pdf,.docx,.doc,.txt,.xlsx,.xls,.zip"
                onChange={handleFileInput}
              />
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-teal-100/90 text-teal-700 flex items-center justify-center border border-teal-200/80 shadow-2xs shrink-0">
                  <Upload size={16} aria-hidden="true" />
                </div>
                <strong className="text-sm font-extrabold text-slate-900 whitespace-nowrap">{selectedCopy.uploadTitle}</strong>
              </div>

              <div className="flex items-center gap-2.5 text-xs text-slate-600 font-medium ml-auto">
                <span className="hidden md:inline">{selectedCopy.uploadText}</span>
                <span className="md:hidden text-[11px]">Нажмите для выбора (PDF, DOCX, XLSX, ZIP)</span>
                <span className="px-2.5 py-1 bg-white border border-teal-300 text-teal-800 rounded-lg text-xs font-bold shadow-2xs shrink-0">
                  Выбрать файл
                </span>
              </div>
            </div>

            {selectedFiles.length ? (
              <div className="p-2 bg-slate-50 border border-slate-200/80 rounded-lg space-y-1">
                <div className="flex items-center justify-between text-xs font-bold text-slate-700">
                  <span>Выбранные файлы ({selectedFiles.length}):</span>
                  <button
                    type="button"
                    className="px-2 py-0.5 text-[10px] font-bold text-rose-600 hover:text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-md transition-colors cursor-pointer"
                    onClick={clearSelectedFiles}
                  >
                    Очистить все
                  </button>
                </div>
                <ul className="space-y-1">
                  {selectedFiles.map((file, idx) => (
                    <li key={`${file.name}-${idx}`} className="flex items-center justify-between text-xs bg-white p-1 rounded-md border border-slate-200/70 text-slate-800">
                      <span className="truncate max-w-xs font-medium text-xs">{file.name}</span>
                      <span className="text-[10px] text-slate-400 font-mono shrink-0 ml-2">{(file.size / 1024).toFixed(1)} KB</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {acceptsSources ? (
              <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-2 w-full">
                <label className="flex flex-col gap-1 text-xs font-bold text-slate-700 flex-1 min-w-0">
                  <span className="text-[11px]">{selectedCopy.sourceLabel}</span>
                  <input
                    className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-xs font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 shadow-2xs h-[38px]"
                    value={sourceUrls}
                    onChange={(event) => setSourceUrls(event.target.value)}
                    placeholder={selectedCopy.sourcePlaceholder}
                  />
                </label>
                <button
                  className="px-5 h-[38px] bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-500 hover:to-teal-600 active:from-teal-700 active:to-teal-800 text-white text-xs font-extrabold rounded-lg shadow-sm hover:shadow-md transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shrink-0 whitespace-nowrap border border-teal-500/40"
                  type="submit"
                  disabled={busy}
                >
                  {busy ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : null}
                  <span>{selectedCopy.submit}</span>
                </button>
              </div>
            ) : null}

            {acceptsText ? (
              <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-2 w-full">
                <label className="flex flex-col gap-1 text-xs font-bold text-slate-700 flex-1 min-w-0">
                  <span className="text-[11px]">{selectedCopy.textLabel}</span>
                  <textarea
                    className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-xs font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 shadow-2xs resize-y min-h-[50px]"
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    rows={2}
                    placeholder={selectedCopy.textPlaceholder}
                  />
                </label>
                <button
                  className="px-5 h-[50px] bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-500 hover:to-teal-600 active:from-teal-700 active:to-teal-800 text-white text-xs font-extrabold rounded-lg shadow-sm hover:shadow-md transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shrink-0 sm:max-w-[220px] whitespace-normal text-center leading-snug border border-teal-500/40"
                  type="submit"
                  disabled={busy}
                >
                  {busy ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : null}
                  <span>{selectedCopy.submit}</span>
                </button>
              </div>
            ) : null}
          </div>
        </form>
      </section>

      {/* Jobs History Table */}
      <section id="jobs" className="bg-white border border-slate-200/90 rounded-xl p-3 sm:p-4 shadow-xs space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2.5 pb-2 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-extrabold text-slate-900">Задачи</h2>
            <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-lg">
              {jobsTotal ? `${jobsStart}-${jobsEnd} из ${jobsTotal}` : "0 задач"}
            </span>
          </div>

          <div className="flex items-center gap-3">
            {jobsTotal > CUSTOMER_JOBS_PAGE_SIZE ? (
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700" aria-label="Навигация по задачам">
                <button
                  type="button"
                  className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-bold transition-colors cursor-pointer disabled:opacity-50"
                  onClick={() => setJobsPage((page) => Math.max(1, page - 1))}
                  disabled={jobsPage <= 1 || jobsLoading}
                >
                  <ChevronLeft size={16} aria-hidden="true" />
                  Назад
                </button>
                <span className="px-2 text-xs font-medium text-slate-600">
                  Страница {jobsPage} из {jobsPageCount}
                </span>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-bold transition-colors cursor-pointer disabled:opacity-50"
                  onClick={() => setJobsPage((page) => Math.min(jobsPageCount, page + 1))}
                  disabled={jobsPage >= jobsPageCount || jobsLoading}
                >
                  Вперёд
                  <ChevronRight size={16} aria-hidden="true" />
                </button>
              </div>
            ) : null}


          </div>
        </div>



        <div className="w-full space-y-3 font-sans">
          <div className="hidden md:grid grid-cols-12 gap-4 pb-3 border-b border-slate-200 text-[11px] font-bold text-slate-400 uppercase tracking-wider px-4">
            <span className="col-span-4">Задача</span>
            <span className="col-span-2">Режим</span>
            <span className="col-span-1">Статус</span>
            <span className="col-span-2">Прогресс</span>
            <span className="col-span-3 text-right">Результат</span>
          </div>

          {jobs.length ? (
            jobs.map((job) => {
              const offer = (job as unknown as { result_offer?: { kind?: string; can_accept?: boolean; can_decline?: boolean } }).result_offer;
              const isFailed = job.status === "failed" || job.status === "error";
              const isPending = job.status === "pending" || job.status === "running";
              const isAwaiting = job.status === "awaiting_customer_confirmation";
              const isCompletedWithResult = job.status === "done" || (Boolean(job.result_files?.length) && !isPending && !isFailed);
              const jobCreatedTs = job.created_at ? new Date(apiDateValue(job.created_at)).getTime() : 0;
              const isCreatedAfterFeature = !Number.isNaN(jobCreatedTs) && jobCreatedTs >= NOTIFICATION_FEATURE_START_TS;
              const isUnviewed = isCreatedAfterFeature && isCompletedWithResult && !viewedJobIds.includes(job.id);

              return (
                <article
                  key={job.id}
                  id={`job-${job.id}`}
                  onClick={() => {
                    if (isUnviewed) markJobAsViewed(job.id);
                  }}
                  className={`p-4 rounded-2xl transition-all space-y-3 md:space-y-0 md:grid md:grid-cols-12 md:gap-4 md:items-center text-xs font-medium text-slate-800 shadow-2xs border ${
                    isUnviewed
                      ? "bg-teal-50/40 hover:bg-teal-50/70 border-teal-300 ring-1 ring-teal-400/40"
                      : "bg-slate-50/60 hover:bg-slate-100/70 border-slate-200/80"
                  }`}
                >
                  <div className="col-span-12 md:col-span-4 flex flex-col gap-0.5 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <strong className="font-bold text-xs text-slate-900 leading-snug break-words">{job.human_title}</strong>
                      {isUnviewed ? (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-extrabold bg-teal-600 text-white animate-pulse shadow-2xs shrink-0">
                          <Sparkles size={10} aria-hidden="true" />
                          Новая
                        </span>
                      ) : null}
                    </div>
                    <span className="text-[11px] font-medium text-slate-400 block mt-0.5">
                      {formatDate(job.created_at)}{formatJobDuration(job, nowTs) ? ` · ${formatJobDuration(job, nowTs)}` : ""} · файлов: {job.file_count}
                    </span>
                  </div>

                  <div className="col-span-6 md:col-span-2 text-xs font-semibold text-slate-700">
                    {modeDisplayName(job)}
                  </div>

                  <div className="col-span-6 md:col-span-1 flex flex-col gap-1">
                    <span
                      className={`inline-flex items-center px-2.5 py-1 rounded-lg text-[11px] font-bold border w-max ${
                        isFailed
                          ? "bg-rose-50 text-rose-700 border-rose-200"
                          : isPending
                          ? "bg-amber-50 text-amber-800 border-amber-200 animate-pulse"
                          : isAwaiting
                          ? "bg-sky-50 text-sky-800 border-sky-200"
                          : "bg-emerald-50 text-emerald-700 border-emerald-200"
                      }`}
                    >
                      {job.status_label}
                    </span>
                    {job.error ? <small className="text-rose-600 text-[10px] block mt-0.5">{job.error}</small> : null}
                  </div>

                  <div className="col-span-12 md:col-span-2 flex flex-col gap-1 text-xs text-slate-600">
                    {activeJobStatuses.has(job.status) ? <JobStageSteps progress={job.progress} /> : null}
                    <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden mt-1.5" aria-label={`Прогресс ${job.progress}%`}>
                      <i
                        className={`block h-full transition-all rounded-full ${isFailed ? "bg-rose-500" : "bg-teal-600"}`}
                        style={{ width: `${Math.max(0, Math.min(100, job.progress))}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono">{job.message || `${job.progress}%`}</span>
                  </div>

                  <div className="col-span-12 md:col-span-3 flex flex-wrap items-center gap-1.5 md:justify-end">
                    {isFailed ? (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold transition-all shadow-2xs cursor-pointer shrink-0"
                        onClick={(e) => {
                          e.stopPropagation();
                          void retryJob(job);
                        }}
                        disabled={busy}
                      >
                        <RotateCcw size={15} aria-hidden="true" />
                        <span>{job.mode === "procurement_report" ? "Повторить анализ" : "Повторить поиск"}</span>
                      </button>
                    ) : null}

                    {job.awaiting_customer_confirmation ? (
                      <>
                        {!offer || offer.can_accept ? (
                          <button
                            type="button"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-xl text-xs font-bold transition-all shadow-2xs cursor-pointer"
                            onClick={(e) => {
                              e.stopPropagation();
                              markJobAsViewed(job.id);
                              acceptPartial(job);
                            }}
                            disabled={busy}
                          >
                            <CheckCircle2 size={16} aria-hidden="true" />
                            <span>{offer?.kind === "registry_fallback" ? "Получить без реестра" : "Получить и списать"}</span>
                          </button>
                        ) : null}
                        {!offer || offer.can_decline ? (
                          <button
                            type="button"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-xl text-xs font-bold transition-all shadow-2xs cursor-pointer"
                            onClick={(e) => {
                              e.stopPropagation();
                              markJobAsViewed(job.id);
                              declinePartial(job);
                            }}
                            disabled={busy}
                          >
                            <XCircle size={16} aria-hidden="true" />
                            <span>Отказаться</span>
                          </button>
                        ) : null}
                      </>
                    ) : (
                      <>
                        {job.can_cancel ? (
                          <button
                            type="button"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-xl text-xs font-bold transition-all shadow-2xs cursor-pointer"
                            onClick={(e) => {
                              e.stopPropagation();
                              void cancelJob(job);
                            }}
                            disabled={busy}
                          >
                            <XCircle size={16} aria-hidden="true" />
                            <span>Отменить</span>
                          </button>
                        ) : null}
                        {job.result_files?.length ? (
                          job.result_files.map((file) => {
                            const isQuoteRequest = file.kind === "quote_request";
                            return (
                              <button
                                key={`${job.id}-${file.kind}`}
                                type="button"
                                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs transition-all shadow-2xs cursor-pointer shrink-0 border ${
                                  isUnviewed
                                    ? "bg-teal-600 hover:bg-teal-700 text-white border-teal-600 ring-2 ring-teal-400/80 animate-pulse shadow-teal-600/30 font-extrabold"
                                    : "bg-white hover:bg-slate-100 text-slate-800 border-slate-300 font-bold"
                                }`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  markJobAsViewed(job.id);
                                  if (isQuoteRequest) openQuoteRequest(job, file);
                                  else downloadJobFile(job, file);
                                }}
                                disabled={busy}
                              >
                                {isQuoteRequest ? <Eye size={15} aria-hidden="true" /> : <Download size={15} aria-hidden="true" />}
                                <span>{file.label || "Скачать"}</span>
                              </button>
                            );
                          })
                        ) : null}
                        {job.can_find_more_suppliers ? (
                          <button
                            type="button"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200/80 rounded-xl text-xs font-bold transition-all cursor-pointer shrink-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              markJobAsViewed(job.id);
                              setFindMoreConfirmJob(job);
                            }}
                            disabled={busy}
                          >
                            <Search size={15} aria-hidden="true" />
                            <span>Найти ещё</span>
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
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 rounded-xl text-xs font-bold transition-all shadow-2xs cursor-pointer shrink-0"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  void retryJob(job);
                                }}
                                disabled={busy}
                                title="Продолжить поиск поставщиков"
                              >
                                <RotateCcw size={15} aria-hidden="true" />
                                <span>Продолжить поиск</span>
                              </button>
                            );
                          }
                          return null;
                        })()}
                      </>
                    )}
                  </div>
                </article>
              );
            })
          ) : (
            <div className="p-8 text-center bg-slate-50 rounded-2xl border border-slate-200/60 text-slate-500 text-xs">
              У вас пока нет запущенных задач.
            </div>
          )}
        </div>
      </section>

      {quoteRequestModal ? (
        <div
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 overflow-y-auto"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setQuoteRequestModal(null);
          }}
        >
          <section className="bg-white rounded-3xl p-6 sm:p-8 max-w-3xl w-full shadow-2xl border border-slate-200 space-y-6 max-h-[90vh] flex flex-col font-sans" role="dialog" aria-modal="true" aria-labelledby="quote-request-title">
            <header className="flex items-center justify-between pb-4 border-b border-slate-200 shrink-0">
              <div>
                <h2 id="quote-request-title" className="text-lg font-extrabold text-slate-900">Запрос коммерческого предложения</h2>
                <span className="text-xs text-slate-500 font-medium">{quoteRequestModal.job.human_title}</span>
              </div>
              <button type="button" className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-colors shrink-0 cursor-pointer" onClick={() => setQuoteRequestModal(null)} disabled={busy} aria-label="Закрыть">
                <X size={18} aria-hidden="true" />
              </button>
            </header>
            <div
              ref={quoteEditorRef}
              className="flex-1 overflow-y-auto p-5 bg-white border border-slate-200 rounded-2xl font-sans text-xs text-slate-900 space-y-4 min-h-[300px] shadow-inner leading-relaxed"
              contentEditable
              suppressContentEditableWarning
              dangerouslySetInnerHTML={{ __html: quoteRequestModal.html }}
              onInput={() => {
                if (quoteRequestModal.copied) {
                  setQuoteRequestModal({ ...quoteRequestModal, html: quoteEditorRef.current?.innerHTML || quoteRequestModal.html, copied: false });
                }
              }}
              aria-label="Текст запроса коммерческого предложения"
            />
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200 shrink-0">
              <button type="button" className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 font-bold text-xs rounded-xl transition-all cursor-pointer" onClick={() => setQuoteRequestModal(null)} disabled={busy}>
                Закрыть
              </button>
              <button type="button" className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-300 font-bold text-xs rounded-xl transition-all cursor-pointer" onClick={() => void copyQuoteRequestText()} disabled={busy}>
                <Copy size={16} aria-hidden="true" />
                <span>{quoteRequestModal.copied ? "Скопировано" : "Копировать"}</span>
              </button>
              <button className="px-6 py-2.5 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white text-xs font-bold rounded-xl shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50" type="button" onClick={() => void downloadEditedQuoteRequest()} disabled={busy}>
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
            if (event.target === event.currentTarget) setFindMoreConfirmJob(null);
          }}
        >
          <section className="bg-white rounded-3xl p-6 max-w-md w-full shadow-2xl border border-slate-200 space-y-4 font-sans text-center" role="dialog" aria-modal="true" aria-labelledby="find-more-confirm-title">
            <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-700 mx-auto flex items-center justify-center border border-amber-200 shadow-2xs mb-2">
              <Search size={20} aria-hidden="true" />
            </div>
            <div className="space-y-1">
              <h2 id="find-more-confirm-title" className="text-base font-extrabold text-slate-900">Найти ещё поставщиков?</h2>
              <p className="text-xs text-slate-600 leading-relaxed">С баланса спишется стоимость добора поставщиков. Уже найденные компании не попадут в новый результат.</p>
              <span className="text-[11px] font-bold text-slate-400 block mt-1">{findMoreConfirmJob.human_title}</span>
            </div>
            <div className="flex items-center justify-center gap-3 pt-2">
              <button className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 font-bold text-xs rounded-xl transition-all cursor-pointer" type="button" onClick={() => setFindMoreConfirmJob(null)} disabled={busy}>
                Отмена
              </button>
              <button className="px-6 py-2.5 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white text-xs font-bold rounded-xl shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50" type="button" onClick={() => void findMoreSuppliers(findMoreConfirmJob)} disabled={busy}>
                {busy ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <Search size={16} aria-hidden="true" />}
                <span>Продолжить</span>
              </button>
            </div>
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
    </main>
  );
}

const activeJobStatuses = new Set(["pending", "running", "awaiting_customer_confirmation"]);
const processingStages = ["Принято", "Анализ", "Поиск", "Готово"];

function JobStageSteps({ progress }: { progress: number }) {
  const boundedProgress = Math.max(0, Math.min(100, progress));
  const currentStep = Math.min(processingStages.length - 1, Math.floor((boundedProgress / 100) * processingStages.length));

  return (
    <div className="flex items-center gap-1 flex-wrap text-[10px] text-slate-500 mt-1" aria-label="Этапы обработки задачи">
      {processingStages.map((stage, index) => (
        <span
          key={stage}
          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
            index < currentStep
              ? "bg-teal-100 text-teal-800"
              : index === currentStep
              ? "bg-amber-100 text-amber-800 animate-pulse"
              : "bg-slate-100 text-slate-400"
          }`}
        >
          {stage}
        </span>
      ))}
    </div>
  );
}
