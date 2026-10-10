"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  FileSpreadsheet,
  FileText,
  Search,
  RotateCcw,
  Sparkles,
  Sliders,
  XCircle,
  CheckCircle2,
  ChevronDown,
  ArrowRight,
  Layers,
  Settings2,
  ExternalLink,
  Eye,
  Copy,
  Check,
  Zap,
  Filter,
  SlidersHorizontal,
  ArrowLeft,
  Info,
  ChevronUp,
  Download,
  AlertCircle,
  CheckSquare,
  Square,
  HelpCircle,
} from "lucide-react";

type ButtonStyleKey =
  | "modern-precision"
  | "segmented-toolbar"
  | "architectural-ghost"
  | "sharp-industrial"
  | "frosted-glass"
  | "dropdown-hub"
  | "high-contrast-obsidian"
  | "pastel-squircle"
  | "file-badges"
  | "compact-dense";

interface StyleDefinition {
  id: ButtonStyleKey;
  number: number;
  name: string;
  tagline: string;
  philosophy: string;
  badge: string;
}

const STYLES: StyleDefinition[] = [
  {
    id: "modern-precision",
    number: 1,
    name: "Modern Precision (SaaS Stripe/Linear)",
    tagline: "Строгие скругления 6px, деликатные границы, микротени",
    philosophy: "Без круглых 'пилюль'. Умеренные углы, спокойная палитра, цветные акцентные иконки. Проверенный мировой стандарт для enterprise B2B инструментов.",
    badge: "🏆 ВЫБРАН ВАМИ (внедрён в ЛК)",
  },
  {
    id: "segmented-toolbar",
    number: 2,
    name: "Segmented Action Bar (Монолитная панель macOS)",
    tagline: "Кнопки объединены в цельный тулбар с тонкими разделителями",
    philosophy: "Исключает ощущение 'разбросанных кнопок'. Все действия сгруппированы в аккуратный монолитный блок, как в Apple macOS и Figma.",
    badge: "Компактный монолит",
  },
  {
    id: "architectural-ghost",
    number: 3,
    name: "Architectural Ghost & Glow (Vercel / Notion)",
    tagline: "Без тяжелых рамок, чистый воздух, цветной ховер",
    philosophy: "В покое кнопки минималистичны и не отвлекают от текста задачи. При наведении раскрывается цветной мягкий тинт и сочная иконка.",
    badge: "Воздушный минимализм",
  },
  {
    id: "sharp-industrial",
    number: 4,
    name: "Sharp Industrial (Fintech / Bloomberg / CAD)",
    tagline: "Четкие прямые углы 2px, контрастные границы, моноширинные акценты",
    philosophy: "Бескомпромиссная деловая эстетика тендерного софта. Четкие строгие формы без лишних декоративных скруглений.",
    badge: "Строгий финтех",
  },
  {
    id: "frosted-glass",
    number: 5,
    name: "Frosted Glass & Neo-Surface (macOS Tahoe)",
    tagline: "Полупрозрачные подложки с микро-блюром и мягким градиентом",
    philosophy: "Мягкий премиальный лоск. Кнопки ощущаются как физические пластины из матового стекла с деликатными световыми бликами.",
    badge: "Премиум матовый",
  },
  {
    id: "dropdown-hub",
    number: 6,
    name: "Smart Dropdown Hub (Сжатый смарт-блок)",
    tagline: "Главное действие + выпадающее меню дополнительных действий",
    philosophy: "Вместо 4–5 горизонтальных кнопок — одна главная кнопка 'Скачать отчёт' и компактное меню. Экономит до 60% ширины таблицы.",
    badge: "Максимальная экономия места",
  },
  {
    id: "high-contrast-obsidian",
    number: 7,
    name: "High-Contrast Obsidian (Nordic Clean)",
    tagline: "Глубокий графитовый монохром для главных действий + контур для сервисных",
    philosophy: "Идеальная иерархия взгляда: пользователь сразу видит главный результат (темная контрастная кнопка), а второстепенные опции не спорят с ней.",
    badge: "Четкая иерархия",
  },
  {
    id: "pastel-squircle",
    number: 8,
    name: "Pastel Squircle (Apple iOS 18)",
    tagline: "Суперэллипс 8px, деликатные пастельные фоны с цветным текстом",
    philosophy: "Отказ от серых скучных кнопок. Зеленоватый оттенок для Excel, синий для Запроса КП, янтарный для добора. Дружелюбно и легко считывается.",
    badge: "Цветовая навигация",
  },
  {
    id: "file-badges",
    number: 9,
    name: "File-Type Visual Badges (Метки форматов XLS/DOC)",
    tagline: "Кнопки со специальными ярлычками расширений файлов",
    philosophy: "Пользователь с первого взгляда понимает тип документа: зеленая плашка XLS, синяя DOCX, фиолетовая AI. Никакой путаницы в отчётах.",
    badge: "Информативный",
  },
  {
    id: "compact-dense",
    number: 10,
    name: "Compact Dense Data-Row (Корпоративный ультра-режим)",
    tagline: "Уменьшенная высота 28px, мелкая четкая типографика, плотная сетка",
    philosophy: "Для профессионалов, которым важна плотность информации на экране. Строки не раздуваются по высоте, влезает максимум задач.",
    badge: "Ультраплотный",
  },
];

export default function TestButtonsPage() {
  const [activeStyle, setActiveStyle] = useState<ButtonStyleKey>("modern-precision");
  const [activeTab, setActiveTab] = useState<"interactive" | "gallery" | "strategy-concepts">("interactive");
  const [openDropdownJobId, setOpenDropdownJobId] = useState<string | null>(null);
  const [lastActionMessage, setLastActionMessage] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // State for Strategy Concepts Demo
  const [conceptS2Mode, setConceptS2Mode] = useState<"balanced" | "per_item">("balanced");
  const [conceptS3Open, setConceptS3Open] = useState(false);
  const [conceptS4Expanded, setConceptS4Expanded] = useState(true);
  const [conceptS4Mode, setConceptS4Mode] = useState<"balanced" | "per_item">("per_item");
  const [conceptS4ShowAll, setConceptS4ShowAll] = useState(false);
  const [conceptS4PreviewCategories, setConceptS4PreviewCategories] = useState(false);
  const [conceptS4CategoriesCollapsed, setConceptS4CategoriesCollapsed] = useState(false);
  const [conceptS4Items, setConceptS4Items] = useState([
    { id: "1", name: "Потолочная панель СМЛ 600x600", core: true, checked: true, qty: "2 400 м²" },
    { id: "2", name: "Профили направляющие Т24/29", core: true, checked: true, qty: "1 850 м.п." },
    { id: "3", name: "Алюминиевый профиль скрытый для LED", core: true, checked: true, qty: "420 м.п." },
    { id: "4", name: "Светильники встраиваемые 595x595", core: true, checked: true, qty: "320 шт." },
    { id: "5", name: "Минеральная вата 50мм теплоизоляция", core: true, checked: true, qty: "1 200 м²" },
    { id: "6", name: "Подвесы евро и регулируемые тяги", core: false, checked: true, qty: "900 шт." },
    { id: "7", name: "Уголок пристенный PL-19 стальной", core: false, checked: true, qty: "650 м.п." },
    { id: "8", name: "Дюбель-гвозди 6x40 сталь", core: false, checked: true, qty: "5 000 шт." },
    { id: "9", name: "Саморезы металл-металл LN 3.5x9", core: false, checked: true, qty: "3 200 шт." },
    { id: "10", name: "Звукоизоляционная лента Дихтунг", core: false, checked: true, qty: "40 рул." },
    { id: "11", name: "Соединители крестообразные «Краб»", core: false, checked: true, qty: "450 шт." },
    { id: "12", name: "Грунтовка глубокого проникновения", core: false, checked: true, qty: "60 кан." },
  ]);
  const [conceptS5Open, setConceptS5Open] = useState(false);

  const triggerAction = (msg: string) => {
    setLastActionMessage(msg);
    setTimeout(() => setLastActionMessage(null), 3000);
  };

  const copyToClipboard = (text: string, label: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text);
      setCopiedKey(label);
      setTimeout(() => setCopiedKey(null), 2000);
    }
  };

  // Render buttons based on selected style
  const renderJobActionButtons = (
    styleKey: ButtonStyleKey,
    type: "suppliers" | "analogs" | "awaiting_strategy" | "cancelled",
    jobId: string
  ) => {
    const isDropdownOpen = openDropdownJobId === jobId;

    // --- СТИЛЬ 1: Modern Precision (SaaS Stripe/Linear) ---
    if (styleKey === "modern-precision") {
      if (type === "suppliers") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание XLSX отчёта по поставщикам")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-800 border border-slate-200/90 hover:border-slate-300 rounded-md text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              <FileSpreadsheet size={14} className="text-emerald-600" />
              <span>Поставщики</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Скачивание DOCX Запроса КП")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-800 border border-slate-200/90 hover:border-slate-300 rounded-md text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              <FileText size={14} className="text-blue-600" />
              <span>Запрос КП</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Запуск добора поставщиков")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-teal-50/50 text-teal-800 border border-slate-200/90 hover:border-teal-300 rounded-md text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              <Search size={14} className="text-teal-600" />
              <span>Найти ещё</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Повторный запуск задачи")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-white hover:bg-slate-50 text-slate-600 border border-slate-200/90 hover:border-slate-300 rounded-md text-xs font-medium shadow-xs transition-colors cursor-pointer"
              title="Повторить"
            >
              <RotateCcw size={14} />
              <span>Повторить</span>
            </button>
          </div>
        );
      }
      if (type === "analogs") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание отчёта по аналогам (.docx)")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-800 border border-slate-200/90 hover:border-slate-300 rounded-md text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              <FileText size={14} className="text-indigo-600" />
              <span>Подбор товара и аналоги</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Запуск поиска поставщиков по аналогам")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              <Search size={14} />
              <span>Найти поставщиков</span>
            </button>
          </div>
        );
      }
      if (type === "awaiting_strategy") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Открытие окна выбора стратегии")}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-bold shadow-xs transition-colors cursor-pointer"
            >
              <Sliders size={14} />
              <span>Выбрать стратегию</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Отмена задачи клиентом (успешно сработало!)")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 rounded-md text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              <XCircle size={14} />
              <span>Отменить</span>
            </button>
          </div>
        );
      }
      return null;
    }

    // --- СТИЛЬ 2: Segmented Action Bar (Монолитная панель macOS) ---
    if (styleKey === "segmented-toolbar") {
      if (type === "suppliers") {
        return (
          <div className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50/80 p-0.5 shadow-2xs divide-x divide-slate-200">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание XLSX")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-slate-800 hover:bg-white hover:shadow-2xs rounded-xs text-xs font-semibold transition-all cursor-pointer"
            >
              <FileSpreadsheet size={13} className="text-emerald-600" />
              <span>Поставщики</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Скачивание Запроса КП")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-slate-800 hover:bg-white hover:shadow-2xs rounded-xs text-xs font-semibold transition-all cursor-pointer"
            >
              <FileText size={13} className="text-blue-600" />
              <span>Запрос КП</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Запуск добора")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-teal-800 hover:bg-white hover:shadow-2xs rounded-xs text-xs font-semibold transition-all cursor-pointer"
            >
              <Search size={13} className="text-teal-600" />
              <span>Найти ещё</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Повторный запуск")}
              className="inline-flex items-center gap-1 px-2 py-1 text-slate-600 hover:bg-white hover:shadow-2xs rounded-xs text-xs font-medium transition-all cursor-pointer"
              title="Повторить"
            >
              <RotateCcw size={12} />
              <span>Повтор</span>
            </button>
          </div>
        );
      }
      if (type === "analogs") {
        return (
          <div className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50/80 p-0.5 shadow-2xs divide-x divide-slate-200">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание аналогов")}
              className="inline-flex items-center gap-1.5 px-3 py-1 text-slate-800 hover:bg-white hover:shadow-2xs rounded-xs text-xs font-semibold transition-all cursor-pointer"
            >
              <FileText size={13} className="text-indigo-600" />
              <span>Отчёт по аналогам</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти поставщиков по аналогам")}
              className="inline-flex items-center gap-1.5 px-3 py-1 bg-teal-600 text-white hover:bg-teal-700 rounded-xs text-xs font-semibold transition-all cursor-pointer"
            >
              <Search size={13} />
              <span>Найти поставщиков</span>
            </button>
          </div>
        );
      }
      if (type === "awaiting_strategy") {
        return (
          <div className="inline-flex items-center rounded-md border border-teal-200 bg-teal-50/60 p-0.5 shadow-2xs divide-x divide-teal-200">
            <button
              type="button"
              onClick={() => triggerAction("Выбор стратегии")}
              className="inline-flex items-center gap-1.5 px-3 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-xs text-xs font-bold transition-all cursor-pointer"
            >
              <Sliders size={13} />
              <span>Выбрать стратегию</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Отмена задачи")}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-rose-700 hover:bg-rose-100 rounded-xs text-xs font-semibold transition-all cursor-pointer"
            >
              <XCircle size={13} />
              <span>Отменить</span>
            </button>
          </div>
        );
      }
      return null;
    }

    // --- СТИЛЬ 3: Architectural Ghost & Glow (Vercel / Notion) ---
    if (styleKey === "architectural-ghost") {
      if (type === "suppliers") {
        return (
          <div className="flex items-center flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание XLSX")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-slate-700 hover:text-emerald-900 hover:bg-emerald-50 rounded-md text-xs font-semibold transition-colors cursor-pointer"
            >
              <FileSpreadsheet size={15} className="text-emerald-600" />
              <span>Поставщики</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Скачивание Запроса КП")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-slate-700 hover:text-blue-900 hover:bg-blue-50 rounded-md text-xs font-semibold transition-colors cursor-pointer"
            >
              <FileText size={15} className="text-blue-600" />
              <span>Запрос КП</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти ещё")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-teal-800 hover:bg-teal-50 rounded-md text-xs font-semibold transition-colors cursor-pointer"
            >
              <Search size={15} className="text-teal-600" />
              <span>Найти ещё</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Повторить")}
              className="inline-flex items-center gap-1 px-2 py-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-md text-xs font-medium transition-colors cursor-pointer"
              title="Повторить"
            >
              <RotateCcw size={14} />
            </button>
          </div>
        );
      }
      if (type === "analogs") {
        return (
          <div className="flex items-center flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание аналогов")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-slate-700 hover:text-indigo-900 hover:bg-indigo-50 rounded-md text-xs font-semibold transition-colors cursor-pointer"
            >
              <FileText size={15} className="text-indigo-600" />
              <span>Подбор товара и аналоги</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти поставщиков")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600/90 hover:bg-teal-600 text-white rounded-md text-xs font-semibold transition-colors cursor-pointer"
            >
              <Search size={14} />
              <span>Найти поставщиков</span>
            </button>
          </div>
        );
      }
      if (type === "awaiting_strategy") {
        return (
          <div className="flex items-center flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => triggerAction("Выбрать стратегию")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-black text-white rounded-md text-xs font-bold transition-colors cursor-pointer shadow-xs"
            >
              <Sliders size={14} className="text-teal-400" />
              <span>Выбрать стратегию</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Отменить задачу")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-rose-600 hover:bg-rose-50 rounded-md text-xs font-semibold transition-colors cursor-pointer"
            >
              <XCircle size={14} />
              <span>Отменить</span>
            </button>
          </div>
        );
      }
      return null;
    }

    // --- СТИЛЬ 4: Sharp Industrial (Fintech / Bloomberg / CAD) ---
    if (styleKey === "sharp-industrial") {
      if (type === "suppliers") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание XLSX")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-white hover:bg-slate-100 text-slate-900 border border-slate-400 rounded-none text-[11px] font-bold tracking-tight uppercase transition-colors cursor-pointer"
            >
              <FileSpreadsheet size={13} className="text-emerald-700" />
              <span>Поставщики</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Запрос КП")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-white hover:bg-slate-100 text-slate-900 border border-slate-400 rounded-none text-[11px] font-bold tracking-tight uppercase transition-colors cursor-pointer"
            >
              <FileText size={13} className="text-blue-700" />
              <span>Запрос КП</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Добор")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-teal-900 border border-teal-600 rounded-none text-[11px] font-bold tracking-tight uppercase transition-colors cursor-pointer"
            >
              <Search size={13} className="text-teal-700" />
              <span>Добор</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Повтор")}
              className="inline-flex items-center gap-1 px-2 py-1 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded-none text-[11px] font-semibold tracking-tight transition-colors cursor-pointer"
            >
              <RotateCcw size={12} />
            </button>
          </div>
        );
      }
      if (type === "analogs") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание аналогов")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-white hover:bg-slate-100 text-slate-900 border border-slate-400 rounded-none text-[11px] font-bold tracking-tight uppercase transition-colors cursor-pointer"
            >
              <FileText size={13} className="text-indigo-700" />
              <span>Аналоги (.DOCX)</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти поставщиков")}
              className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-900 hover:bg-black text-white border border-slate-900 rounded-none text-[11px] font-bold tracking-tight uppercase transition-colors cursor-pointer"
            >
              <Search size={13} />
              <span>Найти поставщиков</span>
            </button>
          </div>
        );
      }
      if (type === "awaiting_strategy") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Выбрать стратегию")}
              className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-500 hover:bg-amber-600 text-slate-950 border border-amber-600 rounded-none text-[11px] font-black tracking-wide uppercase transition-colors cursor-pointer"
            >
              <Sliders size={13} />
              <span>Стратегия (6 поз.)</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Отменить")}
              className="inline-flex items-center gap-1 px-2 py-1 bg-white hover:bg-rose-50 text-rose-800 border border-rose-300 rounded-none text-[11px] font-bold tracking-tight uppercase transition-colors cursor-pointer"
            >
              <XCircle size={13} />
              <span>Отмена</span>
            </button>
          </div>
        );
      }
      return null;
    }

    // --- СТИЛЬ 5: Frosted Glass & Neo-Surface (macOS Tahoe) ---
    if (styleKey === "frosted-glass") {
      if (type === "suppliers") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание XLSX")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100/80 hover:bg-white text-slate-800 border border-slate-200/70 hover:border-slate-300 rounded-lg text-xs font-semibold backdrop-blur-md shadow-2xs hover:shadow-xs transition-all cursor-pointer"
            >
              <FileSpreadsheet size={14} className="text-emerald-600" />
              <span>Поставщики</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Запрос КП")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100/80 hover:bg-white text-slate-800 border border-slate-200/70 hover:border-slate-300 rounded-lg text-xs font-semibold backdrop-blur-md shadow-2xs hover:shadow-xs transition-all cursor-pointer"
            >
              <FileText size={14} className="text-blue-600" />
              <span>Запрос КП</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти ещё")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-50/80 hover:bg-teal-100/90 text-teal-800 border border-teal-200/70 rounded-lg text-xs font-semibold backdrop-blur-md shadow-2xs hover:shadow-xs transition-all cursor-pointer"
            >
              <Search size={14} className="text-teal-600" />
              <span>Найти ещё</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Повторить")}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-slate-100/60 hover:bg-white text-slate-600 border border-slate-200/50 rounded-lg text-xs font-medium backdrop-blur-md transition-all cursor-pointer"
            >
              <RotateCcw size={13} />
            </button>
          </div>
        );
      }
      if (type === "analogs") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание аналогов")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100/80 hover:bg-white text-slate-800 border border-slate-200/70 rounded-lg text-xs font-semibold backdrop-blur-md shadow-2xs transition-all cursor-pointer"
            >
              <FileText size={14} className="text-indigo-600" />
              <span>Подбор товара и аналоги</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти поставщиков")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-700 hover:to-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-all cursor-pointer"
            >
              <Search size={14} />
              <span>Найти поставщиков</span>
            </button>
          </div>
        );
      }
      if (type === "awaiting_strategy") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Выбрать стратегию")}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-lg text-xs font-bold shadow-xs transition-all cursor-pointer"
            >
              <Sliders size={14} />
              <span>Выбрать стратегию</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Отменить")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-50/80 hover:bg-rose-100 text-rose-700 border border-rose-200/70 rounded-lg text-xs font-semibold backdrop-blur-md shadow-2xs transition-all cursor-pointer"
            >
              <XCircle size={14} />
              <span>Отменить</span>
            </button>
          </div>
        );
      }
      return null;
    }

    // --- СТИЛЬ 6: Smart Dropdown Hub (Сжатый смарт-блок) ---
    if (styleKey === "dropdown-hub") {
      if (type === "suppliers") {
        return (
          <div className="relative inline-flex items-center gap-2">
            <div className="inline-flex items-center rounded-md border border-slate-200 bg-white shadow-2xs divide-x divide-slate-200">
              <button
                type="button"
                onClick={() => triggerAction("Скачивание Поставщики XLSX")}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-slate-800 hover:bg-slate-50 text-xs font-semibold cursor-pointer"
              >
                <FileSpreadsheet size={14} className="text-emerald-600" />
                <span>Отчёт (83)</span>
              </button>
              <button
                type="button"
                onClick={() => setOpenDropdownJobId(isDropdownOpen ? null : jobId)}
                className="px-2 py-1.5 text-slate-600 hover:bg-slate-50 cursor-pointer"
                title="Все файлы и действия"
              >
                <ChevronDown size={14} />
              </button>
            </div>
            <button
              type="button"
              onClick={() => triggerAction("Запуск добора")}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-white hover:bg-teal-50 text-teal-800 border border-slate-200 rounded-md text-xs font-semibold shadow-2xs cursor-pointer"
            >
              <Search size={13} className="text-teal-600" />
              <span>Добор</span>
            </button>

            {/* Dropdown Menu */}
            {isDropdownOpen && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-slate-200 rounded-lg shadow-lg z-30 py-1 text-xs">
                <button
                  type="button"
                  onClick={() => {
                    setOpenDropdownJobId(null);
                    triggerAction("Скачан XLSX Поставщики");
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-slate-50 font-medium text-slate-800"
                >
                  <FileSpreadsheet size={14} className="text-emerald-600" />
                  <span>Скачать Excel (.xlsx)</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setOpenDropdownJobId(null);
                    triggerAction("Скачан DOCX Запрос КП");
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-slate-50 font-medium text-slate-800"
                >
                  <FileText size={14} className="text-blue-600" />
                  <span>Запрос КП (.docx)</span>
                </button>
                <div className="border-t border-slate-100 my-1" />
                <button
                  type="button"
                  onClick={() => {
                    setOpenDropdownJobId(null);
                    triggerAction("Задача перезапущена");
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-slate-50 text-slate-600 font-medium"
                >
                  <RotateCcw size={14} />
                  <span>Повторить задачу</span>
                </button>
              </div>
            )}
          </div>
        );
      }
      if (type === "analogs") {
        return (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание аналогов")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-800 border border-slate-200 rounded-md text-xs font-semibold shadow-2xs cursor-pointer"
            >
              <FileText size={14} className="text-indigo-600" />
              <span>Аналоги (.docx)</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти поставщиков")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-semibold shadow-2xs cursor-pointer"
            >
              <Search size={14} />
              <span>Поставщики</span>
            </button>
          </div>
        );
      }
      if (type === "awaiting_strategy") {
        return (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Выбор стратегии")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-bold shadow-2xs cursor-pointer"
            >
              <Sliders size={14} />
              <span>Стратегия</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Отменить")}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 rounded-md text-xs font-semibold cursor-pointer"
            >
              <XCircle size={14} />
              <span>Отмена</span>
            </button>
          </div>
        );
      }
      return null;
    }

    // --- СТИЛЬ 7: High-Contrast Obsidian / Nordic Clean ---
    if (styleKey === "high-contrast-obsidian") {
      if (type === "suppliers") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание XLSX")}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-slate-900 hover:bg-black text-white rounded-md text-xs font-bold shadow-xs transition-colors cursor-pointer"
            >
              <FileSpreadsheet size={14} className="text-emerald-400" />
              <span>Поставщики</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Запрос КП")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-800 border border-slate-300 rounded-md text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              <FileText size={14} className="text-slate-600" />
              <span>Запрос КП</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти ещё")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-800 border border-slate-300 rounded-md text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              <Search size={14} className="text-slate-600" />
              <span>Найти ещё</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Повторить")}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-white hover:bg-slate-50 text-slate-600 border border-slate-300 rounded-md text-xs font-medium cursor-pointer"
              title="Повторить"
            >
              <RotateCcw size={13} />
            </button>
          </div>
        );
      }
      if (type === "analogs") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание аналогов")}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-slate-900 hover:bg-black text-white rounded-md text-xs font-bold shadow-xs transition-colors cursor-pointer"
            >
              <FileText size={14} className="text-indigo-300" />
              <span>Подбор аналогов</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти поставщиков")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-teal-50 text-teal-800 border border-teal-300 rounded-md text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              <Search size={14} className="text-teal-600" />
              <span>Найти поставщиков</span>
            </button>
          </div>
        );
      }
      if (type === "awaiting_strategy") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Выбрать стратегию")}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-bold shadow-xs transition-colors cursor-pointer"
            >
              <Sliders size={14} />
              <span>Выбрать стратегию</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Отменить")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-rose-50 text-rose-700 border border-slate-300 rounded-md text-xs font-semibold cursor-pointer"
            >
              <XCircle size={14} />
              <span>Отменить</span>
            </button>
          </div>
        );
      }
      return null;
    }

    // --- СТИЛЬ 8: Pastel Squircle (Apple iOS 18) ---
    if (styleKey === "pastel-squircle") {
      if (type === "suppliers") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание XLSX")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/80 rounded-lg text-xs font-bold transition-all cursor-pointer"
            >
              <FileSpreadsheet size={14} className="text-emerald-700" />
              <span>Поставщики</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Запрос КП")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-800 border border-blue-200/80 rounded-lg text-xs font-bold transition-all cursor-pointer"
            >
              <FileText size={14} className="text-blue-700" />
              <span>Запрос КП</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти ещё")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-200/80 rounded-lg text-xs font-bold transition-all cursor-pointer"
            >
              <Search size={14} className="text-amber-700" />
              <span>Найти ещё</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Повторить")}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition-all cursor-pointer"
            >
              <RotateCcw size={13} />
            </button>
          </div>
        );
      }
      if (type === "analogs") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание аналогов")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-900 border border-indigo-200/80 rounded-lg text-xs font-bold transition-all cursor-pointer"
            >
              <FileText size={14} className="text-indigo-700" />
              <span>Подбор товара и аналоги</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти поставщиков")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-xs font-bold shadow-xs transition-all cursor-pointer"
            >
              <Search size={14} />
              <span>Найти поставщиков</span>
            </button>
          </div>
        );
      }
      if (type === "awaiting_strategy") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Выбрать стратегию")}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-xs font-bold shadow-xs transition-all cursor-pointer"
            >
              <Sliders size={14} />
              <span>Выбрать стратегию</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Отменить")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-800 border border-rose-200/80 rounded-lg text-xs font-bold transition-all cursor-pointer"
            >
              <XCircle size={14} />
              <span>Отменить</span>
            </button>
          </div>
        );
      }
      return null;
    }

    // --- СТИЛЬ 9: File-Type Visual Badges (Метки форматов XLS/DOC) ---
    if (styleKey === "file-badges") {
      if (type === "suppliers") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание XLSX")}
              className="inline-flex items-center gap-2 pl-1.5 pr-3 py-1 bg-white hover:bg-slate-50 text-slate-800 border border-slate-200 rounded-md text-xs font-semibold shadow-2xs transition-colors cursor-pointer"
            >
              <span className="px-1.5 py-0.5 rounded-xs bg-emerald-100 text-emerald-800 text-[10px] font-black uppercase tracking-wider">
                XLS
              </span>
              <span>Поставщики</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Запрос КП")}
              className="inline-flex items-center gap-2 pl-1.5 pr-3 py-1 bg-white hover:bg-slate-50 text-slate-800 border border-slate-200 rounded-md text-xs font-semibold shadow-2xs transition-colors cursor-pointer"
            >
              <span className="px-1.5 py-0.5 rounded-xs bg-blue-100 text-blue-800 text-[10px] font-black uppercase tracking-wider">
                DOC
              </span>
              <span>Запрос КП</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти ещё")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-white hover:bg-teal-50 text-teal-800 border border-slate-200 rounded-md text-xs font-semibold shadow-2xs transition-colors cursor-pointer"
            >
              <Search size={13} className="text-teal-600" />
              <span>Найти ещё</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Повторить")}
              className="inline-flex items-center gap-1 px-2 py-1.5 bg-white hover:bg-slate-50 text-slate-600 border border-slate-200 rounded-md text-xs font-medium cursor-pointer"
              title="Повторить"
            >
              <RotateCcw size={13} />
            </button>
          </div>
        );
      }
      if (type === "analogs") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание аналогов")}
              className="inline-flex items-center gap-2 pl-1.5 pr-3 py-1 bg-white hover:bg-slate-50 text-slate-800 border border-slate-200 rounded-md text-xs font-semibold shadow-2xs transition-colors cursor-pointer"
            >
              <span className="px-1.5 py-0.5 rounded-xs bg-indigo-100 text-indigo-800 text-[10px] font-black uppercase tracking-wider">
                DOC
              </span>
              <span>Аналоги товара</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти поставщиков")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-bold shadow-2xs transition-colors cursor-pointer"
            >
              <Search size={13} />
              <span>Найти поставщиков</span>
            </button>
          </div>
        );
      }
      if (type === "awaiting_strategy") {
        return (
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={() => triggerAction("Выбрать стратегию")}
              className="inline-flex items-center gap-2 pl-2 pr-3.5 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-bold shadow-2xs transition-colors cursor-pointer"
            >
              <span className="px-1.5 py-0.5 rounded-xs bg-teal-800 text-teal-100 text-[10px] font-black uppercase">
                6 ПОЗ
              </span>
              <span>Выбрать стратегию</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Отменить")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 rounded-md text-xs font-semibold cursor-pointer"
            >
              <XCircle size={13} />
              <span>Отменить</span>
            </button>
          </div>
        );
      }
      return null;
    }

    // --- СТИЛЬ 10: Compact Dense Data-Row (Корпоративный ультра-режим) ---
    if (styleKey === "compact-dense") {
      if (type === "suppliers") {
        return (
          <div className="flex items-center flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание XLSX")}
              className="inline-flex items-center gap-1 px-2 py-1 bg-white hover:bg-slate-100 text-slate-800 border border-slate-300 rounded-xs text-[11px] font-semibold transition-colors cursor-pointer"
            >
              <FileSpreadsheet size={12} className="text-emerald-600" />
              <span>Поставщики</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Запрос КП")}
              className="inline-flex items-center gap-1 px-2 py-1 bg-white hover:bg-slate-100 text-slate-800 border border-slate-300 rounded-xs text-[11px] font-semibold transition-colors cursor-pointer"
            >
              <FileText size={12} className="text-blue-600" />
              <span>Запрос КП</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти ещё")}
              className="inline-flex items-center gap-1 px-2 py-1 bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-300 rounded-xs text-[11px] font-semibold transition-colors cursor-pointer"
            >
              <Search size={12} className="text-teal-700" />
              <span>Добор</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Повторить")}
              className="inline-flex items-center gap-0.5 px-1.5 py-1 bg-white hover:bg-slate-100 text-slate-600 border border-slate-300 rounded-xs text-[11px] font-medium cursor-pointer"
              title="Повторить"
            >
              <RotateCcw size={11} />
            </button>
          </div>
        );
      }
      if (type === "analogs") {
        return (
          <div className="flex items-center flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => triggerAction("Скачивание аналогов")}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-white hover:bg-slate-100 text-slate-800 border border-slate-300 rounded-xs text-[11px] font-semibold transition-colors cursor-pointer"
            >
              <FileText size={12} className="text-indigo-600" />
              <span>Аналоги</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Найти поставщиков")}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-xs text-[11px] font-bold transition-colors cursor-pointer"
            >
              <Search size={12} />
              <span>Найти поставщиков</span>
            </button>
          </div>
        );
      }
      if (type === "awaiting_strategy") {
        return (
          <div className="flex items-center flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => triggerAction("Выбрать стратегию")}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-xs text-[11px] font-bold transition-colors cursor-pointer"
            >
              <Sliders size={12} />
              <span>Стратегия</span>
            </button>
            <button
              type="button"
              onClick={() => triggerAction("Отменить")}
              className="inline-flex items-center gap-1 px-2 py-1 bg-white hover:bg-rose-50 text-rose-700 border border-rose-300 rounded-xs text-[11px] font-semibold cursor-pointer"
            >
              <XCircle size={12} />
              <span>Отмена</span>
            </button>
          </div>
        );
      }
      return null;
    }

    return null;
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-20">
      {/* Top Notification Toast */}
      {lastActionMessage && (
        <div className="fixed top-5 right-5 z-50 bg-slate-900 text-white px-4 py-2.5 rounded-lg shadow-xl text-xs font-semibold flex items-center gap-2 border border-slate-800 animate-in fade-in slide-in-from-top-3 duration-200">
          <CheckCircle2 size={16} className="text-emerald-400" />
          <span>{lastActionMessage}</span>
        </div>
      )}

      {/* Header Bar */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-2xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              href="/cabinet"
              className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-600 hover:text-slate-900 px-2.5 py-1.5 rounded-md hover:bg-slate-100 transition-colors"
            >
              <ArrowLeft size={15} />
              <span>В личный кабинет</span>
            </Link>
            <div className="h-4 w-px bg-slate-200" />
            <h1 className="text-base sm:text-lg font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
              <Sparkles size={18} className="text-teal-600" />
              <span>Лаборатория дизайна кнопок</span>
            </h1>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => copyToClipboard(`Выбираю Стиль #${STYLES.find((s) => s.id === activeStyle)?.number}: ${STYLES.find((s) => s.id === activeStyle)?.name}`, "copy-choice")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-md text-xs font-bold transition-colors cursor-pointer"
            >
              {copiedKey === "copy-choice" ? <Check size={14} className="text-emerald-600" /> : <Copy size={14} />}
              <span>{copiedKey === "copy-choice" ? "Скопировано!" : "Скопировать выбор"}</span>
            </button>
          </div>
        </div>

        {/* View Tabs */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center gap-6 text-xs font-bold border-t border-slate-100">
          <button
            type="button"
            onClick={() => setActiveTab("interactive")}
            className={`py-3 border-b-2 transition-all cursor-pointer ${
              activeTab === "interactive"
                ? "border-teal-600 text-teal-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            1. Интерактивная таблица (10 стилей)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("gallery")}
            className={`py-3 border-b-2 transition-all cursor-pointer ${
              activeTab === "gallery"
                ? "border-teal-600 text-teal-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            2. Визуальная витрина всех 10 стилей рядом
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("strategy-concepts")}
            className={`py-3 border-b-2 transition-all cursor-pointer ${
              activeTab === "strategy-concepts"
                ? "border-teal-600 text-teal-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            3. Концепты кнопки «Выбрать стратегию» (UX)
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        {/* TAB 1: INTERACTIVE TABLE SIMULATION */}
        {activeTab === "interactive" && (
          <div className="space-y-6">
            {/* Style Selector Chips */}
            <div className="bg-white rounded-xl border border-slate-200/90 p-4 shadow-2xs">
              <div className="text-xs font-extrabold uppercase tracking-wider text-slate-500 mb-3 flex items-center justify-between">
                <span>Выберите один из 10 стилей для просмотра в таблице:</span>
                <span className="text-teal-700 lowercase font-medium">Кликните по стилю для мгновенного переключения</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
                {STYLES.map((style) => (
                  <button
                    key={style.id}
                    type="button"
                    onClick={() => setActiveStyle(style.id)}
                    className={`p-2.5 rounded-lg text-left border transition-all cursor-pointer ${
                      activeStyle === style.id
                        ? "bg-teal-50/80 border-teal-500 text-teal-950 ring-1 ring-teal-500/30 font-bold"
                        : "bg-slate-50/60 hover:bg-slate-100/80 border-slate-200 text-slate-700 font-medium"
                    }`}
                  >
                    <div className="flex items-center justify-between text-[11px] mb-1">
                      <span className="font-mono text-slate-400 font-bold">#{style.number}</span>
                      {style.badge && (
                        <span className="text-[9px] px-1 py-0.2 rounded-xs bg-slate-200/70 text-slate-600 font-semibold">
                          {style.badge}
                        </span>
                      )}
                    </div>
                    <div className="text-xs leading-snug line-clamp-2">{style.name}</div>
                  </button>
                ))}
              </div>

              {/* Active Style Description */}
              {(() => {
                const cur = STYLES.find((s) => s.id === activeStyle);
                if (!cur) return null;
                return (
                  <div className="mt-4 pt-4 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                    <div>
                      <span className="font-extrabold text-slate-900">{cur.name}: </span>
                      <span className="text-slate-600">{cur.philosophy}</span>
                    </div>
                    <div className="shrink-0 text-slate-500 font-mono text-[11px]">
                      Форма: {cur.tagline}
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Simulated Cabinet Tasks Table */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
              <div className="px-5 py-3.5 border-b border-slate-200/80 bg-slate-50/60 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold text-slate-900">Задачи клиента (живая симуляция таблицы кабинета)</h2>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 font-bold">1-4 из 107</span>
                </div>
                <div className="text-xs text-slate-500">
                  Активный стиль: <strong className="text-teal-700">{STYLES.find((s) => s.id === activeStyle)?.name}</strong>
                </div>
              </div>

              <div className="divide-y divide-slate-100 overflow-x-auto">
                {/* Row 1: #854 Awaiting Strategy with 6 items (The one user had trouble with) */}
                <div className="p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 hover:bg-slate-50/50 transition-colors">
                  <div className="space-y-1.5 min-w-[280px]">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono font-bold text-slate-400">#854</span>
                      <h3 className="text-sm font-bold text-slate-900">ТЗ: Отделочные материалы - Казань (1)</h3>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span>Поиск поставщиков (Обычный)</span>
                      <span>·</span>
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 font-semibold border border-blue-200/60">
                        ожидает клиента
                      </span>
                      <span>·</span>
                      <span>В ТЗ обнаружено 6 позиций</span>
                    </div>
                    <p className="text-xs text-slate-500">
                      Ожидает выбора стратегии: сбалансированный поиск (1 списание) или попозиционный глубокий сбор.
                    </p>
                  </div>

                  {/* Actions Column */}
                  <div className="shrink-0 flex items-center justify-end">
                    {renderJobActionButtons(activeStyle, "awaiting_strategy", "job-854")}
                  </div>
                </div>

                {/* Row 2: #851 Completed Multi-Item Suppliers Search */}
                <div className="p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 hover:bg-slate-50/50 transition-colors">
                  <div className="space-y-1.5 min-w-[280px]">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono font-bold text-slate-400">#851</span>
                      <h3 className="text-sm font-bold text-slate-900">ТЗ: Потолочная панель СМЛ и ещё 6 позиции</h3>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span>Поиск поставщиков (Обычный)</span>
                      <span>·</span>
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200/60">
                        готово
                      </span>
                      <span>·</span>
                      <span className="text-emerald-700 font-bold">Отобрано кандидатов: 83</span>
                    </div>
                    <p className="text-xs text-slate-500">
                      Сбалансированный поиск по 6 категориям. Уровень технического совпадения указан в отчёте.
                    </p>
                  </div>

                  {/* Actions Column */}
                  <div className="shrink-0 flex items-center justify-end">
                    {renderJobActionButtons(activeStyle, "suppliers", "job-851")}
                  </div>
                </div>

                {/* Row 3: #717 Completed Analogs Selection */}
                <div className="p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 hover:bg-slate-50/50 transition-colors">
                  <div className="space-y-1.5 min-w-[280px]">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono font-bold text-slate-400">#717</span>
                      <h3 className="text-sm font-bold text-slate-900">Подбор товаров: Сушилки для рук - Норильск</h3>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span>Подбор товара и аналогов</span>
                      <span>·</span>
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200/60">
                        готово
                      </span>
                      <span>·</span>
                      <span>Выявлено 1 поз. с аналогами</span>
                    </div>
                    <p className="text-xs text-slate-500">
                      Сформирован подробный отчёт сопоставления технических характеристик в формате Word (.docx).
                    </p>
                  </div>

                  {/* Actions Column */}
                  <div className="shrink-0 flex items-center justify-end">
                    {renderJobActionButtons(activeStyle, "analogs", "job-717")}
                  </div>
                </div>

                {/* Row 4: #716 Completed Registry Suppliers Search */}
                <div className="p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 hover:bg-slate-50/50 transition-colors">
                  <div className="space-y-1.5 min-w-[280px]">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono font-bold text-slate-400">#716</span>
                      <h3 className="text-sm font-bold text-slate-900">ТЗ: Сушилка для рук</h3>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span>Поиск поставщиков (Только реестр Минпромторг)</span>
                      <span>·</span>
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200/60">
                        готово
                      </span>
                      <span>·</span>
                      <span>1 кандидат в реестре</span>
                    </div>
                    <p className="text-xs text-slate-500">
                      Отобран производитель с действующим заключением Минпромторга.
                    </p>
                  </div>

                  {/* Actions Column */}
                  <div className="shrink-0 flex items-center justify-end">
                    {renderJobActionButtons(activeStyle, "suppliers", "job-716")}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: VISUAL GALLERY OF ALL 10 STYLES SIDE-BY-SIDE */}
        {activeTab === "gallery" && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-2xs space-y-2">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <h2 className="text-sm font-extrabold text-slate-900">
                  Визуальная витрина всех 10 стилей кнопок рядом
                </h2>
                <span className="text-[11px] font-bold text-teal-800 bg-teal-50 px-2.5 py-1 rounded-md border border-teal-200/80">
                  Стиль #1 выбран и активен в ЛК
                </span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                <strong>Пояснение по вкладке:</strong> здесь каждый из 10 стилей показан в четырёх ключевых сценариях личного кабинета (готовая задача со скачиванием файлов, ожидание выбора стратегии с балансом, отменённая задача и повтор поиска). Поскольку вы выбрали <strong>Стиль #1 (Modern Precision)</strong>, все эти четыре сценария уже переведены на него в рабочем личном кабинете.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {STYLES.map((style) => (
                <div
                  key={style.id}
                  className={`bg-white rounded-xl border p-5 shadow-2xs transition-all ${
                    activeStyle === style.id ? "border-teal-500 ring-2 ring-teal-500/20" : "border-slate-200/90"
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-4 border-b border-slate-100 gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs px-2 py-0.5 rounded-md bg-slate-100 text-slate-800 font-black">
                          ВАРИАНТ {style.number}
                        </span>
                        <h3 className="text-sm font-bold text-slate-900">{style.name}</h3>
                        {style.badge && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-50 text-teal-700 font-bold border border-teal-200/60">
                            {style.badge}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 mt-1">{style.philosophy}</p>
                    </div>

                    <button
                      type="button"
                      onClick={() => {
                        setActiveStyle(style.id);
                        setActiveTab("interactive");
                      }}
                      className="inline-flex items-center gap-1 text-xs font-bold text-teal-700 hover:text-teal-900 cursor-pointer self-start sm:self-auto shrink-0"
                    >
                      <span>Открыть в таблице</span>
                      <ArrowRight size={13} />
                    </button>
                  </div>

                  {/* Side by side showcases for this style */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-1">
                    {/* Finished Job buttons */}
                    <div className="bg-slate-50/70 p-3.5 rounded-lg border border-slate-100">
                      <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2.5">
                        Готовая задача (Поставщики / Запрос КП / Добор)
                      </div>
                      <div className="flex items-center flex-wrap gap-2">
                        {renderJobActionButtons(style.id, "suppliers", `gallery-${style.id}-sup`)}
                      </div>
                    </div>

                    {/* Awaiting strategy & Analogs buttons */}
                    <div className="bg-slate-50/70 p-3.5 rounded-lg border border-slate-100">
                      <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2.5">
                        Выбор стратегии (#854) и Подбор аналогов (#717)
                      </div>
                      <div className="flex items-center flex-wrap gap-3">
                        {renderJobActionButtons(style.id, "awaiting_strategy", `gallery-${style.id}-strat`)}
                        <span className="text-slate-300">|</span>
                        {renderJobActionButtons(style.id, "analogs", `gallery-${style.id}-ana`)}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 3: STRATEGY BUTTON FUNCTIONAL & FRONTEND CONCEPTS */}
        {activeTab === "strategy-concepts" && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs space-y-2">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <h2 className="text-base font-extrabold text-slate-900">
                  Выбор стратегии поиска для многопозиционных спецификаций (UX)
                </h2>
                <span className="text-xs font-bold text-teal-800 bg-teal-50 px-3 py-1 rounded-md border border-teal-200/80">
                  🏆 Концепт S4 выбран и внедрен в ваш ЛК
                </span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed max-w-4xl">
                Вы выбрали <strong>Концепт S4 (Инлайн-аккордеон прямо в строке без модального окна)</strong>. Ниже представлена его обновлённая интерактивная модель с поддержкой 12 позиций, кнопкой разворота «Показать ещё» и полосой прокрутки, исключающей растягивание таблицы, а также зелеными чекбоксами TenderLex.
              </p>
            </div>

            {/* CONCEPT S1: High-Visibility Badge CTA */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs px-2 py-0.5 rounded-md bg-teal-100 text-teal-800 font-black">
                    КОНЦЕПТ S1
                  </span>
                  <h3 className="text-sm font-bold text-slate-900">
                    High-Visibility Smart CTA (Заметная кнопка с бейджем позиций и пульсаром)
                  </h3>
                </div>
                <span className="text-xs font-semibold text-slate-500">Улучшенная текущая модель</span>
              </div>
              <p className="text-xs text-slate-600">
                Кнопка выглядит как приоритетный призыв к действию: аккуратный мягкий градиент, пульсирующая точка внимания и бейдж с количеством категорий. Кнопка «Отменить» оформлена деликатно, чтобы не перебивать фокус.
              </p>

              <div className="p-4 bg-slate-50 rounded-lg border border-slate-200/80 flex items-center justify-between flex-wrap gap-3">
                <div className="text-xs">
                  <span className="font-bold text-slate-800">#854 Отделочные материалы</span>
                  <span className="text-slate-500"> · Ожидает подтверждения стратегии</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => triggerAction("Открытие модального окна выбора стратегии")}
                    className="relative inline-flex items-center gap-2 px-3.5 py-1.5 bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white rounded-md text-xs font-bold shadow-xs transition-all cursor-pointer"
                  >
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-300 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-white"></span>
                    </span>
                    <Sliders size={14} />
                    <span>Выбрать стратегию</span>
                    <span className="px-1.5 py-0.2 rounded-xs bg-teal-800/80 text-[10px] font-mono font-bold">
                      6 поз.
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => triggerAction("Задача отменена")}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-white hover:bg-rose-50 text-rose-700 border border-slate-200 hover:border-rose-300 rounded-md text-xs font-semibold shadow-2xs transition-all cursor-pointer"
                  >
                    <XCircle size={14} />
                    <span>Отменить</span>
                  </button>
                </div>
              </div>
            </div>

            {/* CONCEPT S2: Inline Instant Segmented Switcher */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs px-2 py-0.5 rounded-md bg-blue-100 text-blue-800 font-black">
                    КОНЦЕПТ S2
                  </span>
                  <h3 className="text-sm font-bold text-slate-900">
                    Inline Instant Switcher (Быстрый запуск в 1 клик прямо из строки)
                  </h3>
                </div>
                <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md">
                  Самый быстрый UX
                </span>
              </div>
              <p className="text-xs text-slate-600">
                Клиенту не обязательно открывать модальное окно. Прямо в строке таблицы расположен двухпозиционный селектор. Можно сразу нажать «Сбалансированный» или «Попозиционный», а шестерёнка открывает окно только если нужно снять галочки с отдельных позиций.
              </p>

              <div className="p-4 bg-slate-50 rounded-lg border border-slate-200/80 flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="text-xs space-y-0.5">
                  <div className="font-bold text-slate-800">#854 ТЗ: Отделочные материалы (6 категорий)</div>
                  <div className="text-slate-500">Выберите вариант и нажмите «Старт»:</div>
                </div>

                <div className="flex items-center flex-wrap gap-2">
                  {/* Segmented Switcher */}
                  <div className="inline-flex items-center rounded-md border border-slate-300 bg-white p-0.5 shadow-2xs">
                    <button
                      type="button"
                      onClick={() => setConceptS2Mode("balanced")}
                      className={`px-3 py-1 rounded-xs text-xs font-bold transition-all cursor-pointer ${
                        conceptS2Mode === "balanced"
                          ? "bg-teal-600 text-white shadow-2xs"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      ⚖️ Сбалансированный (1 списание)
                    </button>
                    <button
                      type="button"
                      onClick={() => setConceptS2Mode("per_item")}
                      className={`px-3 py-1 rounded-xs text-xs font-bold transition-all cursor-pointer ${
                        conceptS2Mode === "per_item"
                          ? "bg-teal-600 text-white shadow-2xs"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      🔍 Попозиционный (6 спис.)
                    </button>
                  </div>

                  {/* Settings gear */}
                  <button
                    type="button"
                    onClick={() => triggerAction("Открытие тонкой настройки категорий")}
                    className="p-1.5 text-slate-600 hover:text-slate-900 bg-white hover:bg-slate-100 border border-slate-200 rounded-md transition-colors cursor-pointer"
                    title="Выбрать конкретные категории"
                  >
                    <Settings2 size={16} />
                  </button>

                  {/* Start Confirmation */}
                  <button
                    type="button"
                    onClick={() => triggerAction(`Запущен поиск в режиме: ${conceptS2Mode === "balanced" ? "Сбалансированный" : "Попозиционный"}`)}
                    className="px-3.5 py-1 bg-slate-900 hover:bg-black text-white rounded-md text-xs font-bold shadow-2xs cursor-pointer"
                  >
                    Старт →
                  </button>

                  <button
                    type="button"
                    onClick={() => triggerAction("Задача отменена")}
                    className="p-1.5 text-rose-600 hover:bg-rose-50 border border-slate-200 rounded-md cursor-pointer"
                    title="Отменить задачу"
                  >
                    <XCircle size={16} />
                  </button>
                </div>
              </div>
            </div>

            {/* CONCEPT S3: Split-Button with Instant Actions Dropdown */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs px-2 py-0.5 rounded-md bg-purple-100 text-purple-800 font-black">
                    КОНЦЕПТ S3
                  </span>
                  <h3 className="text-sm font-bold text-slate-900">
                    Split-Button с выпадающим меню быстрого выбора (Dropdown Action)
                  </h3>
                </div>
                <span className="text-xs font-semibold text-slate-500">Универсальный сплит</span>
              </div>
              <p className="text-xs text-slate-600">
                Основная часть кнопки сразу запускает рекомендуемый «Сбалансированный поиск» в 1 клик, а стрелочка раскрывает меню с альтернативами: попозиционный, тонкая настройка или отмена.
              </p>

              <div className="p-4 bg-slate-50 rounded-lg border border-slate-200/80 flex items-center justify-between flex-wrap gap-3">
                <div className="text-xs">
                  <span className="font-bold text-slate-800">#854 ТЗ: Отделочные материалы</span>
                  <span className="text-slate-500"> · В ТЗ выделено 6 категорий</span>
                </div>

                <div className="relative inline-flex items-center">
                  <div className="inline-flex rounded-md shadow-xs">
                    <button
                      type="button"
                      onClick={() => triggerAction("Запущен сбалансированный поиск (1 списание)")}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-l-md text-xs font-bold cursor-pointer border-r border-teal-700"
                    >
                      <Zap size={14} />
                      <span>Запустить: Сбалансированный (1 шт)</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setConceptS3Open(!conceptS3Open)}
                      className="px-2 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-r-md cursor-pointer"
                      title="Другие варианты"
                    >
                      <ChevronDown size={14} />
                    </button>
                  </div>

                  {conceptS3Open && (
                    <div className="absolute right-0 top-full mt-1.5 w-64 bg-white border border-slate-200 rounded-lg shadow-xl z-30 py-1 text-xs">
                      <button
                        type="button"
                        onClick={() => {
                          setConceptS3Open(false);
                          triggerAction("Запущен сбалансированный поиск");
                        }}
                        className="w-full flex items-start gap-2 px-3 py-2 text-left hover:bg-slate-50"
                      >
                        <Zap size={14} className="text-teal-600 mt-0.5 shrink-0" />
                        <div>
                          <div className="font-bold text-slate-900">Сбалансированный (1 списание)</div>
                          <div className="text-[11px] text-slate-500">Квота распределяется по всем 6 позициям</div>
                        </div>
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setConceptS3Open(false);
                          triggerAction("Запущен попозиционный поиск");
                        }}
                        className="w-full flex items-start gap-2 px-3 py-2 text-left hover:bg-slate-50"
                      >
                        <Search size={14} className="text-blue-600 mt-0.5 shrink-0" />
                        <div>
                          <div className="font-bold text-slate-900">Попозиционный (6 списаний)</div>
                          <div className="text-[11px] text-slate-500">Глубокий независимый пул по каждой позиции</div>
                        </div>
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setConceptS3Open(false);
                          triggerAction("Открыто окно ручного выбора позиций");
                        }}
                        className="w-full flex items-start gap-2 px-3 py-2 text-left hover:bg-slate-50"
                      >
                        <Filter size={14} className="text-amber-600 mt-0.5 shrink-0" />
                        <div>
                          <div className="font-bold text-slate-900">Настроить категории вручную</div>
                          <div className="text-[11px] text-slate-500">Выбрать только нужные позиции галочками</div>
                        </div>
                      </button>
                      <div className="border-t border-slate-100 my-1" />
                      <button
                        type="button"
                        onClick={() => {
                          setConceptS3Open(false);
                          triggerAction("Задача отменена клиентом");
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-rose-50 text-rose-700 font-semibold"
                      >
                        <XCircle size={14} />
                        <span>Отменить задачу (возврат баланса)</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* CONCEPT S4: Expandable Accordion Card Directly in Row */}
            <div className="bg-white rounded-xl border-2 border-teal-500/80 p-5 shadow-sm space-y-3.5 relative overflow-hidden">
              <div className="absolute top-0 right-0 bg-teal-600 text-white text-[10px] font-black uppercase tracking-wider px-3 py-1 rounded-bl-lg shadow-2xs">
                🏆 ВЫБРАН ВАМИ — ВНЕДРЁН В ЛК
              </div>

              <div className="flex items-center justify-between pr-24">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs px-2 py-0.5 rounded-md bg-teal-100 text-teal-800 font-black">
                    КОНЦЕПТ S4 (АКТИВНЫЙ)
                  </span>
                  <h3 className="text-sm font-bold text-slate-900">
                    Инлайн-аккордеон прямо в строке задачи (Zero Modal Windows)
                  </h3>
                </div>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                По нажатию «Выбрать стратегию» строка не открывает громоздкое модальное окно, а плавно раскрывается прямо внутри таблицы. Для больших спецификаций (10–50 позиций) встроен режим «Показать ещё» и деликатная полоса прокрутки, исключающая бесконечное растягивание страницы.
              </p>

              <div className="bg-slate-50/80 rounded-lg border border-slate-200/90 overflow-hidden">
                {/* Accordion Trigger Header */}
                <div
                  onClick={() => setConceptS4Expanded(!conceptS4Expanded)}
                  className="p-3.5 sm:p-4 flex items-center justify-between gap-3 cursor-pointer hover:bg-slate-100/70 transition-colors bg-white border-b border-slate-200/70"
                >
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-mono font-bold text-slate-400">#854</span>
                    <span className="font-bold text-slate-900">Подвесные потолочные системы и светильники</span>
                    <span className="text-slate-300">·</span>
                    <span className="text-teal-700 font-bold bg-teal-50 px-2 py-0.5 rounded-md border border-teal-200/60">
                      Выбор стратегии ({conceptS4Items.length} категорий)
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-600">
                      {conceptS4Expanded ? "Свернуть" : "Раскрыть настройку"}
                    </span>
                    {conceptS4Expanded ? <ChevronUp size={16} className="text-teal-600" /> : <ChevronDown size={16} />}
                  </div>
                </div>

                {/* Accordion Content */}
                {conceptS4Expanded && (
                  <div className="p-4 bg-white space-y-3.5">
                    {/* Information Note */}
                    <div className="bg-teal-50/70 border border-teal-200/80 rounded-lg p-3 sm:p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                      <div className="flex items-start sm:items-center gap-2.5">
                        <div className="w-7 h-7 rounded-md bg-teal-600 text-white flex items-center justify-center shrink-0 mt-0.5 sm:mt-0 shadow-2xs">
                          <Sliders size={14} />
                        </div>
                        <div>
                          <div className="text-xs font-extrabold text-slate-900 flex items-center gap-2 flex-wrap">
                            <span>В спецификации выделено {conceptS4Items.length} категорий</span>
                            <span className="text-[10px] font-bold text-teal-800 bg-teal-100/90 px-2 py-0.5 rounded-xs">
                              Кластеризовано по пулам поставщиков
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">
                            Сопутствующий крепеж и расходники поглощены основными системами. Выберите способ поиска поставщиков:
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Top Control Bar: Segmented Switcher & Primary CTA */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-slate-50/80 p-2 sm:p-2.5 rounded-lg border border-slate-200/80">
                      {/* Segmented Mode Switcher */}
                      <div className="inline-flex items-center rounded-md border border-slate-200 bg-white p-0.5 shadow-2xs">
                        <button
                          type="button"
                          onClick={() => setConceptS4Mode("balanced")}
                          className={`px-3 py-1.5 rounded-xs text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                            conceptS4Mode === "balanced"
                              ? "bg-teal-600 text-white shadow-2xs"
                              : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                          }`}
                        >
                          <span>⚖️ Сбалансированный поиск</span>
                          <span className={`text-[10px] px-1.5 py-0.2 rounded-xs font-semibold ${
                            conceptS4Mode === "balanced" ? "bg-teal-700/80 text-white" : "bg-slate-100 text-slate-500"
                          }`}>
                            1 задача
                          </span>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setConceptS4Mode("per_item");
                            setConceptS4CategoriesCollapsed(false);
                          }}
                          className={`px-3 py-1.5 rounded-xs text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                            conceptS4Mode === "per_item"
                              ? "bg-teal-600 text-white shadow-2xs"
                              : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                          }`}
                        >
                          <span>🔍 Попозиционный поиск</span>
                          <span className={`text-[10px] px-1.5 py-0.2 rounded-xs font-semibold ${
                            conceptS4Mode === "per_item" ? "bg-teal-700/80 text-white" : "bg-slate-100 text-slate-500"
                          }`}>
                            {conceptS4Items.filter((i) => i.checked).length} поз.
                          </span>
                        </button>
                      </div>

                      {/* Quick Launch CTA right in the control bar */}
                      <div className="flex items-center gap-2">
                        {conceptS4Mode === "balanced" ? (
                          <button
                            type="button"
                            onClick={() => triggerAction("Запущен сбалансированный поиск (1 задача)")}
                            className="px-4 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-bold shadow-xs cursor-pointer flex items-center gap-1.5"
                          >
                            <CheckCircle2 size={14} />
                            <span>Запустить поиск (1 задача)</span>
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => triggerAction(`Запущен попозиционный поиск (${conceptS4Items.filter((i) => i.checked).length} задач)`)}
                            className="px-4 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-bold shadow-xs cursor-pointer flex items-center gap-1.5"
                            disabled={conceptS4Items.filter((i) => i.checked).length === 0}
                          >
                            <CheckCircle2 size={14} />
                            <span>Запустить ({conceptS4Items.filter((i) => i.checked).length} {conceptS4Items.filter((i) => i.checked).length === 1 ? "задача" : conceptS4Items.filter((i) => i.checked).length < 5 ? "задачи" : "задач"})</span>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Quiet Subtitle / Description */}
                    {conceptS4Mode === "balanced" ? (
                      <div className="flex items-center justify-between text-xs text-slate-600 px-1 flex-wrap gap-2">
                        <p className="leading-snug">
                          Единый консолидированный отчёт. Поставщики подбираются пропорционально по всем {conceptS4Items.length} позициям ТЗ без доплат (1 задача).
                        </p>
                        <button
                          type="button"
                          onClick={() => setConceptS4PreviewCategories(!conceptS4PreviewCategories)}
                          className="text-teal-700 hover:text-teal-900 font-semibold text-[11px] underline cursor-pointer shrink-0"
                        >
                          {conceptS4PreviewCategories ? "Скрыть список категорий ▴" : `Посмотреть позиции ТЗ (${conceptS4Items.length}) ▾`}
                        </button>
                      </div>
                    ) : (
                      <div className="text-xs text-slate-600 px-1 leading-snug">
                        Глубокий независимый сбор по каждой выбранной позиции в отдельные вкладки отчёта (по 1 задаче за категорию).
                      </div>
                    )}

                    {/* Balanced Mode Optional Preview of Items (read-only, no checkboxes) */}
                    {conceptS4Mode === "balanced" && conceptS4PreviewCategories ? (
                      <div className="p-3 bg-white rounded-lg border border-slate-200/80 space-y-2">
                        <div className="text-[11px] font-bold text-slate-700">
                          Включены в консолидированный поиск ({conceptS4Items.length}):
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {conceptS4Items.map((it, idx) => (
                            <span
                              key={it.id || idx}
                              className="inline-flex items-center gap-1 px-2 py-1 bg-slate-50 border border-slate-200 rounded-md text-xs text-slate-800"
                            >
                              <span className="font-bold text-slate-500">{idx + 1}.</span>
                              <span>{it.name}</span>
                              {it.qty ? <span className="text-slate-400 text-[10px]">({it.qty})</span> : null}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    {/* PER-ITEM MODE: Categories Selection Accordion (ONLY RENDERS IN PER_ITEM MODE!) */}
                    {conceptS4Mode === "per_item" ? (
                      <div className="bg-white rounded-lg border border-slate-200/90 p-3 sm:p-3.5 space-y-2.5">
                        {/* Categories Selection Toolbar */}
                        <div className="flex items-center justify-between gap-2 flex-wrap pb-2 border-b border-slate-100">
                          <div className="text-xs font-bold text-slate-800 flex items-center gap-2">
                            <span>Категории ТЗ ({conceptS4Items.length}):</span>
                            <span className="text-[11px] font-normal text-slate-500">
                              отметьте зелеными галочками нужные для поиска
                            </span>
                          </div>

                          <div className="flex items-center gap-2 text-[11px]">
                            <button
                              type="button"
                              onClick={() => {
                                const allChecked = conceptS4Items.map((it) => ({ ...it, checked: true }));
                                setConceptS4Items(allChecked);
                              }}
                              className="px-2 py-1 bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-md font-semibold cursor-pointer"
                            >
                              Выбрать все ({conceptS4Items.length})
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                const coreChecked = conceptS4Items.map((it) => ({ ...it, checked: it.core }));
                                setConceptS4Items(coreChecked);
                              }}
                              className="px-2 py-1 bg-teal-50 hover:bg-teal-100 text-teal-800 border border-teal-200 rounded-md font-bold cursor-pointer"
                            >
                              Только основные ({conceptS4Items.filter((i) => i.core).length})
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                const allUnchecked = conceptS4Items.map((it) => ({ ...it, checked: false }));
                                setConceptS4Items(allUnchecked);
                              }}
                              className="px-2 py-1 text-slate-500 hover:text-slate-800 font-medium cursor-pointer"
                            >
                              Снять все
                            </button>
                            <div className="h-3.5 w-px bg-slate-200" />
                            <button
                              type="button"
                              onClick={() => setConceptS4CategoriesCollapsed(!conceptS4CategoriesCollapsed)}
                              className="px-2 py-1 text-teal-700 hover:text-teal-900 font-bold flex items-center gap-1 cursor-pointer"
                            >
                              <span>{conceptS4CategoriesCollapsed ? "Развернуть список" : "Свернуть список"}</span>
                              {conceptS4CategoriesCollapsed ? <ChevronDown size={13} /> : <ChevronUp size={13} />}
                            </button>
                          </div>
                        </div>

                        {/* Categories Grid (collapsible) */}
                        {!conceptS4CategoriesCollapsed ? (
                          <>
                            <div className={`grid grid-cols-1 sm:grid-cols-2 gap-2 ${
                              conceptS4Items.length > 6 && conceptS4ShowAll ? "max-h-64 overflow-y-auto pr-1 category-scroll-container" : ""
                            }`}>
                              {(conceptS4Items.length <= 6 || conceptS4ShowAll ? conceptS4Items : conceptS4Items.slice(0, 6)).map((item, idx) => {
                                const isChecked = item.checked;
                                return (
                                  <div
                                    key={item.id}
                                    onClick={() => {
                                      const updated = [...conceptS4Items];
                                      const targetIdx = conceptS4Items.findIndex((it) => it.id === item.id);
                                      if (targetIdx !== -1) {
                                        updated[targetIdx].checked = !updated[targetIdx].checked;
                                        setConceptS4Items(updated);
                                      }
                                    }}
                                    className={`flex flex-col text-xs bg-white p-2.5 rounded-md border transition-all cursor-pointer ${
                                      isChecked
                                        ? "border-teal-400 bg-teal-50/20 shadow-2xs"
                                        : "border-slate-200 opacity-60 hover:opacity-100 hover:border-slate-300"
                                    }`}
                                  >
                                    <div className="flex items-center justify-between gap-2">
                                      <div className="flex items-center gap-2 min-w-0">
                                        <div
                                          className={`w-4 h-4 rounded border flex items-center justify-center transition-all shrink-0 ${
                                            isChecked
                                              ? "bg-emerald-600 border-emerald-600 text-white shadow-2xs"
                                              : "bg-white border-slate-300 hover:border-emerald-500"
                                          }`}
                                        >
                                          {isChecked && <Check size={11} strokeWidth={3.5} className="text-white" />}
                                        </div>
                                        <span className="font-bold text-slate-800 truncate">
                                          {idx + 1}. {item.name}
                                        </span>
                                      </div>
                                      <div className="flex items-center gap-1.5 shrink-0">
                                        {item.core ? (
                                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-xs bg-teal-50 text-teal-700 border border-teal-200/70">
                                            Основная
                                          </span>
                                        ) : (
                                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-xs bg-amber-50 text-amber-800 border border-amber-200/70">
                                            Комплектующие
                                          </span>
                                        )}
                                        {item.qty ? (
                                          <span className="text-slate-500 font-medium text-[11px]">
                                            {item.qty}
                                          </span>
                                        ) : null}
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>

                            {conceptS4Items.length > 6 ? (
                              <button
                                type="button"
                                onClick={() => setConceptS4ShowAll(!conceptS4ShowAll)}
                                className="w-full py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-md text-xs font-bold transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                              >
                                {conceptS4ShowAll ? (
                                  <>
                                    <ChevronUp size={14} />
                                    <span>Свернуть список категорий (показаны все {conceptS4Items.length})</span>
                                  </>
                                ) : (
                                  <>
                                    <ChevronDown size={14} />
                                    <span>Показать ещё {conceptS4Items.length - 6} категорий с прокруткой (всего {conceptS4Items.length})</span>
                                  </>
                                )}
                              </button>
                            ) : null}
                          </>
                        ) : null}

                        {/* Summary Bar */}
                        <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600 flex-wrap gap-2">
                          <div>
                            Выбрано категорий: <strong className="text-slate-900">{conceptS4Items.filter((i) => i.checked).length}</strong> из {conceptS4Items.length} · К списанию: <strong className="text-teal-700">{conceptS4Items.filter((i) => i.checked).length} {conceptS4Items.filter((i) => i.checked).length === 1 ? "задача" : conceptS4Items.filter((i) => i.checked).length < 5 ? "задачи" : "задач"}</strong>
                          </div>
                          <button
                            type="button"
                            onClick={() => triggerAction(`Запущен попозиционный поиск (${conceptS4Items.filter((i) => i.checked).length} задач)`)}
                            className="px-3.5 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-md text-xs font-bold shadow-xs cursor-pointer flex items-center gap-1.5"
                            disabled={conceptS4Items.filter((i) => i.checked).length === 0}
                          >
                            <CheckCircle2 size={14} />
                            <span>Запустить ({conceptS4Items.filter((i) => i.checked).length} {conceptS4Items.filter((i) => i.checked).length === 1 ? "задача" : conceptS4Items.filter((i) => i.checked).length < 5 ? "задачи" : "задач"})</span>
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            </div>

            {/* CONCEPT S5: Compact Micro-Popover */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-800 font-black">
                    КОНЦЕПТ S5
                  </span>
                  <h3 className="text-sm font-bold text-slate-900">
                    Floating Micro-Popover (Плавающий диалог над кнопкой)
                  </h3>
                </div>
                <span className="text-xs font-semibold text-slate-500">Компактное окно</span>
              </div>
              <p className="text-xs text-slate-600">
                Всплывает компактное окошко прямо возле кнопки с переключателем и кнопками «Старт» / «Отмена». Не затемняет экран и не скроллит страницу.
              </p>

              <div className="p-4 bg-slate-50 rounded-lg border border-slate-200/80 flex items-center justify-between flex-wrap gap-3">
                <div className="text-xs">
                  <span className="font-bold text-slate-800">#854 ТЗ: Отделочные материалы</span>
                  <span className="text-slate-500"> · Выбор стратегии</span>
                </div>

                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setConceptS5Open(!conceptS5Open)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-800 border border-slate-300 rounded-md text-xs font-bold shadow-2xs cursor-pointer"
                  >
                    <Sliders size={14} className="text-teal-600" />
                    <span>Выбрать стратегию (6 поз.)</span>
                    <ChevronDown size={14} />
                  </button>

                  {conceptS5Open && (
                    <div className="absolute right-0 bottom-full mb-2 w-72 bg-white border border-slate-200 rounded-xl shadow-2xl z-30 p-3.5 space-y-3 text-xs">
                      <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                        <span className="font-bold text-slate-900">Стратегия поиска (6 кат.)</span>
                        <button
                          type="button"
                          onClick={() => setConceptS5Open(false)}
                          className="text-slate-400 hover:text-slate-700"
                        >
                          ✕
                        </button>
                      </div>

                      <div className="space-y-2">
                        <label className="flex items-start gap-2 p-2 rounded-lg bg-teal-50/70 border border-teal-200/60 cursor-pointer">
                          <input type="radio" name="popover-strat" defaultChecked className="mt-0.5 text-teal-600" />
                          <div>
                            <div className="font-bold text-teal-950">Сбалансированный</div>
                            <div className="text-[11px] text-teal-800">1 списание с баланса, сводный отчёт</div>
                          </div>
                        </label>
                        <label className="flex items-start gap-2 p-2 rounded-lg bg-slate-50 border border-slate-200 cursor-pointer">
                          <input type="radio" name="popover-strat" className="mt-0.5 text-teal-600" />
                          <div>
                            <div className="font-bold text-slate-900">Попозиционный</div>
                            <div className="text-[11px] text-slate-500">6 списаний, детальные пулы</div>
                          </div>
                        </label>
                      </div>

                      <div className="pt-1 flex items-center justify-between gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setConceptS5Open(false);
                            triggerAction("Задача отменена клиентом");
                          }}
                          className="text-rose-600 hover:underline font-semibold text-[11px]"
                        >
                          Отменить задачу
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setConceptS5Open(false);
                            triggerAction("Стратегия подтверждена");
                          }}
                          className="px-3 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-md font-bold shadow-2xs"
                        >
                          Применить
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Bottom Recommendation & Feedback Box */}
        <div className="mt-8 bg-gradient-to-r from-teal-900 to-slate-900 rounded-xl p-6 text-white shadow-lg flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-1.5 max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full bg-teal-400 text-slate-950">
                Рекомендация инженера
              </span>
              <span className="text-xs font-semibold text-teal-200">Какой вариант лучше внедрить?</span>
            </div>
            <h4 className="text-base font-bold">
              Рекомендуем: Стиль #1 (Modern Precision) для таблицы + Концепт S2 или S3 для стратегии
            </h4>
            <p className="text-xs text-slate-300 leading-relaxed">
              <strong>Стиль #1</strong> навсегда убирает неестественные круглые пилюли, дает строгие скругления 6px, деликатные границы и цветовую кодировку иконок. А <strong>Концепт S2/S3</strong> позволяет клиенту запускать поиск по сложному ТЗ в 1 клик прямо из таблицы без необходимости всплытия модального окна.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={() => copyToClipboard("Внедряем Стиль #1 (Modern Precision) и Концепт S2 (Inline Switcher)", "verdict-1")}
              className="px-4 py-2.5 bg-teal-500 hover:bg-teal-400 text-slate-950 rounded-lg text-xs font-black shadow-md transition-all cursor-pointer text-center"
            >
              {copiedKey === "verdict-1" ? "✓ Скопировано!" : "Скопировать вердикт #1 + S2"}
            </button>
            <Link
              href="/cabinet"
              className="px-4 py-2.5 bg-white/10 hover:bg-white/20 text-white border border-white/20 rounded-lg text-xs font-bold transition-all text-center"
            >
              Вернуться в кабинет
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
