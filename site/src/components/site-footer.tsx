import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { TenderLexLogo } from "@/components/logo";

export function SiteFooter() {
  return (
    <footer className="bg-white text-slate-600 text-xs border-t border-slate-200">
      {/* Main navigation columns */}
      <div className="container max-w-6xl mx-auto px-4 sm:px-6 py-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
        {/* Brand Column */}
        <div className="space-y-4">
          <TenderLexLogo size={32} textColor="text-teal-700" />
          <p className="text-slate-600 text-xs leading-relaxed">
            Онлайн-платформа ИИ-автоматизации снабжения: поиск прямых контактов производителей по всей России и анализ рисков закупочной документации 44-ФЗ / 223-ФЗ.
          </p>
          <div className="pt-1 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-bold text-teal-800 bg-teal-50 px-3 py-1.5 rounded-xl border border-teal-200">
              <ShieldCheck size={14} className="text-teal-600" />
              Соответствие 152-ФЗ
            </span>
            <a
              href="https://productradar.ru"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-700 bg-slate-50 hover:bg-slate-100 px-3 py-1.5 rounded-xl border border-slate-200 hover:border-slate-300 transition-colors"
              title="TenderLex на Product Radar"
            >
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              Мы на <strong>Product Radar</strong>
            </a>
          </div>
        </div>

        {/* Services Column */}
        <div>
          <strong className="text-slate-900 font-bold text-sm block mb-3">Сервисы платформы</strong>
          <ul className="space-y-2.5">
            <li><Link href="/poisk-postavshchikov-po-tz" className="hover:text-teal-700 transition-colors font-medium">Поиск поставщиков по ТЗ</Link></li>
            <li><Link href="/poisk-proizvoditeley-po-tz" className="hover:text-teal-700 transition-colors font-medium">Поиск заводов-производителей</Link></li>
            <li><Link href="/poisk-postavshchikov-dlya-tendera" className="hover:text-teal-700 transition-colors font-medium">Подбор поставщиков под тендер</Link></li>
            <li><Link href="/postavshchiki-dlya-zaprosa-kp" className="hover:text-teal-700 transition-colors font-medium">База адресатов для запроса КП</Link></li>
            <li><Link href="/zapros-kp-po-tz" className="hover:text-teal-700 transition-colors font-medium">Генератор Запроса КП (RFQ)</Link></li>
            <li><Link href="/analiz-zakupochnoi-dokumentacii" className="hover:text-teal-700 transition-colors font-medium">Анализ документации</Link></li>
            <li><Link href="/reestr-minpromtorga-v-zakupkah" className="hover:text-teal-700 transition-colors font-medium">Реестр Минпромторга (ПП 616/617)</Link></li>
          </ul>
        </div>

        {/* Knowledge Base */}
        <div>
          <strong className="text-slate-900 font-bold text-sm block mb-3">База знаний</strong>
          <ul className="space-y-2.5">
            <li><Link href="/baza-znaniy" className="hover:text-teal-700 font-bold transition-colors">Все руководства и статьи</Link></li>
            <li><Link href="/baza-znaniy/kak-naiti-postavshchika-po-tz" className="hover:text-teal-700 transition-colors font-medium">Как найти поставщика по ТЗ</Link></li>
            <li><Link href="/baza-znaniy/analiz-riskov-zakupki-44-fz-223-fz" className="hover:text-teal-700 transition-colors font-medium">Чек-лист рисков 44-ФЗ</Link></li>
            <li><Link href="/baza-znaniy/reestr-minpromtorga-postanovleniya-616-617" className="hover:text-teal-700 transition-colors font-medium">Постановления № 616 и 617</Link></li>
            <li><Link href="/baza-znaniy/kak-sostavit-zapros-kp-postavshchiku" className="hover:text-teal-700 transition-colors font-medium">Как составить Запрос КП</Link></li>
            <li><Link href="/baza-znaniy/proverka-dilerskih-sertifikatov-b2b" className="hover:text-teal-700 transition-colors font-medium">Проверка дилерских сертификатов</Link></li>
          </ul>
        </div>

        {/* Legal & About */}
        <div>
          <strong className="text-slate-900 font-bold text-sm block mb-3">О сервисе и оферта</strong>
          <ul className="space-y-2.5">
            <li><Link href="/about" className="hover:text-teal-700 font-bold transition-colors">О сервисе TenderLex</Link></li>
            <li><Link href="/#pricing" className="hover:text-teal-700 transition-colors font-medium">Тарифные пакеты</Link></li>
            <li><Link href="/terms" className="hover:text-teal-700 transition-colors font-medium">Публичная оферта</Link></li>
            <li><Link href="/privacy" className="hover:text-teal-700 transition-colors font-medium">Политика конфиденциальности</Link></li>
            <li><Link href="/personal-data" className="hover:text-teal-700 transition-colors font-medium">Согласие на обработку 152-ФЗ</Link></li>
            <li><Link href="/legal" className="hover:text-teal-700 transition-colors font-medium">Реквизиты и контакты</Link></li>
          </ul>
        </div>
      </div>

      {/* Requisites Bar */}
      <div className="border-t border-slate-200 bg-slate-50 py-6 px-4 sm:px-6 text-slate-500 text-[11px] leading-relaxed">
        <div className="container max-w-6xl mx-auto flex flex-col md:flex-row justify-between gap-4">
          <div>
            <strong className="text-slate-700 block font-bold">ИП Груздев Игорь Вячеславович</strong>
            <span>ИНН: 352516048881 • ОГРНИП: 323352500038991 • 160541, Вологодская обл., Вологодский р-н, дер. Тарасово, д. 3</span>
          </div>
          <div className="text-slate-600">
            <span>© {new Date().getFullYear()} TenderLex. Все права защищены. Работает по всей территории РФ.</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
