import type { Metadata } from "next";
import { buildBreadcrumbJsonLd, buildHowToJsonLd } from "@/lib/seo";
import { KnowledgeArticleLayout } from "@/components/knowledge-article-layout";

export const metadata: Metadata = {
  title: "Анализ рисков закупки по 44-ФЗ и 223-ФЗ до подачи заявки — Руководство TenderLex",
  description: "Практическое руководство для поставщиков: как выявить скрытые штрафы, короткие сроки и нетипичные требования в проекте госконтракта.",
  alternates: { canonical: "/baza-znaniy/analiz-riskov-zakupki-44-fz-223-fz" },
};

const steps = [
  { name: "Сверка сроков поставки и экспертизы", text: "Проверьте, реален ли срок передачи товара заказчику с учетом времени на приемку и лабораторный контроль." },
  { name: "Аудит штрафов и неустоек", text: "Убедитесь, что штрафы соответствуют Постановлению Правительства № 1042 и не содержат скрытых санкций." },
  { name: "Проверка нацрежима (ПП 616/617)", text: "Проверьте ОКПД2 товара на предмет запретов или ограничений допуска иностранной продукции." },
  { name: "Подготовка запроса на разъяснение", text: "При обнаружении разночтений направьте официальный запрос заказчику через электронную площадку." },
];

export default function GuideRiskAnalysisPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "База знаний", item: "https://tenderlex.ru/baza-znaniy" },
    { name: "Анализ рисков закупки", item: "https://tenderlex.ru/baza-znaniy/analiz-riskov-zakupki-44-fz-223-fz" },
  ]);

  const howToSchema = buildHowToJsonLd({
    name: "Как проверить риски контракта 44-ФЗ",
    description: "Методика проверки закупочной документации на скрытые риски.",
    steps,
  });

  return (
    <KnowledgeArticleLayout
      tag="Поставщикам и тендерам"
      title="Анализ рисков закупки по 44-ФЗ и 223-ФЗ до подачи заявки"
      subtitle="Чек-лист ключевых ловушек в документации заказчиков и способы правовой защиты поставщика."
      steps={steps}
      breadcrumbSchema={breadcrumbSchema}
      howToSchema={howToSchema}
    >
      <div className="space-y-6">
        <h2 className="text-xl font-bold text-white">1. Основные зоны риска в госзакупках</h2>
        <p>
          Участие в закупках по 44-ФЗ и 223-ФЗ требует тщательного анализа проекта контракта. Невнимательность к условиям приемки или обеспечительным мерам может привести к расторжению договора в одностороннем порядке и внесению компании в Реестр недобросовестных поставщиков (РНП).
        </p>

        <h2 className="text-xl font-bold text-white">2. Использование TenderLex для аудита рисков</h2>
        <p>
          TenderLex автоматически считывает проект контракта и выявляет скрытые штрафы, невыполнимые сроки и ограничения Минпромторга за 3 минуты.
        </p>
      </div>
    </KnowledgeArticleLayout>
  );
}
