import {
  ArrowRight,
  Building2,
  CheckCircle2,
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
    icon: FileText,
    title: "Анализ закупочной документации",
    text: "Структурирует предмет закупки, требования к участнику, сроки, обеспечение, оплату, поставку и условия договора.",
  },
  {
    icon: ShieldCheck,
    title: "Риски до подачи заявки",
    text: "Выносит спорные требования, штрафы, приемку, нереалистичные сроки и вопросы, которые лучше уточнить заранее.",
  },
  {
    icon: Search,
    title: "Подбор поставщиков под ТЗ",
    text: "Ищет производителей, официальных дистрибьюторов, региональных дилеров и профильных поставщиков по предмету закупки.",
  },
  {
    icon: MessageCircle,
    title: "Подготовка к запросу КП",
    text: "Показывает, к кому обратиться, что запросить и какие параметры проверить перед сравнением предложений.",
  },
];

const processSteps = [
  {
    title: "Выберите задачу",
    text: "Проверьте закупку перед участием, подберите поставщиков под ТЗ или используйте оба сценария вместе.",
  },
  {
    title: "Передайте материалы",
    text: "Для анализа подойдет номер извещения, ссылка или комплект документов. Для поиска поставщиков — ТЗ или описание позиции.",
  },
  {
    title: "Работайте с результатом",
    text: "Получите структурированный разбор, перечень рисков, вопросы заказчику и список поставщиков для запроса КП.",
  },
];

const useCases = [
  {
    icon: Target,
    title: "Поставщикам и тендерным отделам",
    points: [
      "быстро понять, стоит ли заходить в закупку",
      "увидеть требования, сроки, обеспечение, оплату и риски договора",
      "подготовить вопросы заказчику и аргументы для решения об участии",
    ],
  },
  {
    icon: Building2,
    title: "Закупщикам и снабжению",
    points: [
      "найти поставщиков по техническому заданию или описанию товара",
      "собрать производителей, дилеров и профильных поставщиков",
      "понять, какие параметры уточнять в запросе коммерческого предложения",
    ],
  },
];

const trustItems = [
  {
    icon: ShieldCheck,
    title: "Работа по документам и открытым источникам",
    text: "Анализ строится по номеру извещения, официальным данным закупки и присланным документам, а поставщики и контакты проверяются по открытым сайтам.",
  },
  {
    icon: FileSearch,
    title: "Ваши материалы не показываются другим",
    text: "Номер закупки, документы и описание задачи используются для подготовки результата в вашем кабинете или Telegram.",
  },
  {
    icon: CheckCircle2,
    title: "Решение остается за командой",
    text: "TenderLex ускоряет анализ и подготовку данных, но финальную юридическую, ценовую и коммерческую проверку делает человек.",
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
            <h1>Анализ закупок и подбор поставщиков для запроса КП</h1>
            <p>
              TenderLex помогает тендерным отделам и снабжению быстро разобрать документацию,
              увидеть критичные условия и найти релевантных поставщиков под техническое задание.
              Работать можно на сайте или в Telegram.
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
              <ProofItem value="Документация" label="требования, сроки, обеспечение, договор" />
              <ProofItem value="Риски" label="спорные условия и вопросы заказчику" />
              <ProofItem value="Поставщики" label="производители, дилеры и аналоги под ТЗ" />
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
            text="Сценарии можно использовать отдельно или вместе: оценить закупку перед участием, найти поставщиков и подготовить запрос КП."
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
            title="Для тендеров и закупок"
            text="Один и тот же механизм полезен и тем, кто участвует в закупках, и тем, кто внутри компании ищет товар или поставщика по техническому заданию."
          />
          <div className="usecase-grid">
            {useCases.map((item) => (
              <article key={item.title} className="usecase-card">
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

      <section className="section result-section">
        <div className="container result-layout">
          <div>
            <SectionHeader
              title="Что получает команда"
              text="Не просто пересказ документов, а рабочая структура для решения: участвовать, уточнять условия, считать экономику или запрашивать цены."
              align="left"
            />
            <ul className="result-list">
              <ResultPoint title="Карта закупки" text="Предмет, процедура, сроки, обеспечение, оплата, поставка, требования к участнику и ключевые документы." />
              <ResultPoint title="Риски и уточнения" text="Спорные условия договора, приемка, штрафы, требования к эквивалентам и вопросы заказчику до подачи заявки." />
              <ResultPoint title="Подбор поставщиков" text="Компании под ТЗ: производители, официальные дистрибьюторы, региональные дилеры, поставщики аналогов и профильные продавцы." />
              <ResultPoint title="Основа для КП" text="Кого запросить, какие характеристики проверить и какие условия сравнить после получения предложений." />
            </ul>
          </div>
          <SupplierSheet />
        </div>
      </section>

      <section id="tariffs" className="section pricing-section">
        <div className="container">
          <SectionHeader
            title="Стоимость услуг"
            text="Направления разделены по задаче: отдельно анализ закупки, отдельно подбор поставщиков. Для полного цикла можно использовать оба."
          />
          <div className="pricing-grid">
            <PricingTable
              icon={Search}
              title="Подбор поставщиков"
              subtitle="Компании, контакты и комментарии для запроса КП"
              tariffs={supplierTariffs}
              contactUrl={contactUrl}
            />
            <PricingTable
              icon={FileText}
              title="Анализ закупки"
              subtitle="Требования, условия, риски и вопросы заказчику"
              tariffs={reportTariffs}
              contactUrl={contactUrl}
            />
          </div>
        </div>
      </section>

      <section id="trust" className="section trust-section">
        <div className="container trust-layout">
          <div>
            <h2>Ускоряет работу, но не подменяет ответственность</h2>
            <p>
              TenderLex нужен, чтобы быстрее разобрать закупочную документацию или найти поставщиков
              с рабочими контактами. Итоговое решение по участию, цене, юридическим обязательствам и выбору
              поставщика остается за вашей командой.
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
          <h2>Попробуйте TenderLex на сайте или в Telegram</h2>
          <p>Передайте номер извещения, документы или ТЗ. TenderLex подготовит разбор закупки или список поставщиков для запроса КП.</p>
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
              <ContactLink href={data.contacts.telegram_url} icon={MessageCircle} label={data.contacts.telegram} />
              <ContactLink href={data.contacts.email ? `mailto:${data.contacts.email}` : ""} icon={Mail} label={data.contacts.email} />
            </div>
          </div>
        </div>
      </section>

      <Footer email={data.contacts.email} telegramUrl={data.contacts.telegram_url} telegram={data.contacts.telegram} />
    </main>
  );
}

function Header({ contactUrl, ctaLabel }: { contactUrl: string; ctaLabel: string }) {
  return (
    <header className="site-header">
      <div className="container header-inner">
        <a className="brand" href="#" aria-label="TenderLex">
          <Image src="/tenderlex-logo.png" alt="" width={32} height={32} priority />
          <span>TenderLex</span>
        </a>
        <nav aria-label="Основная навигация">
          <a href="#features">Возможности</a>
          <a href="#process">Процесс</a>
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
          номер закупки, документы, ссылка или ТЗ
        </span>
      </div>

      <div className="hero-output-grid">
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

        <article className="output-card">
          <div className="output-head">
            <span className="icon-box">
              <Search size={20} aria-hidden="true" />
            </span>
            <div>
              <p>Подбор поставщиков</p>
              <h2>Поставщики по ТЗ</h2>
            </div>
          </div>
          <div className="output-badges">
            <span>производители</span>
            <span>дилеры</span>
            <span>комплектующие</span>
          </div>
          <div className="supplier-scale">
            TenderLex ищет компании, связанные с нужной номенклатурой, и выводит рабочую основу для запроса КП.
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
            Готово к запросу КП и сравнению условий
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
        <strong>по ТЗ на цемент и сухие смеси</strong>
      </div>
      <table>
        <thead>
          <tr>
            <th>Компания</th>
            <th>Профиль</th>
            <th>Контакты</th>
            <th>Что проверить в КП</th>
          </tr>
        </thead>
        <tbody>
          {supplierRows.map(([company, specialization, contact, note]) => (
            <tr key={company}>
              <td data-label="Компания">{company}</td>
              <td data-label="Профиль">{specialization}</td>
              <td data-label="Контакты">{contact}</td>
              <td data-label="Что проверить в КП">{note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="sheet-footer">
        <span>
          <Phone size={16} aria-hidden="true" />
          Основа для запроса КП: цена, марка, фасовка, документы качества, доставка
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
}: {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  tariffs: PublicTariff[];
  contactUrl: string;
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
      <Button asChild variant="secondary">
        <a href={contactUrl} target={contactUrl.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
          Выбрать пакет
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

function ContactLink({ href, icon: Icon, label }: { href: string; icon: LucideIcon; label: string }) {
  if (!href || !label) {
    return null;
  }
  return (
    <a className="contact-link" href={href} target={href.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
      <Icon size={17} aria-hidden="true" />
      {label}
    </a>
  );
}

function Footer({ email, telegramUrl, telegram }: { email: string; telegramUrl: string; telegram: string }) {
  return (
    <footer className="site-footer">
      <div className="container footer-inner">
        <div>
          <a className="brand" href="#" aria-label="TenderLex">
            <Image src="/tenderlex-logo.png" alt="" width={30} height={30} />
            <span>TenderLex</span>
          </a>
          <p>Сервис для анализа закупок и поиска поставщиков на сайте и в Telegram.</p>
        </div>
        <nav aria-label="Навигация в подвале">
          <a href="#features">Возможности</a>
          <a href="#process">Процесс</a>
          <a href="#tariffs">Тарифы</a>
          <a href="#contacts">Контакты</a>
          <a href="/terms">Условия</a>
          <a href="/privacy">Конфиденциальность</a>
        </nav>
        <div className="footer-contacts">
          <a href={telegramUrl} target="_blank" rel="noreferrer">{telegram}</a>
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
    return "Подбор релевантных компаний и контактов для запроса КП.";
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
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "TenderLex",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web, Telegram",
    url: siteUrl,
    description:
      "Сервис для анализа закупочной документации, оценки рисков и подбора поставщиков для запроса КП.",
    offers: {
      "@type": "Offer",
      priceCurrency: "RUB",
      availability: "https://schema.org/InStock",
    },
    provider: {
      "@type": "Organization",
      name: "TenderLex",
      url: siteUrl,
      email,
      sameAs: [botUrl, contactTelegramUrl].filter(Boolean),
    },
  };
}
