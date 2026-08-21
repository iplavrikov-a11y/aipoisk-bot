import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

export const metadata: Metadata = {
  title: "Публичная оферта",
  description: "Публичная оферта платформы TenderLex на заключение договора оказания информационных услуг для юридических лиц и ИП.",
  alternates: { canonical: "/terms" },
};

export default function TermsPage() {
  return (
    <main className="bg-slate-50/60 text-slate-900 min-h-screen font-sans">
      <SiteHeader />

      <section className="py-16 sm:py-24 border-b border-slate-200">
        <div className="container max-w-4xl mx-auto px-4 sm:px-6">
          <Link href="/legal" className="text-teal-700 font-bold text-xs uppercase tracking-wider hover:underline inline-block mb-4">
            ← Правовая информация
          </Link>
          <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight mb-2">
            Публичная оферта
          </h1>
          <p className="text-slate-500 text-sm mb-12">
            Редакция от 17 июля 2026 года • версия 2026-07-17
          </p>

          <div className="space-y-8 text-sm text-slate-700 leading-relaxed">
            <section className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-4 shadow-2xs">
              <h2 className="text-xl font-black text-slate-900">1. Общие положения</h2>
              <p>
                Настоящая оферта адресована юридическим лицам и индивидуальным предпринимателям, приобретающим услуги
                для предпринимательской или иной профессиональной деятельности. Физическое лицо может пользоваться
                TenderLex только как уполномоченный представитель организации или ИП, а не для личных, семейных или
                домашних нужд.
              </p>
              <p>
                Исполнитель — индивидуальный предприниматель Груздев Игорь Вячеславович, ИНН 352516048881,
                ОГРНИП 323352500038991. Сервис доступен на tenderlex.ru, в личном кабинете и Telegram-боте TenderLex.
              </p>
            </section>

            <section className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-4 shadow-2xs">
              <h2 className="text-xl font-black text-slate-900">2. Акцепт и заключение договора</h2>
              <p>
                В личном кабинете договор заключается при отдельном подтверждении оферты. В Telegram-боте акцептом является
                явное нажатие кнопки «Запустить» после выбора услуги и добавления материалов. Оплата счета также подтверждает
                акцепт. Пользователь подтверждает полномочия действовать от имени заказчика. Исполнитель фиксирует идентификатор
                пользователя, дату, канал и версию оферты. Согласие на обработку персональных данных оформляется отдельно.
              </p>
            </section>

            <section className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-4 shadow-2xs">
              <h2 className="text-xl font-black text-slate-900">3. Предмет договора</h2>
              <p>
                Исполнитель предоставляет доступ к TenderLex и оказывает автоматизированные информационно-аналитические
                услуги: анализ закупочной документации, поиск и первичную проверку потенциальных поставщиков, подготовку
                рабочих материалов и предоставление результата. Состав задачи определяется выбранным режимом, тарифом и
                переданными заказчиком данными.
              </p>
            </section>

            <section className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-4 shadow-2xs">
              <h2 className="text-xl font-black text-slate-900">4. Порядок оказания услуг и сдача-приемка</h2>
              <p>
                Услуги оказываются программным комплексом в автоматическом режиме после постановки задачи. Результат
                предоставляется в интерфейсе сервиса, Telegram-боте или формируется в виде структурированного файла.
                Услуга считается оказанной в момент предоставления результата или завершения обработки задачи.
              </p>
            </section>

            <section className="p-8 rounded-3xl bg-white border-2 border-slate-200 space-y-4 shadow-2xs">
              <h2 className="text-xl font-black text-slate-900">5. Стоимость и порядок расчетов</h2>
              <p>
                Стоимость услуг определяется действующими тарифами Исполнителя, опубликованными в интерфейсе сервиса на
                момент оформления заказа. Оплата производится в рублях РФ безналичным расчетом через платежные системы
                или по счету. При регистрации пользователю может предоставляться бесплатный пробный доступ.
              </p>
            </section>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
