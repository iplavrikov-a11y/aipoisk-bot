'use client';

import Link from "next/link";
import { usePublicSiteContacts } from "@/lib/public-site-settings";
import { TenderLexLogo } from "@/components/logo";
import { Send, Sparkles, Mail, MessageSquare } from "lucide-react";

export function SiteHeader() {
  const data = usePublicSiteContacts();
  const botUrl = data.bot.telegram_url;
  const cabinetUrl = "/cabinet";
  const telegramSupportUrl = data.contacts.telegram_url;

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
              href={`mailto:${data.contacts.email}`}
              className="hover:text-teal-300 transition-colors flex items-center gap-1"
            >
              <Mail size={12} className="text-teal-400" />
              {data.contacts.email}
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

        {/* Navigation Menu (clean, single-line, whitespace-nowrap) */}
        <nav className="hidden lg:flex items-center gap-5 whitespace-nowrap">
          <Link
            href="/poisk-postavshchikov-po-tz"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors whitespace-nowrap"
          >
            Поиск поставщиков
          </Link>
          <Link
            href="/podbor-tovara-i-analogov-po-tz"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors whitespace-nowrap"
          >
            Подбор аналогов
          </Link>
          <Link
            href="/analiz-zakupochnoi-dokumentacii"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors whitespace-nowrap"
          >
            Анализ документации
          </Link>
          <Link
            href="/#pricing"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors whitespace-nowrap"
          >
            Тарифы
          </Link>
          <Link
            href="/api-integracii"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors whitespace-nowrap"
          >
            API
          </Link>
          <Link
            href="/baza-znaniy"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors whitespace-nowrap"
          >
            База знаний
          </Link>
          <Link
            href="/about"
            className="text-slate-700 font-semibold hover:text-teal-700 text-sm transition-colors whitespace-nowrap"
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
      <details className="border-t border-slate-200 lg:hidden">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-slate-700 focus-visible:outline-2 focus-visible:outline-teal-600 focus-visible:outline-offset-2">
          Меню
        </summary>
        <nav aria-label="Мобильная навигация" className="grid gap-1 px-4 pb-3">
          {[
            ["/poisk-postavshchikov-po-tz", "Поиск поставщиков"],
            ["/podbor-tovara-i-analogov-po-tz", "Подбор товара и аналогов"],
            ["/analiz-zakupochnoi-dokumentacii", "Анализ документации"],
            ["/#pricing", "Тарифы"],
            ["/api-integracii", "B2B API и интеграции"],
            ["/baza-znaniy", "База знаний"],
          ].map(([href, label]) => (
            <Link
              key={href}
              href={href}
              onClick={(event) => event.currentTarget.closest("details")?.removeAttribute("open")}
              className="rounded-lg px-3 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-teal-600"
            >
              {label}
            </Link>
          ))}
        </nav>
      </details>
    </header>
  );
}
