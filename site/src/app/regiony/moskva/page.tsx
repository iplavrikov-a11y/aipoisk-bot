import type { Metadata } from "next";
import { buildBreadcrumbJsonLd, buildServiceJsonLd } from "@/lib/seo";
import { RegionalPageLayout } from "@/components/regional-page-layout";

export const metadata: Metadata = {
  title: "Поиск поставщиков по ТЗ в Москве и Московской области",
  description:
    "Подбор B2B-поставщиков, заводов и официальных дилеров по спецификациям в Москве и МО. Проверка контактов и отправка запроса КП.",
  keywords: [
    "поиск поставщиков Москва",
    "подбор поставщиков по ТЗ Москва",
    "производители Москва закупки",
    "официальные дилеры Москва",
    "запрос КП Москва",
  ],
  alternates: {
    canonical: "/regiony/moskva",
  },
  openGraph: {
    type: "website",
    url: "/regiony/moskva",
    title: "Поиск поставщиков по ТЗ в Москве и МО | TenderLex",
    description: "Автоматизированный подбор контрагентов под спецификации закупки в Москве и ЦФО.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

export default function MoscowRegionPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Регионы", item: "https://tenderlex.ru/regiony" },
    { name: "Москва и МО", item: "https://tenderlex.ru/regiony/moskva" },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков по ТЗ в Москве и МО",
    description: "TenderLex подбирает производителей, дилеров и дистрибьюторов в Москве и Московской области под технические задания.",
    path: "/regiony/moskva",
  });

  return (
    <RegionalPageLayout
      regionName="Москве и Подмосковье"
      regionDistrict="Центральный федеральный округ (ЦФО)"
      headline="Поиск поставщиков и производителей по ТЗ в Москве"
      description="Подбор проверенных контрагентов в столичном регионе: выявление прямых складов, дилеров и изготовителей под спецификации закупки."
      breadcrumbSchema={breadcrumbSchema}
      serviceSchema={serviceSchema}
      features={[
        "Отсечение недобросовестных посредников и досок объявлений",
        "Проверка авторизованных дилеров с действующими сертификатами",
        "Прямые email и телефоны отделов оптовых продаж",
        "Учет расположения центральных складов и терминалов отгрузки",
      ]}
      industrialSpecialties={[
        {
          title: "Центральные склады и дистрибьюторы",
          desc: "Крупнейшие логистические хабы электротехники, кабельной продукции, крепежа и инструмента.",
        },
        {
          title: "Металлообработка и металлоконструкции",
          desc: "Производственные площадки в Московской области по изготовлению металлоизделий и резервуаров.",
        },
      ]}
    />
  );
}
