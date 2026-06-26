import {
  ArrowRight,
  Building2,
  CheckCircle2,
  ClipboardList,
  FileSearch,
  FileText,
  Mail,
  MessageCircle,
  Paperclip,
  Phone,
  Search,
  Send,
  ShieldCheck,
  Target,
  type LucideIcon,
} from "lucide-react";
import Image from "next/image";

import { Button } from "@/components/ui/button";
import { formatRubles, getSiteData, type PublicTariff } from "@/lib/site-data";

export const dynamic = "force-dynamic";

const featureItems = [
  {
    icon: Search,
    title: "Найти компании под позицию",
    text: "Собирает производителей, дилеров, дистрибьюторов и профильных продавцов по описанию товара, спецификации или документам закупки.",
  },
  {
    icon: ClipboardList,
    title: "Подготовить запрос цены",
    text: "Собирает один понятный текст для поставщика: что нужно, какие условия важны и какие документы попросить сразу.",
  },
  {
    icon: FileText,
    title: "Разобрать закупку",
    text: "Выносит предмет, сроки, обеспечение, оплату, поставку, требования к участнику и спорные места договора.",
  },
  {
    icon: ShieldCheck,
    title: "Понять риски до участия",
    text: "Показывает, где могут быть проблемы: приемка, штрафы, короткие сроки, ограничения допуска и вопросы заказчику.",
  },
];

const processSteps = [
  {
    title: "Поставьте задачу",
    text: "Нужно найти кому написать, подготовить запрос цены или сначала понять условия закупки.",
  },
  {
    title: "Передайте материалы",
    text: "Подойдет описание позиции, спецификация, ссылка на закупку, номер извещения или комплект документов.",
  },
  {
    title: "Получите рабочий список",
    text: "В результате есть компании, контакты, комментарии по релевантности и вопросы для первого обращения.",
  },
];

const useCases = [
  {
    icon: Building2,
    title: "Снабжению и закупкам",
    points: [
      "быстро понять, кому отправить запрос цены",
      "получить контакты производителей, дилеров и профильных продавцов",
      "собрать сравнимые ответы по цене, срокам и условиям",
    ],
  },
  {
    icon: Target,
    title: "Поставщикам и тендерным отделам",
    points: [
      "быстро понять, стоит ли заходить в закупку",
      "увидеть сроки, обеспечение, оплату и риски договора",
      "подготовить вопросы заказчику и аргументы для решения об участии",
    ],
  },
];

const primaryScenario = {
  href: "/poisk-postavshchikov-po-tz",
  title: "Список компаний для запроса цены",
  text: "Кто реально производит, продает или официально поставляет нужную позицию. Сайт, контакты, роль компании и что уточнить перед письмом.",
  points: ["производитель, дилер или поставщик", "рабочие контакты", "что спросить в первом письме"],
};

const relatedScenarios = [
  {
    href: "/poisk-postavshchikov-dlya-tendera",
    title: "Разобрать закупку",
    text: "Сроки, обеспечение, договор и спорные требования.",
  },
  {
    href: "/poisk-proizvoditeley-po-tz",
    title: "Выйти на завод",
    text: "Когда посредник не подходит.",
  },
  {
    href: "/postavshchiki-dlya-zaprosa-kp",
    title: "Собрать адресатов",
    text: "Кому отправить первый запрос.",
  },
  {
    href: "/zapros-kp-po-tz",
    title: "Подготовить письмо",
    text: "Позиции, условия и вопросы без канцелярита.",
  },
  {
    href: "/analiz-zakupochnoi-dokumentacii",
    title: "Сравнить ответы",
    text: "Цена, сроки, доставка и документы.",
  },
  {
    href: "/reestr-minpromtorga-v-zakupkah",
    title: "Проверить допуск",
    text: "Реестры и ограничения, если они есть.",
  },
];

const trustItems = [
  {
    icon: ShieldCheck,
    title: "Работа по документам и открытым источникам",
    text: "Анализ строится по номеру извещения, официальным данным и присланным материалам, а компании и контакты проверяются по открытым сайтам.",
  },
  {
    icon: FileSearch,
    title: "Ваши материалы не показываются другим",
    text: "Номер закупки, документы и описание задачи используются только для подготовки результата в вашем кабинете или Telegram.",
  },
  {
    icon: CheckCircle2,
    title: "Решение остается за командой",
    text: "TenderLex ускоряет подготовку, но финальную юридическую, ценовую и коммерческую проверку делает человек.",
  },
];

const reportRows = [
  ["Предмет закупки", "минераловатный утеплитель для кровли и фасадных работ"],
  ["Критичные условия", "плотность, толщина, упаковка, сертификаты, сроки отгрузки и доставка на объект"],
  ["Что уточнить", "замены по характеристикам, пожарные требования, сохранность упаковки при поставке"],
];

const supplierRows = [
  ["ЦЕМРОС", "производитель цемента и строительных материалов", "официальный сайт, региональные продажи", "уточнить марку, фасовку, объем партии и график отгрузки"],
  ["КНАУФ", "производитель сухих смесей и строительных систем", "официальный сайт, дилерская сеть", "проверить линейку смеси, наличие и условия доставки"],
  ["Старатели", "производитель сухих строительных смесей", "официальный сайт, контакты продаж", "сравнить фасовку, сроки поставки и документы качества"],
];

const heroSupplierRows = [
  ["ТЕХНОНИКОЛЬ", "официальный сайт, дилерская сеть", "плотность, толщина, сроки"],
  ["ROCKWOOL", "официальный сайт, региональные контакты", "сертификаты и наличие"],
  ["ISOVER", "официальный сайт, дилерская сеть", "формат плит и доставка"],
];

export default async function Home() {
  const data = await getSiteData();
  const contactUrl = data.contacts.telegram_url || (data.contacts.email ? `mailto:${data.contacts.email}` : "#contacts");
  const contactActionLabel = data.contacts.telegram_url ? "Написать в Telegram" : "Написать на email";
  const botUrl = data.bot?.telegram_url || "https://t.me/tenderlex_bot";
  const cabinetUrl = "/cabinet";
  const supplierTariffs = data.tariff_groups.supplier_search;
  const reportTariffs = data.tariff_groups.procurement_report;

  return (
    <main>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(buildJsonLd(data.site.domain, botUrl, data.contacts.telegram_url, data.contacts.email)),
        }}
      />
      <Header contactUrl={cabinetUrl} ctaLabel="Личный кабинет" />

      <section className="hero">
        <div className="container hero-layout">
          <div className="hero-copy">
            <h1>Поиск поставщиков под вашу спецификацию</h1>
            <p>
              Загрузите описание позиции, ссылку на закупку или документы. TenderLex выделит
              нужный товар, найдет компании, покажет контакты и подскажет, что спросить у
              поставщика перед сравнением цен. Если закупка сложная, отдельно разберет сроки,
              обеспечение, договор и спорные требования.
            </p>
            <div className="hero-actions">
              <Button asChild size="lg">
                <a href={cabinetUrl}>
                  <FileText size={18} aria-hidden="true" />
                  Попробовать на сайте
                </a>
              </Button>
              <Button asChild variant="secondary" size="lg">
                <a href={botUrl} target={botUrl.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
                  <Send size={18} aria-hidden="true" />
                  Попробовать в Telegram
                </a>
              </Button>
            </div>
            <dl className="hero-proof" aria-label="Коротко о сервисе">
              <ProofItem value="Компании" label="производители, дилеры, дистрибьюторы и профильные продавцы" />
              <ProofItem value="Контакты" label="сайт, страница связи, email или телефон, комментарий" />
              <ProofItem value="Проверки" label="что уточнить по цене, срокам, документам и ограничениям" />
            </dl>
          </div>

          <HeroProduct />
        </div>
      </section>

      <section id="features" className="feature-band">
        <div className="container feature-grid">
          {featureItems.map((item) => (
            <article key={item.title} className="feature-card">
              <span className="icon-box">
                <item.icon size={22} aria-hidden="true" />
              </span>
              <h2>{item.title}</h2>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="process" className="section process-section">
        <div className="container">
          <SectionHeader
            title="Как это работает"
            text="Главный результат — список компаний, с которыми можно связаться. Разбор закупки и письмо поставщику подключаются только там, где они нужны."
          />
          <div className="process-grid">
            {processSteps.map((step, index) => (
              <article key={step.title} className="process-step">
                <span>{index + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section usecase-section">
        <div className="container">
          <SectionHeader
            title="Для рабочих закупочных задач"
            text="TenderLex полезен, когда нужно не прочитать еще одну справку, а быстро получить основу для действия: кому писать, что спросить и какие условия проверить."
          />
          <div className="usecase-panel">
            {useCases.map((item) => (
              <article key={item.title} className="usecase-item">
                <span className="icon-box accent">
                  <item.icon size={22} aria-hidden="true" />
                </span>
                <h3>{item.title}</h3>
                <ul>
                  {item.points.map((point) => (
                    <li key={point}>
                      <CheckCircle2 size={17} aria-hidden="true" />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="scenarios" className="section scenario-section">
        <div className="container scenario-layout">
          <SectionHeader
            title="Сначала список компаний"
            text="Один основной путь: найти, кому отправить запрос цены. Остальные проверки нужны только когда задача сложнее обычного подбора."
            align="left"
          />
          <div className="scenario-board" aria-label="Сценарии работы TenderLex">
            <a className="scenario-primary" href={primaryScenario.href}>
              <span className="scenario-tag">Основной путь</span>
              <h3>{primaryScenario.title}</h3>
              <p>{primaryScenario.text}</p>
              <ul>
                {primaryScenario.points.map((point) => (
                  <li key={point}>
                    <CheckCircle2 size={16} aria-hidden="true" />
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
              <span className="scenario-primary-link">
                Подробнее
                <ArrowRight size={18} aria-hidden="true" />
              </span>
            </a>
            <div className="scenario-related">
              <p>Что подключить при необходимости</p>
              <div className="scenario-related-grid">
                {relatedScenarios.map((item) => (
                  <a key={item.href} className="scenario-related-link" href={item.href}>
                    <strong>{item.title}</strong>
                    <span>{item.text}</span>
                    <ArrowRight size={17} aria-hidden="true" />
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section result-section">
        <div className="container result-layout">
          <div>
            <SectionHeader
              title="На выходе не просто ссылки"
              text="Команда получает список для действия: кто подходит, куда писать, что спросить и какие условия сравнить между ответами."
              align="left"
            />
            <ul className="result-list">
              <ResultPoint title="Кого запросить" text="Производители, официальные дистрибьюторы, региональные дилеры, поставщики аналогов и профильные продавцы." />
              <ResultPoint title="Куда писать" text="Сайты, страницы связи, email или телефон, профиль компании и комментарий, почему она подходит под задачу." />
              <ResultPoint title="Что спросить" text="Цена, наличие, срок поставки, доставка, документы качества, гарантия, замены и ограничения по партии." />
              <ResultPoint title="Что проверить" text="Сроки закупки, обеспечение, оплату, приемку, договор и специальные требования, если задача идет через процедуру." />
            </ul>
          </div>
          <SupplierSheet />
        </div>
      </section>

      <section id="tariffs" className="section pricing-section">
        <div className="container">
          <SectionHeader
            title="Стоимость услуг"
            text="Базовая услуга — поиск компаний и контактов. Разбор закупки подключается отдельно, если перед запросом цены нужно понять условия и риски."
          />
          <div className="pricing-grid">
            <PricingTable
              icon={Search}
              title="Поиск компаний"
              subtitle="Список, контакты и комментарии для первого запроса"
              tariffs={supplierTariffs}
              contactUrl={contactUrl}
              contactLabel={contactActionLabel}
              note="Нужен больший список компаний или нестандартная товарная группа? Напишите нам — обсудим условия под вашу задачу."
            />
            <PricingTable
              icon={FileText}
              title="Разбор закупки"
              subtitle="Требования, условия, риски и вопросы заказчику"
              tariffs={reportTariffs}
              contactUrl={contactUrl}
              contactLabel={contactActionLabel}
            />
          </div>
        </div>
      </section>

      <section id="trust" className="section trust-section">
        <div className="container trust-layout">
          <div>
            <h2>Инструмент для подготовки, не замена решения</h2>
            <p>
              TenderLex помогает быстрее собрать компании, контакты, вопросы и условия для сравнения.
              Итоговое решение по цене, обязательствам и выбору поставщика остается за вашей командой.
            </p>
          </div>
          <div className="trust-list">
            {trustItems.map((item) => (
              <article key={item.title} className="trust-item">
                <item.icon size={20} aria-hidden="true" />
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="contacts" className="cta-section">
        <div className="container cta-inner">
          <h2>Получите список компаний для запроса цены</h2>
          <p>Передайте описание позиции, спецификацию, номер извещения или документы. TenderLex найдет компании, покажет контакты и подготовит основу для первого обращения.</p>
          <div className="cta-actions">
            <Button asChild size="lg">
              <a href={cabinetUrl}>
                <FileText size={18} aria-hidden="true" />
                Попробовать на сайте
              </a>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <a href={botUrl} target={botUrl.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
                <Send size={18} aria-hidden="true" />
                Попробовать в Telegram
              </a>
            </Button>
            <div className="contact-stack">
              {data.contacts.telegram_url ? <ContactLink href={data.contacts.telegram_url} icon={MessageCircle} label="Telegram" /> : null}
              <ContactLink href={data.contacts.max_url} icon={MessageCircle} label="MAX" staticLabel={data.contacts.max || "MAX"} />
              <ContactLink href={data.contacts.email ? `mailto:${data.contacts.email}` : ""} icon={Mail} label={data.contacts.email} />
            </div>
          </div>
        </div>
      </section>

      <Footer email={data.contacts.email} telegramUrl={data.contacts.telegram_url} maxUrl={data.contacts.max_url} max={data.contacts.max} />
    </main>
  );
}

function Header({ contactUrl, ctaLabel }: { contactUrl: string; ctaLabel: string }) {
  return (
    <header className="site-header">
      <div className="container header-inner">
        <a className="brand" href="/" aria-label="TenderLex">
          <Image src="/tenderlex-logo.png" alt="" width={32} height={32} priority />
          <span>TenderLex</span>
        </a>
        <nav aria-label="Основная навигация">
          <a href="#features">Возможности</a>
          <a href="#process">Процесс</a>
          <a href="#scenarios">Сценарии</a>
          <a href="#tariffs">Тарифы</a>
          <a href="#contacts">Контакты</a>
        </nav>
        <Button asChild className="header-cta">
          <a href={contactUrl} target={contactUrl.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
            {ctaLabel}
          </a>
        </Button>
      </div>
    </header>
  );
}

function HeroProduct() {
  return (
    <div className="hero-product" aria-label="Два режима работы TenderLex">
      <div className="task-strip">
        <div>
          <Image src="/tenderlex-logo.png" alt="" width={32} height={32} />
          <div>
            <strong>TenderLex</strong>
            <span>Сайт и Telegram</span>
          </div>
        </div>
        <span>
          <Paperclip size={15} aria-hidden="true" />
          номер закупки, документы, ссылка или спецификация
        </span>
      </div>

      <div className="hero-output-grid">
        <article className="output-card">
          <div className="output-head">
            <span className="icon-box">
              <Search size={20} aria-hidden="true" />
            </span>
            <div>
              <p>Поиск поставщиков</p>
              <h2>Компании под спецификацию</h2>
            </div>
          </div>
          <div className="output-badges">
            <span>производители</span>
            <span>дилеры</span>
            <span>комплектующие</span>
          </div>
          <div className="supplier-scale">
            TenderLex ищет компании, связанные с нужной номенклатурой, и выводит основу для первого запроса.
          </div>
          <div className="supplier-mini-list">
            {heroSupplierRows.map(([type, contact, note]) => (
              <div key={type} className="supplier-mini-row">
                <div className="supplier-mini-meta">
                  <strong>{type}</strong>
                  <small>{contact}</small>
                </div>
                <p>{note}</p>
              </div>
            ))}
          </div>
          <div className="output-footer">
            <MessageCircle size={15} aria-hidden="true" />
            Готово к письму поставщику и сравнению условий
          </div>
        </article>

        <article className="output-card">
          <div className="output-head">
            <span className="icon-box">
              <FileText size={20} aria-hidden="true" />
            </span>
            <div>
              <p>Анализ закупки</p>
              <h2>Поставка минераловатного утеплителя</h2>
            </div>
          </div>
          <div className="output-badges">
            <span>стройматериалы</span>
            <span>гарантия</span>
            <span>доставка</span>
          </div>
          <div className="risk-note compact">
            <ShieldCheck size={17} aria-hidden="true" />
            <p>До подачи заявки видно, где нужны уточнения: плотность, толщина, сертификаты, упаковка и доставка до объекта.</p>
          </div>
          <table className="output-table">
            <tbody>
              {reportRows.map(([section, value]) => (
                <tr key={section}>
                  <td>{section}</td>
                  <td>{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="output-footer">
            <CheckCircle2 size={15} aria-hidden="true" />
            Вердикт: участвовать после уточнений
          </div>
        </article>
      </div>
    </div>
  );
}

function SupplierSheet() {
  return (
    <div className="supplier-sheet" aria-label="Пример результата поиска поставщиков">
      <div className="sheet-bar">
        <span>Пример подбора поставщиков</span>
        <strong>по цементу и сухим смесям</strong>
      </div>
      <table>
        <thead>
          <tr>
            <th>Компания</th>
            <th>Профиль</th>
            <th>Контакты</th>
            <th>Что проверить в предложении</th>
          </tr>
        </thead>
        <tbody>
          {supplierRows.map(([company, specialization, contact, note]) => (
            <tr key={company}>
              <td data-label="Компания">{company}</td>
              <td data-label="Профиль">{specialization}</td>
              <td data-label="Контакты">{contact}</td>
              <td data-label="Что проверить в предложении">{note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="sheet-footer">
        <span>
          <Phone size={16} aria-hidden="true" />
          Основа для запроса: цена, марка, фасовка, документы качества, доставка
        </span>
        <CheckCircle2 size={18} aria-hidden="true" />
      </div>
    </div>
  );
}

function PricingTable({
  icon: Icon,
  title,
  subtitle,
  tariffs,
  contactUrl,
  contactLabel,
  note,
}: {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  tariffs: PublicTariff[];
  contactUrl: string;
  contactLabel: string;
  note?: string;
}) {
  return (
    <article className="pricing-table">
      <div className="pricing-title">
        <span className="icon-box accent">
          <Icon size={20} aria-hidden="true" />
        </span>
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
      </div>
      <div className="tariff-rows">
        {tariffs.map((tariff) => (
          <div key={tariff.id} className="tariff-row">
            <div>
              <strong>{tariffDisplayName(tariff)}</strong>
              <span>{tariffDescription(tariff)}</span>
            </div>
            <b>{formatRubles(tariff.price_kopeks)}</b>
          </div>
        ))}
      </div>
      {note ? <p className="pricing-note">{note}</p> : null}
      <Button asChild variant="secondary">
        <a href={contactUrl} target={contactUrl.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
          {contactLabel}
          <ArrowRight size={17} aria-hidden="true" />
        </a>
      </Button>
    </article>
  );
}

function SectionHeader({ title, text, align = "center" }: { title: string; text: string; align?: "center" | "left" }) {
  return (
    <div className={`section-header ${align === "left" ? "align-left" : ""}`}>
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}

function ProofItem({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <dt>{value}</dt>
      <dd>{label}</dd>
    </div>
  );
}

function ResultPoint({ title, text }: { title: string; text: string }) {
  return (
    <li>
      <CheckCircle2 size={19} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <span>{text}</span>
      </div>
    </li>
  );
}

function ContactLink({ href, icon: Icon, label, staticLabel }: { href: string; icon: LucideIcon; label: string; staticLabel?: string }) {
  const fallbackLabel = staticLabel || label;
  if (!fallbackLabel) {
    return null;
  }
  if (!href) {
    return (
      <span className="contact-link contact-link-static">
        <Icon size={17} aria-hidden="true" />
        {fallbackLabel}
      </span>
    );
  }
  return (
    <a className="contact-link" href={href} target={href.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
      <Icon size={17} aria-hidden="true" />
      {label}
    </a>
  );
}

function Footer({ email, telegramUrl, maxUrl, max }: { email: string; telegramUrl: string; maxUrl: string; max: string }) {
  return (
    <footer className="site-footer">
      <div className="container footer-inner">
        <div>
          <a className="brand" href="/" aria-label="TenderLex">
            <Image src="/tenderlex-logo.png" alt="" width={30} height={30} />
            <span>TenderLex</span>
          </a>
          <p>Сервис для поиска компаний под закупочную задачу: контакты, вопросы поставщику и разбор условий.</p>
        </div>
        <nav className="footer-nav" aria-label="Навигация в подвале">
          <div className="footer-group">
            <strong>Сервис</strong>
            <a href="#features">Возможности</a>
            <a href="#process">Процесс</a>
            <a href="#scenarios">Сценарии</a>
            <a href="#tariffs">Тарифы</a>
          </div>
          <div className="footer-group">
            <strong>Страницы</strong>
            <a href="/poisk-postavshchikov-po-tz">Поставщики под спецификацию</a>
            <a href="/poisk-postavshchikov-dlya-tendera">Поставщики для тендера</a>
            <a href="/poisk-proizvoditeley-po-tz">Выйти на производителя</a>
            <a href="/postavshchiki-dlya-zaprosa-kp">Кого запросить</a>
            <a href="/zapros-kp-po-tz">Подготовить письмо</a>
            <a href="/analiz-zakupochnoi-dokumentacii">Разобрать закупку</a>
            <a href="/reestr-minpromtorga-v-zakupkah">Проверить допуск</a>
            <a href="/terms">Условия</a>
            <a href="/privacy">Конфиденциальность</a>
          </div>
        </nav>
        <div className="footer-contacts footer-group">
          <strong>Связь</strong>
          {telegramUrl ? <a href={telegramUrl} target="_blank" rel="noreferrer">Telegram</a> : null}
          {max ? (maxUrl ? <a href={maxUrl} target="_blank" rel="noreferrer">MAX</a> : <span>{max}</span>) : null}
          <a href={`mailto:${email}`}>{email}</a>
        </div>
      </div>
    </footer>
  );
}

function tariffCountLabel(tariff: PublicTariff) {
  const variants: [string, string, string] =
    tariff.kind === "procurement_report"
      ? ["отчёт", "отчёта", "отчётов"]
      : ["запрос", "запроса", "запросов"];
  return `${tariff.units} ${pluralizeRu(tariff.units, variants)}`;
}

function pluralizeRu(value: number, [one, few, many]: [string, string, string]) {
  const mod10 = Math.abs(value) % 10;
  const mod100 = Math.abs(value) % 100;
  if (mod10 === 1 && mod100 !== 11) {
    return one;
  }
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return few;
  }
  return many;
}

function tariffDescription(tariff: PublicTariff) {
  if (tariff.kind === "procurement_report") {
    return "Требования, условия участия, риски договора и вопросы заказчику.";
  }
  if (tariff.kind === "supplier_search") {
    return "Подбор релевантных компаний и контактов для первого запроса.";
  }
  return tariff.description.trim() || tariffCountLabel(tariff);
}

function tariffDisplayName(tariff: PublicTariff) {
  if (tariff.kind === "procurement_report") {
    return tariff.units === 1 ? "1 анализ закупки" : `${tariff.units} анализов закупок`;
  }
  if (tariff.kind === "supplier_search") {
    return tariff.units === 1 ? "1 подбор поставщиков" : `${tariff.units} подборов поставщиков`;
  }
  return tariff.name;
}

function buildJsonLd(siteUrl: string, botUrl: string, contactTelegramUrl: string, email: string) {
  const normalizedSiteUrl = siteUrl.replace(/\/+$/, "");
  const sameAs = [botUrl, contactTelegramUrl].filter(Boolean);

  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": `${normalizedSiteUrl}/#organization`,
        name: "TenderLex",
        url: normalizedSiteUrl,
        logo: {
          "@type": "ImageObject",
          url: `${normalizedSiteUrl}/tenderlex-logo.png`,
          width: 512,
          height: 512,
        },
        image: `${normalizedSiteUrl}/tenderlex-product-preview.png`,
        email,
        sameAs,
        contactPoint: email
          ? [
              {
                "@type": "ContactPoint",
                email,
                contactType: "customer support",
                availableLanguage: ["ru"],
              },
            ]
          : undefined,
      },
      {
        "@type": "WebSite",
        "@id": `${normalizedSiteUrl}/#website`,
        name: "TenderLex",
        url: normalizedSiteUrl,
        inLanguage: "ru-RU",
        description:
          "TenderLex помогает найти компании под закупочную задачу, собрать контакты, подготовить вопросы поставщику и разобрать условия закупки.",
        publisher: {
          "@id": `${normalizedSiteUrl}/#organization`,
        },
      },
      {
        "@type": "SoftwareApplication",
        "@id": `${normalizedSiteUrl}/#software`,
        name: "TenderLex",
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web, Telegram",
        url: normalizedSiteUrl,
        image: `${normalizedSiteUrl}/tenderlex-product-preview.png`,
        description:
          "Сервис для поиска поставщиков под спецификацию, проверки контактов, подготовки запроса цены и разбора закупочной документации.",
        featureList: [
          "Поиск поставщиков под спецификацию",
          "Подготовка запроса цены",
          "Проверка контактов и профиля поставщика",
          "Разбор закупочной документации",
          "Проверка рисков до подачи заявки",
          "Проверка специальных требований допуска",
        ],
        offers: {
          "@type": "AggregateOffer",
          priceCurrency: "RUB",
          lowPrice: "100",
          highPrice: "5000",
          availability: "https://schema.org/InStock",
        },
        provider: {
          "@id": `${normalizedSiteUrl}/#organization`,
        },
      },
    ],
  };
}
