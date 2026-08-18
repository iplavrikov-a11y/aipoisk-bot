"use client";

import { useState } from "react";
import {
  CheckCircle2,
  ShieldAlert,
  Sparkles,
  Building2,
  Phone,
  Mail,
  FileText,
  Copy,
  Search,
  FileCheck,
  Zap,
  ArrowRight,
  Send,
} from "lucide-react";

type Mode = "supplier_search" | "doc_analysis" | "combined";

type DemoSpec = {
  id: string;
  name: string;
  category: string;
  itemsCount: string;
  suppliers: {
    name: string;
    role: string;
    location: string;
    matchLevel: string;
    email: string;
    phone: string;
  }[];
  rfqText: string;
  risks: {
    type: "warning" | "danger" | "info";
    title: string;
    desc: string;
  }[];
};

const demoSpecs: DemoSpec[] = [
  {
    id: "cable",
    name: "Кабель ВВГнг-LS 3х2.5 (ГОСТ 31996-2012)",
    category: "Кабельно-проводниковая продукция",
    itemsCount: "2 позиции в ТЗ",
    suppliers: [
      {
        name: 'ООО "Кавказкабель"',
        role: "Завод-изготовитель",
        location: "Россия (Прямой завод)",
        matchLevel: "Точное совпадение ГОСТ",
        email: "sales@kavkazkabel.ru",
        phone: "+7 (866) 240-77-11",
      },
      {
        name: 'ООО "Севкабель-Дистрибуция"',
        role: "Официальный дилер",
        location: "Россия (Центральный склад)",
        matchLevel: "Профильный склад",
        email: "msk@sevkabel.ru",
        phone: "+7 (495) 120-44-88",
      },
    ],
    rfqText:
      "Здравствуйте! Просим выставить коммерческое предложение на поставку: Кабель ВВГнг-LS 3х2.5 (ГОСТ 31996-2012) — 5 000 м. Просим указать актуальную цену с НДС, условия оплаты (аванс/постоплата), сроки изготовления и приложить сертификаты соответствия ЕАЭС.",
    risks: [
      {
        type: "warning",
        title: "Срок поставки: 7 рабочих дней",
        desc: "Короткий срок. Рекомендуется запросить наличие на складах дилеров до подачи заявки.",
      },
      {
        type: "info",
        title: "Сертификация ЕАЭС",
        desc: "Требуется паспорт качества производителя на каждую партию согласно ГОСТ 31996-2012.",
      },
    ],
  },
  {
    id: "insulation",
    name: "Минераловатный утеплитель 100мм (110 кг/м³)",
    category: "Теплоизоляционные материалы",
    itemsCount: "3 позиции в ТЗ",
    suppliers: [
      {
        name: 'ООО "ТЕХНОНИКОЛЬ Продажи"',
        role: "Завод-изготовитель",
        location: "Россия (Прямой завод)",
        matchLevel: "Точное совпадение",
        email: "tn@technonicol.ru",
        phone: "8 (800) 200-04-00",
      },
      {
        name: 'ООО "СтройКомплект Снаб"',
        role: "Официальный дистрибьютор",
        location: "Россия (Федеральная сеть)",
        matchLevel: "Профильный склад",
        email: "sales@stroykomplekt.ru",
        phone: "+7 (812) 334-11-22",
      },
    ],
    rfqText:
      "Здравствуйте! Просим выставить КП на минераловатный утеплитель 100мм (110 кг/м³) — 1 200 кв.м. Просим указать стоимость куб.м, нормативную плотность, объем поддона и условия транспортировки.",
    risks: [
      {
        type: "danger",
        title: "Постоплата 100% через 30 дней",
        desc: "Аванс не предусмотрен контрактом. Требуются собственные оборотные средства поставщика.",
      },
      {
        type: "info",
        title: "Требования к упаковке",
        desc: "Контроль целостности влагозащитной пленки при приемке на объекте заказчика.",
      },
    ],
  },
  {
    id: "valve",
    name: "Задвижка стальная 30ч6бр РУ10 ДУ100",
    category: "Трубопроводная арматура",
    itemsCount: "4 позиции в ТЗ",
    suppliers: [
      {
        name: 'АО "Челябинский Завод Арматуры"',
        role: "Завод-изготовитель",
        location: "Россия (Прямой завод)",
        matchLevel: "Точное совпадение",
        email: "sales@chza-armatura.ru",
        phone: "+7 (351) 778-90-00",
      },
      {
        name: 'ООО "АрмСнаб Поставка"',
        role: "Официальный дистрибьютор",
        location: "Россия (Складской хаб)",
        matchLevel: "Профильный поставщик",
        email: "sales@armsnab.ru",
        phone: "+7 (343) 220-55-44",
      },
    ],
    rfqText:
      "Здравствуйте! Просим направить КП на задвижки 30ч6бр РУ10 ДУ100 — 45 шт. Просим приложить выписку из реестра Минпромторга (Постановление № 616) и указать наличие на складе.",
    risks: [
      {
        type: "danger",
        title: "Минпромторг № 616 (Нацрежим)",
        desc: "Обязательное условие: подтверждение происхождения товара выпиской из реестра ГИСП.",
      },
      {
        type: "warning",
        title: "Нетипичные штрафные санкции",
        desc: "Штраф 0.5% за каждый день просрочки предоставления паспортов на арматуру.",
      },
    ],
  },
];

export function InteractiveHeroDemo() {
  const [activeMode, setActiveMode] = useState<Mode>("supplier_search");
  const [activeSpecId, setActiveSpecId] = useState<string>("cable");
  const [copied, setCopied] = useState(false);

  const activeSpec = demoSpecs.find((s) => s.id === activeSpecId) || demoSpecs[0];

  const handleCopy = () => {
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-white border-2 border-slate-200 rounded-3xl p-5 sm:p-6 text-slate-800 shadow-xl relative overflow-hidden space-y-5">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-teal-600 animate-pulse" />
          <span className="text-xs font-black uppercase tracking-wider text-slate-900">
            Симулятор возможностей TenderLex
          </span>
        </div>
        <span className="text-[11px] px-3 py-1 rounded-full bg-teal-50 border border-teal-200 text-teal-900 font-extrabold">
          Поиск по всей России
        </span>
      </div>

      {/* Mode Selector Tabs */}
      <div className="grid grid-cols-3 gap-1.5 p-1 bg-slate-100 rounded-2xl text-xs font-bold">
        <button
          onClick={() => setActiveMode("supplier_search")}
          className={`py-2 px-2 rounded-xl transition-all text-center flex items-center justify-center gap-1.5 ${
            activeMode === "supplier_search"
              ? "bg-white text-teal-900 shadow-xs border border-slate-200"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <Search className="w-3.5 h-3.5 text-teal-600 shrink-0" />
          <span className="hidden sm:inline">1. Поиск поставщиков</span>
          <span className="sm:hidden">Поиск</span>
        </button>

        <button
          onClick={() => setActiveMode("doc_analysis")}
          className={`py-2 px-2 rounded-xl transition-all text-center flex items-center justify-center gap-1.5 ${
            activeMode === "doc_analysis"
              ? "bg-white text-teal-900 shadow-xs border border-slate-200"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <FileCheck className="w-3.5 h-3.5 text-teal-600 shrink-0" />
          <span className="hidden sm:inline">2. Риски 44-ФЗ</span>
          <span className="sm:hidden">Риски</span>
        </button>

        <button
          onClick={() => setActiveMode("combined")}
          className={`py-2 px-2 rounded-xl transition-all text-center flex items-center justify-center gap-1.5 ${
            activeMode === "combined"
              ? "bg-white text-teal-900 shadow-xs border border-slate-200"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <Zap className="w-3.5 h-3.5 text-teal-600 shrink-0" />
          <span className="hidden sm:inline">3. Готовый Запрос КП</span>
          <span className="sm:hidden">Запрос КП</span>
        </button>
      </div>

      {/* Specification selector chips */}
      <div className="space-y-2">
        <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
          Пример спецификации из ТЗ:
        </span>
        <div className="flex flex-wrap gap-2">
          {demoSpecs.map((spec) => (
            <button
              key={spec.id}
              onClick={() => setActiveSpecId(spec.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                spec.id === activeSpecId
                  ? "bg-teal-600 text-white shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200"
              }`}
            >
              {spec.name}
            </button>
          ))}
        </div>
      </div>

      {/* Active Spec Info */}
      <div className="p-3 bg-slate-50 rounded-2xl border border-slate-200 flex justify-between items-center text-xs">
        <div>
          <span className="text-slate-500 block text-[10px] uppercase font-bold">Категория номенклатуры:</span>
          <strong className="text-slate-900 font-extrabold">{activeSpec.category}</strong>
        </div>
        <span className="px-2.5 py-1 bg-white rounded-lg border border-slate-200 font-bold text-slate-700 text-[11px]">
          {activeSpec.itemsCount}
        </span>
      </div>

      {/* Dynamic Tab Content */}
      {/* 1. Suppliers Tab */}
      {(activeMode === "supplier_search" || activeMode === "combined") && (
        <div className="space-y-3">
          <div className="flex justify-between items-center text-xs">
            <span className="font-extrabold text-slate-900 uppercase tracking-wider text-[11px]">
              Извлеченная база прямых контактов по РФ:
            </span>
            <span className="text-slate-500 text-[11px] font-bold">2 завода • 4 дилера</span>
          </div>

          <div className="space-y-2.5">
            {activeSpec.suppliers.map((supp, sIdx) => (
              <div
                key={sIdx}
                className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 text-xs space-y-2 hover:border-teal-500 transition-colors"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-1.5 font-black text-slate-900">
                      <Building2 className="w-3.5 h-3.5 text-teal-600" />
                      <span>{supp.name}</span>
                    </div>
                    <span className="text-[10px] text-slate-500">{supp.location}</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-100 text-teal-900 font-extrabold border border-teal-200">
                    {supp.role}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-700 pt-1 border-t border-slate-200/60">
                  <span className="flex items-center gap-1 font-bold text-teal-700">
                    <Mail className="w-3 h-3 text-teal-600" />
                    {supp.email}
                  </span>
                  <span className="flex items-center gap-1 font-bold text-slate-800">
                    <Phone className="w-3 h-3 text-slate-500" />
                    {supp.phone}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 2. Risks Analysis Tab */}
      {(activeMode === "doc_analysis" || activeMode === "combined") && (
        <div className="space-y-3">
          <span className="font-extrabold text-slate-900 uppercase tracking-wider text-[11px] block">
            Результат анализа рисков документации:
          </span>

          <div className="space-y-2">
            {activeSpec.risks.map((r, rIdx) => (
              <div
                key={rIdx}
                className={`p-3 rounded-2xl border text-xs space-y-1 ${
                  r.type === "danger"
                    ? "bg-rose-50 border-rose-200 text-rose-900"
                    : r.type === "warning"
                    ? "bg-amber-50 border-amber-200 text-amber-900"
                    : "bg-teal-50 border-teal-200 text-teal-900"
                }`}
              >
                <div className="flex items-center gap-1.5 font-black">
                  <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                  <span>{r.title}</span>
                </div>
                <p className="text-[11px] leading-relaxed opacity-90">{r.desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. RFQ Text Output Tab */}
      {(activeMode === "combined" || activeMode === "supplier_search") && (
        <div className="space-y-2 pt-2 border-t border-slate-200">
          <div className="flex justify-between items-center">
            <span className="font-extrabold text-slate-900 uppercase tracking-wider text-[11px] flex items-center gap-1">
              <FileText className="w-3.5 h-3.5 text-teal-600" />
              Сформированный Запрос КП (RFQ):
            </span>
            <button
              onClick={handleCopy}
              className="text-[10px] font-bold text-teal-700 hover:text-teal-900 flex items-center gap-1 bg-teal-50 px-2.5 py-1 rounded-lg border border-teal-200 transition-colors"
            >
              <Copy className="w-3 h-3" />
              {copied ? "Скопировано!" : "Скопировать"}
            </button>
          </div>

          <div className="p-3 bg-slate-50 rounded-2xl border border-slate-200 text-[11px] text-slate-700 font-mono leading-relaxed">
            {activeSpec.rfqText}
          </div>
        </div>
      )}

      {/* Footer CTA */}
      <div className="pt-2">
        <a
          href="/cabinet"
          className="w-full py-3.5 px-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-md shadow-teal-600/20 transition-all hover:scale-[1.01]"
        >
          <span>Запустить поиск по своему ТЗ бесплатно</span>
          <ArrowRight size={14} />
        </a>
      </div>
    </div>
  );
}
