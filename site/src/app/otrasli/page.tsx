import type { Metadata } from "next";
import Link from "next/link";
import { Building2, Cable, Layers, ShieldCheck, Wrench, ArrowRight, Sparkles } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { buildBreadcrumbJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Поиск поставщиков по отраслям номенклатуры и ТЗ",
  description:
    "Отраслевой подбор производителей и дилеров по спецификациям: металлопрокат, кабельная продукция, запорная арматура, стройматериалы, СИЗ и спецодежда по всей России.",
  alternates: {
    canonical: "/otrasli",
  },
  openGraph: {
    type: "website",
    url: "/otrasli",
    title: "Поиск поставщиков по отраслям номенклатуры и ТЗ | TenderLex",
    description: "Отраслевой подбор производителей и дилеров под закупки и спецификации по отраслям промышленности РФ.",
    siteName: "TenderLex",
    images: ["/tenderlex-product-preview.png"],
  },
};

const industries = [
  {
    slug: "/otrasli/metalloprokat",
    title: "Металлопрокат и трубы",
    tag: "Металлургия и прокат",
    icon: Layers,
    description:
      "Сортовой и листовой прокат, бесшовные и электросварные трубы, нержавеющие стали по ГОСТ, профильные трубы и метизы от прямых заводов.",
  },
  {
    slug: "/otrasli/kabel-i-provod",
    title: "Кабель и электротехника",
    tag: "Электрооборудование",
    icon: Cable,
    description:
      "Силовые кабели (ВВГнг, КГ, АВБбШв), контрольные и оптические кабели, трансформаторы, щитовое оборудование и кабеленесущие системы.",
  },
  {
    slug: "/otrasli/truboprovodnaya-armatura",
    title: "Трубопроводная и запорная арматура",
    tag: "Трубопроводы и ТЭК",
    icon: Wrench,
    description:
      "Задвижки (стальные, чугунные), шаровые краны, дисковые затворы, фланцы, отводы, компенсаторы и насосное оборудование для сетей и промышленности.",
  },
  {
    slug: "/otrasli/stroitelnye-materialy",
    title: "Строительные материалы",
    tag: "Капитальное строительство",
    icon: Building2,
    description:
      "Сухие строительные смеси, теплоизоляция, ЖБИ, гидроизоляционные мембраны, фасадные системы и кирпич под ведомости материалов проектов.",
  },
  {
    slug: "/otrasli/siz-i-specodezhda",
    title: "СИЗ и спецодежда",
    tag: "Охрана труда и безопасность",
    icon: ShieldCheck,
    description:
      "Летняя и зимняя спецодежда, защитная спецобувь, респираторы, противогазы, монтажные пояса и средства защиты рук от производителей.",
  },
];

export default function IndustriesHubPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Отрасли", item: "https://tenderlex.ru/otrasli" },
  ]);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      <main className="bg-slate-50/60 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

        {/* HERO */}
        <section className="relative overflow-hidden pt-12 pb-20 border-b border-slate-200/90 bg-gradient-to-b from-teal-50/60 via-slate-50 to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-black uppercase tracking-wider shadow-2xs">
              <Layers size={14} className="text-teal-600" />
              <span>Отраслевая классификация ТЗ</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Поиск поставщиков по отраслям номенклатуры
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              TenderLex распознает ГОСТы, марки сплавов, маркоразмеры и технические стандарты для точного выхода на профильные заводы по всей России.
            </p>
          </div>
        </section>

        {/* INDUSTRIES GRID */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {industries.map((item) => {
                const IconComp = item.icon;
                return (
                  <article
                    key={item.slug}
                    className="p-8 bg-slate-50 rounded-3xl border-2 border-slate-200 hover:border-teal-500 hover:shadow-xl transition-all flex flex-col justify-between group shadow-2xs"
                  >
                    <div className="space-y-4">
                      <div className="w-12 h-12 rounded-2xl bg-teal-100 border border-teal-200 text-teal-700 flex items-center justify-center group-hover:scale-110 transition-transform">
                        <IconComp size={24} />
                      </div>
                      <span className="inline-block px-3 py-1 text-[10px] font-black uppercase tracking-wider text-teal-900 bg-teal-100 border border-teal-300 rounded-lg">
                        {item.tag}
                      </span>
                      <h2 className="text-xl font-black text-slate-900 group-hover:text-teal-700 transition-colors">
                        <Link href={item.slug}>{item.title}</Link>
                      </h2>
                      <p className="text-xs text-slate-600 leading-relaxed font-medium">
                        {item.description}
                      </p>
                    </div>

                    <div className="pt-6 mt-6 border-t border-slate-200">
                      <Link
                        href={item.slug}
                        className="text-xs font-black text-teal-700 hover:text-teal-900 inline-flex items-center gap-1.5 transition-colors"
                      >
                        <span>Смотреть отрасль</span>
                        <ArrowRight size={14} />
                      </Link>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <ContactSection />

        <SiteFooter />
      </main>
    </>
  );
}
