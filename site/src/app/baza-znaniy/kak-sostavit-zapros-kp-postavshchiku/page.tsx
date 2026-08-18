import type { Metadata } from "next";
import { buildBreadcrumbJsonLd, buildHowToJsonLd } from "@/lib/seo";
import { KnowledgeArticleLayout } from "@/components/knowledge-article-layout";

export const metadata: Metadata = {
  title: "Как составить запрос коммерческого предложения (КП) поставщику — Руководство TenderLex",
  description: "Правильная структура делового письма для закупки: номенклатура, ГОСТы, объемы, требования к фасовке и условиям отгрузки.",
  alternates: { canonical: "/baza-znaniy/kak-sostavit-zapros-kp-postavshchiku" },
};

const steps = [
  { name: "Четкая структурированная таблица", text: "Указывайте наименование, марку, ГОСТ/ТУ, объем и единицы измерения в понятной таблице." },
  { name: "Сроки ответа и дедлайн", text: "Всегда фиксируйте желаемую дату предоставления коммерческого предложения." },
  { name: "Условия логистики и оплаты", text: "Указывайте точный адрес доставки (или самовывоз) и предпочтительные условия расчетов." },
  { name: "Запрос документов качества", text: "Сразу запрашивайте паспорта качества, сертификаты соответствия и гарантийные сроки." },
];

export default function GuideRfqPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "База знаний", item: "https://tenderlex.ru/baza-znaniy" },
    { name: "Запрос КП поставщику", item: "https://tenderlex.ru/baza-znaniy/kak-sostavit-zapros-kp-postavshchiku" },
  ]);

  const howToSchema = buildHowToJsonLd({
    name: "Как составить запрос коммерческого предложения",
    description: "Инструкция по составлению официального письма запроса КП.",
    steps,
  });

  return (
    <KnowledgeArticleLayout
      tag="Практика снабжения"
      title="Как правильно составить запрос коммерческого предложения (КП)"
      subtitle="Структура идеального обращения закупщика к заводам и дилерам для получения минимальной цены в кратчайшие сроки."
      steps={steps}
      breadcrumbSchema={breadcrumbSchema}
      howToSchema={howToSchema}
    >
      <div className="space-y-6">
        <h2 className="text-xl font-bold text-white">1. Почему грамотный запрос КП экономит время</h2>
        <p>
          Четко сформулированный запрос коммерческого предложения позволяет менеджеру поставщика сразу рассчитать стоимость и логистику без дополнительных уточняющих звонков и переписок.
        </p>

        <h2 className="text-xl font-bold text-white">2. Автогенерация КП через TenderLex</h2>
        <p>
          TenderLex автоматически преобразует загруженное ТЗ в готовый текст электронного письма с таблицей номенклатуры и всеми необходимыми юридическими оговорками.
        </p>
      </div>
    </KnowledgeArticleLayout>
  );
}
