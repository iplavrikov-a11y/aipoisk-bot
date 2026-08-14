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
        location: "Нальчик / СКФО",
        matchLevel: "Точное совпадение",
        email: "sales@kavkazkabel.ru",
        phone: "+7 (866) 240-77-11",
      },
      {
        name: 'ООО "Севкабель-Дистрибуция"',
        role: "Официальный дилер",
        location: "Москва / ЦФО",
        matchLevel: "Профильный поставщик",
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
        desc: "Риск просрочки при отгрузке в удаленные регионы. Рекомендуется уточнить наличие на складах.",
      },
      {
        type: "info",
        title: "Сертификация ЕАЭС",
        desc: "Подтвержден ГОСТ 31996-2012. Требуется паспорт качества производителя на каждую партию.",
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
        location: "Рязань / РФ",
        matchLevel: "Точное совпадение",
        email: "tn@technonicol.ru",
        phone: "8 (800) 200-04-00",
      },
      {
        name: 'ООО "СтройКомплект Снаб"',
        role: "Региональный склад",
        location: "Санкт-Петербург / СЗФО",
        matchLevel: "Смежная категория",
        email: "spb@stroykomplekt.ru",
        phone: "+7 (812) 334-11-22",
      },
    ],
    rfqText:
      "Здравствуйте! Просим выставить КП на минераловатный утеплитель 100мм (110 кг/м³) — 1 200 кв.м. Просим указать стоимость куб.м, нормативную плотность, объем поддона и условия транспортировки.",
    risks: [
      {
        type: "danger",
        title: "Постоплата 100% через 30 дней",
        desc: "Аванс не предусмотрен контрактом. Требуются собственные оборотные средства.",
      },
      {
        type: "info",
        title: "Требования к упаковке",
        desc: "Контроль целостности влагозащитной пленки при приемке на объекте.",
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
        location: "Челябинск / Урал",
        matchLevel: "Точное совпадение",
        email: "sales@chza-armatura.ru",
        phone: "+7 (351) 778-90-00",
      },
      {
        name: 'ООО "АрмСнаб Поставка"',
        role: "Официальный дистрибьютор",
        location: "Екатеринбург / УрФО",
        matchLevel: "Профильный поставщик",
        email: "ekb@armsnab.ru",
        phone: "+7 (343) 220-55-44",
      },
    ],
    rfqText:
      "Здравствуйте! Просим направить КП на задвижки 30ч6бр РУ10 ДУ100 — 45 шт. Просим приложить выписку из реестра Минпромторга (Постановление № 616) и указать наличие на складе.",
    risks: [
      {
        type: "danger",
        title: "Минпромторг № 616 (Нацрежим)",
        desc: "Обязательное условие: подтверждение происхождения товара выпиской из ГИСП.",
      },
      {
        type: "warning",
        title: "Нетипичные штрафные санкции",
        desc: "Штраф 0.5% за каждый день просрочки представления исполнительной документации.",
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
    <div className="bg-white/95 backdrop-blur-xl border-2 border-slate-200/90 rounded-2xl p-5 sm:p-6 text-slate-800 shadow-xl relative overflow-hidden space-y-5">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-teal-600 animate-pulse" />
          <span className="text-xs font-extrabold uppercase tracking-wider text-slate-900">
            Симулятор возможностей TenderLex
          </span>
        </div>
        <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-teal-100 border border-teal-300 text-teal-900 font-bold">
          Реальный функционал ИИ
        </span>
      </div>

      {/* Mode Selector Tabs (Real Backend Scenarios) */}
      <div className="grid grid-cols-3 gap-1.5 p-1 bg-slate-100 rounded-xl text-xs font-bold">
        <button
          onClick={() => setActiveMode("supplier_search")}
          className={`py-2 px-2 rounded-lg transition-all text-center flex items-center justify-center gap-1.5 ${
            activeMode === "supplier_search"
              ? "bg-white text-teal-800 shadow-xs border border-slate-200"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <Search className="w-3.5 h-3.5 text-teal-600 shrink-0" />
          <span className="hidden sm:inline">1. Поиск поставщиков</span>
          <span className="sm:hidden">Поиск</span>
        </button>

        <button
          onClick={() => setActiveMode("doc_analysis")}
          className={`py-2 px-2 rounded-lg transition-all text-center flex items-center justify-center gap-1.5 ${
            activeMode === "doc_analysis"
              ? "bg-white text-teal-800 shadow-xs border border-slate-200"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <FileCheck className="w-3.5 h-3.5 text-teal-600 shrink-0" />
          <span className="hidden sm:inline">2. Разбор ЕИС 44-ФЗ</span>
          <span className="sm:hidden">Анализ</span>
        </button>

        <button
          onClick={() => setActiveMode("combined")}
          className={`py-2 px-2 rounded-lg transition-all text-center flex items-center justify-center gap-1.5 ${
            activeMode === "combined"
              ? "bg-white text-teal-800 shadow-xs border border-slate-200"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <Zap className="w-3.5 h-3.5 text-teal-600 shrink-0" />
          <span className="hidden sm:inline">3. Анализ + Поиск</span>
          <span className="sm:hidden">Всё вместе</span>
        </button>
      </div>

      {/* Specification selector chips */}
      <div className="space-y-2">
        <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
          Пример спецификации из ТЗ:
        </span>
        <div className="flex flex-nowrap overflow-x-auto pb-1 gap-2 scrollbar-none">
          {demoSpecs.map((spec) => (
            <button
              key={spec.id}
              onClick={() => setActiveSpecId(spec.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold shrink-0 transition-all ${
                spec.id === activeSpecId
                  ? "bg-teal-600 text-white shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200"
              }`}
            >
              {spec.name.split(" (")[0]}
            </button>
          ))}
        </div>
      </div>

      {/* Mode 1: Supplier Search Output */}
      {(activeMode === "supplier_search" || activeMode === "combined") && (
        <div className="space-y-4 pt-1">
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex justify-between items-center text-xs">
            <div>
              <span className="font-bold text-teal-700 block">{activeSpec.category}</span>
              <span className="text-slate-900 font-semibold">{activeSpec.name}</span>
            </div>
            <span className="text-[10px] font-bold bg-teal-100 text-teal-800 px-2 py-0.5 rounded border border-teal-200 shrink-0">
              {activeSpec.itemsCount}
            </span>
          </div>

          <div>
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                Извлеченная база прямых контактов:
              </span>
              <span className="text-[10px] text-slate-500 font-mono">2 завода • 4 дилера</span>
            </div>

            <div className="space-y-2">
              {activeSpec.suppliers.map((s) => (
                <div
                  key={s.name}
                  className="p-3 bg-white rounded-xl border border-slate-200 shadow-2xs hover:border-teal-400 transition-colors space-y-1.5 text-xs"
                >
                  <div className="flex flex-wrap justify-between items-center gap-2">
                    <span className="font-bold text-slate-900 flex items-center gap-1.5">
                      <Building2 className="w-3.5 h-3.5 text-teal-600 shrink-0" />
                      {s.name}
                    </span>
                    <span className="text-[10px] font-bold bg-emerald-50 border border-emerald-300 text-emerald-800 px-2 py-0.5 rounded">
                      {s.role}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px]">
                    <span className="text-slate-600 flex items-center gap-1">
                      <Mail className="w-3 h-3 text-teal-600 shrink-0" />
                      <strong className="text-teal-700 font-mono">{s.email}</strong>
                    </span>
                    <span className="text-slate-600 flex items-center gap-1">
                      <Phone className="w-3 h-3 text-teal-600 shrink-0" />
                      <span className="font-mono text-slate-800">{s.phone}</span>
                    </span>
                    <span className="text-slate-400 text-[10px] font-medium ml-auto">
                      {s.matchLevel}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Generated RFQ Email Box */}
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-2 text-xs">
            <div className="flex justify-between items-center border-b border-slate-200 pb-2">
              <span className="font-bold text-slate-900 flex items-center gap-1.5 text-[11px]">
                <FileText className="w-3.5 h-3.5 text-teal-600" /> Сгенерированный Запрос КП:
              </span>
              <button
                onClick={handleCopy}
                className="text-[10px] font-bold text-teal-700 hover:text-teal-800 flex items-center gap-1 bg-white px-2 py-1 rounded border border-slate-200 shadow-2xs"
              >
                <Copy className="w-3 h-3" />
                {copied ? "Скопировано!" : "Скопировать"}
              </button>
            </div>
            <p className="text-slate-700 font-mono text-[11px] leading-relaxed">
              {activeSpec.rfqText}
            </p>
          </div>
        </div>
      )}

      {/* Mode 2: Procurement Risk Analysis */}
      {(activeMode === "doc_analysis" || activeMode === "combined") && (
        <div className="space-y-3 pt-1">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              Аудит рисков контракта (ЕИС / 44-ФЗ / 223-ФЗ):
            </span>
            <span className="text-[10px] text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
              Проверка завершена
            </span>
          </div>

          <div className="space-y-2">
            {activeSpec.risks.map((r, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-xl border text-xs space-y-1 ${
                  r.type === "danger"
                    ? "bg-rose-50/80 border-rose-200 text-rose-900"
                    : r.type === "warning"
                    ? "bg-amber-50/80 border-amber-200 text-amber-900"
                    : "bg-teal-50/80 border-teal-200 text-teal-900"
                }`}
              >
                <div className="flex items-center gap-1.5">
                  {r.type === "danger" || r.type === "warning" ? (
                    <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4 text-teal-600 shrink-0" />
                  )}
                  <strong className="font-bold">{r.title}</strong>
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed pl-5.5">{r.desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Footer */}
      <div className="pt-2 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs">
        <span className="text-slate-500 font-medium text-[11px]">
          Выгрузка: XLSX таблицы • DOCX отчеты • Telegram и Веб-кабинет
        </span>
        <a
          href="/cabinet"
          className="inline-flex items-center gap-1 font-bold text-teal-700 hover:text-teal-800"
        >
          Запустить разбор по вашему ТЗ <ArrowRight className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  );
}
