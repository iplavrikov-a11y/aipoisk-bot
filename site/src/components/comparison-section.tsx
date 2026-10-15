import { XCircle, CheckCircle2, Zap, Clock, ShieldCheck, Mail, Database, Search } from "lucide-react";

export function ComparisonSection() {
  const comparisonRows = [
    {
      title: "Поиск контактов по номенклатуре",
      manual: "Ручной перебор выдачи, каталогов и сайтов компаний с проверкой релевантности контактов.",
      tenderlex: "Сопоставление марок и ГОСТов с формированием списка компаний и проекта запроса КП для последующей проверки.",
    },
    {
      title: "Выход на производителей и заводы",
      manual: "Сложно отличить изготовителя от посредника без проверки документов и официальных каналов.",
      tenderlex: "Четкая маркировка компаний: Завод-изготовитель, Официальный дилер, Складской дистрибьютор.",
    },
    {
      title: "Подготовка официального запроса КП",
      manual: "Ручной набор писем в почте, перепечатывание таблиц из PDF/Word, высокий риск ошибок в маркировках.",
      tenderlex: "Автоматическая генерация готового текста официального запроса КП со структурированной таблицей.",
    },
    {
      title: "Анализ рисков закупки (44-ФЗ / 223-ФЗ)",
      manual: "Вычитывание десятков страниц проекта контракта юристом, риск пропустить короткие сроки и санкции.",
      tenderlex: "Выявление условий, требующих проверки: штрафов, сроков и требований национального режима.",
    },
  ];

  return (
    <div className="space-y-8">
      <div className="grid md:grid-cols-2 gap-8">
        {/* Left: Traditional Manual Method */}
        <div className="p-7 sm:p-8 rounded-3xl bg-rose-50/50 border-2 border-rose-200/80 shadow-xs space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-rose-100 text-rose-700 flex items-center justify-center font-bold">
              <XCircle size={22} />
            </div>
            <div>
              <span className="text-[10px] font-black uppercase tracking-wider text-rose-700 block">
                Традиционный подход
              </span>
              <h3 className="text-xl font-black text-slate-900">
                Ручной поиск и сбор в поисковиках
              </h3>
            </div>
          </div>

          <ul className="space-y-4 text-xs sm:text-sm text-slate-700 font-medium">
            <li className="flex items-start gap-3 p-3.5 rounded-xl bg-white/80 border border-rose-200/60">
              <span className="text-rose-600 font-bold text-base mt-0.5">✕</span>
              <span>Повторяющаяся ручная проверка спецификации и контактов</span>
            </li>
            <li className="flex items-start gap-3 p-3.5 rounded-xl bg-white/80 border border-rose-200/60">
              <span className="text-rose-600 font-bold text-base mt-0.5">✕</span>
              <span>Риск не отличить изготовителя от посредника без проверки</span>
            </li>
            <li className="flex items-start gap-3 p-3.5 rounded-xl bg-white/80 border border-rose-200/60">
              <span className="text-rose-600 font-bold text-base mt-0.5">✕</span>
              <span>Риск не заметить кабальные условия контракта 44-ФЗ</span>
            </li>
            <li className="flex items-start gap-3 p-3.5 rounded-xl bg-white/80 border border-rose-200/60">
              <span className="text-rose-600 font-bold text-base mt-0.5">✕</span>
              <span>Общие контакты без подтверждения роли компании</span>
            </li>
          </ul>
        </div>

        {/* Right: TenderLex AI Method */}
        <div className="p-7 sm:p-8 rounded-3xl bg-gradient-to-br from-teal-50/80 via-emerald-50/60 to-white border-2 border-teal-300 shadow-lg shadow-teal-900/5 space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-teal-600 text-white flex items-center justify-center font-bold shadow-md shadow-teal-600/20">
              <CheckCircle2 size={22} />
            </div>
            <div>
              <span className="text-[10px] font-black uppercase tracking-wider text-teal-800 font-extrabold block">
                С TenderLex
              </span>
              <h3 className="text-xl font-black text-slate-900">
                ИИ-автоматизация закупочного процесса
              </h3>
            </div>
          </div>

          <ul className="space-y-4 text-xs sm:text-sm text-slate-800 font-bold">
            <li className="flex items-start gap-3 p-3.5 rounded-xl bg-white border border-teal-200/80 shadow-2xs">
              <CheckCircle2 size={18} className="text-teal-600 shrink-0 mt-0.5" />
              <span>Структурирование требований для последующей проверки</span>
            </li>
            <li className="flex items-start gap-3 p-3.5 rounded-xl bg-white border border-teal-200/80 shadow-2xs">
              <CheckCircle2 size={18} className="text-teal-600 shrink-0 mt-0.5" />
              <span>Сопоставление производителей, дилеров и поставщиков по роли</span>
            </li>
            <li className="flex items-start gap-3 p-3.5 rounded-xl bg-white border border-teal-200/80 shadow-2xs">
              <CheckCircle2 size={18} className="text-teal-600 shrink-0 mt-0.5" />
              <span>Карта условий, требующих правовой и коммерческой оценки</span>
            </li>
            <li className="flex items-start gap-3 p-3.5 rounded-xl bg-white border border-teal-200/80 shadow-2xs">
              <CheckCircle2 size={18} className="text-teal-600 shrink-0 mt-0.5" />
              <span>Контакты и проект запроса КП для проверки перед отправкой</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
