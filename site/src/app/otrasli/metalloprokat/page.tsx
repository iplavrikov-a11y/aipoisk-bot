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
  title: "Поиск поставщиков металлопроката и труб по ТЗ",
  description:
    "Автоматический подбор заводов-производителей и дилеров металлопроката по спецификации ТЗ: сортовой, листовой прокат, трубы ГОСТ и метизы.",
  alternates: {
    canonical: "/otrasli/metalloprokat",
  },
};

const pagePath = "/otrasli/metalloprokat";

const faqItems: FaqItem[] = [
  { question: "Как TenderLex разбирает спецификацию металлопроката?", answer: "Сервис извлекает указанные марки стали, стандарты, толщины, диаметры и длины. Сверьте распознанные позиции с исходной спецификацией; качество и соответствие партии подтверждают документами изготовителя." },
  { question: "Как проверить, является ли компания изготовителем?", answer: "В списке кандидатов могут быть заводы и торговые компании. Роль продавца, полномочия дилера и изготовителя конкретной партии подтвердите по первоисточникам и документам компании." },
  { question: "Можно ли подготовить единый запрос КП по спецификации?", answer: "TenderLex помогает составить черновик обращения с позициями и условиями поставки. Проверьте полноту перечня и укажите нужные документы на товар; цену и срок ответа определяет поставщик." },
];

const steps = [
  { name: "Загрузка спецификации металлопроката", text: "Передайте файл Excel, PDF или ведомость металлоконструкций (КМ/КМД)." },
  { name: "Парсинг марок сталей и ГОСТов", text: "Алгоритм извлекает диаметры, стенки, марки сплавов и тоннаж." },
  { name: "Отбор металлургических заводов и трейдеров", text: "Перечень кандидатов и доступных контактов; роль продавца и реквизиты подтверждают отдельно." },
  { name: "Генерация единого запроса КП", text: "Черновик письма для проверки и отправки выбранным компаниям." },
];

const nomenclatures = [
  "Трубы бесшовные горячедеформированные (ГОСТ 8732-78, 09Г2С, ст.20)",
  "Трубы электросварные прямошовные (ГОСТ 10704-91, ГОСТ 10705-80)",
  "Листовой прокат горячекатаный и холоднокатаный (ГОСТ 19903-2015)",
  "Сортовой прокат: арматура А500С, балка двутавровая, швеллер, уголок",
  "Прокат из нержавеющих и жаропрочных сталей (12Х18Н10Т, AISI 304, AISI 316)",
  "Метизная продукция, крепеж повышенной прочности (класс 8.8, 10.9)",
];

export default function MetalloprokatPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Отрасли", item: "https://tenderlex.ru/otrasli" },
    { name: "Металлопрокат и трубы", item: "https://tenderlex.ru" + pagePath },
  ]);

  const serviceSchema = buildServiceJsonLd({
    name: "Поиск поставщиков металлопроката и труб по ТЗ",
    description: "Сервис извлечения марок сталей и подбора металлургических заводов по спецификации.",
    path: pagePath,
  });

  const faqSchema = buildFaqJsonLd(faqItems);
  const howToSchema = buildHowToJsonLd({
    name: "Как найти завод металлопроката по спецификации",
    description: "Пошаговый процесс подбора производителей металлопроката.",
    steps,
  });

  return (
    <IndustryPageLayout
      categoryTitle="Металлопрокат и трубы"
      badge="Металлургия и трубный прокат"
      headline="Поиск поставщиков металлопроката и труб по спецификации ТЗ"
      description="Разбор спецификации металлопроката и поиск кандидатов по маркам стали, размерам и требованиям ТЗ. Сверьте характеристики и документы конкретной партии перед заказом."
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
