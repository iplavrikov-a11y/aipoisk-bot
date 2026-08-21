import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

export const metadata: Metadata = {
  title: "Политика конфиденциальности",
  description: "Политика обработки и защиты персональных данных пользователей сервиса TenderLex в соответствии с Федеральным законом № 152-ФЗ.",
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <main className="bg-slate-50/60 text-slate-900 min-h-screen font-sans">
      <SiteHeader />

      <section className="py-16 sm:py-24 border-b border-slate-200">
        <div className="container max-w-4xl mx-auto px-4 sm:px-6">
          <Link href="/legal" className="text-teal-700 font-bold text-xs uppercase tracking-wider hover:underline inline-block mb-4">
            ← Правовая информация
          </Link>
          <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight mb-2">
            Политика конфиденциальности
          </h1>
          <p className="text-slate-500 text-sm mb-12">
            Редакция от 17 июля 2026 года • Регламент обработки данных 152-ФЗ
          </p>

          <div className="space-y-8 text-sm text-slate-700 leading-relaxed">
            <section className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-4 shadow-2xs">
              <h2 className="text-xl font-black text-slate-900">1. Назначение и правовые основания</h2>
              <p>
                Настоящая Политика определяет порядок сбора, обработки и защиты персональных данных пользователей сервиса
                TenderLex, расположенного на сайте tenderlex.ru и в Telegram-боте @tenderlex_bot, в соответствии с
                Федеральным законом № 152-ФЗ «О персональных данных».
              </p>
              <p>
                Оператор персональных данных: Индивидуальный предприниматель Груздев Игорь Вячеславович (ИНН 352516048881,
                ОГРНИП 323352500038991).
              </p>
            </section>

            <section className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-4 shadow-2xs">
              <h2 className="text-xl font-black text-slate-900">2. Состав обрабатываемых данных</h2>
              <p>
                Оператор может обрабатывать следующие данные: номер телефона, адрес электронной почты, идентификатор
                пользователя в Telegram, наименование организации/ИП, реквизиты, технические метаданные и файлы,
                загружаемые для анализа в рамках оказания услуг.
              </p>
            </section>

            <section className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-4 shadow-2xs">
              <h2 className="text-xl font-black text-slate-900">3. Цели обработки и безопасность</h2>
              <p>
                Данные обрабатываются исключительно в целях предоставления доступа к функционалу платформы, исполнения
                договора оферты, связи с пользователем, выставления бухгалтерских документов и технической поддержки.
                Хранение данных осуществляется на серверах, физически размещенных на территории Российской Федерации.
              </p>
            </section>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
