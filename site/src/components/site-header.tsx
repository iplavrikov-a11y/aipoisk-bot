'use client';

import Link from "next/link";
import { TenderLexLogo } from "@/components/logo";
import { Send, Sparkles, Mail, MessageSquare } from "lucide-react";

export function SiteHeader() {
  const botUrl = process.env.NEXT_PUBLIC_BOT_URL || "https://t.me/tenderlex_bot";
  const cabinetUrl = "/cabinet";
  const telegramSupportUrl = "https://t.me/lexelence";

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-2xs">
      {/* Top contact microbar */}
      <div className="bg-slate-900 text-slate-300 text-[11px] py-1.5 px-4 hidden md:block border-b border-slate-800">
        <div className="container max-w-6xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-3">
            <span className="text-teal-400 font-bold flex items-center gap-1.5">
              <Sparkles size={12} />
              ИИ-платформа снабжения и анализа документации
            </span>
            <span className="text-slate-600">•</span>
            <span className="text-slate-400">Поиск поставщиков по всей России</span>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <a
              href={telegramSupportUrl}
              target="_blank"
              rel="noreferrer"
              className="hover:text-cyan-400 transition-colors flex items-center gap-1"
            >
              <Send size={12} className="text-cyan-400" />
              Telegram
            </a>
            <span className="text-slate-700">|</span>
            <a
              href="mailto:info@tenderlex.ru"
              className="hover:text-teal-300 transition-colors flex items-center gap-1"
            >
              <Mail size={12} className="text-teal-400" />
              info@tenderlex.ru
            </a>
            <span className="text-slate-700">|</span>
            <button
              type="button"
              onClick={() => {
                if (typeof window !== "undefined") {
                  window.dispatchEvent(new CustomEvent("open_tenderlex_chat"));
                  (window as unknown as { openTenderlexChat?: () => void }).openTenderlexChat?.();
                }
              }}
              className="hover:text-teal-300 transition-colors flex items-center gap-1 cursor-pointer text-slate-300"
            >
              <MessageSquare size={12} className="text-teal-400" />
              Чат
            </button>
          </div>
        </div>
      </div>

      {/* Main navigation bar */}
      <div className="container max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-6">
        {/* Brand Logo with clear right margin */}
        <div className="shrink-0 mr-4">
          <TenderLexLogo size={34} textColor="text-teal-700" />
        </div>

        {/* Navigation Menu (clean, focused on core product) */}
        <nav className="hidden lg:flex items-center gap-6">
          <Link
            href="/poisk-postavshchikov-po-tz"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors"
          >
            Поиск поставщиков
          </Link>
          <Link
            href="/podbor-tovara-i-analogov-po-tz"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors flex items-center gap-1"
          >
            <span>Аналоги и Форма 2</span>
            <span className="text-[10px] font-black uppercase text-teal-700 bg-teal-50 border border-teal-200 px-1.5 py-0.2 rounded-full">New</span>
          </Link>
          <Link
            href="/analiz-zakupochnoi-dokumentacii"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors"
          >
            Анализ документации
          </Link>
          <Link
            href="/#pricing"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors"
          >
            Тарифы
          </Link>
          <Link
            href="/baza-znaniy"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors"
          >
            База знаний
          </Link>
          <Link
            href="/about"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors"
          >
            О сервисе
          </Link>
        </nav>

        {/* Action CTAs */}
        <div className="flex items-center gap-3 shrink-0">
          <a
            href={botUrl}
            target="_blank"
            rel="noreferrer"
            className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition-all border border-slate-200"
          >
            <Send size={13} className="text-teal-600" />
            <span>Telegram-бот</span>
          </a>
          <a
            href={cabinetUrl}
            className="inline-flex items-center justify-center px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold shadow-md shadow-teal-600/20 transition-all hover:scale-[1.02]"
          >
            <span>Войти в кабинет</span>
          </a>
        </div>
      </div>
    </header>
  );
}
