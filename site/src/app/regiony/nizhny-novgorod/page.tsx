import type { Metadata } from "next";
import { buildBreadcrumbJsonLd, buildServiceJsonLd } from "@/lib/seo";
import { RegionalPageLayout } from "@/components/regional-page-layout";

export const metadata: Metadata = {
  title: "Поиск поставщиков по ТЗ в Нижнем Новгороде — TenderLex",
  description: "Подбор машиностроительных, судостроительных и кабельных заводов Нижегородской области.",
  alternates: { canonical: "/regiony/nizhny-novgorod" },
};

export default function NizhnyNovgorodRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Регионы", item: "https://tenderlex.ru/regiony" },
    { name: "Нижний Новгород", item: "https://tenderlex.ru/regiony/nizhny-novgorod" },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ в Нижнем Новгороде",
    description: "Подбор заводов и поставщиков в Нижегородской области.",
    path: "/regiony/nizhny-novgorod",
  });

  return (
    <RegionalPageLayout
      regionName="Нижнем Новгороде"
      regionDistrict="Приволжский федеральный округ (ПФО)"
      headline="Поиск заводов и поставщиков по ТЗ в Нижнем Новгороде"
      description="Мощный центр транспортного машиностроения, атомного приборостроения, черной металлургии и кабельных производств."
      breadcrumbSchema={breadcrumbSchema}
      serviceSchema={serviceSchema}
      features={[
        "Прямые контакты отделов сбыта машиностроительных заводов",
        "Проверка сертификатов соответствия и паспортов качества",
        "Исключение посредников с завышенной наценкой",
        "Быстрая рассылка запроса КП в 1 клик",
      ]}
      industrialSpecialties={[
        {
          title: "Автопром и спецтехника",
          desc: "Компоненты коммерческого транспорта, гидравлика, надстройки и спецавтомобили.",
        },
        {
          title: "Трубная продукция и металлургия",
          desc: "Бесшовные трубы, колесные пары, металлопрокат и литье.",
        },
      ]}
    />
  );
}
