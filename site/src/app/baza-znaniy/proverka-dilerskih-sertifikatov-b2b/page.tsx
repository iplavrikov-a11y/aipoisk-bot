import type { Metadata } from "next";
import { buildBreadcrumbJsonLd, buildHowToJsonLd } from "@/lib/seo";
import { KnowledgeArticleLayout } from "@/components/knowledge-article-layout";

export const metadata: Metadata = {
  title: "Проверка дилерских сертификатов и полномочий поставщика — Руководство TenderLex",
  description: "Инструкция по проверке подлинности дилерских писем, дистрибьюторских договоров и предотвращению поставок контрафакта в B2B.",
  alternates: { canonical: "/baza-znaniy/proverka-dilerskih-sertifikatov-b2b" },
};

const steps = [
  { name: "Сверка срока действия сертификата", text: "Проверьте дату выдачи и срок действия дилерского свидетельства на официальном бланке." },
  { name: "Проверка списка дилеров на сайте производителя", text: "Сверьтесь с разделом «Где купить» или «Официальные партнеры» на сайте завода-изготовителя." },
  { name: "Запрос подтверждения у производителя", text: "При крупных суммах закупки направьте официальный запрос на завод с просьбой подтвердить статус дилера." },
  { name: "Контроль гарантийных обязательств", text: "Убедитесь, что заводская гарантия распространяется на продукцию, поставленную через данного дилера." },
];

export default function GuideDealerVerificationPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "База знаний", item: "https://tenderlex.ru/baza-znaniy" },
    { name: "Проверка дилерских сертификатов", item: "https://tenderlex.ru/baza-znaniy/proverka-dilerskih-sertifikatov-b2b" },
  ]);

  const howToSchema = buildHowToJsonLd({
    name: "Как проверить полномочия дилера",
    description: "Методология проверки подлинности дилерских соглашений в закупках.",
    steps,
  });

  return (
    <KnowledgeArticleLayout
      tag="Безопасность закупок"
      title="Проверка дилерских сертификатов и полномочий поставщика"
      subtitle="Как убедиться в подлинности статуса официального представителя завода и избежать риска поставки фальсификата."
      steps={steps}
      breadcrumbSchema={breadcrumbSchema}
      howToSchema={howToSchema}
    >
      <div className="space-y-6">
        <h2 className="text-xl font-bold text-white">1. Зачем проверять дилерский статус</h2>
        <p>
          В коммерческих и государственных закупках нередки случаи предоставления поддельных дилерских писем. Работа с неавторизованным поставщиком может привести к отказу завода в гарантийном обслуживании и срыву сроков поставки.
        </p>

        <h2 className="text-xl font-bold text-white">2. Проверка поставщиков через TenderLex</h2>
        <p>
          TenderLex верифицирует связь между производителем и торговым представителем, отбирая только официальные дистрибьюторские каналы.
        </p>
      </div>
    </KnowledgeArticleLayout>
  );
}
