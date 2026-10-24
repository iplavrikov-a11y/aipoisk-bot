"use client";

import Link from "next/link";
import { ChevronDown, Mail, Menu, MessageCircle, Send, X } from "lucide-react";
import { usePublicSiteContacts } from "@/lib/public-site-settings";
import { TenderLexLogo } from "@/components/logo";

const moduleLinks = [
  ["/poisk-postavshchikov-po-tz", "Поставщики"],
  ["/podbor-tovara-i-analogov-po-tz", "Аналоги"],
  ["/analiz-zakupochnoi-dokumentacii", "Анализ закупок"],
] as const;

const resourceLinks = [
  ["/baza-znaniy", "База знаний"],
  ["/api-integracii", "API и интеграции"],
  ["/otrasli", "Отрасли"],
  ["/regiony", "Регионы"],
  ["/about", "О сервисе"],
] as const;

function openSupportChat() {
  window.dispatchEvent(new CustomEvent("open_tenderlex_chat"));
  (window as Window & { openTenderlexChat?: () => void }).openTenderlexChat?.();
}

export function SiteHeader() {
  const data = usePublicSiteContacts();

  return (
    <header
      className="tl-site-header"
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        const opened =
          event.currentTarget.querySelector<HTMLDetailsElement>(
            "details[open]",
          );
        if (opened) {
          opened.open = false;
          opened.querySelector<HTMLElement>("summary")?.focus();
        }
      }}
    >
      <div className="tl-site-header__inner">
        <TenderLexLogo size={34} textColor="text-[#174b3f]" />

        <nav className="tl-site-header__nav" aria-label="Основная навигация">
          {moduleLinks.map(([href, label]) => (
            <Link href={href} key={href}>
              {label}
            </Link>
          ))}
          <Link href="/#pricing">Тарифы</Link>
          <details className="tl-site-header__resources">
            <summary>
              Ресурсы <ChevronDown aria-hidden="true" />
            </summary>
            <div className="tl-site-header__dropdown">
              {resourceLinks.map(([href, label]) => (
                <Link href={href} key={href}>
                  {label}
                </Link>
              ))}
              <a
                href={data.contacts.telegram_url}
                target="_blank"
                rel="noreferrer"
              >
                Поддержка в Telegram
              </a>
              <a href={`mailto:${data.contacts.email}`}>Написать на email</a>
              {data.contacts.phone ? (
                <a
                  href={
                    data.contacts.phone_url ||
                    `tel:${data.contacts.phone.replace(/[^0-9+]/g, "")}`
                  }
                >
                  {data.contacts.phone}
                </a>
              ) : null}
            </div>
          </details>
        </nav>

        <div className="tl-site-header__actions">
          <button
            type="button"
            className="tl-site-header__chat"
            onClick={openSupportChat}
            aria-label="Открыть чат поддержки"
          >
            <MessageCircle aria-hidden="true" /> <span>Поддержка</span>
          </button>
          <a
            href={data.bot.telegram_url}
            target="_blank"
            rel="noreferrer"
            className="tl-site-header__bot"
          >
            <Send aria-hidden="true" /> <span>Telegram-бот</span>
          </a>
          <Link className="tl-site-header__cabinet" href="/cabinet">
            Кабинет
          </Link>
        </div>

        <details className="tl-site-header__mobile">
          <summary aria-label="Открыть меню">
            <Menu className="tl-menu-icon" aria-hidden="true" />
            <X className="tl-close-icon" aria-hidden="true" />
          </summary>
          <nav
            aria-label="Мобильная навигация"
            onClick={(event) => {
              if ((event.target as Element).closest("a, button")) {
                event.currentTarget.closest("details")?.removeAttribute("open");
              }
            }}
          >
            <p>Инструменты</p>
            {moduleLinks.map(([href, label]) => (
              <Link href={href} key={href}>
                {label}
              </Link>
            ))}
            <Link href="/#pricing">Тарифы</Link>
            <p>Ресурсы</p>
            {resourceLinks.map(([href, label]) => (
              <Link href={href} key={href}>
                {label}
              </Link>
            ))}
            <a href={data.bot.telegram_url} target="_blank" rel="noreferrer">
              Telegram-бот
            </a>
            <a
              href={data.contacts.telegram_url}
              target="_blank"
              rel="noreferrer"
            >
              Поддержка в Telegram
            </a>
            <a href={`mailto:${data.contacts.email}`}>
              <Mail aria-hidden="true" /> Написать на email
            </a>
            {data.contacts.phone ? (
              <a
                href={
                  data.contacts.phone_url ||
                  `tel:${data.contacts.phone.replace(/[^0-9+]/g, "")}`
                }
              >
                {data.contacts.phone}
              </a>
            ) : null}
            <button type="button" onClick={openSupportChat}>
              Написать в поддержку
            </button>
            <Link className="tl-site-header__cabinet" href="/cabinet">
              Открыть кабинет
            </Link>
          </nav>
        </details>
      </div>
    </header>
  );
}
