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
  title: "Поиск поставщиков металлопроката и труб по ТЗ — TenderLex",
  description:
    "Автоматический подбор заводов-производителей и дилеров металлопроката по спецификации ТЗ: сортовой, листовой прокат, трубы ГОСТ и метизы.",
  alternates: {
    canonical: "/otrasli/metalloprokat",
  },
};

const pagePath = "/otrasli/metalloprokat";

const faqItems: FaqItem[] = [
  {
    question: "Как TenderLex распознаёт сложные спецификации металлопроката?",
    answer:
      "ИИ-алгоритм парсит марки стали (ст3сп, 09Г2С, 12Х18Н10Т, 40Х), ГОСТы (ГОСТ 8732-78, ГОСТ 535-2005, ГОСТ 19903-2015), толщины, диаметры и длины.",
  },
  {
    question: "Помогает ли сервис отличать заводы от перекупщиков?",
    answer:
      "Да. Сервис классифицирует контрагентов на металлургические комбинаты, трубные заводы, официальных трейдеров и складские металлобазы.",
  },
  {
    question: "Можно ли сформировать общий запрос КП на 50+ позиций проката?",
    answer:
      "Да. После анализа спецификации сервис формирует единый текст запроса КП с перечнем всех позиций, тоннажа, условий доставки и сертификатов 3.1.",
  },
];

const steps = [
  { name: "Загрузка спецификации металлопроката", text: "Передайте файл Excel, PDF или ведомость металлоконструкций (КМ/КМД)." },
  { name: "Парсинг марок сталей и ГОСТов", text: "Алгоритм извлекает диаметры, стенки, марки сплавов и тоннаж." },
  { name: "Отбор металлургических заводов и трейдеров", text: "Формирование реестра с прямыми контактами оптовых отделов сбыта." },
  { name: "Генерация единого запроса КП", text: "Готовое письмо для мгновенной отправки поставщикам." },
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
      description="Автоматический парсинг марок сталей, диаметров, ГОСТов и сбор прямых контактов металлургических комбинатов и официальных трейдеров по всей России."
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
