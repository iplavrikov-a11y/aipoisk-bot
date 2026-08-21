import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { FileText, ShieldCheck, UserCheck, Phone, Mail, Send, MessageCircle } from "lucide-react";

export const metadata: Metadata = {
  title: "Правовая информация и реквизиты",
  description: "Официальные документы, условия оферты, политика конфиденциальности и юридические реквизиты платформы TenderLex.",
  alternates: { canonical: "/legal" },
};

export default function LegalPage() {
  return (
    <main className="bg-slate-50/60 text-slate-900 min-h-screen font-sans">
      <SiteHeader />

      <section className="py-16 sm:py-24 border-b border-slate-200">
        <div className="container max-w-4xl mx-auto px-4 sm:px-6">
          <div className="mb-10">
            <Link href="/" className="text-teal-700 font-bold text-xs uppercase tracking-wider hover:underline inline-block mb-3">
              ← На главную
            </Link>
            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight">
              Правовая информация и реквизиты
            </h1>
            <p className="text-slate-500 text-sm mt-3">
              Редакция от 17 июля 2026 года • Регламенты и юридические документы сервиса TenderLex
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
              <span className="text-xs font-black text-teal-700 mt-4 block">Читать документ →</span>
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
              <span className="text-xs font-black text-teal-700 mt-4 block">Читать документ →</span>
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
              <span className="text-xs font-black text-teal-700 mt-4 block">Читать документ →</span>
            </Link>
          </div>

          {/* Official Requisites */}
          <div className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-6 shadow-2xs">
            <h2 className="text-2xl font-black text-slate-900">Владелец сервиса и официальные реквизиты</h2>

            <div className="grid sm:grid-cols-2 gap-6 text-xs text-slate-700">
              <div className="space-y-3">
                <div>
                  <span className="text-slate-400 block uppercase font-bold text-[10px]">Наименование</span>
                  <strong className="text-sm font-bold text-slate-900">Индивидуальный предприниматель Груздев Игорь Вячеславович</strong>
                </div>
                <div>
                  <span className="text-slate-400 block uppercase font-bold text-[10px]">ИНН</span>
                  <strong className="text-slate-900 text-sm">352516048881</strong>
                </div>
                <div>
                  <span className="text-slate-400 block uppercase font-bold text-[10px]">ОГРНИП</span>
                  <strong className="text-slate-900 text-sm">323352500038991</strong>
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <span className="text-slate-400 block uppercase font-bold text-[10px]">Юридический адрес</span>
                  <span className="text-slate-800">160541, Вологодская область, Вологодский район, деревня Тарасово, д. 3</span>
                </div>
                <div>
                  <span className="text-slate-400 block uppercase font-bold text-[10px]">Каналы связи</span>
                  <div className="space-y-1 mt-1">
                    <a href="tel:+79211460080" className="block text-teal-700 font-bold hover:underline">
                      +7 (921) 146-00-80 (Телефон)
                    </a>
                    <a href="mailto:info@tenderlex.ru" className="block text-teal-700 font-bold hover:underline">
                      info@tenderlex.ru
                    </a>
                    <a href="https://t.me/lexelence" target="_blank" rel="noreferrer" className="block text-teal-700 font-bold hover:underline">
                      Telegram: @lexelence
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
