import type { Metadata } from "next";

import { buildBreadcrumbJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Поиск поставщиков и производителей по регионам России",
  description:
    "Региональный подбор B2B-поставщиков, заводов и дилеров по спецификациям: Москва, Санкт-Петербург, Екатеринбург, Новосибирск, Казань, Нижний Новгород, Краснодар, Самара.",
  alternates: {
    canonical: "/regiony",
  },
  openGraph: {
    type: "website",
    url: "/regiony",
    title: "Поиск поставщиков по регионам России | TenderLex",
    description:
      "Подбор контрагентов под закупочную задачу по федеральным округам и промышленным центрам России.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

const regions = [
  {
    slug: "/regiony/moskva",
    title: "Москва и ЦФО",
    description: "Заводы, дистрибьюторы и склады в Москве и Подмосковье.",
  },
  {
    slug: "/regiony/sankt-peterburg",
    title: "Санкт-Петербург и СЗФО",
    description: "Изготовители и дилеры в СПб и Северо-Западном округе.",
  },
  {
    slug: "/regiony/ekaterinburg",
    title: "Екатеринбург и Урал",
    description: "Заводы металлообработки, арматуры и кабеля на Урале.",
  },
  {
    slug: "/regiony/novosibirsk",
    title: "Новосибирск и СФО",
    description: "Промышленные предприятия и дилеры Сибирского региона.",
  },
  {
    slug: "/regiony/kazan",
    title: "Казань и Татарстан",
    description: "Нефтехимические, полимерные и машиностроительные заводы.",
  },
  {
    slug: "/regiony/nizhny-novgorod",
    title: "Нижний Новгород",
    description: "Машиностроительные и судостроительные заводы Нижегородской области.",
  },
  {
    slug: "/regiony/krasnodar",
    title: "Краснодар и Юг РФ",
    description: "Поставщики стройматериалов и агропрома Южного округа.",
  },
  {
    slug: "/regiony/samara",
    title: "Самара и Поволжье",
    description: "Автопром, оборудование и металлоконструкции Поволжья.",
  },
];

export default function RegionalHubPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "TenderLex", path: "/" },
    { name: "Регионы", path: "/regiony" },
  ]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 font-sans py-12 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      <div className="mb-10">
        <a href="/" className="text-xs font-semibold text-teal-700 font-bold hover:underline">
          ← На главную TenderLex
        </a>
        <h1 className="text-3xl font-extrabold text-slate-900 mt-4 mb-2">
          Поиск поставщиков и заводов по регионам России
        </h1>
        <p className="text-base text-slate-700 font-medium">
          Географический подбор производителей, дилеров и дистрибьюторов под спецификации и закупки по всей РФ.
        </p>
      </div>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {regions.map((r) => (
          <article
            key={r.slug}
            className="p-6 bg-white rounded-2xl border border-slate-200 hover:border-teal-500/40 transition-all flex flex-col justify-between"
          >
            <div>
              <span className="inline-block px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-teal-950 font-extrabold bg-teal-100 border border-teal-300 rounded mb-3">
                {r.title}
              </span>
              <p className="text-xs text-slate-700 font-medium mb-4 leading-relaxed">{r.description}</p>
            </div>
            <a
              href={r.slug}
              className="text-xs font-bold text-teal-700 font-bold hover:text-teal-950 font-extrabold flex items-center gap-1 mt-2"
            >
              Смотреть регион →
            </a>
          </article>
        ))}
      </div>
    </main>
  );
}
