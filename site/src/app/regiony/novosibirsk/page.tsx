import type { Metadata } from "next";
import { buildBreadcrumbJsonLd, buildServiceJsonLd } from "@/lib/seo";
import { RegionalPageLayout } from "@/components/regional-page-layout";

export const metadata: Metadata = {
  title: "Поиск поставщиков и заводов в Новосибирске и Сибири",
  description: "Подбор промышленных предприятий, поставщиков оборудования и стройматериалов в СФО.",
  alternates: { canonical: "/regiony/novosibirsk" },
};

export default function NskRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Регионы", item: "https://tenderlex.ru/regiony" },
    { name: "Новосибирск и СФО", item: "https://tenderlex.ru/regiony/novosibirsk" },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ в Новосибирске и СФО",
    description: "Подбор заводов и поставщиков в Сибирском федеральном округе.",
    path: "/regiony/novosibirsk",
  });

  return (
    <RegionalPageLayout
      regionName="Новосибирске и Сибири"
      regionDistrict="Сибирский федеральный округ (СФО)"
      headline="Поиск поставщиков и заводов в Новосибирске и Сибири"
      description="Главный логистический и промышленный узел Сибири: электротехника, генераторы, стройматериалы и горное оборудование."
      breadcrumbSchema={breadcrumbSchema}
      serviceSchema={serviceSchema}
      features={[
        "Подбор поставщиков с учетом сибирской транспортной логистики",
        "Прямые контакты машиностроительных и приборостроительных заводов",
        "Проверка дилеров с региональными распределительными складами",
        "Автогенерация запроса КП под требования сибирских заказчиков",
      ]}
      industrialSpecialties={[
        {
          title: "Электротехника и приборостроение",
          desc: "Трансформаторы, щитовое оборудование, автоматика и контрольно-измерительные приборы.",
        },
        {
          title: "Промышленные стройматериалы",
          desc: "Железобетонные конструкции, теплоизоляция, сухие смеси с учетом северных стандартов.",
        },
      ]}
    />
  );
}
