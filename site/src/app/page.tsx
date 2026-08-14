import { TenderLexLogo } from '@/components/logo';
import type { Metadata } from 'next';
import Link from 'next/link';
import { InteractiveHeroDemo } from '@/components/interactive-hero-demo';
import { getSiteData } from '@/lib/site-data';
import {
  buildOrganizationJsonLd,
  buildSoftwareApplicationJsonLd,
  buildWebSiteJsonLd,
  buildFaqJsonLd,
} from '@/lib/seo';
import {
  FileText,
  Search,
  Zap,
  Building2,
  ShieldCheck,
  ArrowRight,
  Mail,
  CheckCircle2,
  Sparkles,
} from 'lucide-react';

export const revalidate = 300;

export const metadata: Metadata = {
  title: 'TenderLex — Извлечение контактов поставщиков и разбор ТЗ за 3 минуты',
  description:
    'ИИ-платформа для закупщиков: извлечение номенклатуры из ТЗ, сбор прямых email/телефонов заводов и дилеров по всей России, автоматическая генерация запросов КП и экспресс-анализ 44-ФЗ / 223-ФЗ.',
  keywords:
    'поиск поставщиков по ТЗ, коммерческое предложение закупка, контакты дилеров заводов, анализ рисков ТЗ 44-ФЗ, автоматизация закупа тендер',
  openGraph: {
    title: 'TenderLex — Извлечение контактов поставщиков и разбор ТЗ за 3 минуты',
    description:
      'ИИ-помощник отдела снабжения. Находите прямые контакты производителей и дилеров по вашему ТЗ за 3 минуты.',
    url: 'https://tenderlex.ru',
    siteName: 'TenderLex',
    locale: 'ru_RU',
    type: 'website',
  },
};

export default async function HomePage() {
  const data = await getSiteData();
  const botUrl = process.env.NEXT_PUBLIC_BOT_URL || 'https://t.me/TenderLexBot';
  const cabinetUrl = '/cabinet';

  const orgSchema = buildOrganizationJsonLd();
  const appSchema = buildSoftwareApplicationJsonLd();
  const websiteSchema = buildWebSiteJsonLd();

  const homeFaqItems = [
    {
      question: 'Как TenderLex находит прямые контакты поставщиков?',
      answer:
        'Сервис сопоставляет извлеченную номенклатуру ТЗ с базой контрагентов, фильтруя компании по ролям (Завод-изготовитель, Дилер) и предоставляя e-mail отделов оптовых продаж.',
    },
    {
      question: 'Как получить бесплатный триал-период?',
      answer:
        'При регистрация каждому новому пользователю автоматически начисляется 200 рублей приветственного баланса. Этого достаточно для выполнения первых двух бесплатных поисков или анализов документов.',
    },
    {
      question: 'Можно ли использовать Telegram-бота без регистрации на сайте?',
      answer:
        'Да, наш Telegram-бот @TenderLexBot обладает полным функционалом поиска контактов и разбора закупки 44-ФЗ. Баланс отчетов единый для сайта и бота.',
    },
    {
      question: 'Можно ли автоматизировать работу отдела снабжения для всей компании?',
      answer:
        'Да. Использование TenderLex сокращает время поиска релевантных адресатов и подготовки единых писем с нескольких часов до 3 минут.',
    },
  ];

  const faqSchema = buildFaqJsonLd(homeFaqItems);

  const scenarios = [
    {
      id: 'kp',
      title: 'Сбор контрагентов для Запроса КП',
      tag: 'Поиск контактов',
      desc: 'Извлечение сложных позиций из ТЗ и сбор прямых e-mail отделов продаж заводов и официальных дилеров.',
      points: [
        'Сбор базы контрагентов для Запроса КП',
        'Подготовка вопросов заказчику закупки',
        'Поиск аналогов и оценка исполнимости контракта',
      ],
      link: '/postavshchiki-dlya-zaprosa-kp',
    },
    {
      id: 'tz',
      title: 'Поиск поставщиков по ТЗ',
      tag: 'База заводов и дилеров',
      desc: 'Глубокий анализ спецификации, определение категорий товаров и выгрузка списка проверенных поставщиков.',
      points: [
        'Поиск прямых изготовителей по ГОСТ/ТУ',
        'Фильтрация дилеров по регионам',
        'Прямые контакты отделов продаж',
      ],
      link: '/poisk-postavshchikov-po-tz',
    },
    {
      id: 'risks',
      title: 'Анализ рисков 44-ФЗ / 223-ФЗ',
      tag: 'Экспресс-аудит',
      desc: 'Проверка проекта контракта на сжатые сроки, нетипичные штрафы, реестры Минпромторга и скрытые требования.',
      points: [
        'Выявление жестких сроков приемки',
        'Проверка Постановлений № 616/617',
        'Подготовка вопросов для разъяснений',
      ],
      link: '/ocenka-riskov-zakupki',
    },
    {
      id: 'mfg',
      title: 'Поиск производителей по ТЗ',
      tag: 'Прямые заводы',
      desc: 'Поиск завода-изготовителя без посредников для получения минимальной цены и выявления официальных дистрибьюторов.',
      points: [
        'Идентификация заводов по номенклатуре',
        'Проверка наличия дилерской сети',
        'Формирование официального Запроса КП',
      ],
      link: '/poisk-proizvoditeley-po-tz',
    },
  ];

  const features = [
    {
      icon: Search,
      badge: 'Поиск по ТЗ',
      title: 'Авто-извлечение номенклатуры',
      desc: 'Загрузите проект контракта или файл ТЗ (PDF, Word, Excel). ИИ сам распознает таблицы, маркировки и ГОСТы.',
    },
    {
      icon: Mail,
      badge: 'Прямые контакты',
      title: 'E-mail и телефоны продаж',
      desc: 'Сервис предоставляет не общие инфо-адреса, а прямые контакты отделов оптовых продаж и менеджеров.',
    },
    {
      icon: FileText,
      badge: 'Готовый Запрос КП',
      title: 'Единый текст обращения',
      desc: 'Формирование готового официального письма Запроса КП с выбранными позициями ТЗ в один клик.',
    },
    {
      icon: ShieldCheck,
      badge: 'Аудит рисков',
      title: 'Разбор контракта 44-ФЗ / 223-ФЗ',
      desc: 'Мгновенное выявление подвохов в условиях оплаты, нетипичных штрафах, авансировании и приемке.',
    },
  ];

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(orgSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(appSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
      />

      <main className="bg-slate-50 text-slate-900 min-h-screen font-sans">
        {/* TOP HEADER */}
        <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-slate-200/90 shadow-2xs">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
            <TenderLexLogo size={36} textColor="text-teal-700" />

            <nav className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-slate-700 font-bold hover:text-teal-700 text-sm transition-colors">
                Возможности
              </a>
              <Link href="/regiony" className="text-slate-700 font-bold hover:text-teal-700 text-sm transition-colors">
                Регионы
              </Link>
              <Link href="/baza-znaniy" className="text-slate-700 font-bold hover:text-teal-700 text-sm transition-colors">
                База знаний
              </Link>
              <a href="#faq" className="text-slate-700 font-bold hover:text-teal-700 text-sm transition-colors">
                FAQ
              </a>
            </nav>

            <div className="flex items-center gap-3">
              <a
                href={botUrl}
                target="_blank"
                rel="noreferrer"
                className="hidden sm:inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition-all border border-slate-200"
              >
                Telegram-бот
              </a>
              <a
                href={cabinetUrl}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-extrabold shadow-sm transition-all hover:scale-[1.02]"
              >
                Личный кабинет
              </a>
            </div>
          </div>
        </header>

        {/* HERO */}
        <section className="py-12 sm:py-20 bg-gradient-to-b from-teal-50/70 via-slate-50 to-slate-50 border-b border-slate-200">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-3xl mx-auto space-y-6">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-teal-100/90 border border-teal-200 text-teal-800 text-xs font-extrabold shadow-2xs">
                <Sparkles size={14} className="text-teal-600" />
                <span>Платформа ИИ-автоматизации снабжения</span>
              </div>

              <h1 className="text-3xl sm:text-5xl font-black tracking-tight text-slate-900 leading-[1.15]">
                Извлечение контактов поставщиков и разбор ТЗ за 3 минуты
              </h1>

              <p className="text-base sm:text-lg text-slate-700 font-medium leading-relaxed">
                Загрузите ТЗ или спецификацию закупки — TenderLex автоматически распознает позицию, сопоставит контакты прямых изготовителей и дилеров по всей России и выявит риски 44-ФЗ.
              </p>

              <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
                <a
                  href={cabinetUrl}
                  className="inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-extrabold shadow-md shadow-teal-600/20 text-sm transition-all hover:scale-[1.01]"
                >
                  Попробовать бесплатно (200 ₽ на баланс)
                  <ArrowRight size={16} />
                </a>
                <a
                  href={botUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl bg-white hover:bg-slate-100 text-slate-800 font-extrabold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
                >
                  Открыть Telegram-бота
                </a>
              </div>
            </div>

            <div className="mt-12 sm:mt-16">
              <InteractiveHeroDemo />
            </div>
          </div>
        </section>

        {/* FEATURES GRID */}
        <section id="features" className="py-16 sm:py-24 bg-white border-b border-slate-200">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-2xl mx-auto mb-12 sm:mb-16 space-y-3">
              <span className="text-xs font-extrabold uppercase tracking-wider text-teal-700">Возможности платформы</span>
              <h2 className="text-2xl sm:text-4xl font-black text-slate-900 tracking-tight">
                Инструменты отделов снабжения и тендерных специалистов
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {features.map((item, idx) => {
                const IconComp = item.icon;
                return (
                  <div
                    key={idx}
                    className="p-6 rounded-2xl bg-slate-50 border-2 border-slate-200/90 shadow-2xs hover:border-teal-500/80 transition-all group"
                  >
                    <div className="w-12 h-12 rounded-xl bg-teal-100 text-teal-700 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
                      <IconComp size={24} />
                    </div>
                    <span className="text-xs font-bold text-teal-700 uppercase tracking-wider block mb-1">
                      {item.badge}
                    </span>
                    <h3 className="text-lg font-black text-slate-900 mb-2">{item.title}</h3>
                    <p className="text-xs text-slate-700 font-medium leading-relaxed">{item.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* SCENARIOS */}
        <section className="py-16 sm:py-24 bg-slate-50 border-b border-slate-200">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="text-center max-w-2xl mx-auto mb-12 sm:mb-16 space-y-3">
              <span className="text-xs font-extrabold uppercase tracking-wider text-teal-700">Сценарии работы</span>
              <h2 className="text-2xl sm:text-4xl font-black text-slate-900 tracking-tight">
                Решение задач любой сложности
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 sm:gap-8">
              {scenarios.map((sc) => (
                <div
                  key={sc.id}
                  className="p-8 rounded-2xl bg-white border-2 border-slate-200 shadow-2xs hover:shadow-md transition-all flex flex-col justify-between"
                >
                  <div className="space-y-4">
                    <span className="text-xs font-extrabold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200 inline-block">
                      {sc.tag}
                    </span>
                    <h3 className="text-xl font-black text-slate-900">{sc.title}</h3>
                    <p className="text-sm text-slate-700 font-medium leading-relaxed">{sc.desc}</p>

                    <ul className="space-y-2.5 pt-2">
                      {sc.points.map((pt, pIdx) => (
                        <li key={pIdx} className="flex items-start gap-2.5 text-xs text-slate-800 font-bold">
                          <CheckCircle2 size={16} className="text-teal-600 shrink-0 mt-0.5" />
                          <span>{pt}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="pt-6 mt-6 border-t border-slate-100">
                    <Link
                      href={sc.link}
                      className="inline-flex items-center gap-2 text-sm font-extrabold text-teal-700 hover:text-teal-800 transition-colors"
                    >
                      <span>Узнать больше</span>
                      <ArrowRight size={16} />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* FAQ SECTION */}
        <section id="faq" className="py-16 sm:py-24 bg-white border-b border-slate-200">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6">
            <h2 className="text-2xl sm:text-4xl font-black text-slate-900 text-center tracking-tight mb-12">
              Часто задаваемые вопросы
            </h2>

            <div className="space-y-4">
              {homeFaqItems.map((faq, idx) => (
                <details key={idx} className="group bg-slate-50 p-6 rounded-2xl border-2 border-slate-200 text-left transition-all shadow-2xs">
                  <summary className="font-bold text-slate-900 text-base cursor-pointer flex justify-between items-center list-none">
                    <span>{faq.question}</span>
                    <span className="transition group-open:rotate-180 text-teal-700">▼</span>
                  </summary>
                  <p className="mt-4 text-sm text-slate-700 font-medium leading-relaxed border-t border-slate-200 pt-4">
                    {faq.answer}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* CTA SECTION */}
        <section id="contacts" className="py-16 sm:py-24 bg-gradient-to-b from-slate-50 via-teal-50/60 to-teal-100/70 border-b border-slate-200 text-slate-900 text-center">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6 space-y-6">
            <span className="text-xs font-extrabold uppercase tracking-wider text-teal-950 bg-teal-200/80 px-3.5 py-1.5 rounded-full border border-teal-300 shadow-2xs inline-block">
              Мгновенный запуск за 3 минуты
            </span>
            <h2 className="text-2xl sm:text-4xl font-black text-slate-900 tracking-tight">
              Получите 200 ₽ на баланс при регистрации и начните работу
            </h2>
            <p className="text-slate-700 max-w-2xl mx-auto text-base font-semibold leading-relaxed">
              Зарегистрируйтесь в веб-кабинете или воспользуйтесь Telegram-ботом TenderLex для оперативного сбора контрагентов.
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-4">
              <a
                href={cabinetUrl}
                className="inline-flex items-center justify-center px-8 py-3.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-extrabold shadow-md shadow-teal-600/20 text-sm transition-all hover:scale-[1.01]"
              >
                Зарегистрироваться и получить 200 ₽
              </a>
              <a
                href={botUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center px-8 py-3.5 rounded-xl bg-white hover:bg-slate-100 text-slate-800 font-extrabold border-2 border-slate-300 shadow-xs text-sm transition-all hover:border-teal-500"
              >
                Запустить Telegram-бота
              </a>
            </div>
          </div>
        </section>

        {/* FOOTER */}
        <footer className="py-12 bg-white text-slate-600 text-xs border-t border-slate-200">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6 grid grid-cols-2 md:grid-cols-4 gap-8">
            <div>
              <strong className="text-slate-900 font-bold text-sm block mb-2">TenderLex</strong>
              <p className="text-slate-600 leading-relaxed">
                ИИ-сервис извлечения контактов поставщиков и экспресс-анализа рисков закупок 44-ФЗ / 223-ФЗ.
              </p>
            </div>
            <div>
              <strong className="text-slate-900 font-bold text-sm block mb-2">Сервисы</strong>
              <ul className="space-y-1.5">
                <li><Link href="/poisk-postavshchikov-po-tz" className="hover:text-teal-700 font-semibold">Поиск по ТЗ</Link></li>
                <li><Link href="/poisk-proizvoditeley-po-tz" className="hover:text-teal-700 font-semibold">Поиск заводов</Link></li>
                <li><Link href="/ocenka-riskov-zakupki" className="hover:text-teal-700 font-semibold">Анализ 44-ФЗ</Link></li>
              </ul>
            </div>
            <div>
              <strong className="text-slate-900 font-bold text-sm block mb-2">Информация</strong>
              <ul className="space-y-1.5">
                <li><Link href="/baza-znaniy" className="hover:text-teal-700 font-semibold">База знаний</Link></li>
                <li><Link href="/regiony" className="hover:text-teal-700 font-semibold">Регионы поставки</Link></li>
                <li><Link href="/about" className="hover:text-teal-700 font-semibold">О сервисе</Link></li>
              </ul>
            </div>
            <div>
              <strong className="text-slate-900 font-bold text-sm block mb-2">Правовая информация</strong>
              <ul className="space-y-1.5">
                <li><Link href="/privacy" className="hover:text-teal-700 font-semibold">Политика конфиденциальности</Link></li>
                <li><Link href="/terms" className="hover:text-teal-700 font-semibold">Условия использования</Link></li>
              </ul>
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}
