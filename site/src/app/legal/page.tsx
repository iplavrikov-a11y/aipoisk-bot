import { PublicSiteLink } from "@/components/public-site-link";
import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { FileText, ShieldCheck, UserCheck } from "lucide-react";
import { buildBreadcrumbJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Правовая информация и контакты",
  description: "Официальные документы, условия оферты, политика конфиденциальности и каналы связи платформы TenderLex.",
  alternates: { canonical: "/legal" },
};

export default function LegalPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Правовая информация", item: "https://tenderlex.ru/legal" },
  ]);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      <main className="bg-slate-50/60 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

      <section className="py-16 sm:py-24 border-b border-slate-200">
        <div className="container max-w-4xl mx-auto px-4 sm:px-6">
          <div className="mb-10">
            <Link href="/" className="text-teal-700 font-bold text-xs uppercase tracking-wider hover:underline inline-block mb-3">
              ← На главную
            </Link>
            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight">
              Правовая информация и контакты
            </h1>
            <p className="text-slate-500 text-sm mt-3">
              Редакция от 17 июля 2026 года • Регламенты, документы и каналы связи сервиса TenderLex
            </p>
          </div>

          {/* Legal document cards */}
          <div className="grid sm:grid-cols-3 gap-6 mb-12">
            <Link
              href="/terms"
              className="p-6 rounded-3xl bg-white border-2 border-slate-200 hover:border-teal-500 hover:shadow-xl transition-all flex flex-col justify-between group shadow-2xs"
            >
              <div>
                <div className="w-10 h-10 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <FileText size={20} />
                </div>
                <strong className="text-base font-black text-slate-900 block mb-2 group-hover:text-teal-700">
                  Публичная оферта
                </strong>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Условия использования сервиса, порядок оплаты, оказания услуг и возвратов.
                </p>
              </div>
              <span className="text-xs font-black text-teal-700 mt-4 block">Читать документ</span>
            </Link>

            <Link
              href="/privacy"
              className="p-6 rounded-3xl bg-white border-2 border-slate-200 hover:border-teal-500 hover:shadow-xl transition-all flex flex-col justify-between group shadow-2xs"
            >
              <div>
                <div className="w-10 h-10 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <ShieldCheck size={20} />
                </div>
                <strong className="text-base font-black text-slate-900 block mb-2 group-hover:text-teal-700">
                  Политика конфиденциальности
                </strong>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Правила сбора, хранения и защиты персональных данных согласно 152-ФЗ.
                </p>
              </div>
              <span className="text-xs font-black text-teal-700 mt-4 block">Читать документ</span>
            </Link>

            <Link
              href="/personal-data"
              className="p-6 rounded-3xl bg-white border-2 border-slate-200 hover:border-teal-500 hover:shadow-xl transition-all flex flex-col justify-between group shadow-2xs"
            >
              <div>
                <div className="w-10 h-10 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <UserCheck size={20} />
                </div>
                <strong className="text-base font-black text-slate-900 block mb-2 group-hover:text-teal-700">
                  Согласие на обработку данных
                </strong>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Текст согласия субъекта персональных данных при регистрации на сайте и в боте.
                </p>
              </div>
              <span className="text-xs font-black text-teal-700 mt-4 block">Читать документ</span>
            </Link>
          </div>

          {/* Contacts & Requisites Grid */}
          <div className="grid md:grid-cols-2 gap-6 mb-12">
            {/* Requisites Block */}
            <div className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-6 shadow-2xs">
              <h2 className="text-xl font-black text-slate-900">Реквизиты оператора сервиса</h2>
              <div className="text-xs text-slate-700 space-y-2.5">
                <div>
                  <span className="text-slate-400 block uppercase font-bold text-[10px]">Наименование</span>
                  <span className="font-bold text-slate-900">Индивидуальный предприниматель Груздев Игорь Вячеславович</span>
                </div>
                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div>
                    <span className="text-slate-400 block uppercase font-bold text-[10px]">ИНН</span>
                    <span className="font-mono font-bold text-slate-900">352516048881</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block uppercase font-bold text-[10px]">ОГРНИП</span>
                    <span className="font-mono font-bold text-slate-900">323352500038991</span>
                  </div>
                </div>
                <div className="pt-1">
                  <span className="text-slate-400 block uppercase font-bold text-[10px]">Адрес регистрации</span>
                  <span className="text-slate-700">160541, Россия, Вологодская область, Вологодский р-н, д. Тарасово, д. 3</span>
                </div>
                <div className="pt-2 border-t border-slate-100 space-y-1.5">
                  <span className="text-slate-400 block uppercase font-bold text-[10px]">Банковские реквизиты</span>
                  <div className="text-[11px] space-y-1 text-slate-600">
                    <div>Расчётный счёт: <b className="font-mono text-slate-900">40802810217430000342</b></div>
                    <div>Банк: АО «АЛЬФА-БАНК»</div>
                    <div>БИК: <b className="font-mono text-slate-900">044525593</b></div>
                    <div>Корр. счёт: <b className="font-mono text-slate-900">30101810200000000593</b></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Contacts */}
            <div className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-6 shadow-2xs">
              <h2 className="text-xl font-black text-slate-900">Каналы связи и поддержка</h2>

              <div className="text-xs text-slate-700 space-y-4 max-w-md">
                <div>
                  <span className="text-slate-400 block uppercase font-bold text-[10px]">Поддержка в Telegram</span>
                  <PublicSiteLink channel="telegram" target="_blank" rel="noreferrer" className="block text-teal-700 font-bold hover:underline text-sm mt-0.5"></PublicSiteLink>
                </div>
                <div>
                  <span className="text-slate-400 block uppercase font-bold text-[10px]">Telegram-бот сервиса</span>
                  <PublicSiteLink channel="bot" target="_blank" rel="noreferrer" className="block text-teal-700 font-bold hover:underline text-sm mt-0.5"></PublicSiteLink>
                </div>
                <div>
                  <span className="text-slate-400 block uppercase font-bold text-[10px]">Телефон горячей линии</span>
                  <PublicSiteLink channel="phone" className="block text-teal-700 font-bold hover:underline text-sm mt-0.5"></PublicSiteLink>
                </div>
                <div>
                  <span className="text-slate-400 block uppercase font-bold text-[10px]">Электронная почта</span>
                  <PublicSiteLink channel="email" className="block text-teal-700 font-bold hover:underline text-sm mt-0.5"></PublicSiteLink>
                </div>
              </div>
            </div>
          </div>

          {/* Delivery, Payment & Refund Terms */}
          <div className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-6 shadow-2xs">
            <h2 className="text-xl font-black text-slate-900">Порядок оплаты, получения услуг и возвратов</h2>
            <div className="grid sm:grid-cols-3 gap-6 text-xs text-slate-600 leading-relaxed">
              <div>
                <strong className="text-slate-900 font-bold block mb-1.5 text-sm">Способ получения услуг</strong>
                <p>
                  Сервис TenderLex предоставляет онлайн-услуги в цифровом виде. Результаты обработки (отчёты по поставщикам, анализ закупочной документации) формируются программным комплексом моментально и доставляются в личном кабинете на сайте, в Telegram-боте и по электронной почте. Физическая доставка не требуется.
                </p>
              </div>
              <div>
                <strong className="text-slate-900 font-bold block mb-1.5 text-sm">Способы оплаты</strong>
                <p>
                  Оплата тарифных планов и пополнение баланса производятся в российских рублях онлайн с помощью банковских карт (МИР, Visa, MasterCard), Системы быстрых платежей (СБП), либо по безналичному расчету по выставленному счёту для юридических лиц и индивидуальных предпринимателей.
                </p>
              </div>
              <div>
                <strong className="text-slate-900 font-bold block mb-1.5 text-sm">Условия возврата средств</strong>
                <p>
                  В случае технического сбоя или неоказания оплаченной услуги средства возвращаются в полном объёме на баланс личного кабинета либо по письменному заявлению пользователя на банковскую карту или расчётный счёт, с которого была произведена оплата.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
    </>
  );
}
