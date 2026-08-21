import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

export const metadata: Metadata = {
  title: "Согласие на обработку персональных данных",
  description: "Порядок и условия согласия пользователя на обработку и хранение персональных данных сервисом TenderLex в рамках 152-ФЗ.",
  alternates: { canonical: "/personal-data" },
};

export default function PersonalDataPage() {
  return (
    <main className="bg-slate-50/60 text-slate-900 min-h-screen font-sans">
      <SiteHeader />

      <section className="py-16 sm:py-24 border-b border-slate-200">
        <div className="container max-w-4xl mx-auto px-4 sm:px-6">
          <Link href="/legal" className="text-teal-700 font-bold text-xs uppercase tracking-wider hover:underline inline-block mb-4">
            ← Правовая информация
          </Link>
          <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight mb-2">
            Согласие на обработку персональных данных
          </h1>
          <p className="text-slate-500 text-sm mb-12">
            Редакция от 17 июля 2026 года • Согласие субъекта персональных данных
          </p>

          <div className="space-y-8 text-sm text-slate-700 leading-relaxed">
            <section className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-4 shadow-2xs">
              <h2 className="text-xl font-black text-slate-900">1. Текст согласия</h2>
              <p>
                Регистрируясь в личном кабинете на сайте tenderlex.ru или запуская Telegram-бота @tenderlex_bot,
                пользователь свободно, своей волей и в своем интересе дает согласие Индивидуальному предпринимателю
                Груздеву Игорю Вячеславовичу (ИНН 352516048881, ОГРНИП 323352500038991) на обработку своих персональных
                данных.
              </p>
            </section>

            <section className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-4 shadow-2xs">
              <h2 className="text-xl font-black text-slate-900">2. Перечень действий и срок действия</h2>
              <p>
                Согласие дается на совершение следующих действий с персональными данными: сбор, запись, систематизацию,
                накопление, хранение, уточнение (обновление, изменение), извлечение, использование, передачу, блокирование,
                удаление и уничтожение. Согласие действует бессрочно до момента его отзыва путем направления письменного
                уведомления на email: support@tenderlex.ru.
              </p>
            </section>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
