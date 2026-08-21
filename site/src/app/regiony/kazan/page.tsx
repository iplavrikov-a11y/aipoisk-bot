import type { Metadata } from "next";
import { buildBreadcrumbJsonLd, buildServiceJsonLd } from "@/lib/seo";
import { RegionalPageLayout } from "@/components/regional-page-layout";

export const metadata: Metadata = {
  title: "Поиск поставщиков по ТЗ в Казани и Татарстане",
  description: "Подбор нефтехимических, полимерных и машиностроительных заводов в Республике Татарстан.",
  alternates: { canonical: "/regiony/kazan" },
};

export default function KazanRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Регионы", item: "https://tenderlex.ru/regiony" },
    { name: "Казань и Татарстан", item: "https://tenderlex.ru/regiony/kazan" },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ в Казани и Татарстане",
    description: "Подбор нефтехимических, полимерных и машиностроительных заводов.",
    path: "/regiony/kazan",
  });

  return (
    <RegionalPageLayout
      regionName="Казани и Татарстане"
      regionDistrict="Приволжский федеральный округ (ПФО)"
      headline="Поиск поставщиков и заводов в Казани и Татарстане"
      description="Один из ключевых индустриальных центров РФ: полимеры, резинотехнические изделия, нефтехимия, автокомпоненты и вертолетостроение."
      breadcrumbSchema={breadcrumbSchema}
      serviceSchema={serviceSchema}
      features={[
        "Прямой доступ к производителям полимерной и химической продукции",
        "Проверка статуса резидентов ОЭЗ и индустриальных парков Татарстана",
        "Прямые контакты отделов сбыта заводов",
        "Формирование официального запроса КП",
      ]}
      industrialSpecialties={[
        {
          title: "Нефтехимия и полимеры",
          desc: "Полиэтилен, полипропилен, синтетические каучуки, полимерные трубы и РТИ.",
        },
        {
          title: "Машиностроение и приборостроение",
          desc: "Компрессорное оборудование, насосы, арматура и металлообработка.",
        },
      ]}
    />
  );
}
