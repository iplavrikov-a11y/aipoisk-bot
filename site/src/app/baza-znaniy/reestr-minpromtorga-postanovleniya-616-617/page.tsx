import type { Metadata } from "next";
import { buildBreadcrumbJsonLd, buildHowToJsonLd } from "@/lib/seo";
import { KnowledgeArticleLayout } from "@/components/knowledge-article-layout";

export const metadata: Metadata = {
  title: "Реестр Минпромторга и Постановления № 616 и 617 в закупках — Руководство TenderLex",
  description: "Разбор правил применения национального режима, проверки реестровых номеров ГИСП и правил подтверждения отечественного происхождения.",
  alternates: { canonical: "/baza-znaniy/reestr-minpromtorga-postanovleniya-616-617" },
};

const steps = [
  { name: "Определение кода ОКПД2 товара", text: "Сопоставьте наименование закупаемой позиции с классификатором ОКПД2." },
  { name: "Проверка перечня ПП № 616", text: "Если код входит в ПП 616, установлен полный запрет на иностранный товар (за исключением ЕАЭС)." },
  { name: "Проверка перечня ПП № 617", text: "Если код входит в ПП 617, применяется ограничение по правилу «третий лишний»." },
  { name: "Получение выписки из реестра ГИСП", text: "Убедитесь в наличии действующей реестровой записи у завода-изготовителя." },
];

export default function GuideMinpromtorgPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "База знаний", item: "https://tenderlex.ru/baza-znaniy" },
    { name: "Реестр Минпромторга", item: "https://tenderlex.ru/baza-znaniy/reestr-minpromtorga-postanovleniya-616-617" },
  ]);

  const howToSchema = buildHowToJsonLd({
    name: "Как проверить товар по Реестру Минпромторга",
    description: "Порядок проверки национального режима в госзакупках.",
    steps,
  });

  return (
    <KnowledgeArticleLayout
      tag="Нацрежим и допуски"
      title="Реестр Минпромторга и Постановления № 616 и 617 в закупках"
      subtitle="Как правильно проверять реестровые номера ГИСП и соблюдать требования нацрежима без риска отклонения заявки."
      steps={steps}
      breadcrumbSchema={breadcrumbSchema}
      howToSchema={howToSchema}
    >
      <div className="space-y-6">
        <h2 className="text-xl font-bold text-white">1. Разница между ПП № 616 и ПП № 617</h2>
        <p>
          Постановление № 616 устанавливает прямой запрет на закупку иностранных промышленных товаров, в то время как Постановление № 617 работает по механизму ограничений («третий лишний»). Для допуска заявки поставщик обязан указать реестровый номер записи из государственной информационной системы промышленности (ГИСП).
        </p>

        <h2 className="text-xl font-bold text-white">2. Поиск отечественных производителей через TenderLex</h2>
        <p>
          TenderLex фильтрует российские заводы, продукция которых уже внесена в реестр Минпромторга РФ, помогая быстро подтвердить происхождение товара.
        </p>
      </div>
    </KnowledgeArticleLayout>
  );
}
