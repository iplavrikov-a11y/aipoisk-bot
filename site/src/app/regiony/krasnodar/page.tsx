import type { Metadata } from "next";
import { buildBreadcrumbJsonLd, buildServiceJsonLd } from "@/lib/seo";
import { RegionalPageLayout } from "@/components/regional-page-layout";

export const metadata: Metadata = {
  title: "Поиск поставщиков по ТЗ в Краснодаре и на Юге РФ — TenderLex",
  description: "Подбор поставщиков стройматериалов, агропромышленного оборудования и металлоконструкций на Юге России.",
  alternates: { canonical: "/regiony/krasnodar" },
};

export default function KrasnodarRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Регионы", item: "https://tenderlex.ru/regiony" },
    { name: "Краснодар и Юг РФ", item: "https://tenderlex.ru/regiony/krasnodar" },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ в Краснодаре и ЮФО",
    description: "Подбор поставщиков стройкомплекса и оборудования на Юге России.",
    path: "/regiony/krasnodar",
  });

  return (
    <RegionalPageLayout
      regionName="Краснодаре и на Юге РФ"
      regionDistrict="Южный федеральный округ (ЮФО)"
      headline="Поиск поставщиков и заводов в Краснодаре и ЮФО"
      description="Главный строительный и агропромышленный кластер Юга: ЖБИ, сухие смеси, металлоконструкции, насосы и трубопроводная арматура."
      breadcrumbSchema={breadcrumbSchema}
      serviceSchema={serviceSchema}
      features={[
        "Учет логистики по побережью и ключевым транспортным коридорам Юга",
        "Прямой выход на карьеры, заводы ЖБИ и цементные заводы",
        "Проверка официальных дистрибьюторов строительной химии",
        "Единый запрос коммерческого предложения",
      ]}
      industrialSpecialties={[
        {
          title: "Строительный комплекс и ЖБИ",
          desc: "Железобетонные изделия, фундаментные блоки, товарный бетон и инертные материалы.",
        },
        {
          title: "Трубопроводы и водоснабжение",
          desc: "Полиэтиленовые напорные трубы, запорная арматура для орошения и ЖКХ.",
        },
      ]}
    />
  );
}
