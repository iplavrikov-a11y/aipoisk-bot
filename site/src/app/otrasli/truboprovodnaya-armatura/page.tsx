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
  title: "Поиск поставщиков трубопроводной арматуры по ТЗ",
  description:
    "Подбор заводов арматуры по ведомостям ТХ и спецификациям: задвижки, шаровые краны, дисковые затворы, фланцы, Ду 15–1200, Ру 16–250.",
  alternates: {
    canonical: "/otrasli/truboprovodnaya-armatura",
  },
};

const pagePath = "/otrasli/truboprovodnaya-armatura";

const faqItems: FaqItem[] = [
  { question: "Как сервис извлекает параметры трубопроводной арматуры?", answer: "TenderLex извлекает указанные Ду/DN, Ру/PN, присоединение, привод и материал корпуса. Проверьте распознавание и совместимость с рабочей средой; характеристики и применимые документы подтвердите у изготовителя." },
  { question: "Можно ли найти контакты арматурных заводов?", answer: "Сервис помогает искать кандидатов и доступные контакты из открытых источников. Изготовителя, полномочия продавца, комплектность и возможность поставки подтвердите у компании." },
];

const steps = [
  { name: "Загрузка ведомости трубопроводов", text: "Загрузите проект ТХ, спецификацию или таблицу запорной арматуры." },
  { name: "Парсинг Ду, Ру и сред", text: "Алгоритм выделяет типоразмеры, давления, классы герметичности и материалы." },
  { name: "Подбор заводов арматуры", text: "Перечень потенциальных поставщиков; применимость и действительность документов на конкретное изделие проверяют отдельно." },
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
      description="Разбор спецификаций по Ду/Ру, материалам и условиям эксплуатации; поиск потенциальных поставщиков арматуры. Паспорта и применимые документы на изделия проверяют отдельно."
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
