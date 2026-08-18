"use client";

import { useState } from "react";
import { Calculator, TrendingUp, Clock, DollarSign, Sparkles, CheckCircle2, ArrowRight } from "lucide-react";

export function ProcurementCalculator() {
  const [specsPerMonth, setSpecsPerMonth] = useState<number>(15);
  const [itemsPerSpec, setItemsPerSpec] = useState<number>(5);
  const [procurementSpecialists, setProcurementSpecialists] = useState<number>(1);

  // Realistic procurement calculations:
  // An experienced procurement specialist spends ~10-12 minutes per item position
  // (searching verified manufacturers, finding direct sales emails, checking certificates, drafting RFQ).
  // With TenderLex automated semantic extraction: ~2-3 minutes per entire specification.
  const totalItems = specsPerMonth * itemsPerSpec;
  const manualHours = Math.round((totalItems * 0.18 * procurementSpecialists) * 10) / 10;
  const tenderlexHours = Math.round((specsPerMonth * 0.04) * 10) / 10;
  const savedHours = Math.max(1, Math.round(manualHours - tenderlexHours));

  // Average procurement specialist hourly rate in RF: ~750 RUB/hour
  const savedBudget = Math.round(savedHours * 750);
  const speedMultiplier = 10;

  return (
    <div className="bg-gradient-to-br from-white via-teal-50/30 to-slate-50 rounded-3xl border-2 border-slate-200 p-6 sm:p-10 shadow-lg space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-100 text-teal-900 text-xs font-bold uppercase tracking-wider mb-2">
            <Calculator size={13} className="text-teal-700" />
            <span>Калькулятор эффективности снабжения</span>
          </div>
          <h3 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Расчет экономии времени отдела закупок
          </h3>
          <p className="text-sm text-slate-600 mt-1">
            Оцените сокращение рутины при поиске контактов заводов и проверке документации.
          </p>
        </div>

        <div className="flex items-center gap-2 bg-teal-100 text-teal-900 px-4 py-2 rounded-2xl border border-teal-200 font-bold text-xs shrink-0 self-start sm:self-auto">
          <Sparkles size={16} className="text-teal-700" />
          <span>Ускорение процессов в ~{speedMultiplier} раз</span>
        </div>
      </div>

      <div className="grid lg:grid-cols-12 gap-8 items-center">
        {/* Sliders Area */}
        <div className="lg:col-span-7 space-y-6">
          {/* Slider 1 */}
          <div className="space-y-2 bg-white p-4 rounded-2xl border border-slate-200 shadow-2xs">
            <div className="flex justify-between items-center text-sm font-bold text-slate-800">
              <span>Спецификаций и закупок в месяц:</span>
              <span className="text-teal-700 font-extrabold text-base bg-teal-50 px-3 py-0.5 rounded-lg border border-teal-200">
                {specsPerMonth} шт.
              </span>
            </div>
            <input
              type="range"
              min={3}
              max={100}
              step={1}
              value={specsPerMonth}
              onChange={(e) => setSpecsPerMonth(Number(e.target.value))}
              className="w-full accent-teal-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-400 font-medium">
              <span>3 шт.</span>
              <span>50 шт.</span>
              <span>100 шт.</span>
            </div>
          </div>

          {/* Slider 2 */}
          <div className="space-y-2 bg-white p-4 rounded-2xl border border-slate-200 shadow-2xs">
            <div className="flex justify-between items-center text-sm font-bold text-slate-800">
              <span>Среднее кол-во позиций в одном ТЗ:</span>
              <span className="text-teal-700 font-extrabold text-base bg-teal-50 px-3 py-0.5 rounded-lg border border-teal-200">
                {itemsPerSpec} поз.
              </span>
            </div>
            <input
              type="range"
              min={2}
              max={50}
              step={1}
              value={itemsPerSpec}
              onChange={(e) => setItemsPerSpec(Number(e.target.value))}
              className="w-full accent-teal-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-400 font-medium">
              <span>2 поз.</span>
              <span>25 поз.</span>
              <span>50 поз.</span>
            </div>
          </div>

          {/* Slider 3 */}
          <div className="space-y-2 bg-white p-4 rounded-2xl border border-slate-200 shadow-2xs">
            <div className="flex justify-between items-center text-sm font-bold text-slate-800">
              <span>Специалистов в отделе снабжения:</span>
              <span className="text-teal-700 font-extrabold text-base bg-teal-50 px-3 py-0.5 rounded-lg border border-teal-200">
                {procurementSpecialists} чел.
              </span>
            </div>
            <input
              type="range"
              min={1}
              max={10}
              step={1}
              value={procurementSpecialists}
              onChange={(e) => setProcurementSpecialists(Number(e.target.value))}
              className="w-full accent-teal-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-400 font-medium">
              <span>1 чел.</span>
              <span>5 чел.</span>
              <span>10 чел.</span>
            </div>
          </div>
        </div>

        {/* Results Card */}
        <div className="lg:col-span-5 bg-gradient-to-br from-emerald-50 via-teal-50/40 to-white text-slate-900 p-7 rounded-3xl shadow-xl border-2 border-emerald-300 space-y-6 flex flex-col justify-between">
          <div className="flex justify-between items-center">
            <span className="text-xs font-extrabold uppercase tracking-wider text-emerald-800 block">
              Прогнозируемый результат в месяц
            </span>
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-900 border border-emerald-200">
              ~10x быстрее
            </span>
          </div>

          <div className="space-y-5">
            <div className="border-b border-slate-200 pb-4">
              <div className="flex items-center gap-2 text-slate-600 text-xs font-bold mb-1">
                <Clock size={14} className="text-emerald-600" />
                <span>Экономия рабочего времени:</span>
              </div>
              <div className="text-3xl sm:text-4xl font-extrabold text-emerald-700">
                ~{savedHours} {savedHours === 1 ? "час" : savedHours < 5 ? "часа" : "часов"}
              </div>
              <span className="text-[11px] text-slate-500">
                вместо ручного сбора контактов и набора запросов КП
              </span>
            </div>

            <div>
              <div className="flex items-center gap-2 text-slate-600 text-xs font-bold mb-1">
                <DollarSign size={14} className="text-emerald-600" />
                <span>Экономия фонда оплаты труда:</span>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-slate-900">
                ~{savedBudget.toLocaleString("ru-RU")} ₽
              </div>
              <span className="text-[11px] text-slate-500">
                освобождение времени для работы с ценами и сделками
              </span>
            </div>
          </div>

          <a
            href="/cabinet"
            className="inline-flex items-center justify-center gap-2 w-full py-3.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs transition-all shadow-md shadow-emerald-600/20 hover:scale-[1.01]"
          >
            <span>Попробовать бесплатно</span>
            <ArrowRight size={14} />
          </a>
        </div>
      </div>
    </div>
  );
}
