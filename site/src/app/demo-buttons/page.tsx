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

type ButtonVariant = {
  id: number;
  name: string;
  category: string;
  description: string;
  renderButton: (size?: "normal" | "large") => React.ReactNode;
};

export default function DemoButtonsPage() {
  const [selectedVariant, setSelectedVariant] = useState<number>(1);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const copyVariant = (id: number) => {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(`Выбираю вариант №${id}`);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  const variants: ButtonVariant[] = [
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
      name: "Серая кнопка с золотой иконкой подарка",
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

  const currentVariant = variants.find((v) => v.id === selectedVariant) || variants[0];

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-20">
      {/* Top bar */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-2xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/cabinet"
              className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-600 hover:text-teal-700 transition-colors"
            >
              <ArrowLeft size={14} />
              <span>Вернуться в кабинет</span>
            </Link>
            <span className="text-slate-300">|</span>
            <span className="text-xs font-bold text-slate-900">
              Витрина вариантов кнопки «Пригласить (+1 000 ₽)»
            </span>
          </div>
          <div className="text-xs font-bold text-teal-800 bg-teal-50 px-2.5 py-1 rounded-full border border-teal-200">
            10 вариантов для согласования
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-8 space-y-8">
        {/* Intro */}
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Выберите дизайн кнопки «Пригласить»
          </h1>
          <p className="text-sm text-slate-600 leading-relaxed">
            Кнопка должна быть заметной, но не утяжелять панель управления. Ниже представлены 10 вариантов:
            сверху — интерактивный просмотр в реальном тулбаре, ниже — детальное сравнение каждого варианта.
          </p>
        </div>

        {/* Live Toolbar Sandbox */}
        <section className="bg-white rounded-2xl p-5 sm:p-6 border border-slate-200 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-teal-700">
                Интерактивный предварительный просмотр
              </div>
              <h2 className="text-base font-extrabold text-slate-900 mt-0.5">
                Как панель выглядит с вариантом №{currentVariant.id}: {currentVariant.name}
              </h2>
            </div>
            <button
              type="button"
              onClick={() => copyVariant(currentVariant.id)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-700 hover:bg-teal-800 text-white rounded-lg text-xs font-bold transition-colors cursor-pointer shrink-0"
            >
              {copiedId === currentVariant.id ? (
                <>
                  <Check size={13} />
                  <span>Скопировано в буфер!</span>
                </>
              ) : (
                <>
                  <Copy size={13} />
                  <span>Выбрать вариант №{currentVariant.id}</span>
                </>
              )}
            </button>
          </div>

          {/* Realistic Toolbar Simulation */}
          <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-200 overflow-x-auto">
            <div className="min-w-[900px]">
              <div className="bg-white rounded-xl p-2.5 border border-slate-200 shadow-2xs flex items-center justify-between gap-2">
                {/* Left group */}
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

                  {/* TESTED BUTTON */}
                  <div className="relative">
                    {currentVariant.renderButton("normal")}
                    <span className="absolute -top-2 -right-2 bg-teal-600 text-white text-[9px] font-black w-4 h-4 rounded-full flex items-center justify-center shadow-xs">
                      {currentVariant.id}
                    </span>
                  </div>
                </div>

                {/* Right group */}
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

          {/* Quick Select Buttons 1-10 */}
          <div className="flex items-center gap-1.5 flex-wrap pt-2">
            <span className="text-xs font-bold text-slate-500 mr-1">Быстрое переключение:</span>
            {variants.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => setSelectedVariant(v.id)}
                className={`px-3 py-1 rounded-lg text-xs font-extrabold transition-all cursor-pointer ${
                  selectedVariant === v.id
                    ? "bg-teal-700 text-white shadow-2xs"
                    : "bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200"
                }`}
              >
                №{v.id}
              </button>
            ))}
          </div>
        </section>

        {/* 10 Variants Grid Catalog */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-extrabold text-slate-900">
              Все 10 вариантов дизайна с подробным описанием
            </h2>
            <span className="text-xs text-slate-500 font-medium">
              Кликните на карточку или кнопку «Выбрать», чтобы согласовать
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {variants.map((variant) => {
              const isSelected = selectedVariant === variant.id;
              return (
                <div
                  key={variant.id}
                  onClick={() => setSelectedVariant(variant.id)}
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

                    {/* Button Demo in Isolation */}
                    <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 flex items-center justify-center">
                      {variant.renderButton("large")}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                    <span className="text-[11px] text-slate-400 font-medium">
                      Размер: 12px в тулбаре / 14px увеличенный
                    </span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedVariant(variant.id);
                        copyVariant(variant.id);
                      }}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                        isSelected
                          ? "bg-teal-700 hover:bg-teal-800 text-white"
                          : "bg-slate-100 hover:bg-slate-200 text-slate-800"
                      }`}
                    >
                      {copiedId === variant.id ? (
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

        {/* Footer recommendation note */}
        <div className="bg-teal-50 border border-teal-200 rounded-2xl p-5 text-center max-w-2xl mx-auto space-y-1.5">
          <div className="text-xs font-extrabold uppercase tracking-wider text-teal-800">
            Рекомендация дизайнера
          </div>
          <p className="text-xs text-teal-950 leading-relaxed">
            Наиболее сбалансированными считаются <strong>Вариант №1</strong> (мягкий тинт в тон чата сайта) и{" "}
            <strong>Вариант №3</strong> (строгая серая кнопка с изумрудным бейджем суммы). Назовите мне номер,
            который понравился, и я сразу применю его в кабинете.
          </p>
        </div>
      </div>
    </main>
  );
}
