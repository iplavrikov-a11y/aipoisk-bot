import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Download,
  FileArchive,
  FileSearch,
  FileText,
  Mail,
  MailCheck,
  MessageCircle,
  Paperclip,
  Phone,
  Search,
  Send,
  ShieldCheck,
  Table2,
  Target,
  type LucideIcon,
} from "lucide-react";
import Image from "next/image";

import { Button } from "@/components/ui/button";
import { formatRubles, getSiteData, type PublicSitePayload, type PublicTariff } from "@/lib/site-data";

export const dynamic = "force-dynamic";

type PublicTrial = PublicSitePayload["trial"];

const featureItems = [
  {
    icon: FileArchive,
    title: "Анализ документации",
    text: "Принимает номер извещения, архив закупки, отдельные файлы, проект договора и ссылку на ЕИС, ЭТП или сайт заказчика.",
  },
  {
    icon: Table2,
    title: "Тендерный лист и риски",
    text: "Собирает НМЦК, сроки, обеспечение, нацрежим, оплату, НДС, адрес поставки, требования и подводные камни.",
  },
  {
    icon: Search,
    title: "Поиск поставщиков",
    text: "Ищет компании по ТЗ, ООЗ, описанию товара или закупочной задаче: точные товары, аналоги и профильных производителей.",
  },
  {
    icon: MailCheck,
    title: "Контакты для запроса КП",
    text: "На выходе не просто названия компаний: в XLSX попадают email, телефоны, сайт, страница контактов и комментарий по релевантности. Объём поиска задаётся под задачу.",
  },
];

const processSteps = [
  {
    title: "Выберите задачу",
    text: "Запустите анализ документации, поиск поставщиков или оба сценария сразу, если нужно решение по участию и запрос КП.",
  },
  {
    title: "Передайте входные данные",
    text: "Для анализа отправьте номер извещения, архив, файлы или ссылку на закупку. Для поставщиков достаточно ТЗ, ООЗ или описания товара.",
  },
  {
    title: "Получите рабочие файлы",
    text: "На выходе DOCX с тендерным листом и рисками, XLSX с поставщиками, email, телефонами и комментариями. Для широкого поиска можно собрать большой пул контактов.",
  },
];

const useCases = [
  {
    icon: Target,
    title: "Поставщикам и тендерным отделам",
    points: [
      "быстро понять, стоит ли заходить в закупку",
      "увидеть сроки, обеспечение, НДС, нацрежим и риски договора",
      "подготовить вопросы, логистику и запросы поставщикам",
    ],
  },
  {
    icon: Building2,
    title: "Закупщикам и снабжению",
    points: [
      "найти поставщиков по техническому заданию или описанию товара",
      "получить email, телефоны и страницы контактов для запроса КП",
      "сравнить точные товары, аналоги и комментарии по релевантности",
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
    title: "Файлы не становятся витриной",
    text: "Материалы закупки не публикуются на сайте. Сайт показывает возможности сервиса, а работа идет внутри Telegram.",
  },
  {
    icon: CheckCircle2,
    title: "Решение остается за командой",
    text: "Бот ускоряет анализ и подготовку данных, но финальную юридическую, ценовую и коммерческую проверку делает человек.",
  },
];

const reportRows = [
  ["Карточка закупки", "заказчик, ИНН/КПП, НМЦК, 44-ФЗ/223-ФЗ, площадка, сроки"],
  ["ТЗ и спецификация", "позиции, характеристики, единицы, количество, критичные требования"],
  ["Условия и риски", "обеспечение, НДС, нацрежим, логистика, договор, вопросы заказчику"],
];

const contactRows = [
  ["Мстерский завод", "info@kzmstera.ru", "+7 492 432-11-04", "точный товар, есть отдел продаж"],
  ["Норский завод", "norsk35@zaonkz.ru", "страница контактов", "профильный производитель"],
  ["ТД «Клавка Групп»", "sales@klavka.ru", "+7 812 600-42-42", "аналог, уточнить параметры"],
];

export default async function Home() {
  const data = await getSiteData();
  const contactUrl = data.contacts.telegram_url || (data.contacts.email ? `mailto:${data.contacts.email}` : "#contacts");
  const botUrl = data.bot?.telegram_url || "https://t.me/tenderlex_bot";
  const supplierTariffs = data.tariff_groups.supplier_search;
  const reportTariffs = data.tariff_groups.procurement_report;
  const trial = data.trial || { enabled: false, supplier_search_limit: 0, procurement_report_limit: 0, file_limit: 0 };
  const trialAvailable = isTrialAvailable(trial);
  const primaryCta = trialAvailable ? "Попробовать бесплатно" : "Открыть в Telegram";

  return (
    <main>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(buildJsonLd(data.site.domain, botUrl, data.contacts.telegram_url, data.contacts.email)),
        }}
      />
      <Header contactUrl={botUrl} ctaLabel={trialAvailable ? "Попробовать бесплатно" : "Проверить закупку"} />

      <section className="hero">
        <div className="container hero-layout">
          <div className="hero-copy">
            <h1>Анализ закупок и поиск поставщиков в одном Telegram-боте</h1>
            <p>
              TenderLex в Telegram закрывает два самостоятельных сценария: серьёзный анализ закупочной
              документации и масштабируемый поиск поставщиков с email, телефонами, сайтами и комментариями для запроса КП.
            </p>
            <div className="hero-actions">
              <Button asChild size="lg">
                <a href={botUrl} target={botUrl.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
                  <Send size={18} aria-hidden="true" />
                  {primaryCta}
                </a>
              </Button>
              <Button asChild variant="secondary" size="lg">
                <a href="#tariffs">Сравнить тарифы</a>
              </Button>
            </div>
            {trialAvailable ? <TrialCallout trial={trial} contactUrl={botUrl} /> : null}
            <dl className="hero-proof" aria-label="Коротко о сервисе">
              <ProofItem value="Анализ документации" label="тендерный лист DOCX и риски" />
              <ProofItem value="Номер извещения" label="карточка и документы закупки" />
              <ProofItem value="Поиск поставщиков" label="XLSX с контактами для КП" />
              <ProofItem value="Десятки / сотни" label="контактов, если нужен большой пул" />
              {trialAvailable ? <ProofItem value={trialProofValue(trial)} label="пробный доступ без оплаты" /> : null}
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
            title="Как работает бот"
            text="Сценарии можно использовать отдельно или вместе: разобрать закупку, найти поставщиков или собрать большой список контактов для запроса КП."
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
              title="Два самостоятельных результата"
              text="Одним нужен тендерный лист по документации, другим — поставщики с контактами. TenderLex не смешивает ценность: оба результата можно использовать отдельно."
              align="left"
            />
            <ul className="result-list">
              <ResultPoint title="Тендерный лист" text="Структура закупки, ключевые условия, сроки, обеспечение, НДС, нацрежим, логистика, договор и риски." />
              <ResultPoint title="Решение об участии" text="Понятно, что закупают, какие обязательства придется принять и где есть риск потери денег или времени." />
              <ResultPoint title="Поиск поставщиков" text="Компании под ТЗ или описание товара: точные позиции, аналоги, производители и профильные поставщики." />
              <ResultPoint title="Контакты для КП" text="Email, телефоны, сайты, страницы контактов и комментарии по релевантности, чтобы сразу отправлять запрос." />
            </ul>
          </div>
          <SupplierSheet />
        </div>
      </section>

      <section id="tariffs" className="section pricing-section">
        <div className="container">
          <SectionHeader
            title="Стоимость услуг"
            text="Тарифы разделены по двум равным направлениям: отдельно поиск контактов поставщиков и отдельно анализ закупочной документации."
          />
          {trialAvailable ? <TrialBand trial={trial} contactUrl={botUrl} /> : null}
          <div className="pricing-grid">
            <PricingTable
              icon={Search}
              title="Поиск контактов поставщиков"
              subtitle="Email, телефоны, сайты, страницы контактов и комментарии"
              tariffs={supplierTariffs}
              contactUrl={contactUrl}
            />
            <PricingTable
              icon={FileText}
              title="Анализ документации"
              subtitle="Тендерный лист по номеру извещения, комплекту файлов, архиву или ссылке"
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
          <h2>{trialAvailable ? "Попробуйте TenderLex в Telegram" : "Выберите задачу в Telegram"}</h2>
          <p>
            {trialAvailable
              ? trialCtaText(trial)
              : "Передайте номер извещения или документы для анализа, либо ТЗ для поиска поставщиков. Бот вернёт рабочий результат в файлах."}
          </p>
          <div className="cta-actions">
            <Button asChild size="lg">
              <a href={botUrl} target={botUrl.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
                <Send size={18} aria-hidden="true" />
                {trialAvailable ? "Попробовать бесплатно" : "Открыть TenderLex"}
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
            <span>Два режима в Telegram</span>
          </div>
        </div>
        <span>
          <Paperclip size={15} aria-hidden="true" />
          номер, архив, ссылка или ТЗ
        </span>
      </div>

      <div className="hero-output-grid">
        <article className="output-card">
          <div className="output-head">
            <span className="icon-box">
              <FileText size={20} aria-hidden="true" />
            </span>
            <div>
              <p>Анализ документации</p>
              <h2>Тендерный лист DOCX</h2>
            </div>
          </div>
          <div className="output-badges">
            <span>условия</span>
            <span>риски</span>
            <span>позиции</span>
          </div>
          <div className="risk-note compact">
            <ShieldCheck size={17} aria-hidden="true" />
            <p>Показывает спорные условия, требования, логистику и вопросы заказчику до участия.</p>
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
            <Download size={15} aria-hidden="true" />
            Готовый DOCX для команды
          </div>
        </article>

        <article className="output-card">
          <div className="output-head">
            <span className="icon-box">
              <Search size={20} aria-hidden="true" />
            </span>
            <div>
              <p>Поиск поставщиков</p>
              <h2>Контакты XLSX</h2>
            </div>
          </div>
          <div className="output-badges">
            <span>email</span>
            <span>телефоны</span>
            <span>много строк</span>
          </div>
          <div className="supplier-scale">
            Количество поставщиков задаётся под задачу: можно собрать расширенный список для массового запроса КП.
          </div>
          <div className="supplier-mini-list">
            {contactRows.map(([company, email, phone, note]) => (
              <div key={company} className="supplier-mini-row">
                <strong>{company}</strong>
                <span>
                  <Mail size={13} aria-hidden="true" />
                  {email}
                </span>
                <span>
                  <Phone size={13} aria-hidden="true" />
                  {phone}
                </span>
                <p>{note}</p>
              </div>
            ))}
          </div>
          <div className="output-footer">
            <Table2 size={15} aria-hidden="true" />
            XLSX может содержать десятки и сотни контактов
          </div>
        </article>
      </div>
    </div>
  );
}

function SupplierSheet() {
  return (
    <div className="supplier-sheet" aria-label="Пример таблицы поставщиков">
      <div className="sheet-bar">
        <span>Фрагмент XLSX поставщиков</span>
        <strong>email + телефоны</strong>
      </div>
      <table>
        <thead>
          <tr>
            <th>Поставщик</th>
            <th>Email</th>
            <th>Телефон / контакты</th>
            <th>Комментарий</th>
          </tr>
        </thead>
        <tbody>
          {contactRows.map(([company, email, phone, note]) => (
            <tr key={company}>
              <td data-label="Поставщик">{company}</td>
              <td data-label="Email">{email}</td>
              <td data-label="Телефон / контакты">{phone}</td>
              <td data-label="Комментарий">{note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="sheet-footer">
        <span>
          <Phone size={16} aria-hidden="true" />
          Email и телефоны готовы: можно отправлять запрос КП
        </span>
        <CheckCircle2 size={18} aria-hidden="true" />
      </div>
    </div>
  );
}

function TrialCallout({ trial, contactUrl }: { trial: PublicTrial; contactUrl: string }) {
  return (
    <div className="trial-callout">
      <div>
        <strong>Пробный доступ включен</strong>
        <span>{trialShortText(trial)}</span>
      </div>
      <a href={contactUrl} target={contactUrl.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
        Попробовать
        <ArrowRight size={15} aria-hidden="true" />
      </a>
    </div>
  );
}

function TrialBand({ trial, contactUrl }: { trial: PublicTrial; contactUrl: string }) {
  return (
    <section className="trial-band" aria-label="Попробовать TenderLex бесплатно">
      <div>
        <span className="trial-eyebrow">Перед оплатой</span>
        <h3>Проверьте оба сценария бесплатно</h3>
        <p>{trialLongText(trial)}</p>
      </div>
      <div className="trial-counters" aria-label="Что входит в пробный доступ">
        <div>
          <strong>{trial.procurement_report_limit}</strong>
          <span>{pluralizeRu(trial.procurement_report_limit, ["анализ документации", "анализа документации", "анализов документации"])}</span>
        </div>
        <div>
          <strong>{trial.supplier_search_limit}</strong>
          <span>{pluralizeRu(trial.supplier_search_limit, ["поиск поставщиков", "поиска поставщиков", "поисков поставщиков"])}</span>
        </div>
        {trial.file_limit > 0 ? (
          <div>
            <strong>{trial.file_limit}</strong>
            <span>{pluralizeRu(trial.file_limit, ["файл", "файла", "файлов"])} в пробном доступе</span>
          </div>
        ) : null}
      </div>
      <Button asChild size="lg">
        <a href={contactUrl} target={contactUrl.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
          <Send size={18} aria-hidden="true" />
          Попробовать бесплатно
        </a>
      </Button>
    </section>
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
              <strong>{tariff.name}</strong>
              <span>{tariff.description || tariffCountLabel(tariff)}</span>
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
          <p>Telegram-бот для анализа закупок по номеру извещения или файлам, поиска поставщиков и пробного запуска перед оплатой.</p>
        </div>
        <nav aria-label="Навигация в подвале">
          <a href="#features">Возможности</a>
          <a href="#process">Процесс</a>
          <a href="#tariffs">Тарифы</a>
          <a href="#contacts">Контакты</a>
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

function isTrialAvailable(trial: PublicTrial) {
  return Boolean(trial.enabled && (trial.supplier_search_limit > 0 || trial.procurement_report_limit > 0));
}

function trialProofValue(trial: PublicTrial) {
  const parts = [];
  if (trial.procurement_report_limit > 0) {
    parts.push(`${trial.procurement_report_limit} ${pluralizeRu(trial.procurement_report_limit, ["анализ", "анализа", "анализов"])}`);
  }
  if (trial.supplier_search_limit > 0) {
    parts.push(`${trial.supplier_search_limit} ${pluralizeRu(trial.supplier_search_limit, ["поиск", "поиска", "поисков"])}`);
  }
  return parts.join(" + ") || "Пробный доступ";
}

function trialShortText(trial: PublicTrial) {
  const parts = [];
  if (trial.procurement_report_limit > 0) {
    parts.push(`${trial.procurement_report_limit} ${pluralizeRu(trial.procurement_report_limit, ["анализ", "анализа", "анализов"])} документации`);
  }
  if (trial.supplier_search_limit > 0) {
    parts.push(`${trial.supplier_search_limit} ${pluralizeRu(trial.supplier_search_limit, ["поиск", "поиска", "поисков"])} поставщиков`);
  }
  return `${parts.join(" и ")} без оплаты, чтобы оценить результат в боте.`;
}

function trialLongText(trial: PublicTrial) {
  const filePart = trial.file_limit > 0 ? ` Для пробного анализа можно загрузить до ${trial.file_limit} ${pluralizeRu(trial.file_limit, ["файла", "файлов", "файлов"])}.` : "";
  return `${trialShortText(trial)} Сначала проверьте качество тендерного листа и контактов, потом выбирайте платный пакет под поток задач.${filePart}`;
}

function trialCtaText(trial: PublicTrial) {
  return `${trialShortText(trial)} Передайте номер извещения или документы для анализа, либо ТЗ для поиска поставщиков, бот вернёт рабочий результат в файлах.`;
}

function buildJsonLd(siteUrl: string, botUrl: string, contactTelegramUrl: string, email: string) {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "TenderLex",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Telegram",
    url: siteUrl,
    description:
      "Telegram-бот для анализа закупок по номеру извещения или документации, поиска поставщиков с контактами и бесплатного пробного запуска.",
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
