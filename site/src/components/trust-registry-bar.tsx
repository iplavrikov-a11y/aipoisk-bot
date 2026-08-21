import { Globe, Cpu, Building2, Database, Sparkles, CheckCircle2, ShieldCheck, Search, ArrowRight } from "lucide-react";

export function TrustRegistryBar() {
  const pillars = [
    {
      title: "Живой поиск Яндекс & Google",
      subtitle: "Прямой поиск в интернете",
      desc: "ИИ формирует точечные поисковые запросы по ГОСТам, маркам и ТЗ без ограничений устаревшими базами.",
      icon: Search,
      tag: "Live Web Search",
      highlight: "Яндекс / Google",
    },
    {
      title: "Глубокий краулинг сайтов",
      subtitle: "Сбор со страниц компаний",
      desc: "Робот переходит на сайт каждого поставщика, парсит разделы контактов, прайсы и извлекает прямые email сбыта.",
      icon: Cpu,
      tag: "Deep Crawling",
      highlight: "Direct Email & Тел.",
    },
    {
      title: "Реестр Минпромторга (ГИСП)",
      subtitle: "Национальный режим",
      desc: "Сверка номенклатуры с Реестром российской промышленной продукции по ПП РФ № 616 и № 617.",
      icon: Building2,
      tag: "ПП 616 / 617",
      highlight: "ГИСП Минпромторга",
    },
    {
      title: "ЕИС Закупки (44-ФЗ / 223-ФЗ)",
      subtitle: "Госзакупки и контракты",
      desc: "Экспресс-анализ условий проектов контрактов, нетипичных штрафов по ПП № 1042 и сроков поставки.",
      icon: Database,
      tag: "44-ФЗ & 223-ФЗ",
      highlight: "ЕИС Закупки",
    },
  ];

  return (
    <div className="py-8 sm:py-10">
      {/* Title */}
      <div className="text-center max-w-3xl mx-auto mb-8 space-y-2">
        <div className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-teal-50 border border-teal-200 text-teal-800 text-xs font-bold shadow-2xs">
          <Sparkles size={13} className="text-teal-600 shrink-0" />
          <span>Технологии поиска и источники данных</span>
        </div>
        <h3 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
          Как TenderLex находит поставщиков и анализирует риски
        </h3>
        <p className="text-xs sm:text-sm text-slate-600 font-normal max-w-2xl mx-auto leading-relaxed">
          Вместо статичных справочников сервис сканирует реальные сайты производителей через Яндекс и Google в режиме реального времени, извлекая прямые контакты отделов сбыта.
        </p>
      </div>

      {/* 4 Clean Balanced Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 max-w-6xl mx-auto">
        {pillars.map((item, idx) => {
          const Icon = item.icon;
          return (
            <div
              key={idx}
              className="p-6 rounded-2xl bg-white border border-slate-200 shadow-2xs hover:border-teal-400 hover:shadow-md transition-all flex flex-col justify-between"
            >
              <div className="space-y-3.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="w-10 h-10 rounded-xl bg-teal-50 border border-teal-100 text-teal-700 flex items-center justify-center shrink-0">
                    <Icon size={20} />
                  </div>
                  <span className="text-[11px] font-bold text-teal-800 bg-teal-50 px-2.5 py-1 rounded-md border border-teal-200/80 shrink-0">
                    {item.tag}
                  </span>
                </div>

                <div>
                  <span className="text-[11px] font-semibold text-slate-400 block mb-1">
                    {item.subtitle}
                  </span>
                  <h4 className="text-base font-bold text-slate-900 leading-snug">
                    {item.title}
                  </h4>
                </div>

                <p className="text-xs text-slate-600 leading-relaxed font-normal">
                  {item.desc}
                </p>
              </div>

              <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="font-bold text-slate-700 text-[11px]">
                  {item.highlight}
                </span>
                <span className="text-teal-700 font-semibold text-[11px] flex items-center gap-1">
                  <CheckCircle2 size={13} className="text-teal-600 shrink-0" />
                  Актуально
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Compliance & Security Banner */}
      <div className="mt-6 p-4 rounded-2xl bg-slate-900 text-white flex flex-col sm:flex-row items-center justify-between gap-4 text-xs max-w-6xl mx-auto shadow-sm">
        <div className="flex items-center gap-3 text-center sm:text-left">
          <div className="w-7 h-7 rounded-lg bg-teal-500/20 text-teal-300 flex items-center justify-center shrink-0">
            <ShieldCheck size={16} />
          </div>
          <span className="text-slate-200 font-medium text-xs">
            <strong>100% соответствие 152-ФЗ</strong>: данные защищены, поисковые процессы изолированы, серверы в РФ.
          </span>
        </div>
        <div className="flex items-center gap-4 text-slate-300 font-semibold text-[11px] shrink-0">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 size={13} className="text-emerald-400 shrink-0" />
            Без скрытых подписок
          </span>
          <span className="flex items-center gap-1.5">
            <CheckCircle2 size={13} className="text-emerald-400 shrink-0" />
            Пробный доступ при регистрации
          </span>
        </div>
      </div>
    </div>
  );
}
