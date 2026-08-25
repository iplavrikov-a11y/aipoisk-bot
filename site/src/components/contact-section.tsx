import { Phone, Mail, Send, MessageCircle, Sparkles, ShieldCheck } from "lucide-react";

interface ContactSectionProps {
  title?: string;
  subtitle?: string;
  showTrialBadge?: boolean;
}

export function ContactSection({
  title = "Начните работу с TenderLex прямо сейчас",
  subtitle = "Загрузите спецификацию в веб-кабинет или запустите Telegram-бота TenderLex для мгновенного сбора прямых контактов поставщиков и анализа рисков.",
  showTrialBadge = true,
}: ContactSectionProps) {
  const botUrl = process.env.NEXT_PUBLIC_BOT_URL || "https://t.me/tenderlex_bot";
  const cabinetUrl = "/cabinet";
  const whatsappUrl = "https://wa.me/79210629909";
  const telegramSupportUrl = "https://t.me/lexelence";
  const maxMessengerUrl = "https://max.ru/u/f9LHodD0cOJBLDdTXMGDPUvHbbK_bKtz9e0GgYPWHvxUgk9rZvGGwCdYvqs";

  return (
    <section id="contacts" className="py-16 sm:py-24 bg-gradient-to-b from-teal-50/50 via-slate-50 to-white border-b border-slate-200">
      <div className="container max-w-5xl mx-auto px-4 sm:px-6">
        <div className="text-center max-w-3xl mx-auto space-y-6">
          {showTrialBadge && (
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-bold uppercase tracking-wider shadow-2xs">
              <Sparkles size={14} className="text-teal-600 animate-pulse" />
              <span>Бесплатный пробный доступ при регистрации</span>
            </div>
          )}

          <h2 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-slate-900 leading-tight">
            {title}
          </h2>

          <p className="text-slate-600 text-base sm:text-lg font-normal leading-relaxed max-w-2xl mx-auto">
            {subtitle}
          </p>

          {/* Primary CTA buttons */}
          <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
            <a
              href={cabinetUrl}
              className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold shadow-lg shadow-teal-600/20 text-sm transition-all hover:scale-[1.01]"
            >
              <span>Попробовать бесплатно</span>
            </a>
            <a
              href={botUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-bold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
            >
              <Send size={16} className="text-teal-600" />
              <span>Запустить в Telegram</span>
            </a>
          </div>

          {/* Multi-channel direct contact cards */}
          <div className="pt-10 border-t border-slate-200">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 block mb-6">
              Прямая связь со службой поддержки TenderLex
            </span>

            <div className="flex flex-wrap items-center justify-center gap-3 max-w-5xl mx-auto">
              {/* Phone */}
              <a
                href="tel:+79951460080"
                className="py-3 px-5 rounded-2xl bg-white border border-slate-200 shadow-2xs hover:border-teal-500 hover:shadow-md transition-all group flex items-center justify-center gap-2 shrink-0 min-w-[195px]"
              >
                <Phone size={16} className="text-teal-700 shrink-0" />
                <strong className="text-sm font-bold text-slate-900 group-hover:text-teal-700 whitespace-nowrap">
                  +7 (995) 146-00-80
                </strong>
              </a>

              {/* WhatsApp */}
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noreferrer"
                className="py-3 px-5 rounded-2xl bg-white border border-slate-200 shadow-2xs hover:border-emerald-500 hover:shadow-md transition-all group flex items-center justify-center gap-2 shrink-0 min-w-[140px]"
              >
                <MessageCircle size={16} className="text-emerald-600 shrink-0" />
                <strong className="text-sm font-bold text-slate-900 group-hover:text-emerald-700">
                  WhatsApp
                </strong>
              </a>

              {/* Telegram */}
              <a
                href={telegramSupportUrl}
                target="_blank"
                rel="noreferrer"
                className="py-3 px-5 rounded-2xl bg-white border border-slate-200 shadow-2xs hover:border-cyan-500 hover:shadow-md transition-all group flex items-center justify-center gap-2 shrink-0 min-w-[140px]"
              >
                <Send size={16} className="text-cyan-600 shrink-0" />
                <strong className="text-sm font-bold text-slate-900 group-hover:text-cyan-700">
                  Telegram
                </strong>
              </a>

              {/* Max */}
              <a
                href={maxMessengerUrl}
                target="_blank"
                rel="noreferrer"
                className="py-3 px-5 rounded-2xl bg-white border border-slate-200 shadow-2xs hover:border-amber-500 hover:shadow-md transition-all group flex items-center justify-center gap-2 shrink-0 min-w-[120px]"
              >
                <MessageCircle size={16} className="text-amber-600 shrink-0" />
                <strong className="text-sm font-bold text-slate-900 group-hover:text-amber-700">
                  Max
                </strong>
              </a>

              {/* Email */}
              <a
                href="mailto:info@tenderlex.ru"
                className="py-3 px-5 rounded-2xl bg-white border border-slate-200 shadow-2xs hover:border-teal-500 hover:shadow-md transition-all group flex items-center justify-center gap-2 shrink-0 min-w-[120px]"
              >
                <Mail size={16} className="text-teal-700 shrink-0" />
                <strong className="text-sm font-bold text-slate-900 group-hover:text-teal-700">
                  Email
                </strong>
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
