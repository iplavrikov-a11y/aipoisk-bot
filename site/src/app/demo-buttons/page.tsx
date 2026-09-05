"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Gift,
  History,
  MessageCircle,
  Send,
  Mail,
  Sliders,
  BookOpen,
  Bell,
  Check,
  Copy,
  ChevronDown,
  Sparkles,
  ArrowLeft,
  CheckCircle2,
} from "lucide-react";

type SubVariant = {
  code: string;
  name: string;
  fontDesc: string;
  colorDesc: string;
  renderButton: (size?: "normal" | "large") => React.ReactNode;
};

type ButtonVariant = {
  id: number;
  name: string;
  category: string;
  description: string;
  renderButton: (size?: "normal" | "large") => React.ReactNode;
};

export default function DemoButtonsPage() {
  const [activeTab, setActiveTab] = useState<"refined" | "all">("refined");
  const [selectedSub, setSelectedSub] = useState<string>("5.1");
  const [selectedMain, setSelectedMain] = useState<number>(5);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copyCode = (code: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(`Утверждаю вариант ${code}`);
      setCopiedKey(code);
      setTimeout(() => setCopiedKey(null), 2000);
    }
  };

  // 6 refined sub-variants based on Option 5 (colored gift icon + smaller font for +1000)
  const refinedVariants: SubVariant[] = [
    {
      code: "5.1",
      name: "Изумрудный микрошрифт (10px, жирный)",
      fontDesc: "Размер текста (+1 000 ₽) уменьшен до 10px (против 12px у слова «Пригласить»).",
      colorDesc: "Яркая золотистая иконка подарка (amber-500) + сочный темно-изумрудный бонус (emerald-700).",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-amber-500 shrink-0" aria-hidden="true" />
          <span>Пригласить</span>
          <span
            className={`${
              size === "large" ? "text-xs" : "text-[10px]"
            } font-extrabold text-emerald-700 tracking-tight leading-none`}
          >
            (+1 000 ₽)
          </span>
        </button>
      ),
    },
    {
      code: "5.2",
      name: "Сдержанный серый микрошрифт (10px)",
      fontDesc: "Сумма (+1 000 ₽) уменьшена до 10px и окрашена в благородный темно-серый (slate-500).",
      colorDesc: "Единственный цветной акцент на кнопке — золотая иконка подарка. Кнопка не отвлекает от работы.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-amber-500 shrink-0" aria-hidden="true" />
          <span>Пригласить</span>
          <span
            className={`${
              size === "large" ? "text-xs" : "text-[10px]"
            } font-bold text-slate-500 tracking-tight leading-none`}
          >
            (+1 000 ₽)
          </span>
        </button>
      ),
    },
    {
      code: "5.3",
      name: "Фирменный бирюзовый микрошрифт (10px, Teal)",
      fontDesc: "Сумма (+1 000 ₽) уменьшена до 10px и окрашена в фирменный цвет сервиса (teal-700).",
      colorDesc: "Золотой подарок для привлечения внимания + бирюзовая цифра, перекликающаяся с кнопками кабинета.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-amber-500 shrink-0" aria-hidden="true" />
          <span>Пригласить</span>
          <span
            className={`${
              size === "large" ? "text-xs" : "text-[10px]"
            } font-extrabold text-teal-700 tracking-tight leading-none`}
          >
            (+1 000 ₽)
          </span>
        </button>
      ),
    },
    {
      code: "5.4",
      name: "Изумрудный микро-чип (+1 000 ₽, 9px)",
      fontDesc: "Сумма вынесена в аккуратный миниатюрный бейджик сверхкомпактного размера (9px).",
      colorDesc: "Светло-зеленая плашечка (bg-emerald-100 text-emerald-800) мгновенно считывается как бонус.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-amber-500 shrink-0" aria-hidden="true" />
          <span>Пригласить</span>
          <span
            className={`${
              size === "large" ? "text-[11px] px-2 py-0.5" : "text-[9px] px-1.5 py-0.5"
            } rounded bg-emerald-100 text-emerald-800 font-black tracking-tight leading-none`}
          >
            +1 000 ₽
          </span>
        </button>
      ),
    },
    {
      code: "5.5",
      name: "Золотистый микро-чип (+1 000 ₽, 9px)",
      fontDesc: "Микро-чип 9px в единой золотисто-медовой гамме со значком подарка.",
      colorDesc: "Теплая плашечка (bg-amber-100 text-amber-900) создает единый целостный визуальный акцент.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-amber-500 shrink-0" aria-hidden="true" />
          <span>Пригласить</span>
          <span
            className={`${
              size === "large" ? "text-[11px] px-2 py-0.5" : "text-[9px] px-1.5 py-0.5"
            } rounded bg-amber-100 text-amber-900 font-black tracking-tight leading-none`}
          >
            +1 000 ₽
          </span>
        </button>
      ),
    },
    {
      code: "5.6",
      name: "Изумрудная иконка + изумрудный микрошрифт (10px)",
      fontDesc: "Альтернатива золоту: цветная иконка подарка в изумрудном денежном тоне (emerald-600).",
      colorDesc: "Гармония зеленого: и подарок, и уменьшенная сумма (+1 000 ₽) выполнены в одном сочном зеленом цвете.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-emerald-600 shrink-0" aria-hidden="true" />
          <span>Пригласить</span>
          <span
            className={`${
              size === "large" ? "text-xs" : "text-[10px]"
            } font-extrabold text-emerald-700 tracking-tight leading-none`}
          >
            (+1 000 ₽)
          </span>
        </button>
      ),
    },
  ];

  const allVariants: ButtonVariant[] = [
    {
      id: 1,
      name: "Мягкий бирюзовый тинт (Teal Soft)",
      category: "В палитре бренда",
      description: "Легкая бирюзовая подложка в тон соседней кнопке «Чат сайта». Насыщенная иконка и контрастный текст.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-teal-50/90 hover:bg-teal-100 text-teal-950 border border-teal-200/90 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-teal-700 shrink-0" aria-hidden="true" />
          <span>Пригласить (+1 000 ₽)</span>
        </button>
      ),
    },
    {
      id: 2,
      name: "Бирюзовый тинт с акцентной суммой",
      category: "В палитре бренда",
      description: "Бирюзовая подложка, а бонус (+1 000 ₽) дополнительно выделен темно-бирюзовым жирным акцентом.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-teal-50/80 hover:bg-teal-100 text-slate-800 border border-teal-200 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-teal-700 shrink-0" aria-hidden="true" />
          <span>
            Пригласить <span className="text-teal-700 font-extrabold">(+1 000 ₽)</span>
          </span>
        </button>
      ),
    },
    {
      id: 3,
      name: "Нейтральная кнопка + изумрудный чип",
      category: "Чип бонуса",
      description: "Базовый серый фон как у тулбара, а сумма +1 000 ₽ оформлена аккуратным зеленым мини-бейджем.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-emerald-600 shrink-0" aria-hidden="true" />
          <span>Пригласить</span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[10px] font-black leading-none">
            +1 000 ₽
          </span>
        </button>
      ),
    },
    {
      id: 4,
      name: "Нейтральная кнопка + бирюзовый чип",
      category: "Чип бонуса",
      description: "Серая кнопка, чип бонуса выполнен в фирменном бирюзовом цвете TenderLex (teal-100).",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-teal-700 shrink-0" aria-hidden="true" />
          <span>Пригласить</span>
          <span className="px-1.5 py-0.5 rounded bg-teal-100 text-teal-800 text-[10px] font-black leading-none">
            +1 000 ₽
          </span>
        </button>
      ),
    },
    {
      id: 5,
      name: "Серая кнопка с золотой иконкой подарка (Оригинал №5)",
      category: "Акцент на иконке",
      description: "Серая спокойная кнопка, яркий акцент сделан только на золотистом подарке (amber-500) и сумме.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-amber-500 shrink-0" aria-hidden="true" />
          <span>
            Пригласить <span className="text-emerald-700 font-extrabold">(+1 000 ₽)</span>
          </span>
        </button>
      ),
    },
    {
      id: 6,
      name: "Деликатный оттенок шампанского (Light Amber)",
      category: "Теплый оттенок",
      description: "Очень светлый полупрозрачный медово-золотой тон (amber-50/50). Без ядовитой желтизны и тяжести.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-amber-50/50 hover:bg-amber-100/60 text-slate-800 border border-amber-200/70 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-amber-600 shrink-0" aria-hidden="true" />
          <span>
            Пригласить <span className="text-amber-800 font-extrabold">(+1 000 ₽)</span>
          </span>
        </button>
      ),
    },
    {
      id: 7,
      name: "Свежий изумрудный тинт (Emerald Fresh)",
      category: "Изумрудный тон",
      description: "Светло-зеленый изумрудный тон в стиле кнопки «Справка по функциям». Подчеркивает денежный бонус.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-emerald-50/90 hover:bg-emerald-100 text-emerald-950 border border-emerald-200/90 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-emerald-700 shrink-0" aria-hidden="true" />
          <span>Пригласить (+1 000 ₽)</span>
        </button>
      ),
    },
    {
      id: 8,
      name: "Белый фон с тонким бирюзовым контуром",
      category: "Контурный стиль",
      description: "Чистый белый фон с четкой бирюзовой границей (border-teal-500/70). Выглядит как активное действие.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-white hover:bg-teal-50/60 text-teal-900 border border-teal-500/70 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-teal-600 shrink-0" aria-hidden="true" />
          <span>Пригласить (+1 000 ₽)</span>
        </button>
      ),
    },
    {
      id: 9,
      name: "Мягкий бирюзово-мятный градиент",
      category: "Градиент",
      description: "Плавный микро-перелив от бирюзы к изумруду (from-teal-50 via-emerald-50/70 to-teal-50). Премиальный вид.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-gradient-to-r from-teal-50 via-emerald-50/60 to-teal-50 hover:from-teal-100 hover:to-emerald-100 text-teal-950 border border-teal-200/90 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-teal-700 shrink-0" aria-hidden="true" />
          <span>Пригласить (+1 000 ₽)</span>
        </button>
      ),
    },
    {
      id: 10,
      name: "Иконка в отдельном микро-бейдже",
      category: "Иконка в плашке",
      description: "Серая кнопка, где иконка подарка помещена в аккуратный бирюзовый квадрат со скругленными краями.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "pl-2 pr-3.5 py-1.5 text-sm" : "pl-1.5 pr-2.5 py-1 text-xs"
          } bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <span
            className={`${
              size === "large" ? "w-6 h-6" : "w-5 h-5"
            } rounded bg-teal-100 text-teal-800 flex items-center justify-center shrink-0`}
          >
            <Gift size={size === "large" ? 13 : 11} aria-hidden="true" />
          </span>
          <span>Пригласить (+1 000 ₽)</span>
        </button>
      ),
    },
  ];

  const currentRefined =
    refinedVariants.find((r) => r.code === selectedSub) || refinedVariants[0];
  const currentMain =
    allVariants.find((v) => v.id === selectedMain) || allVariants[4];

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-20">
      {/* Sticky top navigation */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-2xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-3">
            <Link
              href="/cabinet"
              className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-600 hover:text-teal-700 transition-colors"
            >
              <ArrowLeft size={14} />
              <span>Вернуться в кабинет</span>
            </Link>
            <span className="text-slate-300">|</span>
            <span className="text-xs font-extrabold text-slate-900">
              Вариант №5: подбор размера шрифта (+1 000 ₽)
            </span>
          </div>

          {/* Mode switch */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200">
            <button
              type="button"
              onClick={() => setActiveTab("refined")}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeTab === "refined"
                  ? "bg-white text-teal-900 shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              ⭐ Уточнения к Варианту 5 (6 версий)
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("all")}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeTab === "all"
                  ? "bg-white text-slate-900 shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Все 10 концептов
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-8 space-y-8">
        {/* Header */}
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 text-amber-900 border border-amber-200 text-xs font-bold">
            <Sparkles size={13} className="text-amber-600" />
            <span>Выбран базовый Вариант №5: серая кнопка + цветная иконка</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            {activeTab === "refined"
              ? "Подбор стиля и размера шрифта «+1 000 ₽»"
              : "Все 10 концептов дизайна кнопки"}
          </h1>
          <p className="text-sm text-slate-600 leading-relaxed">
            {activeTab === "refined"
              ? "Иконка подарка цветная, фон кнопки нейтральный серый в едином стиле тулбара. Ниже представлены 6 вариантов с уменьшенным шрифтом бонуса."
              : "Сравнение исходных концепций кнопки в контексте панели управления."}
          </p>
        </div>

        {/* Live Toolbar Simulation Box */}
        <section className="bg-white rounded-2xl p-5 sm:p-6 border border-slate-200 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-teal-700">
                Интерактивный тулбар кабинета
              </div>
              <h2 className="text-base font-extrabold text-slate-900 mt-0.5">
                {activeTab === "refined"
                  ? `Отображается Вариант ${currentRefined.code}: ${currentRefined.name}`
                  : `Отображается Вариант №${currentMain.id}: ${currentMain.name}`}
              </h2>
            </div>
            <button
              type="button"
              onClick={() => copyCode(activeTab === "refined" ? currentRefined.code : `№${currentMain.id}`)}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-teal-700 hover:bg-teal-800 text-white rounded-lg text-xs font-bold transition-colors cursor-pointer shrink-0 shadow-2xs"
            >
              {copiedKey === (activeTab === "refined" ? currentRefined.code : `№${currentMain.id}`) ? (
                <>
                  <Check size={13} />
                  <span>Скопировано в буфер!</span>
                </>
              ) : (
                <>
                  <Copy size={13} />
                  <span>
                    Утвердить {activeTab === "refined" ? `Вариант ${currentRefined.code}` : `№${currentMain.id}`}
                  </span>
                </>
              )}
            </button>
          </div>

          {/* Full Realistic Toolbar */}
          <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-200 overflow-x-auto">
            <div className="min-w-[920px]">
              <div className="bg-white rounded-xl p-2.5 border border-slate-200 shadow-2xs flex items-center justify-between gap-2">
                {/* Left controls */}
                <div className="flex items-center gap-1.5 shrink-0">
                  {/* Balance */}
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-teal-900 text-white rounded-lg text-xs font-black shadow-2xs shrink-0">
                    <span>БАЛАНС</span>
                    <span className="font-extrabold">92 201 ₽</span>
                  </div>

                  {/* Tariffs */}
                  <div className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-slate-100 text-slate-800 border border-slate-200 rounded-lg text-xs font-bold shrink-0">
                    <Sliders size={13} className="text-teal-600" />
                    <span>Тарифы и цены</span>
                    <ChevronDown size={11} />
                  </div>

                  {/* Chat */}
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-teal-50 text-teal-900 border border-teal-200 rounded-lg text-xs font-bold shrink-0">
                    <MessageCircle size={13} className="text-teal-600" />
                    <span>Чат сайта</span>
                  </div>

                  {/* Telegram */}
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 text-slate-800 border border-slate-200 rounded-lg text-xs font-bold shrink-0">
                    <Send size={13} className="text-sky-500" />
                    <span>Telegram</span>
                  </div>

                  {/* Email */}
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 text-slate-800 border border-slate-200 rounded-lg text-xs font-bold shrink-0">
                    <Mail size={13} className="text-slate-500" />
                    <span>Email</span>
                  </div>

                  {/* History */}
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 text-slate-800 border border-slate-200 rounded-lg text-xs font-bold shrink-0">
                    <History size={13} className="text-teal-600" />
                    <span>История</span>
                  </div>

                  {/* ACTIVE TESTING BUTTON */}
                  <div className="relative">
                    {activeTab === "refined"
                      ? currentRefined.renderButton("normal")
                      : currentMain.renderButton("normal")}
                    <span className="absolute -top-2 -right-2 bg-amber-500 text-white text-[9px] font-black w-4 h-4 rounded-full flex items-center justify-center shadow-xs">
                      {activeTab === "refined" ? currentRefined.code : currentMain.id}
                    </span>
                  </div>
                </div>

                {/* Right controls */}
                <div className="flex items-center gap-1.5 shrink-0 ml-auto">
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-bold border bg-emerald-50 text-emerald-900 border-emerald-200 shrink-0">
                    <BookOpen size={13} className="text-emerald-700" />
                    <span>Справка по функциям</span>
                  </div>
                  <div className="p-1.5 rounded-lg border bg-teal-50 border-teal-200 text-teal-700 shrink-0">
                    <Bell size={13} />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Switchers */}
          <div className="flex items-center gap-2 flex-wrap pt-2">
            <span className="text-xs font-bold text-slate-500">
              {activeTab === "refined" ? "Выберите версию:" : "Выберите вариант:"}
            </span>
            {activeTab === "refined"
              ? refinedVariants.map((r) => (
                  <button
                    key={r.code}
                    type="button"
                    onClick={() => setSelectedSub(r.code)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-extrabold transition-all cursor-pointer ${
                      selectedSub === r.code
                        ? "bg-amber-500 text-white shadow-2xs"
                        : "bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200"
                    }`}
                  >
                    Вариант {r.code}
                  </button>
                ))
              : allVariants.map((v) => (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => setSelectedMain(v.id)}
                    className={`px-3 py-1 rounded-lg text-xs font-extrabold transition-all cursor-pointer ${
                      selectedMain === v.id
                        ? "bg-teal-700 text-white shadow-2xs"
                        : "bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200"
                    }`}
                  >
                    №{v.id}
                  </button>
                ))}
          </div>
        </section>

        {/* Tab 1: Refined Variants for Option 5 */}
        {activeTab === "refined" && (
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-extrabold text-slate-900">
                  6 версий Варианта №5 с уменьшенным шрифтом «+1 000 ₽»
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Базовая кнопка одинаковая: серая, строгая. Различается оформление и размер бонуса.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {refinedVariants.map((sub) => {
                const isSelected = selectedSub === sub.code;
                return (
                  <div
                    key={sub.code}
                    onClick={() => setSelectedSub(sub.code)}
                    className={`bg-white rounded-2xl p-5 border transition-all cursor-pointer flex flex-col justify-between space-y-4 ${
                      isSelected
                        ? "border-amber-500 ring-2 ring-amber-500/20 shadow-md"
                        : "border-slate-200 hover:border-slate-300 shadow-2xs hover:shadow-xs"
                    }`}
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-7 h-7 rounded-lg text-xs font-black flex items-center justify-center shrink-0 ${
                              isSelected
                                ? "bg-amber-500 text-white"
                                : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {sub.code}
                          </span>
                          <div>
                            <h3 className="text-sm font-extrabold text-slate-900 leading-tight">
                              {sub.name}
                            </h3>
                          </div>
                        </div>
                        <span
                          className={`text-[11px] px-2 py-0.5 rounded-full font-bold shrink-0 ${
                            isSelected
                              ? "bg-amber-100 text-amber-900"
                              : "bg-slate-100 text-slate-500"
                          }`}
                        >
                          {isSelected ? "Выбран" : sub.code}
                        </span>
                      </div>

                      <div className="text-xs text-slate-600 space-y-1">
                        <p>
                          <strong className="text-slate-800">Шрифт:</strong> {sub.fontDesc}
                        </p>
                        <p>
                          <strong className="text-slate-800">Цвет:</strong> {sub.colorDesc}
                        </p>
                      </div>

                      {/* Button in Large Preview */}
                      <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 flex items-center justify-center">
                        {sub.renderButton("large")}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                      <span className="text-[11px] text-slate-400 font-medium">
                        В тулбаре: 12px / бонус: 9–10px
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedSub(sub.code);
                          copyCode(sub.code);
                        }}
                        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                          isSelected
                            ? "bg-amber-500 hover:bg-amber-600 text-white"
                            : "bg-slate-100 hover:bg-slate-200 text-slate-800"
                        }`}
                      >
                        {copiedKey === sub.code ? (
                          <>
                            <Check size={13} />
                            <span>Скопировано!</span>
                          </>
                        ) : (
                          <>
                            <Copy size={13} />
                            <span>Утвердить {sub.code}</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Recommendation */}
            <div className="bg-amber-50/70 border border-amber-200/80 rounded-2xl p-5 text-center max-w-2xl mx-auto space-y-1.5">
              <div className="text-xs font-extrabold uppercase tracking-wider text-amber-900">
                Совет дизайнера по Варианту 5
              </div>
              <p className="text-xs text-slate-700 leading-relaxed">
                Самым чистым и сбалансированным выглядит <strong>Вариант 5.1</strong> (золотая иконка + аккуратный
                изумрудный микротекст 10px) и <strong>Вариант 5.4</strong> (золотая иконка + микро-чип 9px). Назовите
                код (например, «5.1» или «5.4»), и я сразу внедрю его в рабочий кабинет.
              </p>
            </div>
          </section>
        )}

        {/* Tab 2: All 10 concepts */}
        {activeTab === "all" && (
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-extrabold text-slate-900">
                Все 10 концептов дизайна кнопки
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {allVariants.map((variant) => {
                const isSelected = selectedMain === variant.id;
                return (
                  <div
                    key={variant.id}
                    onClick={() => setSelectedMain(variant.id)}
                    className={`bg-white rounded-2xl p-5 border transition-all cursor-pointer flex flex-col justify-between space-y-4 ${
                      isSelected
                        ? "border-teal-600 ring-2 ring-teal-600/20 shadow-md"
                        : "border-slate-200 hover:border-slate-300 shadow-2xs hover:shadow-xs"
                    }`}
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-6 h-6 rounded-lg text-xs font-black flex items-center justify-center shrink-0 ${
                              isSelected
                                ? "bg-teal-700 text-white"
                                : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {variant.id}
                          </span>
                          <div>
                            <h3 className="text-sm font-extrabold text-slate-900 leading-tight">
                              {variant.name}
                            </h3>
                            <span className="text-[10px] font-bold uppercase tracking-wider text-teal-700">
                              {variant.category}
                            </span>
                          </div>
                        </div>
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                            isSelected
                              ? "bg-teal-100 text-teal-800"
                              : "bg-slate-100 text-slate-500"
                          }`}
                        >
                          {isSelected ? "Выбран" : `Вариант №${variant.id}`}
                        </span>
                      </div>

                      <p className="text-xs text-slate-600 leading-relaxed">
                        {variant.description}
                      </p>

                      <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 flex items-center justify-center">
                        {variant.renderButton("large")}
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                      <span className="text-[11px] text-slate-400 font-medium">
                        Размер: 12px в тулбаре / 14px увеличенный
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedMain(variant.id);
                          copyCode(`№${variant.id}`);
                        }}
                        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                          isSelected
                            ? "bg-teal-700 hover:bg-teal-800 text-white"
                            : "bg-slate-100 hover:bg-slate-200 text-slate-800"
                        }`}
                      >
                        {copiedKey === `№${variant.id}` ? (
                          <>
                            <Check size={13} />
                            <span>Скопировано!</span>
                          </>
                        ) : (
                          <>
                            <Copy size={13} />
                            <span>Утвердить №{variant.id}</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
