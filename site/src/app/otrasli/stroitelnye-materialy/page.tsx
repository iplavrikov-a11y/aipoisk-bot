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
  title: "Поиск поставщиков стройматериалов по ТЗ",
  description:
    "Автоматический подбор заводов стройматериалов по спецификациям: ЖБИ, сухие смеси, теплоизоляция, кирпич, фасадные системы.",
  alternates: {
    canonical: "/otrasli/stroitelnye-materialy",
  },
};

const pagePath = "/otrasli/stroitelnye-materialy";

const faqItems: FaqItem[] = [
  { question: "Как учитывать доставку стройматериалов?", answer: "Укажите адрес объекта, объемы и график приемки в ТЗ. TenderLex помогает искать кандидатов в нужном регионе; цену доставки, условия разгрузки и срок поставки подтвердите в КП." },
  { question: "Можно ли найти контакты изготовителей ЖБИ?", answer: "Сервис помогает искать профильные компании и доступные контакты из открытых источников. Изготовителя, наличие продукции, реквизиты и адрес получателя подтвердите перед обращением." },
];

const steps = [
  { name: "Загрузка ведомости материалов", text: "Загрузите проект АР/КР или спецификацию строительных материалов." },
  { name: "Парсинг характеристик", text: "ИИ извлекает классы прочности бетона, плотность утеплителя, морозостойкость." },
  { name: "Региональный подбор заводов", text: "Поиск кандидатов в указанном регионе; адрес отгрузки и условия доставки подтверждают у поставщика." },
  { name: "Запрос КП", text: "Формирование единого письма с графиком поставок и объемами." },
];

const nomenclatures = [
  "Железобетонные изделия: плиты перекрытия (ПК, ПБ), сваи, блоки ФБС, перемычки",
  "Сухие строительные смеси: клей для плитки, штукатурка, наливные полы, гидроизоляция",
  "Теплоизоляционные материалы: минеральная вата, экструдированный пенополистирол (XPS)",
  "Гидроизоляционные и кровельные рулонные материалы (Техноэласт, Унифлекс, мембраны)",
  "Кирпич строительный рядовой, облицовочный, газобетонные и керамические блоки",
  "Фасадные системы: керамогранит, металлокассеты, подсистемы и крепеж",
];

export default function StroymaterialyPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Отрасли", item: "https://tenderlex.ru/otrasli" },
    { name: "Строительные материалы", item: "https://tenderlex.ru" + pagePath },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков строительных материалов по ТЗ",
    description: "Сервис подбора заводов стройматериалов и ЖБИ по спецификациям.",
    path: pagePath,
  });

  const faqSchema = buildFaqJsonLd(faqItems);
  const howToSchema = buildHowToJsonLd({
    name: "Как подобрать завод стройматериалов",
    description: "Инструкция по поиску производителей строительных материалов.",
    steps,
  });

  return (
    <IndustryPageLayout
      categoryTitle="Строительные материалы"
      badge="Капитальное строительство и ЖБИ"
      headline="Поиск поставщиков стройматериалов по спецификации ТЗ"
      description="Разбор ведомости стройматериалов и поиск потенциальных поставщиков ЖБИ, смесей и теплоизоляции. Стоимость доставки, наличие и характеристики партии подтвердите в КП."
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
