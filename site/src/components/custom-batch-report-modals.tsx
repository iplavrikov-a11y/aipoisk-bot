"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Check,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Copy,
  Download,
  ExternalLink,
  FileSpreadsheet,
  FileText,
  Loader2,
  Mail,
  Maximize2,
  Minimize2,
  Move,
  Search,
  Sparkles,
  TrendingUp,
  X,
} from "lucide-react";
import { SafeMarkdownView } from "./safe-markdown-view";

export type BatchRegistryPreviewItem = {
  id: string;
  row_no: number;
  sheet_name?: string;
  notice_number: string;
  title: string;
  nmck_value: number | null;
  nmck_raw: string;
  publication_date: string;
  deadline_date: string;
  deadline_ts?: number | null;
  procurement_type: string;
  kontur_url?: string;
  eis_url: string;
  etp_url: string;
  customer_inn: string;
  customer_name: string;
};

export type BatchRegistryPreviewData = {
  target_mode?: "custom_batch_report" | "procurement_report";
  file: File | null;
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
};

export type BatchReportResultItem = {
  index: number;
  id: string;
  notice_number: string;
  title: string;
  nmck_raw: string;
  publication_date: string;
  deadline_date: string;
  procurement_type: string;
  kontur_url?: string;
  eis_url?: string;
  etp_url?: string;
  margin_rub?: string;
  margin_pct?: string;
  margin_rub_value?: number | null;
  margin_pct_value?: number | null;
  verdict_text?: string;
  verdict_is_at_top?: boolean;
  copy_specs_text?: string;
  copy_supplier_email_text?: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  report_markdown: string;
  sources?: { title: string; url: string }[];
  error: string;
  docx_filename: string;
};

export type BatchReportReaderData = {
  job_id: string;
  title: string;
  status: string;
  progress: number;
  message: string;
  total_count: number;
  completed_count: number;
  failed_count: number;
  items: BatchReportResultItem[];
};

function formatRub(kopeks: number): string {
  const rub = kopeks / 100;
  return `${rub.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽`;
}

function safeHttpUrl(raw?: string | null): string | null {
  const trimmed = String(raw || "").trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
  } catch {
    return null;
  }
  return null;
}

async function copyTextReliable(text: string): Promise<boolean> {
  if (!text) return false;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fallback below
  }
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  } catch {
    return false;
  }
}

function getMarginBadgeStyle(item: BatchReportResultItem): {
  label: string;
  classes: string;
  isLoss: boolean;
} | null {
  const rub = String(item.margin_rub || "").trim();
  const pct = String(item.margin_pct || "").trim();
  if (!rub && !pct) return null;

  const pctNum = typeof item.margin_pct_value === "number" ? item.margin_pct_value : null;
  const rubNum = typeof item.margin_rub_value === "number" ? item.margin_rub_value : null;
  const isLoss =
    (pctNum !== null && pctNum <= 0) ||
    (rubNum !== null && rubNum < 0) ||
    rub.startsWith("−") ||
    rub.startsWith("-") ||
    pct.startsWith("−") ||
    pct.startsWith("-");
  const isHigh = !isLoss && ((pctNum !== null && pctNum >= 15) || (pctNum === null && rubNum !== null && rubNum > 0));

  const parts = [rub, pct].filter(Boolean).join(" · ");
  const prefix = isLoss ? "Убыток:" : "Маржа:";

  if (isLoss) {
    return {
      label: `${prefix} ${parts}`,
      classes: "bg-rose-50 text-rose-800 border-rose-200",
      isLoss: true,
    };
  }
  if (isHigh) {
    return {
      label: `${prefix} ${parts}`,
      classes: "bg-emerald-50 text-emerald-800 border-emerald-200",
      isLoss: false,
    };
  }
  return {
    label: `${prefix} ${parts}`,
    classes: "bg-amber-50 text-amber-800 border-amber-200",
    isLoss: false,
  };
}

type BatchSortField = "default" | "deadline" | "price";
type BatchSortDirection = "asc" | "desc";

function getItemDeadlineTs(item: BatchRegistryPreviewItem): number | null {
  if (typeof item.deadline_ts === "number" && Number.isFinite(item.deadline_ts)) {
    return item.deadline_ts;
  }
  const raw = String(item.deadline_date || "")
    .replace(/\(?\s*(?:МСК|MSK|UTC\+?3)\s*\)?/gi, "")
    .trim();
  if (!raw) return null;

  const ruMatch = raw.match(/(\d{1,2})\.(\d{1,2})\.(\d{2,4})(?:[,\sT]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/);
  if (ruMatch) {
    let year = Number(ruMatch[3]);
    if (year < 100) year += 2000;
    const month = Number(ruMatch[2]);
    const day = Number(ruMatch[1]);
    const hour = Number(ruMatch[4] || 0);
    const minute = Number(ruMatch[5] || 0);
    const second = Number(ruMatch[6] || 0);
    const ms = Date.UTC(year, month - 1, day, hour, minute, second);
    return Number.isFinite(ms) ? ms : null;
  }

  const isoMatch = raw.match(/(\d{4})-(\d{1,2})-(\d{1,2})(?:[T\s]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/);
  if (isoMatch) {
    const ms = Date.UTC(
      Number(isoMatch[1]),
      Number(isoMatch[2]) - 1,
      Number(isoMatch[3]),
      Number(isoMatch[4] || 0),
      Number(isoMatch[5] || 0),
      Number(isoMatch[6] || 0)
    );
    return Number.isFinite(ms) ? ms : null;
  }

  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

function getItemNmckValue(item: BatchRegistryPreviewItem): number | null {
  if (typeof item.nmck_value === "number" && Number.isFinite(item.nmck_value)) {
    return item.nmck_value;
  }
  const raw = String(item.nmck_raw || "")
    .replace(/[\u00a0\s₽рубRUB]/gi, "")
    .replace(/,/g, ".")
    .replace(/\.+$/, "");
  if (!raw) return null;
  const num = Number(raw);
  return Number.isFinite(num) ? num : null;
}

export function BatchSheetSelectorModal({
  preview,
  busy,
  error,
  onConfirmSheets,
  onClose,
}: {
  preview: BatchRegistryPreviewData;
  busy: boolean;
  error: string;
  onConfirmSheets: (sheets: string[]) => void;
  onClose: () => void;
}) {
  const initialSheets =
    preview.selected_sheets && preview.selected_sheets.length > 0
      ? preview.selected_sheets
      : preview.sheet_names.slice(0, 1);
  const [chosenSheets, setChosenSheets] = useState<string[]>(initialSheets);

  const chosenSet = useMemo(() => new Set(chosenSheets), [chosenSheets]);

  function toggleSheet(name: string) {
    setChosenSheets((prev) =>
      prev.includes(name) ? prev.filter((item) => item !== name) : [...prev, name]
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-5"
      role="dialog"
      aria-modal="true"
      aria-label="Выбор вкладок Excel для анализа"
    >
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-xl max-h-[85vh] flex flex-col overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between gap-3 bg-slate-50/70">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-teal-600 text-white flex items-center justify-center shrink-0 shadow-xs">
              <FileSpreadsheet size={18} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-extrabold text-slate-900 truncate">
                Выберите вкладки таблицы
              </h3>
              <p className="text-xs text-slate-500 truncate">
                Файл: <span className="font-semibold text-slate-700">{preview.filename}</span> · Вкладок:{" "}
                <span className="font-semibold text-slate-700">{preview.sheet_names.length}</span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
            aria-label="Закрыть окно"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-5 py-3 border-b border-slate-100 bg-white flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-slate-600">
            Отметьте одну или несколько вкладок, из которых нужно загрузить закупки:
          </p>
          <div className="flex items-center gap-2 text-xs">
            <button
              type="button"
              disabled={busy}
              onClick={() => setChosenSheets([...preview.sheet_names])}
              className="px-2.5 py-1 bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200 rounded-lg font-bold transition-colors cursor-pointer"
            >
              Выбрать все
            </button>
            <button
              type="button"
              disabled={busy || chosenSheets.length === 0}
              onClick={() => setChosenSheets([])}
              className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-semibold transition-colors cursor-pointer disabled:opacity-50"
            >
              Снять все
            </button>
          </div>
        </div>

        {error ? (
          <div className="mx-5 mt-3 p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-800 flex items-center gap-2">
            <AlertTriangle size={15} className="text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}

        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-1.5">
          {preview.sheet_names.map((sheetName) => {
            const checked = chosenSet.has(sheetName);
            return (
              <label
                key={sheetName}
                className={`flex items-center gap-3 p-2.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                  checked
                    ? "bg-teal-50/70 border-teal-400 text-slate-900"
                    : "bg-white hover:bg-slate-50 border-slate-200 text-slate-700"
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={busy}
                  onChange={() => toggleSheet(sheetName)}
                  className="w-4 h-4 accent-teal-600 rounded cursor-pointer shrink-0"
                />
                <span className="truncate flex-1">{sheetName}</span>
              </label>
            );
          })}
        </div>

        <div className="px-5 py-3.5 border-t border-slate-200 bg-slate-50 flex flex-wrap items-center justify-between gap-2.5">
          <div className="text-xs text-slate-500">
            Выбрано вкладок: <strong className="text-slate-800">{chosenSheets.length}</strong>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <button
              type="button"
              disabled={busy}
              onClick={onClose}
              className="px-4 py-2 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded-xl text-xs font-bold transition-colors cursor-pointer"
            >
              Отмена
            </button>
            <button
              type="button"
              disabled={busy || chosenSheets.length === 0}
              onClick={() => onConfirmSheets(chosenSheets)}
              className="px-5 py-2 bg-gradient-to-r from-emerald-600 via-teal-600 to-teal-700 hover:from-emerald-500 hover:to-teal-600 text-white rounded-xl text-xs font-extrabold shadow-sm transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {busy ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} className="text-emerald-200" />}
              <span>{busy ? "Читаем вкладки..." : `Загрузить закупки (${chosenSheets.length})`}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function BatchSelectionModal({
  preview,
  selectedIds,
  busy,
  error,
  onToggleItem,
  onSelectAllVisible,
  onClearAll,
  onOpenSheetSelector,
  onConfirm,
  onClose,
}: {
  preview: BatchRegistryPreviewData;
  selectedIds: string[];
  busy: boolean;
  error: string;
  onToggleItem: (id: string) => void;
  onSelectAllVisible: (visibleIds: string[]) => void;
  onClearAll: () => void;
  onOpenSheetSelector?: () => void;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [sortField, setSortField] = useState<BatchSortField>("default");
  const [sortDirection, setSortDirection] = useState<BatchSortDirection>("asc");
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const activeSheets = preview.selected_sheets && preview.selected_sheets.length > 0
    ? preview.selected_sheets
    : (preview.sheet_name ? [preview.sheet_name] : []);

  function handleSortToggle(field: "deadline" | "price") {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortField(field);
    setSortDirection(field === "deadline" ? "asc" : "desc");
  }

  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    const base = !q
      ? preview.items
      : preview.items.filter(
          (it) =>
            it.notice_number.toLowerCase().includes(q) ||
            it.title.toLowerCase().includes(q) ||
            it.nmck_raw.toLowerCase().includes(q) ||
            it.deadline_date.toLowerCase().includes(q) ||
            it.procurement_type.toLowerCase().includes(q)
        );
    if (sortField === "default") {
      return base;
    }
    const copy = [...base];
    copy.sort((a, b) => {
      if (sortField === "deadline") {
        const aVal = getItemDeadlineTs(a);
        const bVal = getItemDeadlineTs(b);
        if (aVal === null && bVal === null) return (a.row_no || 0) - (b.row_no || 0);
        if (aVal === null) return 1;
        if (bVal === null) return -1;
        if (aVal !== bVal) return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
        return (a.row_no || 0) - (b.row_no || 0);
      }
      const aPrice = getItemNmckValue(a);
      const bPrice = getItemNmckValue(b);
      if (aPrice === null && bPrice === null) return (a.row_no || 0) - (b.row_no || 0);
      if (aPrice === null) return 1;
      if (bPrice === null) return -1;
      if (aPrice !== bPrice) return sortDirection === "asc" ? aPrice - bPrice : bPrice - aPrice;
      return (a.row_no || 0) - (b.row_no || 0);
    });
    return copy;
  }, [preview.items, query, sortField, sortDirection]);

  const selectedCount = selectedIds.length;
  const isFullAnalysis = preview.target_mode === "procurement_report";
  const effectiveMaxItems = Math.max(1, preview.max_items || (isFullAnalysis ? 10 : 30));
  const exceedsMaxItems = selectedCount > effectiveMaxItems;
  const totalCostKopeks = selectedCount * preview.unit_price_kopeks;
  const insufficientBalance =
    preview.unit_price_kopeks > 0 && totalCostKopeks > preview.available_kopeks;

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-5"
      role="dialog"
      aria-modal="true"
      aria-label={isFullAnalysis ? "Выбор закупок для анализа документации" : "Выбор закупок для экспресс-оценки"}
    >
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between gap-3 bg-slate-50/70">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-teal-600 text-white flex items-center justify-center shrink-0 shadow-xs">
              <FileSpreadsheet size={18} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-extrabold text-slate-900 truncate">
                {isFullAnalysis ? "Выберите закупки для анализа документации" : "Выберите закупки для экспресс-оценки"}
              </h3>
              <p className="text-xs text-slate-500 truncate">
                Источник: <span className="font-semibold text-slate-700">{preview.filename}</span> · Найдено закупок:{" "}
                <span className="font-semibold text-slate-700">{preview.items.length}</span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
            aria-label="Закрыть окно"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-5 py-3 border-b border-slate-200 bg-white flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex flex-wrap items-center gap-2 flex-1 min-w-[220px]">
            <div className="relative flex-1 min-w-[180px] max-w-sm">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
              />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Поиск по номеру или названию..."
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>
            {preview.sheet_names.length > 1 && preview.file && onOpenSheetSelector ? (
              <button
                type="button"
                disabled={busy}
                onClick={onOpenSheetSelector}
                className="px-2.5 py-1.5 text-xs bg-slate-50 hover:bg-teal-50 border border-slate-300 hover:border-teal-300 rounded-lg font-bold text-slate-800 transition-colors cursor-pointer"
                title={activeSheets.join(", ")}
              >
                Вкладки: {activeSheets.length} из {preview.sheet_names.length}
              </button>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <div className="flex items-center gap-1.5 mr-1">
              <span className="text-[11px] font-semibold text-slate-500 hidden sm:inline">
                Сортировка:
              </span>
              <button
                type="button"
                disabled={busy || filteredItems.length <= 1}
                onClick={() => handleSortToggle("deadline")}
                title={
                  sortField === "deadline"
                    ? sortDirection === "asc"
                      ? "Сначала ближайший срок подачи заявок (нажмите для обратного порядка)"
                      : "Сначала поздний срок подачи заявок (нажмите для сортировки по ближайшим)"
                    : "Сортировать по дате окончания подачи заявки"
                }
                className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg font-bold border transition-colors cursor-pointer disabled:opacity-50 ${
                  sortField === "deadline"
                    ? "bg-teal-600 text-white border-teal-600 shadow-2xs"
                    : "bg-slate-50 hover:bg-teal-50 text-slate-700 border-slate-200 hover:border-teal-300"
                }`}
              >
                {sortField === "deadline" ? (
                  sortDirection === "asc" ? <ArrowUp size={13} /> : <ArrowDown size={13} />
                ) : (
                  <ArrowUpDown size={13} />
                )}
                <span>По дате окончания</span>
              </button>
              <button
                type="button"
                disabled={busy || filteredItems.length <= 1}
                onClick={() => handleSortToggle("price")}
                title={
                  sortField === "price"
                    ? sortDirection === "desc"
                      ? "Сначала самая высокая цена (нажмите для сортировки по возрастанию)"
                      : "Сначала самая низкая цена (нажмите для сортировки по убыванию)"
                    : "Сортировать по цене (НМЦК)"
                }
                className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg font-bold border transition-colors cursor-pointer disabled:opacity-50 ${
                  sortField === "price"
                    ? "bg-teal-600 text-white border-teal-600 shadow-2xs"
                    : "bg-slate-50 hover:bg-teal-50 text-slate-700 border-slate-200 hover:border-teal-300"
                }`}
              >
                {sortField === "price" ? (
                  sortDirection === "asc" ? <ArrowUp size={13} /> : <ArrowDown size={13} />
                ) : (
                  <ArrowUpDown size={13} />
                )}
                <span>По цене</span>
              </button>
              {sortField !== "default" ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setSortField("default")}
                  title="Вернуть исходный порядок строк"
                  className="px-2 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg font-semibold transition-colors cursor-pointer"
                >
                  Сброс
                </button>
              ) : null}
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => onSelectAllVisible(filteredItems.map((it) => it.id))}
              className="px-2.5 py-1.5 bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200 rounded-lg font-bold transition-colors cursor-pointer"
            >
              Выбрать все ({filteredItems.length})
            </button>
            <button
              type="button"
              disabled={busy || selectedCount === 0}
              onClick={onClearAll}
              className="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-semibold transition-colors cursor-pointer disabled:opacity-50"
            >
              Снять все
            </button>
          </div>
        </div>

        {error ? (
          <div className="mx-5 mt-3 p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-800 flex items-center gap-2">
            <AlertTriangle size={15} className="text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}

        <div className="flex-1 overflow-y-auto px-5 py-3">
          {filteredItems.length === 0 ? (
            <div className="py-12 text-center text-sm text-slate-500">
              На этом листе не найдено подходящих строк закупок.
            </div>
          ) : (
            <div className="border border-slate-200 rounded-xl overflow-hidden">
              <table className="w-full text-left border-collapse text-xs">
                <thead className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200 sticky top-0 z-10">
                  <tr>
                    <th className="w-10 px-3 py-2.5 text-center">✓</th>
                    <th className="px-3 py-2.5 w-44">Номер извещения</th>
                    <th className="px-3 py-2.5">Наименование закупки</th>
                    <th className="px-3 py-2.5 w-32 text-right">
                      <button
                        type="button"
                        onClick={() => handleSortToggle("price")}
                        className="inline-flex items-center justify-end gap-1 w-full hover:text-teal-700 transition-colors cursor-pointer"
                      >
                        <span>НМЦК</span>
                        {sortField === "price" ? (
                          sortDirection === "asc" ? <ArrowUp size={12} className="text-teal-700" /> : <ArrowDown size={12} className="text-teal-700" />
                        ) : (
                          <ArrowUpDown size={12} className="text-slate-400" />
                        )}
                      </button>
                    </th>
                    <th className="px-3 py-2.5 w-40">
                      <button
                        type="button"
                        onClick={() => handleSortToggle("deadline")}
                        className="inline-flex items-center gap-1 hover:text-teal-700 transition-colors cursor-pointer"
                      >
                        <span>Окончание подачи</span>
                        {sortField === "deadline" ? (
                          sortDirection === "asc" ? <ArrowUp size={12} className="text-teal-700" /> : <ArrowDown size={12} className="text-teal-700" />
                        ) : (
                          <ArrowUpDown size={12} className="text-slate-400" />
                        )}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200/80 bg-white">
                  {filteredItems.map((item) => {
                    const checked = selectedSet.has(item.id);
                    return (
                      <tr
                        key={item.id}
                        onClick={() => !busy && onToggleItem(item.id)}
                        className={`cursor-pointer transition-colors ${
                          checked ? "bg-teal-50/45 hover:bg-teal-50/80" : "hover:bg-slate-50"
                        }`}
                      >
                        <td className="px-3 py-2.5 text-center align-top">
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={busy}
                            onChange={() => onToggleItem(item.id)}
                            onClick={(e) => e.stopPropagation()}
                            className="w-4 h-4 accent-teal-600 rounded cursor-pointer mt-0.5"
                          />
                        </td>
                        <td className="px-3 py-2.5 align-top">
                          <div className="font-mono font-bold text-slate-900 break-all">
                            {item.notice_number}
                          </div>
                          <div className="flex flex-wrap items-center gap-1 mt-1">
                            {item.procurement_type ? (
                              <span className="inline-block px-1.5 py-0.5 text-[10px] font-semibold rounded bg-slate-100 text-slate-600 border border-slate-200">
                                {item.procurement_type}
                              </span>
                            ) : null}
                            {safeHttpUrl(item.kontur_url) ? (
                              <a
                                href={safeHttpUrl(item.kontur_url)!}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-bold rounded bg-sky-50 hover:bg-sky-100 text-sky-800 border border-sky-200 transition-colors"
                                title="Открыть закупку в Контур.Закупки"
                              >
                                <span>Контур</span>
                                <ExternalLink size={9} aria-hidden="true" />
                              </a>
                            ) : null}
                            {activeSheets.length > 1 && item.sheet_name ? (
                              <span className="inline-block px-1.5 py-0.5 text-[10px] font-medium rounded bg-teal-50 text-teal-800 border border-teal-200">
                                {item.sheet_name}
                              </span>
                            ) : null}
                          </div>
                        </td>
                        <td className="px-3 py-2.5 align-top text-slate-800 font-medium leading-snug">
                          {item.title && item.title !== `Закупка ${item.notice_number}` ? (
                            item.title
                          ) : (
                            <span className="text-slate-400 italic font-normal">
                              Без названия (определим по документации)
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 align-top text-right font-bold text-slate-900 whitespace-nowrap">
                          {item.nmck_raw || "—"}
                        </td>
                        <td className="px-3 py-2.5 align-top text-slate-600 whitespace-nowrap">
                          <div>{item.deadline_date || "—"}</div>
                          {item.publication_date ? (
                            <div className="text-[10px] text-slate-400 mt-0.5">
                              публ. {item.publication_date}
                            </div>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="px-5 py-3.5 border-t border-slate-200 bg-slate-50 flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs text-slate-700 space-y-0.5">
            <div>
              Выбрано закупок: <strong className="text-slate-900">{selectedCount}</strong> из{" "}
              {preview.items.length}
              {preview.unit_price_kopeks > 0 ? (
                <>
                  {" "}
                  · К оплате:{" "}
                  <strong className="text-teal-800">{formatRub(totalCostKopeks)}</strong> (
                  {formatRub(preview.unit_price_kopeks)} за закупку)
                </>
              ) : null}
            </div>
            {insufficientBalance ? (
              <div className="text-rose-700 font-bold">
                Недостаточно средств на балансе (доступно {formatRub(preview.available_kopeks)}). Уменьшите выбор или пополните счёт.
              </div>
            ) : exceedsMaxItems ? (
              <div className="text-rose-700 font-bold">
                За один запуск можно выбрать до {effectiveMaxItems} закупок (сейчас выбрано {selectedCount}).
              </div>
            ) : (
              <div className="text-[11px] text-slate-500">
                {isFullAnalysis
                  ? `По каждой выбранной закупке создастся отдельная задача полного анализа (со всеми кнопками: Запрос КП, отчёты). Если площадка не отдаст документацию — плата вернётся. Лимит за запуск: до ${effectiveMaxItems} зак.`
                  : `Если по какой-то закупке площадка не отдаст документацию — плата за неё не спишется. Лимит за запуск: до ${effectiveMaxItems} зак.`}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2.5 ml-auto">
            <button
              type="button"
              disabled={busy}
              onClick={onClose}
              className="px-4 py-2 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded-xl text-xs font-bold transition-colors cursor-pointer"
            >
              Отмена
            </button>
            <button
              type="button"
              disabled={busy || selectedCount === 0 || exceedsMaxItems || insufficientBalance}
              onClick={onConfirm}
              className="px-5 py-2 bg-gradient-to-r from-emerald-600 via-teal-600 to-teal-700 hover:from-emerald-500 hover:to-teal-600 text-white rounded-xl text-xs sm:text-sm font-extrabold shadow-sm transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {busy ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Sparkles size={15} className="text-emerald-200" />
              )}
              <span>{isFullAnalysis ? `Запустить анализ (${selectedCount})` : `Запустить оценку (${selectedCount})`}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

type WindowRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type ResizeDirection = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

export function BatchResultsReaderModal({
  data,
  activeIndex,
  onSelectIndex,
  onDownloadItemDocx,
  onDownloadAllZip,
  onOpenDetailedAnalysis,
  onClose,
}: {
  data: BatchReportReaderData;
  activeIndex: number;
  onSelectIndex: (idx: number) => void;
  onDownloadItemDocx: (jobId: string, itemIndex: number, filename: string) => void;
  onDownloadAllZip: (jobId: string) => void;
  onOpenDetailedAnalysis?: (noticeNumber: string) => void;
  onClose: () => void;
}) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [copiedSpecsIdx, setCopiedSpecsIdx] = useState<number | null>(null);
  const [copiedEmailIdx, setCopiedEmailIdx] = useState<number | null>(null);
  const [previewCopyBlock, setPreviewCopyBlock] = useState<"specs" | "email" | null>(null);
  const [sidebarSort, setSidebarSort] = useState<"default" | "margin_pct" | "margin_rub">("default");
  const [isMaximized, setIsMaximized] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);
  const [winRect, setWinRect] = useState<WindowRect | null>(null);
  const interactionRef = useRef<
    | {
        mode: "drag";
        startX: number;
        startY: number;
        origRect: WindowRect;
      }
    | {
        mode: "resize";
        dir: ResizeDirection;
        startX: number;
        startY: number;
        origRect: WindowRect;
      }
    | null
  >(null);

  const safeIdx = activeIndex >= 0 && activeIndex < data.items.length ? activeIndex : 0;
  const activeItem = data.items[safeIdx] || null;
  const isSingle = data.items.length <= 1;

  const hasMarginData = useMemo(
    () =>
      data.items.filter(
        (it) =>
          typeof it.margin_pct_value === "number" ||
          typeof it.margin_rub_value === "number"
      ).length >= 2,
    [data.items]
  );

  const orderedSidebarEntries = useMemo(() => {
    const entries = data.items.map((item, rawIdx) => ({ item, rawIdx }));
    if (sidebarSort === "default") return entries;
    return [...entries].sort((a, b) => {
      const aVal =
        sidebarSort === "margin_pct"
          ? a.item.margin_pct_value
          : a.item.margin_rub_value;
      const bVal =
        sidebarSort === "margin_pct"
          ? b.item.margin_pct_value
          : b.item.margin_rub_value;
      const aNum = typeof aVal === "number" && Number.isFinite(aVal) ? aVal : null;
      const bNum = typeof bVal === "number" && Number.isFinite(bVal) ? bVal : null;
      if (aNum === null && bNum === null) return a.rawIdx - b.rawIdx;
      if (aNum === null) return 1;
      if (bNum === null) return -1;
      if (bNum !== aNum) return bNum - aNum;
      return a.rawIdx - b.rawIdx;
    });
  }, [data.items, sidebarSort]);

  useEffect(() => {
    setPreviewCopyBlock(null);
  }, [safeIdx, data.job_id]);

  useEffect(() => {
    const computeInitial = (): WindowRect => {
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const width = Math.min(vw - 32, 1360);
      const height = Math.min(vh - 32, Math.max(520, Math.round(vh * 0.9)));
      return {
        x: Math.max(16, Math.round((vw - width) / 2)),
        y: Math.max(16, Math.round((vh - height) / 2)),
        width,
        height,
      };
    };

    const syncViewport = () => {
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const desktop = vw >= 640;
      setIsDesktop(desktop);
      if (!desktop) return;
      setWinRect((prev) => {
        if (!prev) return computeInitial();
        const width = Math.min(prev.width, vw - 16);
        const height = Math.min(prev.height, vh - 16);
        const x = Math.min(Math.max(prev.x, -(width - 160)), vw - 160);
        const y = Math.min(Math.max(prev.y, 8), vh - 64);
        return { x, y, width, height };
      });
    };

    syncViewport();
    window.addEventListener("resize", syncViewport);
    return () => window.removeEventListener("resize", syncViewport);
  }, []);

  useEffect(() => {
    const onPointerMove = (e: PointerEvent) => {
      const act = interactionRef.current;
      if (!act) return;
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const dx = e.clientX - act.startX;
      const dy = e.clientY - act.startY;
      const minW = Math.min(540, vw - 24);
      const minH = Math.min(380, vh - 24);

      if (act.mode === "drag") {
        const nextX = Math.min(
          Math.max(act.origRect.x + dx, -(act.origRect.width - 160)),
          vw - 160
        );
        const nextY = Math.min(Math.max(act.origRect.y + dy, 8), vh - 64);
        setWinRect({
          ...act.origRect,
          x: nextX,
          y: nextY,
        });
        return;
      }

      let { x, y, width, height } = act.origRect;
      const rightEdge = act.origRect.x + act.origRect.width;
      const bottomEdge = act.origRect.y + act.origRect.height;

      if (act.dir.includes("e")) {
        const maxW = vw - act.origRect.x - 8;
        width = Math.max(minW, Math.min(maxW, act.origRect.width + dx));
      }
      if (act.dir.includes("s")) {
        const maxH = vh - act.origRect.y - 8;
        height = Math.max(minH, Math.min(maxH, act.origRect.height + dy));
      }
      if (act.dir.includes("w")) {
        const nextLeft = Math.max(8, Math.min(rightEdge - minW, act.origRect.x + dx));
        width = rightEdge - nextLeft;
        x = nextLeft;
      }
      if (act.dir.includes("n")) {
        const nextTop = Math.max(8, Math.min(bottomEdge - minH, act.origRect.y + dy));
        height = bottomEdge - nextTop;
        y = nextTop;
      }

      setWinRect({ x, y, width, height });
    };

    const onPointerUp = () => {
      if (interactionRef.current) {
        interactionRef.current = null;
        document.body.style.userSelect = "";
      }
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      document.body.style.userSelect = "";
    };
  }, []);

  function startDrag(e: React.PointerEvent<HTMLDivElement>) {
    if (!isDesktop || isMaximized || !winRect || e.button !== 0) return;
    if ((e.target as HTMLElement).closest("button, a, input, select, textarea")) return;
    e.preventDefault();
    document.body.style.userSelect = "none";
    interactionRef.current = {
      mode: "drag",
      startX: e.clientX,
      startY: e.clientY,
      origRect: winRect,
    };
  }

  function startResize(dir: ResizeDirection, e: React.PointerEvent<HTMLDivElement>) {
    if (!isDesktop || isMaximized || !winRect || e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    document.body.style.userSelect = "none";
    interactionRef.current = {
      mode: "resize",
      dir,
      startX: e.clientX,
      startY: e.clientY,
      origRect: winRect,
    };
  }

  function copyMarkdown(item: BatchReportResultItem) {
    if (!item.report_markdown) return;
    void copyTextReliable(item.report_markdown).then((ok) => {
      if (!ok) return;
      setCopiedIdx(item.index);
      setTimeout(() => setCopiedIdx(null), 2000);
    });
  }

  function copySpecs(item: BatchReportResultItem) {
    const text = String(item.copy_specs_text || "").trim();
    if (!text) return;
    void copyTextReliable(text).then((ok) => {
      if (!ok) return;
      setCopiedSpecsIdx(item.index);
      setTimeout(() => setCopiedSpecsIdx(null), 2400);
    });
  }

  function copySupplierEmail(item: BatchReportResultItem) {
    const text = String(item.copy_supplier_email_text || "").trim();
    if (!text) return;
    void copyTextReliable(text).then((ok) => {
      if (!ok) return;
      setCopiedEmailIdx(item.index);
      setTimeout(() => setCopiedEmailIdx(null), 2400);
    });
  }

  const dialogStyle: React.CSSProperties | undefined = isMaximized
    ? {
        position: "fixed",
        left: 10,
        top: 10,
        width: "calc(100vw - 20px)",
        height: "calc(100vh - 20px)",
        maxWidth: "none",
      }
    : isDesktop && winRect
    ? {
        position: "fixed",
        left: winRect.x,
        top: winRect.y,
        width: winRect.width,
        height: winRect.height,
        maxWidth: "none",
      }
    : undefined;

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/65 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Результаты анализа закупок"
    >
      <div
        style={dialogStyle}
        className="relative bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-7xl h-[92vh] flex flex-col overflow-hidden"
      >
        {isDesktop && !isMaximized ? (
          <>
            <div
              onPointerDown={(e) => startResize("n", e)}
              className="absolute top-0 left-3 right-3 h-1.5 cursor-ns-resize z-30"
              aria-hidden="true"
            />
            <div
              onPointerDown={(e) => startResize("s", e)}
              className="absolute bottom-0 left-3 right-3 h-2 cursor-ns-resize z-30"
              aria-hidden="true"
            />
            <div
              onPointerDown={(e) => startResize("w", e)}
              className="absolute left-0 top-3 bottom-3 w-2 cursor-ew-resize z-30"
              aria-hidden="true"
            />
            <div
              onPointerDown={(e) => startResize("e", e)}
              className="absolute right-0 top-3 bottom-3 w-2 cursor-ew-resize z-30"
              aria-hidden="true"
            />
            <div
              onPointerDown={(e) => startResize("nw", e)}
              className="absolute top-0 left-0 w-3.5 h-3.5 cursor-nwse-resize z-40"
              aria-hidden="true"
            />
            <div
              onPointerDown={(e) => startResize("ne", e)}
              className="absolute top-0 right-0 w-3.5 h-3.5 cursor-nesw-resize z-40"
              aria-hidden="true"
            />
            <div
              onPointerDown={(e) => startResize("sw", e)}
              className="absolute bottom-0 left-0 w-3.5 h-3.5 cursor-nesw-resize z-40"
              aria-hidden="true"
            />
            <div
              onPointerDown={(e) => startResize("se", e)}
              title="Потяните, чтобы изменить размер окна по диагонали"
              className="absolute bottom-0 right-0 w-5 h-5 cursor-nwse-resize z-40 flex items-end justify-end p-1 text-slate-400 hover:text-teal-700 transition-colors"
              aria-label="Изменить размер окна по диагонали"
            >
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none" aria-hidden="true">
                <path
                  d="M10 1L1 10M10 5L5 10M10 9L9 10"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </div>
          </>
        ) : null}

        <div
          onPointerDown={startDrag}
          onDoubleClick={(e) => {
            if (!(e.target as HTMLElement).closest("button, a")) {
              setIsMaximized((prev) => !prev);
            }
          }}
          title={
            isDesktop && !isMaximized
              ? "Перетащите заголовок для перемещения окна; двойной клик — на весь экран"
              : undefined
          }
          className={`px-5 py-3.5 border-b border-slate-200 bg-slate-50 flex flex-wrap items-center justify-between gap-3 ${
            isDesktop && !isMaximized ? "cursor-grab active:cursor-grabbing select-none" : ""
          }`}
        >
          <div className="min-w-0 flex items-center gap-2.5 flex-1">
            {isDesktop && !isMaximized ? (
              <Move size={15} className="text-slate-400 shrink-0" aria-hidden="true" />
            ) : null}
            <div className="min-w-0">
              <h3 className="text-sm sm:text-base font-extrabold text-slate-900 truncate">
                {data.title}
              </h3>
              <p className="text-xs text-slate-500">
                Готово: <strong className="text-emerald-700">{data.completed_count}</strong> из{" "}
                {data.total_count}
                {data.failed_count > 0 ? ` · Без документации: ${data.failed_count}` : ""}
                {data.status === "running" || data.status === "pending"
                  ? " · Обработка продолжается..."
                  : ""}
                {isDesktop && !isMaximized ? " · Можно перетаскивать и растягивать за края/углы" : ""}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5 ml-auto shrink-0">
            {data.completed_count > 1 && data.status === "completed" ? (
              <button
                type="button"
                onClick={() => onDownloadAllZip(data.job_id)}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-xs font-bold shadow-2xs transition-colors cursor-pointer"
              >
                <Download size={14} />
                <span>Скачать все (.zip)</span>
              </button>
            ) : null}
            {isDesktop ? (
              <button
                type="button"
                onClick={() => setIsMaximized((prev) => !prev)}
                className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 transition-colors cursor-pointer"
                title={isMaximized ? "Обычный размер окна" : "Развернуть на весь экран"}
                aria-label={isMaximized ? "Обычный размер окна" : "Развернуть на весь экран"}
              >
                {isMaximized ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              </button>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
              aria-label="Закрыть окно"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="flex-1 flex flex-col md:flex-row min-h-0 min-w-0 overflow-hidden">
          {!isSingle ? (
            <aside className="w-full md:w-80 shrink-0 border-b md:border-b-0 md:border-r border-slate-200 bg-slate-50/60 overflow-y-auto max-h-56 md:max-h-none p-2.5 space-y-1.5">
              {hasMarginData ? (
                <div className="flex items-center justify-between gap-1 px-1 pb-1.5 mb-1 border-b border-slate-200/80">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1">
                    <TrendingUp size={11} className="text-teal-600" aria-hidden="true" />
                    <span>Приоритет</span>
                  </span>
                  <div className="flex items-center gap-1">
                    {(
                      [
                        { id: "default", label: "№" },
                        { id: "margin_pct", label: "Маржа %" },
                        { id: "margin_rub", label: "Маржа ₽" },
                      ] as const
                    ).map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => setSidebarSort(opt.id)}
                        className={`px-2 py-0.5 rounded-md text-[10px] font-bold border transition-colors cursor-pointer ${
                          sidebarSort === opt.id
                            ? "bg-teal-600 text-white border-teal-600 shadow-2xs"
                            : "bg-white hover:bg-teal-50 text-slate-600 border-slate-200"
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
              {orderedSidebarEntries.map(({ item, rawIdx }) => {
                const isSelected = rawIdx === safeIdx;
                const marginBadge = getMarginBadgeStyle(item);
                return (
                  <button
                    key={item.id || rawIdx}
                    type="button"
                    onClick={() => onSelectIndex(rawIdx)}
                    className={`w-full text-left p-2.5 rounded-xl border transition-all cursor-pointer flex items-start gap-2.5 ${
                      isSelected
                        ? "bg-white border-teal-500 ring-2 ring-teal-500/20 shadow-xs"
                        : "bg-white/70 hover:bg-white border-slate-200/80"
                    }`}
                  >
                    <div className="mt-0.5 shrink-0">
                      {item.status === "completed" ? (
                        <CheckCircle2 size={15} className="text-emerald-600" />
                      ) : item.status === "failed" ? (
                        <AlertTriangle size={15} className="text-amber-600" />
                      ) : item.status === "running" ? (
                        <Loader2 size={15} className="text-teal-600 animate-spin" />
                      ) : (
                        <Clock3 size={15} className="text-slate-400" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-1">
                        <span className="font-mono text-[11px] font-bold text-slate-900 truncate">
                          № {item.notice_number}
                        </span>
                        {item.nmck_raw ? (
                          <span className="text-[11px] font-bold text-teal-800 shrink-0">
                            {item.nmck_raw}
                          </span>
                        ) : null}
                      </div>
                      <div className="text-xs text-slate-700 line-clamp-2 mt-0.5 leading-snug">
                        {item.title}
                      </div>
                      {marginBadge ? (
                        <div className="mt-1.5 flex items-center gap-1">
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[11px] font-extrabold leading-tight ${marginBadge.classes}`}
                          >
                            {marginBadge.label}
                          </span>
                        </div>
                      ) : null}
                    </div>
                  </button>
                );
              })}
            </aside>
          ) : null}

          <main className="flex-1 min-w-0 overflow-y-auto overflow-x-auto p-4 sm:p-6 bg-slate-50/75">
            {activeItem ? (
              (() => {
                const activeMargin = getMarginBadgeStyle(activeItem);
                const konturHref = safeHttpUrl(activeItem.kontur_url);
                const eisHref = safeHttpUrl(activeItem.eis_url);
                const etpHref = safeHttpUrl(activeItem.etp_url);
                const showFallbackVerdictBanner =
                  activeItem.status === "completed" &&
                  Boolean(activeItem.verdict_text) &&
                  !activeItem.verdict_is_at_top;
                const hasCopySpecs = Boolean(String(activeItem.copy_specs_text || "").trim());
                const hasCopyEmail = Boolean(String(activeItem.copy_supplier_email_text || "").trim());

                return (
                  <div className="min-w-0">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4 mb-4 shadow-2xs flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 mb-1.5">
                          {activeItem.notice_number ? (
                            <span className="px-2 py-0.5 bg-slate-100 text-slate-800 font-mono font-bold rounded-md">
                              Извещение № {activeItem.notice_number}
                            </span>
                          ) : null}
                          {activeItem.nmck_raw ? (
                            <span className="px-2 py-0.5 bg-teal-50 text-teal-800 font-bold rounded-md border border-teal-200">
                              НМЦК: {activeItem.nmck_raw}
                            </span>
                          ) : null}
                          {activeMargin ? (
                            <span
                              className={`px-2 py-0.5 font-extrabold rounded-md border ${activeMargin.classes}`}
                            >
                              {activeMargin.label}
                            </span>
                          ) : null}
                          {konturHref ? (
                            <a
                              href={konturHref}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-sky-50 hover:bg-sky-100 text-sky-800 font-bold rounded-md border border-sky-200 hover:border-sky-300 transition-colors"
                            >
                              <span>Контур.Закупки</span>
                              <ExternalLink size={11} aria-hidden="true" />
                            </a>
                          ) : null}
                          {eisHref ? (
                            <a
                              href={eisHref}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-50 hover:bg-slate-100 text-slate-700 font-semibold rounded-md border border-slate-200 transition-colors"
                            >
                              <span>ЕИС</span>
                              <ExternalLink size={11} aria-hidden="true" />
                            </a>
                          ) : null}
                          {!konturHref && !eisHref && etpHref ? (
                            <a
                              href={etpHref}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-50 hover:bg-slate-100 text-slate-700 font-semibold rounded-md border border-slate-200 transition-colors"
                            >
                              <span>Площадка</span>
                              <ExternalLink size={11} aria-hidden="true" />
                            </a>
                          ) : null}
                          {activeItem.deadline_date ? (
                            <span>Подача до: {activeItem.deadline_date}</span>
                          ) : null}
                        </div>
                        <h4 className="text-sm sm:text-base font-extrabold text-slate-900 leading-snug">
                          {activeItem.title}
                        </h4>
                      </div>

                      {activeItem.status === "completed" ? (
                        <div className="flex flex-wrap items-center gap-2 shrink-0">
                          {onOpenDetailedAnalysis && activeItem.notice_number ? (
                            <button
                              type="button"
                              onClick={() => onOpenDetailedAnalysis(activeItem.notice_number)}
                              title="Перенести номер закупки в полный «Анализ документации» (полное ТЗ, нацрежим и готовый запрос КП)"
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#174b3f] hover:bg-[#113930] text-white rounded-lg text-xs font-bold shadow-2xs transition-colors cursor-pointer"
                            >
                              <Sparkles size={13} className="text-emerald-200" />
                              <span>Разобрать детально</span>
                            </button>
                          ) : null}
                          <button
                            type="button"
                            onClick={() => copyMarkdown(activeItem)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                          >
                            {copiedIdx === activeItem.index ? (
                              <>
                                <Check size={13} className="text-emerald-600" />
                                <span>Скопировано</span>
                              </>
                            ) : (
                              <>
                                <Copy size={13} />
                                <span>Копировать</span>
                              </>
                            )}
                          </button>
                          {activeItem.docx_filename ? (
                            <button
                              type="button"
                              onClick={() =>
                                onDownloadItemDocx(
                                  data.job_id,
                                  activeItem.index,
                                  activeItem.docx_filename
                                )
                              }
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-teal-50 text-teal-800 border border-teal-300 rounded-lg text-xs font-bold transition-colors cursor-pointer"
                            >
                              <FileText size={13} />
                              <span>Скачать Word</span>
                            </button>
                          ) : null}
                        </div>
                      ) : null}
                    </div>

                    {showFallbackVerdictBanner ? (
                      <div
                        className={`rounded-2xl border p-4 mb-4 shadow-2xs ${
                          activeMargin?.isLoss
                            ? "border-rose-200 bg-rose-50/75"
                            : "border-emerald-200 bg-emerald-50/75"
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                          <div className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wide text-slate-900">
                            {activeMargin?.isLoss ? (
                              <AlertTriangle size={15} className="text-rose-600 shrink-0" />
                            ) : (
                              <CheckCircle2 size={15} className="text-emerald-700 shrink-0" />
                            )}
                            <span>Итоговый вердикт и финансовый результат</span>
                          </div>
                          {activeMargin ? (
                            <span
                              className={`px-2.5 py-0.5 rounded-full border text-xs font-extrabold ${activeMargin.classes}`}
                            >
                              {activeMargin.label}
                            </span>
                          ) : null}
                        </div>
                        <p className="text-[13px] text-slate-800 leading-relaxed">
                          {activeItem.verdict_text}
                        </p>
                      </div>
                    ) : null}

                    {activeItem.status === "completed" && activeItem.report_markdown ? (
                      <>
                        <SafeMarkdownView markdown={activeItem.report_markdown} />

                        {hasCopySpecs || hasCopyEmail ? (
                          <div className="mt-5 rounded-2xl border border-teal-200/90 bg-white p-4 shadow-2xs space-y-3">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div>
                                <div className="text-xs sm:text-sm font-extrabold text-slate-900">
                                  Быстрое копирование для работы с поставщиками
                                </div>
                                <div className="text-[11px] text-slate-500">
                                  В один клик скопируйте ключевые требования ТЗ или готовое письмо для отправки на почту
                                </div>
                              </div>
                            </div>
                            <div className="flex flex-wrap items-center gap-2.5">
                              {hasCopySpecs ? (
                                <div className="inline-flex items-center rounded-xl overflow-hidden border border-slate-300 bg-white shadow-2xs">
                                  <button
                                    type="button"
                                    onClick={() => copySpecs(activeItem)}
                                    className={`inline-flex items-center gap-2 px-3.5 py-2 text-xs font-bold transition-colors cursor-pointer ${
                                      copiedSpecsIdx === activeItem.index
                                        ? "bg-emerald-600 text-white"
                                        : "bg-slate-50 hover:bg-teal-50 text-slate-900"
                                    }`}
                                  >
                                    {copiedSpecsIdx === activeItem.index ? (
                                      <>
                                        <Check size={14} />
                                        <span>Характеристики скопированы</span>
                                      </>
                                    ) : (
                                      <>
                                        <ClipboardList size={14} className="text-teal-700" />
                                        <span>Скопировать тех. характеристики</span>
                                      </>
                                    )}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setPreviewCopyBlock((prev) => (prev === "specs" ? null : "specs"))
                                    }
                                    className="px-2.5 py-2 text-[11px] font-semibold text-slate-500 hover:text-slate-900 hover:bg-slate-100 border-l border-slate-200 transition-colors cursor-pointer"
                                    title="Показать или скрыть текст характеристик"
                                  >
                                    {previewCopyBlock === "specs" ? "Скрыть" : "Текст"}
                                  </button>
                                </div>
                              ) : null}

                              {hasCopyEmail ? (
                                <div className="inline-flex items-center rounded-xl overflow-hidden border border-teal-500 bg-white shadow-2xs">
                                  <button
                                    type="button"
                                    onClick={() => copySupplierEmail(activeItem)}
                                    className={`inline-flex items-center gap-2 px-3.5 py-2 text-xs font-bold transition-colors cursor-pointer ${
                                      copiedEmailIdx === activeItem.index
                                        ? "bg-emerald-600 text-white"
                                        : "bg-teal-600 hover:bg-teal-700 text-white"
                                    }`}
                                  >
                                    {copiedEmailIdx === activeItem.index ? (
                                      <>
                                        <Check size={14} />
                                        <span>Письмо скопировано</span>
                                      </>
                                    ) : (
                                      <>
                                        <Mail size={14} />
                                        <span>Скопировать письмо поставщику</span>
                                      </>
                                    )}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setPreviewCopyBlock((prev) => (prev === "email" ? null : "email"))
                                    }
                                    className="px-2.5 py-2 text-[11px] font-semibold text-teal-800 hover:bg-teal-50 border-l border-teal-200 transition-colors cursor-pointer"
                                    title="Показать или скрыть текст письма"
                                  >
                                    {previewCopyBlock === "email" ? "Скрыть" : "Текст"}
                                  </button>
                                </div>
                              ) : null}
                            </div>

                            {previewCopyBlock ? (
                              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                                <div className="text-[11px] font-bold text-slate-600 mb-1.5">
                                  {previewCopyBlock === "specs"
                                    ? "Текст технических характеристик для копирования:"
                                    : "Готовое письмо производителю / поставщику:"}
                                </div>
                                <pre className="whitespace-pre-wrap font-sans text-xs text-slate-800 leading-relaxed max-h-64 overflow-y-auto">
                                  {previewCopyBlock === "specs"
                                    ? activeItem.copy_specs_text
                                    : activeItem.copy_supplier_email_text}
                                </pre>
                              </div>
                            ) : null}
                          </div>
                        ) : null}

                        {activeItem.sources && activeItem.sources.length > 0 ? (
                          <div className="mt-6 pt-4 border-t border-slate-200">
                            <div className="text-xs font-bold text-slate-600 mb-2">
                              Проверенные страницы товаров и поставщиков из поиска Google:
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {activeItem.sources.map((src, sIdx) => (
                                <a
                                  key={`${src.url}-${sIdx}`}
                                  href={src.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-50 hover:bg-teal-50 text-teal-800 border border-slate-200 hover:border-teal-300 rounded-lg text-xs font-semibold transition-colors"
                                >
                                  <span className="truncate max-w-[240px]">{src.title}</span>
                                  <ExternalLink size={11} className="shrink-0" />
                                </a>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </>
                    ) : activeItem.status === "failed" ? (
                      <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 space-y-1">
                        <div className="font-bold flex items-center gap-1.5">
                          <AlertTriangle size={15} className="text-amber-700" />
                          <span>Документация по этой закупке недоступна</span>
                        </div>
                        <p>{activeItem.error || "Не удалось автоматически получить файлы с площадки. Плата за эту закупку не списана."}</p>
                      </div>
                    ) : (
                      <div className="py-16 flex flex-col items-center justify-center text-slate-500 gap-3">
                        <Loader2 size={26} className="animate-spin text-teal-600" />
                        <p className="text-xs font-medium">
                          Выгружаем документацию и готовим расчёт модели по этой закупке...
                        </p>
                      </div>
                    )}
                  </div>
                );
              })()
            ) : null}
          </main>
        </div>
      </div>
    </div>
  );
}
