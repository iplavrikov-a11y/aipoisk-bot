import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ContactSection } from "@/components/contact-section";
import {
  Building2,
  CheckCircle2,
  MapPin,
  Send,
  Sparkles,
  Truck,
  Layers,
  FileCheck,
  ShieldCheck,
  Clock,
  TrendingUp,
} from "lucide-react";
import type { FaqItem } from "@/lib/seo";

export interface RegionalStat {
  label: string;
  value: string;
  desc?: string;
}

export interface RegionalHub {
  name: string;
  type: string;
  desc: string;
}

export interface RegionalSection {
  title: string;
  text: string;
}

interface RegionalPageLayoutProps {
  regionName: string;
  regionDistrict?: string;
  regionGenitive?: string;
  headline?: string;
  description: string;
  stats?: RegionalStat[];
  logisticsHubs?: RegionalHub[];
  procurementDetails?: RegionalSection[];
  keyIndustries?: string[];
  features?: string[];
  industrialSpecialties?: { title: string; desc: string; items?: string[] }[];
  steps?: { name: string; text: string }[];
  faqItems?: FaqItem[];
  breadcrumbSchema: object;
  serviceSchema: object;
  faqSchema?: object;
  howToSchema?: object;
}

export function RegionalPageLayout({
  regionName,
  regionDistrict,
  regionGenitive = regionName,
  headline = `Поиск производителей и поставщиков по ТЗ в ${regionName}`,
  description,
  stats = [],
  logisticsHubs = [],
  procurementDetails = [],
  keyIndustries = [],
  features = [],
  industrialSpecialties = [],
  steps = [],
  faqItems = [],
  breadcrumbSchema,
  serviceSchema,
  faqSchema,
  howToSchema,
}: RegionalPageLayoutProps) {
  const displayIndustries =
    keyIndustries.length > 0
      ? keyIndustries
      : features.length > 0
      ? features
      : industrialSpecialties.map((s) => `${s.title}: ${s.desc}`);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceSchema) }}
      />
      {faqSchema && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
        />
      )}
      {howToSchema && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(howToSchema) }}
        />
      )}

      <main className="bg-slate-50 text-slate-900 min-h-screen font-sans">
        <SiteHeader />

        {/* HERO */}
        <section className="relative pt-12 pb-20 border-b border-slate-200 bg-gradient-to-b from-teal-50/50 via-slate-50 to-white">
          <div className="container max-w-5xl mx-auto px-4 sm:px-6 text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-teal-200 text-teal-900 text-xs font-bold uppercase tracking-wider shadow-2xs">
              <MapPin size={14} className="text-teal-600" />
              <span>Региональный подбор поставщиков: {regionDistrict || regionName}</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
              {headline}
            </h1>

            <p className="text-slate-600 text-base sm:text-lg max-w-3xl mx-auto font-normal leading-relaxed">
              {description}
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4 pt-2">
              <a
                href="/cabinet"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-sm shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
              >
                <span>Найти поставщиков в регионе</span>
              </a>
              <a
                href="https://t.me/tenderlex_bot"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-bold border-2 border-slate-300 shadow-2xs text-sm transition-all hover:border-teal-500"
              >
                <Send size={16} className="text-teal-600" />
                <span>Запустить в Telegram</span>
              </a>
            </div>
          </div>
        </section>

        {/* REGIONAL STATS & INDUSTRIAL CAPACITY */}
        {stats.length > 0 && (
          <section className="py-12 border-b border-slate-200 bg-white">
            <div className="container max-w-5xl mx-auto px-4 sm:px-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
                {stats.map((st, idx) => (
                  <div
                    key={idx}
                    className="p-5 rounded-2xl bg-slate-50 border border-slate-200 shadow-2xs flex flex-col justify-between"
                  >
                    <span className="text-2xl sm:text-3xl font-black text-teal-700 tracking-tight">
                      {st.value}
                    </span>
                    <div className="mt-2">
                      <span className="text-xs sm:text-sm font-bold text-slate-900 block leading-snug">
                        {st.label}
                      </span>
                      {st.desc && (
                        <span className="text-[11px] text-slate-500 mt-1 block leading-tight">
                          {st.desc}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* INDUSTRIAL SPECIALTIES & PRODUCTION CAPACITIES */}
        {industrialSpecialties.length > 0 ? (
          <section className="py-16 sm:py-20 border-b border-slate-200 bg-slate-50">
            <div className="container max-w-5xl mx-auto px-4 sm:px-6 space-y-10">
              <div className="text-center max-w-3xl mx-auto space-y-3">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-100 text-teal-900 text-xs font-bold uppercase">
                  <Building2 size={14} /> Производственный комплекс
                </div>
                <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900">
                  Ключевые промышленные кластеры: {regionName}
                </h2>
                <p className="text-slate-600 text-sm sm:text-base">
                  Прямой доступ к производителям и официальным распределительным центрам под спецификации любой сложности.
                </p>
              </div>

              <div className="grid sm:grid-cols-2 gap-6">
                {industrialSpecialties.map((spec, idx) => (
                  <div
                    key={idx}
                    className="p-6 rounded-3xl bg-white border-2 border-slate-200 hover:border-teal-400 shadow-2xs transition-all space-y-3"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-8 h-8 rounded-xl bg-teal-50 text-teal-700 font-bold flex items-center justify-center text-sm shrink-0 border border-teal-200">
                        {idx + 1}
                      </span>
                      <h3 className="text-base font-bold text-slate-900">{spec.title}</h3>
                    </div>
                    <p className="text-sm text-slate-600 leading-relaxed">{spec.desc}</p>
                    {spec.items && spec.items.length > 0 && (
                      <ul className="space-y-1 pt-1 text-xs text-slate-700 font-medium">
                        {spec.items.map((item, iIdx) => (
                          <li key={iIdx} className="flex items-center gap-2">
                            <CheckCircle2 size={13} className="text-teal-600 shrink-0" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </section>
        ) : displayIndustries.length > 0 ? (
          <section className="py-16 sm:py-20 border-b border-slate-200 bg-white">
            <div className="container max-w-5xl mx-auto px-4 sm:px-6">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 text-center mb-10">
                Ведущие отрасли производства и поставок: {regionName}
              </h2>

              <div className="grid sm:grid-cols-2 gap-6">
                {displayIndustries.map((ind, idx) => (
                  <div
                    key={idx}
                    className="p-6 rounded-3xl bg-slate-50 border-2 border-slate-200 shadow-2xs flex items-start gap-3"
                  >
                    <CheckCircle2 size={20} className="text-teal-600 shrink-0 mt-0.5" />
                    <span className="text-sm text-slate-800 font-bold">{ind}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        ) : null}

        {/* LOGISTICS & FREIGHT HUBS */}
        {logisticsHubs.length > 0 && (
          <section className="py-16 sm:py-20 border-b border-slate-200 bg-white">
            <div className="container max-w-5xl mx-auto px-4 sm:px-6 space-y-10">
              <div className="text-center max-w-3xl mx-auto space-y-3">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-100 text-teal-900 text-xs font-bold uppercase">
                  <Truck size={14} /> Транспортные коридоры
                </div>
                <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900">
                  Логистические узлы и распределительные центры
                </h2>
                <p className="text-slate-600 text-sm sm:text-base">
                  Оптимизация транспортных затрат за счет подбора контрагентов вблизи грузовых терминалов и магистралей.
                </p>
              </div>

              <div className="grid sm:grid-cols-3 gap-6">
                {logisticsHubs.map((hub, idx) => (
                  <div
                    key={idx}
                    className="p-5 rounded-2xl bg-slate-50 border border-slate-200 space-y-2.5 shadow-2xs"
                  >
                    <span className="text-[10px] font-bold text-teal-700 uppercase tracking-wider block">
                      {hub.type}
                    </span>
                    <h3 className="text-sm font-bold text-slate-900">{hub.name}</h3>
                    <p className="text-xs text-slate-600 leading-relaxed">{hub.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* PROCUREMENT SPECIFICS & REGIONAL DYNAMICS */}
        {procurementDetails.length > 0 && (
          <section className="py-16 sm:py-20 border-b border-slate-200 bg-slate-50">
            <div className="container max-w-5xl mx-auto px-4 sm:px-6 space-y-10">
              <div className="text-center max-w-3xl mx-auto space-y-3">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-100 text-teal-900 text-xs font-bold uppercase">
                  <ShieldCheck size={14} /> Специфика торгов и снабжения
                </div>
                <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900">
                  Особенности закупок и работы с поставщиками региона
                </h2>
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                {procurementDetails.map((sec, idx) => (
                  <div
                    key={idx}
                    className="p-6 rounded-3xl bg-white border border-slate-200 space-y-3 shadow-2xs"
                  >
                    <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-teal-600" />
                      <span>{sec.title}</span>
                    </h3>
                    <p className="text-sm text-slate-600 leading-relaxed">{sec.text}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* STEPS HOW-TO */}
        {steps.length > 0 && (
          <section className="py-16 sm:py-20 border-b border-slate-200 bg-white">
            <div className="container max-w-4xl mx-auto px-4 sm:px-6 space-y-10">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 text-center">
                Порядок подбора поставщиков в регионе через TenderLex
              </h2>
              <div className="space-y-4">
                {steps.map((st, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-4 p-5 rounded-2xl bg-slate-50 border border-slate-200 shadow-2xs"
                  >
                    <span className="w-8 h-8 rounded-xl bg-teal-600 text-white font-black flex items-center justify-center shrink-0 text-sm shadow-xs">
                      {idx + 1}
                    </span>
                    <div>
                      <strong className="text-slate-900 block text-base font-bold">
                        {st.name}
                      </strong>
                      <p className="text-sm text-slate-600 mt-1 leading-relaxed">{st.text}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* FAQ */}
        {faqItems.length > 0 && (
          <section className="py-16 sm:py-24 border-b border-slate-200 bg-slate-50">
            <div className="container max-w-4xl mx-auto px-4 sm:px-6">
              <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 text-center mb-12">
                Вопросы о подборе поставщиков в регионе
              </h2>
              <div className="space-y-4">
                {faqItems.map((item, index) => (
                  <details
                    key={index}
                    className="group bg-white p-6 rounded-2xl border-2 border-slate-200 text-left shadow-2xs"
                  >
                    <summary className="font-bold text-slate-900 text-base cursor-pointer flex justify-between items-center list-none">
                      <span>{item.question}</span>
                      <span className="transition group-open:rotate-180 text-teal-700">▼</span>
                    </summary>
                    <p className="mt-4 text-sm text-slate-700 font-normal leading-relaxed border-t border-slate-200 pt-4">
                      {item.answer}
                    </p>
                  </details>
                ))}
              </div>
            </div>
          </section>
        )}

        <ContactSection
          title={`Подбор поставщиков: ${regionName}`}
          subtitle={`Загрузите файл ТЗ или спецификации для мгновенного сбора прямых контактов заводов в ${regionGenitive}.`}
        />

        <SiteFooter />
      </main>
    </>
  );
}
