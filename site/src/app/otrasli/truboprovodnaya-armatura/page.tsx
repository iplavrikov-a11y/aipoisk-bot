import type { Metadata } from "next";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildHowToJsonLd,
  buildServiceJsonLd,
  type FaqItem,
} from "@/lib/seo";
import { IndustryPageLayout } from "@/components/industry-page-layout";

export const metadata: Metadata = {
  title: "Поиск поставщиков запорной и трубопроводной арматуры по ТЗ — TenderLex",
  description:
    "Подбор заводов арматуры по ведомостям ТХ и спецификациям: задвижки, шаровые краны, дисковые затворы, фланцы, Ду 15–1200, Ру 16–250.",
  alternates: {
    canonical: "/otrasli/truboprovodnaya-armatura",
  },
};

const pagePath = "/otrasli/truboprovodnaya-armatura";

const faqItems: FaqItem[] = [
  {
    question: "Как сервис извлекает параметры запорной арматуры?",
    answer:
      "TenderLex распознает условный проход (Ду/DN), рабочее давление (Ру/PN), тип присоединения (фланцевое, под приварку), тип привода (ручной, электропривод) и материал корпуса (сталь 20, 09Г2С, 12Х18Н10Т, чугун).",
  },
  {
    question: "Предоставляются ли контакты арматурных заводов?",
    answer:
      "Да, система предоставляет прямые контакты отделов сбыта российских заводов-изготовителей трубопроводной арматуры.",
  },
];

const steps = [
  { name: "Загрузка ведомости трубопроводов", text: "Загрузите проект ТХ, спецификацию или таблицу запорной арматуры." },
  { name: "Парсинг Ду, Ру и сред", text: "Алгоритм выделяет типоразмеры, давления, классы герметичности и материалы." },
  { name: "Подбор заводов арматуры", text: "Формирование перечня производителей с сертификатами ТР ТС 032/2013." },
  { name: "Формирование запроса КП", text: "Готовое обращение для запроса паспортов и расчета цен." },
];

const nomenclatures = [
  "Задвижки клиновые стальные и нержавеющие (30с41нж, 30лс41нж, 30нж41нж, Ду 50-1200)",
  "Краны шаровые фланцевые и под приварку (11с67п, полнопроходные, Ру 16-160)",
  "Дисковые поворотные затворы межфланцевые с электроприводом",
  "Клапаны обратные поворотные, подъемные, предохранительные (19с53нж, 17с28нж)",
  "Фланцы стальные плоские и воротниковые по ГОСТ 33259-2015",
  "Отводы крутоизогнутые, переходы, тройники, днища эллиптические (ГОСТ 17375-2001)",
];

export default function ArmaturaPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Отрасли", item: "https://tenderlex.ru/otrasli" },
    { name: "Запорная арматура", item: "https://tenderlex.ru" + pagePath },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков запорной и трубопроводной арматуры по ТЗ",
    description: "Сервис подбора заводов запорной арматуры по спецификациям.",
    path: pagePath,
  });

  const faqSchema = buildFaqJsonLd(faqItems);
  const howToSchema = buildHowToJsonLd({
    name: "Как подобрать завод запорной арматуры",
    description: "Инструкция по поиску изготовителей трубопроводной арматуры.",
    steps,
  });

  return (
    <IndustryPageLayout
      categoryTitle="Запорная и трубопроводная арматура"
      badge="Трубопроводы и запорная арматура"
      headline="Поиск поставщиков запорной и трубопроводной арматуры по ТЗ"
      description="Автоматический разбор спецификаций по Ду/Ру, маркам сталей и подбор арматурных заводов с сертификатами ТР ТС 032/2013."
      nomenclatures={nomenclatures}
      steps={steps}
      faqItems={faqItems}
      breadcrumbSchema={breadcrumbSchema}
      serviceSchema={serviceSchema}
      faqSchema={faqSchema}
      howToSchema={howToSchema}
    />
  );
}
