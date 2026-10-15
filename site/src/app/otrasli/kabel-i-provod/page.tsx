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
  title: "Поиск поставщиков кабеля и провода по ТЗ",
  description:
    "Автоматический подбор кабельных заводов и дистрибьюторов по кабельным журналам и спецификациям: ВВГнг, КГ, АВБбШв, трансформаторы и щиты.",
  alternates: {
    canonical: "/otrasli/kabel-i-provod",
  },
};

const pagePath = "/otrasli/kabel-i-provod";

const faqItems: FaqItem[] = [
  { question: "Как TenderLex разбирает кабельный журнал?", answer: "Сервис извлекает указанные в документе маркоразмеры, длины, напряжение и стандарты. Проверьте распознавание; соответствие кабеля ТЗ подтвердите по паспорту и документам изготовителя." },
  { question: "Можно ли найти кандидатов для поставки кабеля со склада?", answer: "TenderLex помогает искать изготовителей и торговые компании. Актуальные остатки, адрес склада, срок отгрузки и полномочия дистрибьютора подтвердите у компании; результат поиска их не гарантирует." },
];

const steps = [
  { name: "Загрузка кабельного журнала", text: "Загрузите проект ЭОМ/ЭМ или ведомость кабельной продукции." },
  { name: "Парсинг маркоразмеров", text: "ИИ определяет жильность, сечение, тип изоляции и ГОСТы." },
  { name: "Отбор кабельных заводов", text: "Поиск потенциальных изготовителей и продавцов; актуальные остатки и адрес отгрузки уточняют у компании." },
  { name: "Единый запрос КП", text: "Подготовка черновика запроса цен; проверьте текст и адрес получателя перед отправкой." },
];

const nomenclatures = [
  "Силовые кабели с медной и алюминиевой жилой (ВВГнг-LS, ВВГнг-FRLS, АВБбШв)",
  "Кабели гибкие для нестационарной прокладки (КГ-ХЛ, КГН)",
  "Контрольные и сигнальные кабели (КВВГнг, КВВГЭнг)",
  "Кабели связи и оптические кабели (ОКГ, ДПО, витая пара UTP/FTP)",
  "Кабеленесущие системы: лотки перфорированные, лестничные, короба",
  "Трансформаторные подстанции (КТП) и низковольтные комплектные устройства (НКУ)",
];

export default function KabelPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Отрасли", item: "https://tenderlex.ru/otrasli" },
    { name: "Кабель и электротехника", item: "https://tenderlex.ru" + pagePath },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков кабеля и электротехники по ТЗ",
    description: "Сервис подбора кабельных заводов и дистрибьюторов по спецификациям.",
    path: pagePath,
  });

  const faqSchema = buildFaqJsonLd(faqItems);
  const howToSchema = buildHowToJsonLd({
    name: "Как подобрать кабельный завод по ТЗ",
    description: "Пошаговый процесс подбора производителей кабеля.",
    steps,
  });

  return (
    <IndustryPageLayout
      categoryTitle="Кабель и электротехника"
      badge="Электрооборудование и кабельная продукция"
      headline="Поиск поставщиков кабеля и электротехники по спецификации ТЗ"
      description="Разбор кабельного журнала и поиск потенциальных поставщиков по маркоразмерам и условиям ТЗ. Наличие, документы и полномочия продавца подтверждают перед заказом."
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
