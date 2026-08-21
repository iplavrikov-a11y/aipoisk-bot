import type { Metadata } from "next";
import { buildBreadcrumbJsonLd, buildServiceJsonLd } from "@/lib/seo";
import { RegionalPageLayout } from "@/components/regional-page-layout";

export const metadata: Metadata = {
  title: "Поиск поставщиков по ТЗ в Самаре и Поволжье",
  description: "Подбор машиностроительных заводов, производителей емкостей, металлоконструкций и кабеля в Самарской области.",
  alternates: { canonical: "/regiony/samara" },
};

export default function SamaraRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Регионы", item: "https://tenderlex.ru/regiony" },
    { name: "Самара и Поволжье", item: "https://tenderlex.ru/regiony/samara" },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ в Самаре и Поволжье",
    description: "Подбор заводов и поставщиков в Самарской области.",
    path: "/regiony/samara",
  });

  return (
    <RegionalPageLayout
      regionName="Самаре и Поволжье"
      regionDistrict="Приволжский федеральный округ (ПФО)"
      headline="Поиск поставщиков и заводов в Самаре и Поволжье"
      description="Индустриальный центр Поволжья: авиакосмическое машиностроение, емкостное и резервуарное оборудование, электротехника и кабельные заводы."
      breadcrumbSchema={breadcrumbSchema}
      serviceSchema={serviceSchema}
      features={[
        "Прямой контакт с отделами сбыта самарских заводов металлообработки",
        "Проверка дистрибьюторов электротехнической продукции",
        "Исключение фирм-однодневок и неактивных посредников",
        "Формирование сводного запроса цен за 3 минуты",
      ]}
      industrialSpecialties={[
        {
          title: "Емкостное и нефтегазовое оборудование",
          desc: "Резервуары РВС/РГС, сепараторы, теплообменники и насосные станции.",
        },
        {
          title: "Кабельно-проводниковая продукция",
          desc: "Силовые кабели, контрольные кабели и монтажные провода по ГОСТ.",
        },
      ]}
    />
  );
}
