import type { Metadata } from "next";
import { buildBreadcrumbJsonLd, buildServiceJsonLd } from "@/lib/seo";
import { RegionalPageLayout } from "@/components/regional-page-layout";

export const metadata: Metadata = {
  title: "Поиск поставщиков и заводов по ТЗ в Екатеринбурге и на Урале",
  description: "Подбор металлургических заводов, производителей труб, арматуры и кабеля на Урале.",
  alternates: { canonical: "/regiony/ekaterinburg" },
};

export default function EkbRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Регионы", item: "https://tenderlex.ru/regiony" },
    { name: "Екатеринбург и Урал", item: "https://tenderlex.ru/regiony/ekaterinburg" },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ в Екатеринбурге и УФО",
    description: "Подбор заводов металлургии, метизов, арматуры и кабеля на Урале.",
    path: "/regiony/ekaterinburg",
  });

  return (
    <RegionalPageLayout
      regionName="Екатеринбурге и на Урале"
      regionDistrict="Уральский федеральный округ (УФО)"
      headline="Поиск заводов-производителей и поставщиков на Урале"
      description="Крупнейший промышленный кластер России: трубные заводы, металлопрокат, запорная арматура, метизы и тяжелое оборудование."
      breadcrumbSchema={breadcrumbSchema}
      serviceSchema={serviceSchema}
      features={[
        "Прямой контакт с отделами сбыта уральских металлургических комбинатов",
        "Идентификация изготовителей нестандартных поковок, отливок и металлоконструкций",
        "Проверка официальных дилеров и складских запасов",
        "Снижение закупочных цен за счет исключения перекупщиков",
      ]}
      industrialSpecialties={[
        {
          title: "Металлургия и трубный прокат",
          desc: "Бесшовные, электросварные, профильные трубы и сортовой металлопрокат по ГОСТ.",
        },
        {
          title: "Трубопроводная и запорная арматура",
          desc: "Задвижки, шаровые краны, фланцы, клапаны высокого давления Ду 15–1200, Ру 16–250.",
        },
      ]}
    />
  );
}
