import type { Metadata } from "next";
import Link from "next/link";
import {
  Code2,
  Terminal,
  Cpu,
  ShieldCheck,
  Zap,
  ArrowRight,
  CheckCircle2,
  Lock,
  Download,
  Key,
  Layers,
  Search,
  Sparkles,
  FileText,
  Boxes,
} from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { ApiCodeTabs } from "@/components/api-code-tabs";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  type FaqItem,
} from "@/lib/seo";

export const metadata: Metadata = {
  title: { absolute: "B2B API TenderLex: поиск поставщиков, подбор аналогов и анализ закупок" },
  description:
    "Программный REST API и MCP-протокол TenderLex для интеграции с 1С:Предприятие, ERP и CRM. Автоматический поиск прямых поставщиков, подбор аналогов по ТЗ и аудит контрактов по 44-ФЗ и 223-ФЗ.",
  keywords: [
    "api поиска поставщиков",
    "api закупки 44 фз",
    "интеграция 1с поиск поставщиков",
    "api подбор аналогов товаров",
    "mcp server тендеры",
    "rest api госзакупки",
    "реестр минпромторга api",
    "автоматизация закупок 1с",
    "TenderLex API",
  ],
  alternates: {
    canonical: "/api-integracii",
  },
  openGraph: {
    type: "website",
    url: "/api-integracii",
    title: "B2B API TenderLex: интеграция с 1C, ERP и CRM",
    description:
      "Программный доступ к алгоритмам поиска производителей, подбора аналогов по ТЗ и проверки документации. Единый баланс без абонентской платы.",
    siteName: "TenderLex",
    images: [
      {
        url: "/tenderlex-product-preview.png",
        width: 1200,
        height: 630,
        alt: "TenderLex B2B API и интеграции",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "B2B API TenderLex: интеграция снабжения и ТЗ",
    description:
      "REST API и протокол MCP для корпоративных систем закупок. Поиск заводов, подбор аналогов и проверка рисков.",
    images: ["/tenderlex-product-preview.png"],
  },
};

const pagePath = "/api-integracii";

const faqItems: FaqItem[] = [
  {
    question: "Как начать работу с TenderLex API?",
    answer:
      "Зарегистрируйтесь в личном кабинете tenderlex.ru и откройте раздел «API». Сгенерируйте персональный ключ доступа (формата tl_live_...). Сразу после создания ключ готов к использованию в REST-запросах или интеграциях с 1С.",
  },
  {
    question: "Как тарифицируются запросы к API?",
    answer:
      "Оплата списывается с единого баланса вашего аккаунта за фактически выполненные задачи. Если по запросу поставщики не найдены или произошел сетевой сбой, средства не удерживаются. Для новых клиентов при регистрации начисляется приветственный баланс 495 ₽, достаточный для полноценного тестирования всех методов.",
  },
  {
    question: "Можно ли встроить TenderLex напрямую в 1С:Предприятие?",
    answer:
      "Да. API построен по стандартному протоколу REST поверх HTTPS (JSON UTF-8). В типовые конфигурации (1C:ERP, Комплексная автоматизация, Управление торговлей) подключение выполняется штатным объектом «HTTPСоединение» без установки сторонних компонент.",
  },
  {
    question: "В каком формате возвращаются результаты подбора аналогов?",
    answer:
      "Метод подбора аналогов возвращает структурированный JSON с перечнем параметров, степенями соответствия и характеристиками кандидатов, а также прямую ссылку на скачивание полного отчета в формате Word (DOCX).",
  },
  {
    question: "Поддерживается ли Model Context Protocol (MCP)?",
    answer:
      "Да. Вы можете подключить TenderLex к Claude Desktop, Cursor или другим ИИ-ассистентам с помощью нашего легковесного автономного скрипта tenderlex_mcp.py, работающего по стандартному JSON-RPC протоколу.",
  },
];

export default function ApiIntegrationsPage() {
  const breadcrumbJsonLd = buildBreadcrumbJsonLd([
    { name: "Главная", path: "/" },
    { name: "B2B API и интеграции", path: pagePath },
  ]);

  const faqJsonLd = buildFaqJsonLd(faqItems);

  const softwareJsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "TenderLex B2B API",
    applicationCategory: "BusinessApplication",
    operatingSystem: "All",
    offers: {
      "@type": "Offer",
      price: "99.00",
      priceCurrency: "RUB",
      description: "Оплата за выполненный успешный запрос к платформе",
    },
    description:
      "Программный REST API и протокол MCP для поиска производителей, сопоставления номенклатуры и аудита документации госзакупок.",
    provider: {
      "@type": "Organization",
      name: "TenderLex",
      url: "https://tenderlex.ru",
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareJsonLd) }}
      />

      <SiteHeader />

      <main className="min-h-screen bg-slate-50 text-slate-900 font-sans">
        {/* Hero Section */}
        <section className="relative overflow-hidden bg-gradient-to-b from-slate-950 via-slate-900 to-slate-900 text-white pt-16 pb-20 sm:pt-20 sm:pb-24 border-b border-slate-800">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-teal-500/10 via-transparent to-transparent pointer-events-none" />

          <div className="container max-w-6xl mx-auto px-4 sm:px-6 relative z-10">
            {/* Breadcrumb nav */}
            <nav aria-label="Хлебные крошки" className="mb-6 text-xs text-slate-400">
              <ol className="flex items-center gap-1.5 flex-wrap">
                <li>
                  <Link href="/" className="hover:text-teal-300 transition-colors">
                    Главная
                  </Link>
                </li>
                <li>/</li>
                <li className="text-teal-400 font-semibold" aria-current="page">
                  B2B API и интеграции
                </li>
              </ol>
            </nav>

            <div className="max-w-3xl space-y-5">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-500/10 border border-teal-500/30 text-teal-300 text-xs font-bold uppercase tracking-wider">
                <Code2 size={13} />
                <span>B2B API & MCP Protocol</span>
              </div>

              <h1 className="text-3xl sm:text-4xl md:text-5xl font-black text-white tracking-tight leading-tight">
                Программный API поиска поставщиков и анализа закупок
              </h1>

              <p className="text-base sm:text-lg text-slate-300 leading-relaxed font-normal">
                Встройте алгоритмы TenderLex в <strong>1С:Предприятие</strong>, корпоративную ERP или CRM.
                Автоматический поиск прямых производителей, подбор аналогов по ТЗ и аудит контрактов
                через быстрый REST API с оплатой за результат.
              </p>

              <div className="flex flex-wrap items-center gap-3.5 pt-3">
                <Link
                  href="/cabinet"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 text-sm font-extrabold shadow-lg shadow-teal-500/25 transition-all hover:scale-[1.02]"
                >
                  <Key size={16} />
                  <span>Получить API-ключ в кабинете</span>
                </Link>

                <a
                  href="#methods"
                  className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-200 text-sm font-bold border border-slate-700 transition-colors"
                >
                  <Terminal size={15} />
                  <span>Документация методов</span>
                </a>
              </div>

              {/* Trust Badges */}
              <div className="pt-6 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs text-slate-300 border-t border-slate-800/80">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={15} className="text-teal-400 shrink-0" />
                  <span>Единый баланс без подписок</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={15} className="text-teal-400 shrink-0" />
                  <span>1С:Предприятие 8.3 из коробки</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={15} className="text-teal-400 shrink-0" />
                  <span>Списание только за результат</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={15} className="text-teal-400 shrink-0" />
                  <span>495 ₽ стартовый баланс</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 1: Three Core Modules in strict canonical order */}
        <section id="methods" className="py-16 sm:py-20 bg-white border-b border-slate-200">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6 space-y-12">
            <div className="max-w-2xl space-y-3">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                Три сервиса TenderLex в едином программном интерфейсе
              </h2>
              <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                Доступ ко всем ключевым модулям платформы через структурированные JSON-запросы.
                Каждый метод выполняет поиск в режиме реального времени.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Module 1: Поиск поставщиков */}
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 flex flex-col justify-between space-y-4 hover:border-teal-500/50 hover:shadow-md transition-all">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="w-8 h-8 rounded-lg bg-teal-100 text-teal-800 flex items-center justify-center font-bold text-sm">
                      1
                    </span>
                    <span className="text-[11px] font-mono font-bold text-teal-800 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                      POST /suppliers/search
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-slate-900">
                    Поиск поставщиков
                  </h3>

                  <p className="text-xs text-slate-600 leading-relaxed">
                    Подбор проверенных производителей, заводов и оптовых поставщиков по тексту технического задания или номеру закупки.
                  </p>

                  <ul className="space-y-2 text-xs text-slate-600 pt-2 border-t border-slate-200">
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 size={14} className="text-teal-600 shrink-0 mt-0.5" />
                      <span>Прямые контакты отделов сбыта (email, телефон, сайт)</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 size={14} className="text-teal-600 shrink-0 mt-0.5" />
                      <span>ИНН, регион и статус (завод, дилер, поставщик)</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 size={14} className="text-teal-600 shrink-0 mt-0.5" />
                      <span>Фильтрация по Реестру Минпромторга (ПП 616/719)</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 size={14} className="text-teal-600 shrink-0 mt-0.5" />
                      <span>Готовый текст официального запроса КП</span>
                    </li>
                  </ul>
                </div>

                <div className="pt-3 border-t border-slate-200 text-xs text-slate-500 flex items-center justify-between">
                  <span>Тариф за запрос: <strong>от 75.80 до 99 ₽</strong></span>
                </div>
              </div>

              {/* Module 2: Подбор товара и аналогов */}
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 flex flex-col justify-between space-y-4 hover:border-emerald-500/50 hover:shadow-md transition-all">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center font-bold text-sm">
                      2
                    </span>
                    <span className="text-[11px] font-mono font-bold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      POST /products/exact-analogs
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-slate-900">
                    Подбор товара и аналогов
                  </h3>

                  <p className="text-xs text-slate-600 leading-relaxed">
                    Глубокий анализ спецификации, определение скрытого оригинала производителя и сопоставление с подтвержденными эквивалентами.
                  </p>

                  <ul className="space-y-2 text-xs text-slate-600 pt-2 border-t border-slate-200">
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 size={14} className="text-emerald-600 shrink-0 mt-0.5" />
                      <span>Выявление скрытой модели по параметрам ТЗ</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 size={14} className="text-emerald-600 shrink-0 mt-0.5" />
                      <span>Сопоставление диапазонов («не менее», «не более», ГОСТ)</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 size={14} className="text-emerald-600 shrink-0 mt-0.5" />
                      <span>Подбор 2–4 отечественных эквивалентов</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 size={14} className="text-emerald-600 shrink-0 mt-0.5" />
                      <span>Прямая ссылка на официальный отчет в Word (.docx)</span>
                    </li>
                  </ul>
                </div>

                <div className="pt-3 border-t border-slate-200 text-xs text-slate-500 flex items-center justify-between">
                  <span>Тариф за запрос: <strong>от 75.80 до 99 ₽</strong></span>
                </div>
              </div>

              {/* Module 3: Анализ документации */}
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 flex flex-col justify-between space-y-4 hover:border-sky-500/50 hover:shadow-md transition-all">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="w-8 h-8 rounded-lg bg-sky-100 text-sky-800 flex items-center justify-center font-bold text-sm">
                      3
                    </span>
                    <span className="text-[11px] font-mono font-bold text-sky-800 bg-sky-50 px-2 py-0.5 rounded border border-sky-200">
                      POST /procurements/analyze
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-slate-900">
                    Анализ документации
                  </h3>

                  <p className="text-xs text-slate-600 leading-relaxed">
                    Экспертный аудит проекта контракта и извещения по 44-ФЗ и 223-ФЗ. Оценка скрытых штрафов, асимметрии ответственности и рисков приемки.
                  </p>

                  <ul className="space-y-2 text-xs text-slate-600 pt-2 border-t border-slate-200">
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 size={14} className="text-teal-600 shrink-0 mt-0.5" />
                      <span>Проверка кабальных условий и завышенных штрафов</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 size={14} className="text-teal-600 shrink-0 mt-0.5" />
                      <span>Аудит требований национального режима (ПП РФ № 1875)</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 size={14} className="text-teal-600 shrink-0 mt-0.5" />
                      <span>Оценка условий обеспечения и возврата гарантий</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 size={14} className="text-teal-600 shrink-0 mt-0.5" />
                      <span>Структурированный Markdown-отчет с рекомендациями</span>
                    </li>
                  </ul>
                </div>

                <div className="pt-3 border-t border-slate-200 text-xs text-slate-500 flex items-center justify-between">
                  <span>Тариф за запрос: <strong>от 75.80 до 99 ₽</strong></span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 2: Code Snippets & Playground */}
        <section className="py-16 sm:py-20 bg-slate-900 text-white border-b border-slate-800">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6 space-y-8">
            <div className="max-w-2xl space-y-3">
              <div className="inline-flex items-center gap-1.5 text-teal-400 text-xs font-bold uppercase tracking-wider">
                <Terminal size={14} />
                <span>Примеры интеграции</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                Подключение за несколько минут на любом стеке
              </h2>
              <p className="text-sm text-slate-300">
                Выберите язык программирования или скопируйте готовый запрос для cURL, Python, Node.js или внешней обработки 1С:Предприятие.
              </p>
            </div>

            <ApiCodeTabs />
          </div>
        </section>

        {/* Section 3: Model Context Protocol (MCP) Integration */}
        <section className="py-16 sm:py-20 bg-white border-b border-slate-200">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6 space-y-8">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
              <div className="space-y-4">
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-teal-50 border border-teal-200 text-teal-800 text-xs font-bold">
                  <Sparkles size={13} />
                  <span>Model Context Protocol (MCP)</span>
                </div>

                <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                  Прямое подключение к Claude Desktop и Cursor
                </h2>

                <p className="text-sm text-slate-600 leading-relaxed">
                  Благодаря поддержке протокола MCP вы можете вызывать функции поиска поставщиков
                  и анализа ТЗ прямо из диалога с локальными ИИ-ассистентами. Нейросеть сама формирует
                  параметры запроса к TenderLex и выдает проверенные результаты в чат.
                </p>

                <div className="space-y-2.5 pt-2 text-xs text-slate-700">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={15} className="text-teal-600 shrink-0" />
                    <span>Автономный Python-коннектор без внешних зависимостей</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={15} className="text-teal-600 shrink-0" />
                    <span>Стандартный протокол JSON-RPC 2.0 (stdio)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={15} className="text-teal-600 shrink-0" />
                    <span>Совместимость с Claude, Cursor, Zed и Windsurf</span>
                  </div>
                </div>

                <div className="pt-3">
                  <a
                    href="/scripts/tenderlex_mcp.py"
                    download="tenderlex_mcp.py"
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-colors cursor-pointer"
                  >
                    <Download size={14} />
                    <span>Скачать tenderlex_mcp.py</span>
                  </a>
                </div>
              </div>

              <div className="bg-slate-900 p-5 rounded-2xl border border-slate-800 text-xs font-mono text-slate-200 space-y-3">
                <div className="text-slate-400 text-[11px] pb-2 border-b border-slate-800 flex items-center justify-between">
                  <span>Конфигурация claude_desktop_config.json</span>
                  <span className="text-teal-400">JSON</span>
                </div>
                <pre className="text-emerald-300 text-[11px] leading-relaxed overflow-x-auto">
{`{
  "mcpServers": {
    "tenderlex": {
      "command": "python3",
      "args": [
        "tenderlex_mcp.py",
        "--api-key",
        "tl_live_YOUR_API_KEY"
      ]
    }
  }
}`}
                </pre>
              </div>
            </div>
          </div>
        </section>

        {/* Section 4: Transparent Billing & Pricing Guarantee */}
        <section className="py-16 sm:py-20 bg-slate-50 border-b border-slate-200">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6 space-y-10">
            <div className="text-center max-w-2xl mx-auto space-y-3">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                Прозрачные условия тарификации
              </h2>
              <p className="text-sm text-slate-600">
                Никаких скрытых платежей, подписок или сгорающих пакетов.
                Единый баланс для веб-кабинета, Telegram-бота и API.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-3">
                <div className="p-2.5 rounded-xl bg-teal-50 text-teal-700 w-fit">
                  <ShieldCheck size={20} />
                </div>
                <h3 className="text-base font-bold text-slate-900">
                  Двухфазный биллинг
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Средства резервируются в начале запроса и окончательно списываются только после возврата проверенных результатов. Если поставщики не найдены или произошел сетевой сбой — резерв возвращается полностью.
                </p>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-3">
                <div className="p-2.5 rounded-xl bg-teal-50 text-teal-700 w-fit">
                  <Key size={20} />
                </div>
                <h3 className="text-base font-bold text-slate-900">
                  495 ₽ стартовый баланс
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  При регистрации каждый пользователь получает приветственный баланс 495 ₽ в личном кабинете. Этого достаточно, чтобы полноценно протестировать до 5 реальных запросов через API до оплаты.
                </p>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs space-y-3">
                <div className="p-2.5 rounded-xl bg-teal-50 text-teal-700 w-fit">
                  <Zap size={20} />
                </div>
                <h3 className="text-base font-bold text-slate-900">
                  Без абонентской платы
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Пополняйте баланс на любую сумму. Средства на балансе не сгорают в конце месяца. Если вы временно не отправляете запросы к API, баланс сохраняется без каких-либо комиссий.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Section 5: FAQ Section */}
        <section className="py-16 sm:py-20 bg-white border-b border-slate-200">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6 space-y-8">
            <div className="text-center space-y-2">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                Часто задаваемые вопросы
              </h2>
              <p className="text-sm text-slate-600">
                Ответы на популярные вопросы о подключении и использовании B2B API
              </p>
            </div>

            <div className="space-y-4">
              {faqItems.map((item, index) => (
                <details
                  key={index}
                  className="group bg-slate-50 border border-slate-200 rounded-xl p-4 sm:p-5 transition-all open:bg-white open:shadow-xs"
                >
                  <summary className="font-bold text-sm sm:text-base text-slate-800 cursor-pointer list-none flex items-center justify-between gap-4">
                    <span>{item.question}</span>
                    <span className="text-slate-400 group-open:rotate-180 transition-transform">
                      ▼
                    </span>
                  </summary>
                  <div className="mt-3 text-xs sm:text-sm text-slate-600 leading-relaxed pt-2 border-t border-slate-100">
                    {item.answer}
                  </div>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-16 sm:py-20 bg-gradient-to-br from-teal-900 to-slate-950 text-white">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-white tracking-tight">
              Готовы автоматизировать поиск поставщиков и анализ ТЗ?
            </h2>
            <p className="text-sm sm:text-base text-slate-300 max-w-2xl mx-auto leading-relaxed">
              Получите персональный API-ключ в личном кабинете TenderLex, используйте 495 ₽ приветственного баланса и подключите алгоритмы к вашей системе уже сегодня.
            </p>
            <div className="pt-2">
              <Link
                href="/cabinet"
                className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 text-sm font-extrabold shadow-xl shadow-teal-500/25 transition-all hover:scale-[1.03]"
              >
                <Key size={16} />
                <span>Открыть личный кабинет и получить ключ</span>
              </Link>
            </div>
          </div>
        </section>

        <ContactSection />
      </main>

      <SiteFooter />
    </>
  );
}
