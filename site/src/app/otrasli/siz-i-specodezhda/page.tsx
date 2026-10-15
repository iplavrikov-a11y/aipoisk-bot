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
  title: "Поиск поставщиков СИЗ и спецодежды по ТЗ",
  description:
    "Подбор швейных фабрик и производителей СИЗ по нормам выдачи и ТР ТС 019/2011: зимняя и летняя спецодежда, спецобувь, респираторы, средства защиты.",
  alternates: {
    canonical: "/otrasli/siz-i-specodezhda",
  },
};

const pagePath = "/otrasli/siz-i-specodezhda";

const faqItems: FaqItem[] = [
  { question: "Как проверить документы на выбранные СИЗ?", answer: "Запросите применимые документы о соответствии на конкретную модель СИЗ и проверьте область их действия и статус по официальному источнику. Поиск поставщика не подтверждает сертификацию или пригодность изделия для условий работы." },
  { question: "Можно ли найти кандидатов для пошива спецодежды с логотипом?", answer: "Укажите размеры, ростовки, защитные свойства и требования к нанесению символики. Сервис помогает искать профильные компании; возможность пошива, материалы и характеристики изделия подтвердите в ответе производителя." },
];

const steps = [
  { name: "Загрузка норм выдачи СИЗ", text: "Загрузите ведомость спецодежды, размеры, ростовки и защитные свойства (З, Ми, Мп, Тн)." },
  { name: "Анализ защитных свойств", text: "ИИ определяет классы защиты, типы тканей (смесовые, огнестойкие) и стандарты." },
  { name: "Подбор швейных фабрик", text: "Поиск потенциальных поставщиков спецодежды и обуви; возможность изготовления и документы уточняют у компании." },
  { name: "Формирование запроса КП", text: "Единый запрос на расчет стоимости партий с учетом нанесения логотипов." },
];

const nomenclatures = [
  "Спецодежда рабочая летняя (костюмы, полукомбинезоны, халаты, ткань Грета, Рип-Стоп)",
  "Спецодежда утепленная зимняя (куртки, костюмы 1-4 климатических поясов)",
  "Специальная обувь (ботинки с композитным/металлическим подноском, сапоги ЭВА/ПУ)",
  "Средства защиты органов дыхания (респираторы FFP1-FFP3, полумаски, противогазы)",
  "Средства защиты рук (перчатки спилковые, нитриловые, краги сварщика)",
  "Средства индивидуальной защиты от падения с высоты (страховочные привязи, стропы)",
];

export default function SizPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Отрасли", item: "https://tenderlex.ru/otrasli" },
    { name: "СИЗ и спецодежда", item: "https://tenderlex.ru" + pagePath },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков СИЗ и спецодежды по ТЗ",
    description: "Сервис подбора швейных фабрик и производителей СИЗ по спецификациям.",
    path: pagePath,
  });

  const faqSchema = buildFaqJsonLd(faqItems);
  const howToSchema = buildHowToJsonLd({
    name: "Как найти производителя спецодежды и СИЗ",
    description: "Инструкция по поиску швейных фабрик по нормам выдачи.",
    steps,
  });

  return (
    <IndustryPageLayout
      categoryTitle="СИЗ и спецодежда"
      badge="Охрана труда и спецодежда"
      headline="Поиск поставщиков СИЗ и спецодежды по спецификации ТЗ"
      description="Разбор ведомости спецодежды и поиск потенциальных поставщиков по размерам и защитным свойствам. Документы на конкретные СИЗ и пригодность для условий работы проверяют отдельно."
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
