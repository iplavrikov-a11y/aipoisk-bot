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
} from "lucide-react";

type Option54Variant = {
  code: string;
  name: string;
  badgeStyle: string;
  description: string;
  renderButton: (size?: "normal" | "large") => React.ReactNode;
};

export default function DemoButtonsPage() {
  const [selected54, setSelected54] = useState<string>("5.4A");
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copyCode = (code: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(`Утверждаю вариант ${code}`);
      setCopiedKey(code);
      setTimeout(() => setCopiedKey(null), 2000);
    }
  };

  const options54: Option54Variant[] = [
    {
      code: "5.4A",
      name: "Округлая капсула-пилюля (Pill Badge)",
      badgeStyle: "Мягкая скругленная капсула (rounded-full) вместо острого прямоугольника",
      description: "Светло-изумрудный фон с тонкой рамкой, мягкие края. Смотрится аккуратно, органично и не тяжело.",
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
              size === "large" ? "text-[11px] px-2.5 py-0.5" : "text-[9px] px-2 py-0.5"
            } rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300/80 font-black tracking-tight leading-none`}
          >
            +1 000 ₽
          </span>
        </button>
      ),
    },
    {
      code: "5.4B",
      name: "Контурный чип без заливки (Outline)",
      badgeStyle: "Прозрачный фон, только тонкая зеленая рамка",
      description: "Нет сплошного цветного пятна. Зеленый контур привлекает внимание к сумме, но кнопка остается ультра-легкой.",
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
            } rounded border border-emerald-500/80 text-emerald-700 font-extrabold tracking-tight leading-none`}
          >
            +1 000 ₽
          </span>
        </button>
      ),
    },
    {
      code: "5.4C",
      name: "Плотный изумруд с белым текстом (Solid)",
      badgeStyle: "Насыщенная изумрудная плашка, контрастный белый шрифт",
      description: "Четкий, уверенный акцент на бонусе. Выглядит солидно и не размывается на сером фоне.",
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
            } rounded bg-emerald-600 text-white font-black tracking-tight leading-none shadow-2xs`}
          >
            +1 000 ₽
          </span>
        </button>
      ),
    },
    {
      code: "5.4D",
      name: "Встроенный сплит-разделитель (Divider)",
      badgeStyle: "Вертикальная черточка вместо рамочки или плашки",
      description: "Никаких отдельных бейджей: тонкий разделитель отделяет слово «Пригласить» от зеленого бонуса +1 000 ₽.",
      renderButton: (size = "normal") => (
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 ${
            size === "large" ? "px-3.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs"
          } bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg font-bold transition-all shadow-2xs cursor-pointer shrink-0`}
        >
          <Gift size={size === "large" ? 16 : 13} className="text-amber-500 shrink-0" aria-hidden="true" />
          <span>Пригласить</span>
          <span className="w-px h-3 bg-slate-300 mx-0.5 shrink-0" />
          <span
            className={`${
              size === "large" ? "text-xs" : "text-[10px]"
            } font-black text-emerald-700 tracking-tight leading-none`}
          >
            +1 000 ₽
          </span>
        </button>
      ),
    },
    {
      code: "5.4E",
      name: "Лаконичный «+1 000» (без значка рубля)",
      badgeStyle: "Компактная капсула только с цифрой «+1 000»",
      description: "Убран символ ₽ — текст стал короче, кнопка компактнее, акцент строго на круглой цифре бонуса.",
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
            } rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300/80 font-black tracking-tight leading-none`}
          >
            +1 000
          </span>
        </button>
      ),
    },
    {
      code: "5.4F",
      name: "Золотистая капсула в тон подарка (Warm Amber)",
      badgeStyle: "Теплый янтарный бейдж в цвет иконки",
      description: "Единая гармоничная гамма: золотой подарок и золотой бейдж бонуса, без контрастирующего зеленого.",
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
              size === "large" ? "text-[11px] px-2.5 py-0.5" : "text-[9px] px-2 py-0.5"
            } rounded-full bg-amber-100 text-amber-900 border border-amber-300/80 font-black tracking-tight leading-none`}
          >
            +1 000 ₽
          </span>
        </button>
      ),
    },
    {
      code: "5.4G",
      name: "Фирменная бирюзовая капсула (Teal Brand)",
      badgeStyle: "Бейдж в фирменном бирюзовом цвете сервиса",
      description: "Округлая капсула в палитре TenderLex (teal-100). Идеально перекликается с кнопками панели.",
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
              size === "large" ? "text-[11px] px-2.5 py-0.5" : "text-[9px] px-2 py-0.5"
            } rounded-full bg-teal-100 text-teal-800 border border-teal-300/80 font-black tracking-tight leading-none`}
          >
            +1 000 ₽
          </span>
        </button>
      ),
    },
    {
      code: "5.4H",
      name: "Мягкий градиент шампань → изумруд",
      badgeStyle: "Микро-перелив от цвета подарка к цвету бонуса",
      description: "Плавный переход (from-amber-100 via-emerald-50 to-emerald-100). Смотрится стильно и современно.",
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
            } rounded bg-gradient-to-r from-amber-100 via-emerald-50 to-emerald-100 text-emerald-950 border border-emerald-200/90 font-black tracking-tight leading-none`}
          >
            +1 000 ₽
          </span>
        </button>
      ),
    },
  ];

  const currentVariant =
    options54.find((item) => item.code === selected54) || options54[0];

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-20">
      {/* Top Header */}
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
              Вариант 5.4: подбор оформления бонуса «+1 000 ₽»
            </span>
          </div>

          <div className="text-xs font-bold text-amber-900 bg-amber-50 px-2.5 py-1 rounded-full border border-amber-200">
            8 вариантов бейджа +1 000 ₽
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-8 space-y-8">
        {/* Intro */}
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 text-amber-900 border border-amber-200 text-xs font-bold">
            <Sparkles size={13} className="text-amber-600" />
            <span>База 5.4: серая кнопка + золотая иконка + слово «Пригласить»</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Как именно оформить «+1 000 ₽»?
          </h1>
          <p className="text-sm text-slate-600 leading-relaxed">
            Ниже представлены 8 различных способов отображения бонуса: округлые капсулы, контурные рамки,
            контрастная заливка, сплит-разделитель и компактный формат без значка рубля.
          </p>
        </div>

        {/* Live Toolbar Preview */}
        <section className="bg-white rounded-2xl p-5 sm:p-6 border border-slate-200 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-amber-800">
                Интерактивный тулбар кабинета
              </div>
              <h2 className="text-base font-extrabold text-slate-900 mt-0.5">
                Отображается {currentVariant.code}: {currentVariant.name}
              </h2>
            </div>
            <button
              type="button"
              onClick={() => copyCode(currentVariant.code)}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-teal-700 hover:bg-teal-800 text-white rounded-lg text-xs font-bold transition-colors cursor-pointer shrink-0 shadow-2xs"
            >
              {copiedKey === currentVariant.code ? (
                <>
                  <Check size={13} />
                  <span>Скопировано в буфер!</span>
                </>
              ) : (
                <>
                  <Copy size={13} />
                  <span>Утвердить {currentVariant.code}</span>
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

                  {/* ACTIVE BUTTON UNDER TEST */}
                  <div className="relative">
                    {currentVariant.renderButton("normal")}
                    <span className="absolute -top-2 -right-2 bg-amber-500 text-white text-[9px] font-black px-1.5 py-0.5 rounded-full flex items-center justify-center shadow-xs">
                      {currentVariant.code}
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

          {/* Switcher tabs */}
          <div className="flex items-center gap-1.5 flex-wrap pt-2">
            <span className="text-xs font-bold text-slate-500 mr-1">Быстрое переключение:</span>
            {options54.map((item) => (
              <button
                key={item.code}
                type="button"
                onClick={() => setSelected54(item.code)}
                className={`px-3 py-1.5 rounded-lg text-xs font-extrabold transition-all cursor-pointer ${
                  selected54 === item.code
                    ? "bg-amber-500 text-white shadow-2xs"
                    : "bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200"
                }`}
              >
                {item.code}
              </button>
            ))}
          </div>
        </section>

        {/* 8 Cards Detailed Catalog */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-extrabold text-slate-900">
              Все 8 вариантов оформления бейджа с описанием
            </h2>
            <span className="text-xs text-slate-500 font-medium">
              Кликните на карточку или кнопку «Утвердить»
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {options54.map((item) => {
              const isSelected = selected54 === item.code;
              return (
                <div
                  key={item.code}
                  onClick={() => setSelected54(item.code)}
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
                          className={`w-8 h-8 rounded-lg text-xs font-black flex items-center justify-center shrink-0 ${
                            isSelected
                              ? "bg-amber-500 text-white"
                              : "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {item.code}
                        </span>
                        <div>
                          <h3 className="text-sm font-extrabold text-slate-900 leading-tight">
                            {item.name}
                          </h3>
                          <span className="text-[10px] font-bold text-amber-800">
                            {item.badgeStyle}
                          </span>
                        </div>
                      </div>
                      <span
                        className={`text-[11px] px-2 py-0.5 rounded-full font-bold ${
                          isSelected
                            ? "bg-amber-100 text-amber-900"
                            : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {isSelected ? "Выбран" : item.code}
                      </span>
                    </div>

                    <p className="text-xs text-slate-600 leading-relaxed">
                      {item.description}
                    </p>

                    {/* Preview Button */}
                    <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 flex items-center justify-center">
                      {item.renderButton("large")}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                    <span className="text-[11px] text-slate-400 font-medium">
                      Кнопка: серая 12px / Бейдж: 9–10px
                    </span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelected54(item.code);
                        copyCode(item.code);
                      }}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                        isSelected
                          ? "bg-amber-500 hover:bg-amber-600 text-white"
                          : "bg-slate-100 hover:bg-slate-200 text-slate-800"
                      }`}
                    >
                      {copiedKey === item.code ? (
                        <>
                          <Check size={13} />
                          <span>Скопировано!</span>
                        </>
                      ) : (
                        <>
                          <Copy size={13} />
                          <span>Утвердить {item.code}</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Designer recommendations */}
        <div className="bg-amber-50/70 border border-amber-200/80 rounded-2xl p-5 text-center max-w-2xl mx-auto space-y-1.5">
          <div className="text-xs font-extrabold uppercase tracking-wider text-amber-900">
            Рекомендация дизайнера
          </div>
          <p className="text-xs text-slate-700 leading-relaxed">
            Наиболее удачно смотрятся: <strong>5.4A</strong> (скругленная капсула-пилюля мягче прямоугольника),{" "}
            <strong>5.4B</strong> (контурный чип без цветного фона) и <strong>5.4D</strong> (чистый разделитель без бейджей).
            Назовите понравившийся код, и я применю его в кабинете.
          </p>
        </div>
      </div>
    </main>
  );
}
