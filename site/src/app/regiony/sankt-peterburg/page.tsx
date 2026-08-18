import type { Metadata } from "next";
import { buildBreadcrumbJsonLd, buildServiceJsonLd } from "@/lib/seo";
import { RegionalPageLayout } from "@/components/regional-page-layout";

export const metadata: Metadata = {
  title: "Поиск поставщиков по ТЗ в Санкт-Петербурге и СЗФО — TenderLex",
  description: "Подбор B2B-поставщиков, заводов и дилеров по спецификациям в Санкт-Петербурге и Ленинградской области.",
  alternates: { canonical: "/regiony/sankt-peterburg" },
};

export default function SpbRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Регионы", item: "https://tenderlex.ru/regiony" },
    { name: "Санкт-Петербург и СЗФО", item: "https://tenderlex.ru/regiony/sankt-peterburg" },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ в Санкт-Петербурге и СЗФО",
    description: "Подбор контрагентов под спецификации в Северо-Западном федеральном округе.",
    path: "/regiony/sankt-peterburg",
  });

  return (
    <RegionalPageLayout
      regionName="Санкт-Петербурге и СЗФО"
      regionDistrict="Северо-Западный федеральный округ"
      headline="Поиск поставщиков и заводов по ТЗ в Санкт-Петербурге"
      description="Изготовители запорной арматуры, кабельные заводы, судостроительные предприятия и склады снабжения Северо-Запада."
      breadcrumbSchema={breadcrumbSchema}
      serviceSchema={serviceSchema}
      features={[
        "Прямой выход на машиностроительные и приборостроительные заводы СПб",
        "Проверка дистрибьюторов европейского и азиатского оборудования",
        "Извлечение direct email отделов сбыта",
        "Формирование готового текста запроса КП",
      ]}
      industrialSpecialties={[
        {
          title: "Судостроение и тяжелое машиностроение",
          desc: "Заводы энергетического машиностроения, судовые комплектующие и судовая арматура.",
        },
        {
          title: "Кабельная и электротехническая продукция",
          desc: "Ведущие кабельные заводы и региональные распределительные склады.",
        },
      ]}
    />
  );
}
