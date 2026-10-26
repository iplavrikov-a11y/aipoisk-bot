import { PublicSiteLink } from "@/components/public-site-link";
import type { Metadata } from "next";
import Link from "next/link";
import { ShieldCheck, CheckCircle2, FileText, Send, Building2, Sparkles } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { SeoContentBlocks } from "@/components/seo-content-blocks";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildHowToJsonLd,
  buildServiceJsonLd,
  type FaqItem,
} from "@/lib/seo";

export const metadata: Metadata = {
  title: "Поиск поставщиков для тендеров: 44-ФЗ и 223-ФЗ",
  description:
    "Поиск кандидатов на поставку по извещению или ТЗ для закупок по 44-ФЗ, 223-ФЗ и коммерческих процедур: контакты, проект запроса КП и данные для проверки.",
  keywords: [
    "поиск поставщиков для тендера",
    "поставщики под 44-ФЗ",
    "поставщики под 223-ФЗ",
    "коммерческие закупки",
    "подбор контрагентов для закупки",
    "запрос КП под тендер",
    "TenderLex",
  ],
  alternates: {
    canonical: "/poisk-postavshchikov-dlya-tendera",
  },
  openGraph: {
    type: "website",
    url: "/poisk-postavshchikov-dlya-tendera",
    title: "Поиск поставщиков для тендеров: 44-ФЗ и 223-ФЗ | TenderLex",
    description:
      "Поиск кандидатов на поставку по извещению или ТЗ: контакты, проект запроса КП и данные для проверки перед расчётом заявки.",
    siteName: "TenderLex",
    images: [
      {
        url: "/tenderlex-product-preview.png",
        width: 1200,
        height: 630,
        alt: "TenderLex — Поиск поставщиков для тендеров",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Поиск поставщиков для тендеров: 44-ФЗ и 223-ФЗ | TenderLex",
    description:
      "Поиск кандидатов на поставку по извещению или ТЗ: контакты, проект запроса КП и данные для проверки перед расчётом заявки.",
  },
};

const pagePath = "/poisk-postavshchikov-dlya-tendera";

const faqItems: FaqItem[] = [
  {
    question: "Как TenderLex помогает тендерным специалистам при подготовке заявки?",
    answer:
      "Сервис помогает разобрать извещение или ТЗ, собрать кандидатов на поставку и подготовить проект запроса КП. Роль компании, актуальность контактов, цену и условия поставки нужно подтвердить отдельно.",
  },
  {
    question: "Учитываются ли требования национального режима?",
    answer:
      "Требования национального режима и сведения реестров зависят от конкретной закупки. Используйте результат как ориентир и сверяйте применимую редакцию нормативных актов, извещение и запись по конкретной модели в официальном реестре.",
  },
  {
    question: "Сколько поставщиков нужно запрашивать под тендер?",
    answer:
      "Количество зависит от позиции и срока. Для сравнения условий обычно нужны несколько независимых кандидатов, но каждый запрос должен быть одинаковым по составу. Если ответов мало, расширьте географию или проверьте другие каналы поставки.",
  },
  {
    question: "Можно ли использовать результат до подачи заявки?",
    answer:
      "Да, как рабочий материал: кандидаты, вопросы и черновик запроса КП. Перед расчётом заявки проверьте роль компании, контакты, наличие, цену, срок и применимые требования закупки.",
  },
  {
    question: "Как настроить географию поиска — только РФ, СНГ или зарубежные заводы?",
    answer:
      "При запуске задачи можно выбрать нужный охват: «Только Россия» (строго отечественные контрагенты с ИНН РФ для национального режима), «РФ и СНГ (ЕАЭС)» (поставщики и заводы Беларуси, Казахстана и стран союза) или «Весь мир» для импортных позиций и прямых зарубежных фабрик. Для задач с приоритетом реестра Минпромторга география автоматически фиксируется на территории РФ.",
  },
  {
    question: "Что делать, если поставщик не отвечает?",
    answer:
      "Проверьте адрес и канал связи, повторите запрос и зафиксируйте дату. Если ответа нет, подключайте альтернативных кандидатов, чтобы не потерять срок подготовки заявки.",
  },
];

const contentSections = [
  {
    title: "Что меняется при поиске поставщиков под тендер",
    paragraphs: [
      "В тендере цена — только часть решения. Нужно успеть собрать кандидатов, проверить их роль и получить ответы до срока подачи заявки. Ошибка в контакте или единице измерения может сделать расчёт несопоставимым.",
      "Поиск под тендер начинается с разбора требований: что именно закупается, в каком объёме, с какими документами и ограничениями. После этого список кандидатов становится короче и точнее.",
    ],
    bullets: [
      "срок подачи и график ответов;",
      "требования к товару и документам;",
      "география поставки;",
      "национальный режим и ограничения;",
      "цена и условия оплаты.",
    ],
  },
  {
    title: "Как проверять кандидатов до запроса КП",
    paragraphs: [
      "Кандидат из поиска — это ещё не подтверждённый поставщик. Проверяйте, чем компания занимается, где находится, какие товары и документы публикует. Для тендера особенно важно понять, успеет ли поставщик ответить и поставить товар.",
      "Сравнивайте не только названия, но и роль: производитель, официальный дилер, дистрибьютор или посредник. От этого зависят сроки, документы и итоговая цена.",
    ],
    bullets: [
      "сайт и опубликованные контакты;",
      "роль в цепочке поставки;",
      "регион и склад;",
      "сертификаты и паспорта;",
      "опыт похожих поставок.",
    ],
  },
  {
    title: "Типичные ошибки при подборе поставщиков",
    paragraphs: [
      "Одна из частых ошибок — отправить запрос только одному кандидату и считать его цену рыночной. Другая — использовать разные формулировки для разных поставщиков, а потом сравнивать несопоставимые ответы.",
      "Если в закупке есть требования национального режима, их проверяют по конкретной модели и документу на дату закупки, а не по общему описанию компании.",
    ],
    bullets: [
      "запрос без объёма и единиц;",
      "разные условия для разных адресатов;",
      "игнорирование срока ответа;",
      "проверка только по названию компании;",
      "отсутствие фиксации ответов.",
    ],
  },
  {
    title: "Что получает тендерный специалист",
    paragraphs: [
      "Результат помогает подготовить заявку: список кандидатов, вопросы к поставщикам и черновик запроса КП. Это рабочий материал, который нужно проверить и дополнить условиями конкретной закупки.",
    ],
    bullets: [
      "кандидаты с ролью и регионом;",
      "источники для проверки;",
      "проект запроса КП;",
      "вопросы по условиям поставки.",
    ],
  },
];


export default function PoiskPostavshchikovDlyaTenderaPage() {
  const schemaBreadcrumb = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Поиск поставщиков для тендера", item: "https://tenderlex.ru" + pagePath },
  ]);

  const schemaService = buildServiceJsonLd({
    name: "Поиск поставщиков для тендера",
    description: "Сервис подбора поставщиков под закупки 44-ФЗ, 223-ФЗ и коммерческие торги.",
    path: pagePath,
  });

  const schemaFaq = buildFaqJsonLd(faqItems);
  const schemaHowTo = buildHowToJsonLd({
    name: "Как подобрать поставщиков под тендер",
    description: "Пошаговый процесс подбора контрагентов под тендерную заявку.",
    steps: [
      { name: "Загрузка извещения или ТЗ закупки", text: "Передайте файл или номер закупки." },
      { name: "Смысловой анализ требований", text: "ИИ выделяет критические параметры и стандарты." },
      { name: "Формирование списка кандидатов", text: "Сбор доступных контактов для дальнейшей проверки." },
      { name: "Запрос цен для расчёта заявки", text: "Проект письма для уточнения цены, срока и условий." },
    ],
  });

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaBreadcrumb) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaService) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaFaq) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaHowTo) }} />

      <main className="bg-slate-50/60 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

        {/* HERO */}
        <section className="relative overflow-hidden pt-12 pb-20 border-b border-slate-200/90 bg-gradient-to-b from-teal-50/60 via-slate-50 to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-black uppercase tracking-wider shadow-2xs">
              <ShieldCheck size={14} className="text-teal-600" />
              <span>Подбор поставщиков: 44-ФЗ, 223-ФЗ и коммерческие торги</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Поиск поставщиков для тендеров, госзакупок и коммерческих торгов
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              Сбор кандидатов на поставку по требованиям конкурсной документации, чтобы запросить цену, срок и условия для расчёта заявки.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Найти под тендер</span>
              </a>
              <PublicSiteLink
                channel="bot"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-extrabold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
              >
                <Send size={16} className="text-teal-600" />
                <span>Запустить в Telegram</span>
              </PublicSiteLink>
            </div>
          </div>
        </section>

        {/* BENEFITS */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Точный расчет НМЦК</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Сбор актуальных коммерческих предложений для формирования конкурентной цены заявки.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Соблюдение Нацрежима</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Проверка товаров по ПП 616 и ПП 617, подбор заводов с действующими реестровыми номерами ГИСП.
                </p>
              </div>

              <div className="p-8 rounded-3xl bg-slate-50 border-2 border-slate-200/80 space-y-4 shadow-2xs">
                <h3 className="text-lg font-black text-slate-900">Сжатые сроки подготовки</h3>
                <p className="text-xs text-slate-600 leading-relaxed font-medium">
                  Поиск контактов компаний и подготовка данных для их проверки перед обращением.
                </p>
              </div>
            </div>
          </div>
        </section>

        <SeoContentBlocks sections={contentSections} />

        {/* FAQ */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-slate-50">
          <div className="container max-w-4xl mx-auto px-4 sm:px-6">
            <h2 className="text-2xl sm:text-4xl font-black text-slate-900 text-center mb-12">
              Часто задаваемые вопросы
            </h2>
            <div className="space-y-4">
              {faqItems.map((item, index) => (
                <details key={index} className="group bg-white p-6 rounded-2xl border-2 border-slate-200 text-left shadow-2xs">
                  <summary className="font-bold text-slate-900 text-base cursor-pointer flex justify-between items-center list-none">
                    <span>{item.question}</span>
                    <span className="transition group-open:rotate-180 text-teal-700">▼</span>
                  </summary>
                  <p className="mt-4 text-sm text-slate-700 font-medium leading-relaxed border-t border-slate-200 pt-4">
                    {item.answer}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <ContactSection />

        <SiteFooter />
      </main>
    </>
  );
}
