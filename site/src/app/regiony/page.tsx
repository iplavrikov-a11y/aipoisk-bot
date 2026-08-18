import type { Metadata } from "next";
import Link from "next/link";
import { MapPin, ArrowRight, Sparkles, Building2 } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import { buildBreadcrumbJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Поиск поставщиков по регионам России — база заводов TenderLex",
  description:
    "Региональный подбор поставщиков и производителей под технические задания: Москва, Санкт-Петербург, Урал, Сибирь, Поволжье, Юг и другие субъекты РФ.",
  alternates: {
    canonical: "/regiony",
  },
};

const regions = [
  {
    slug: "/regiony/moskva",
    name: "Москва и Московская область (ЦФО)",
    tag: "Центральный ФО",
    description: "Крупнейший логистический узел, центральные склады дистрибьюторов, приборостроение и металлообработка.",
  },
  {
    slug: "/regiony/sankt-peterburg",
    name: "Санкт-Петербург и СЗФО",
    tag: "Северо-Западный ФО",
    description: "Судостроение, кабельные производства, энергетическое машиностроение, портовая логистика.",
  },
  {
    slug: "/regiony/ekaterinburg",
    name: "Екатеринбург и Уральский ФО",
    tag: "Уральский ФО",
    description: "Черная и цветная металлургия, трубные заводы, тяжелое машиностроение, запорная арматура.",
  },
  {
    slug: "/regiony/novosibirsk",
    name: "Новосибирск и Сибирский ФО",
    tag: "Сибирский ФО",
    description: "Горно-шахтное оборудование, металлоконструкции, строительные материалы, электротехника.",
  },
  {
    slug: "/regiony/kazan",
    name: "Казань и Республика Татарстан",
    tag: "Приволжский ФО",
    description: "Нефтехимия, машиностроение, композитные материалы, полимеры и РТИ.",
  },
  {
    slug: "/regiony/nizhny-novgorod",
    name: "Нижний Новгород и Нижегородская область",
    tag: "Приволжский ФО",
    description: "Автомобилестроение, металлопрокат, химическая промышленность, судостроение.",
  },
  {
    slug: "/regiony/krasnodar",
    name: "Краснодар и Южный ФО",
    tag: "Южный ФО",
    description: "Строительный комплекс, сельхозмашиностроение, металлоконструкции, логистика.",
  },
  {
    slug: "/regiony/samara",
    name: "Самара и Самарская область",
    tag: "Приволжский ФО",
    description: "Аэрокосмическое машиностроение, кабельные заводы, нефтепереработка, автокомпоненты.",
  },
];

export default function RegionyHubPage() {
  const breadcrumbSchema = buildBreadcrumbJsonLd([
    { name: "Главная", item: "https://tenderlex.ru" },
    { name: "Регионы", item: "https://tenderlex.ru/regiony" },
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
              <MapPin size={14} className="text-teal-600" />
              <span>Покрытие всех федеральных округов РФ</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              Поиск поставщиков по регионам России
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto font-medium leading-relaxed">
              TenderLex учитывает региональную специфику и локацию заводов, помогая находить ближайших производителей для снижения стоимости логистики.
            </p>
          </div>
        </section>

        {/* REGIONS GRID */}
        <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
          <div className="container max-w-6xl mx-auto px-4 sm:px-6">
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              {regions.map((region) => (
                <article
                  key={region.slug}
                  className="p-6 bg-slate-50 rounded-3xl border-2 border-slate-200 hover:border-teal-500 hover:shadow-xl transition-all flex flex-col justify-between group shadow-2xs"
                >
                  <div className="space-y-3">
                    <span className="inline-block px-2.5 py-1 text-[10px] font-black uppercase tracking-wider text-teal-900 bg-teal-100 border border-teal-300 rounded-lg">
                      {region.tag}
                    </span>
                    <h2 className="text-base font-black text-slate-900 group-hover:text-teal-700 transition-colors">
                      <Link href={region.slug}>{region.name}</Link>
                    </h2>
                    <p className="text-xs text-slate-600 leading-relaxed font-medium">
                      {region.description}
                    </p>
                  </div>

                  <div className="pt-4 mt-4 border-t border-slate-200">
                    <Link
                      href={region.slug}
                      className="text-xs font-black text-teal-700 hover:text-teal-900 inline-flex items-center gap-1 transition-colors"
                    >
                      <span>Поставщики региона</span>
                      <ArrowRight size={13} />
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <ContactSection />

        <SiteFooter />
      </main>
    </>
  );
}
