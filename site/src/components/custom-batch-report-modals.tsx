"use client";

import React, { useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock3,
  Copy,
  Download,
  ExternalLink,
  FileSpreadsheet,
  FileText,
  Loader2,
  Search,
  Sparkles,
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
  procurement_type: string;
  eis_url: string;
  etp_url: string;
  customer_inn: string;
  customer_name: string;
};

export type BatchRegistryPreviewData = {
  file: File | null;
  filename: string;
  sheet_name: string;
  sheet_names: string[];
  selected_sheets?: string[];
  requires_sheet_selection?: boolean;
  items: BatchRegistryPreviewItem[];
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
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const activeSheets = preview.selected_sheets && preview.selected_sheets.length > 0
    ? preview.selected_sheets
    : (preview.sheet_name ? [preview.sheet_name] : []);

  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return preview.items;
    return preview.items.filter(
      (it) =>
        it.notice_number.toLowerCase().includes(q) ||
        it.title.toLowerCase().includes(q) ||
        it.nmck_raw.toLowerCase().includes(q) ||
        it.procurement_type.toLowerCase().includes(q)
    );
  }, [preview.items, query]);

  const selectedCount = selectedIds.length;
  const totalCostKopeks = selectedCount * preview.unit_price_kopeks;
  const insufficientBalance =
    preview.unit_price_kopeks > 0 && totalCostKopeks > preview.available_kopeks;

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-5"
      role="dialog"
      aria-modal="true"
      aria-label="Выбор закупок для массового анализа"
    >
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between gap-3 bg-slate-50/70">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-teal-600 text-white flex items-center justify-center shrink-0 shadow-xs">
              <FileSpreadsheet size={18} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-extrabold text-slate-900 truncate">
                Выберите закупки для анализа
              </h3>
              <p className="text-xs text-slate-500 truncate">
                Файл: <span className="font-semibold text-slate-700">{preview.filename}</span> · Найдено закупок:{" "}
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

          <div className="flex items-center gap-2 text-xs">
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
                    <th className="px-3 py-2.5 w-32 text-right">НМЦК</th>
                    <th className="px-3 py-2.5 w-36">Срок приёма заявок</th>
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
            ) : (
              <div className="text-[11px] text-slate-500">
                Если по какой-то закупке площадка не отдаст документацию — плата за неё не спишется.
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
              disabled={busy || selectedCount === 0 || selectedCount > 60 || insufficientBalance}
              onClick={onConfirm}
              className="px-5 py-2 bg-gradient-to-r from-emerald-600 via-teal-600 to-teal-700 hover:from-emerald-500 hover:to-teal-600 text-white rounded-xl text-xs sm:text-sm font-extrabold shadow-sm transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {busy ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Sparkles size={15} className="text-emerald-200" />
              )}
              <span>Запустить анализ ({selectedCount})</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function BatchResultsReaderModal({
  data,
  activeIndex,
  onSelectIndex,
  onDownloadItemDocx,
  onDownloadAllZip,
  onClose,
}: {
  data: BatchReportReaderData;
  activeIndex: number;
  onSelectIndex: (idx: number) => void;
  onDownloadItemDocx: (jobId: string, itemIndex: number, filename: string) => void;
  onDownloadAllZip: (jobId: string) => void;
  onClose: () => void;
}) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const safeIdx = activeIndex >= 0 && activeIndex < data.items.length ? activeIndex : 0;
  const activeItem = data.items[safeIdx] || null;
  const isSingle = data.items.length <= 1;

  function copyMarkdown(item: BatchReportResultItem) {
    if (!item.report_markdown) return;
    navigator.clipboard?.writeText(item.report_markdown).then(() => {
      setCopiedIdx(item.index);
      setTimeout(() => setCopiedIdx(null), 2000);
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/65 backdrop-blur-xs flex items-center justify-center p-2 sm:p-5"
      role="dialog"
      aria-modal="true"
      aria-label="Результаты анализа закупок"
    >
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-6xl h-[90vh] flex flex-col overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-200 bg-slate-50 flex flex-wrap items-center justify-between gap-3">
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
            </p>
          </div>

          <div className="flex items-center gap-2 ml-auto">
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

        <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
          {!isSingle ? (
            <aside className="w-full md:w-80 shrink-0 border-b md:border-b-0 md:border-r border-slate-200 bg-slate-50/60 overflow-y-auto max-h-48 md:max-h-none p-2.5 space-y-1.5">
              {data.items.map((item, idx) => {
                const isSelected = idx === safeIdx;
                return (
                  <button
                    key={item.id || idx}
                    type="button"
                    onClick={() => onSelectIndex(idx)}
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
                    </div>
                  </button>
                );
              })}
            </aside>
          ) : null}

          <main className="flex-1 overflow-y-auto p-4 sm:p-6 bg-white">
            {activeItem ? (
              <div>
                <div className="pb-3.5 mb-4 border-b border-slate-200 flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 mb-1">
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
                      {activeItem.deadline_date ? (
                        <span>Подача до: {activeItem.deadline_date}</span>
                      ) : null}
                    </div>
                    <h4 className="text-sm sm:text-base font-extrabold text-slate-900 leading-snug">
                      {activeItem.title}
                    </h4>
                  </div>

                  {activeItem.status === "completed" ? (
                    <div className="flex items-center gap-2 shrink-0">
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

                {activeItem.status === "completed" && activeItem.report_markdown ? (
                  <>
                    <SafeMarkdownView markdown={activeItem.report_markdown} />
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
            ) : null}
          </main>
        </div>
      </div>
    </div>
  );
}
