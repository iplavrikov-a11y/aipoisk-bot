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
  {
    question: "Как TenderLex распознает кабельные журналы?",
    answer:
      "Сервис извлекает маркоразмеры (например, ВВГнг(А)-FRLS 5х16), строительные длины, напряжение (0.66 кВ, 1 кВ, 6-10 кВ) и соответствие ГОСТ 31996-2012.",
  },
  {
    question: "Помогает ли сервис найти заводы с наличием на складе?",
    answer:
      "Да, TenderLex находит как заводы под изготовление, так и официальных дистрибьюторов с региональными складами.",
  },
];

const steps = [
  { name: "Загрузка кабельного журнала", text: "Загрузите проект ЭОМ/ЭМ или ведомость кабельной продукции." },
  { name: "Парсинг маркоразмеров", text: "ИИ определяет жильность, сечение, тип изоляции и ГОСТы." },
  { name: "Отбор кабельных заводов", text: "Формирование пула изготовителей и складов по всей РФ." },
  { name: "Единый запрос КП", text: "Мгновенное формирование официального письма для сбора цен." },
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
      description="Автоматический разбор кабельных журналов, сопоставление маркоразмеров по ГОСТ и выход на прямые кабельные заводы по всей России."
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
