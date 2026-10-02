"use client";

import { Mail, Phone, Building2, CheckCircle2, Copy, FileText, Send } from "lucide-react";
import { useState } from "react";

export function RfqPreviewWidget() {
  const [copied, setCopied] = useState(false);

  const [copyError, setCopyError] = useState(false);
  const requestText = "Добрый день!\nПросим предоставить коммерческое предложение:\n1. Кабель ВВГнг-LS 3х2.5 (ГОСТ 31996-2012) — 5 000 метров.\n2. Кабель ВВГнг-LS 5х4.0 (ГОСТ 31996-2012) — 2 400 метров.\nПросим указать наличие, цену с НДС, условия доставки и приложить паспорта качества.\nС уважением, отдел снабжения.";
  const handleCopy = async () => {
    setCopyError(false);
    try {
      await navigator.clipboard.writeText(requestText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { setCopyError(true); }
  };

  return (
    <div className="bg-white border-2 border-slate-200/90 rounded-2xl p-6 sm:p-8 text-slate-800 shadow-xl space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-6 border-b border-slate-200">
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-teal-800 bg-teal-100 px-2.5 py-1 rounded border border-teal-300 font-bold">
            Учебный пример результата
          </span>
          <h3 className="text-xl font-bold text-slate-900 font-bold mt-2">Выгрузка прямых контактов и сгенерированный Запрос КП</h3>
        </div>
        <button
          onClick={handleCopy}
          className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold rounded-lg border border-slate-300 shadow-2xs transition-colors flex items-center gap-1.5"
        >
          <Copy className="w-3.5 h-3.5" />
          {copied ? "Скопировано!" : copyError ? "Не удалось скопировать" : "Скопировать текст КП"}
        </button>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Contact Cards */}
        <div className="space-y-3">
          <p className="text-xs font-bold text-slate-700 font-bold uppercase tracking-wider">
            Пример структуры контактов (данные условные):
          </p>

          <div className="p-4 bg-slate-50/80 rounded-xl border border-slate-200 space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs font-bold text-slate-900 font-bold flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-teal-600" /> Производитель (учебный пример)
              </span>
              <span className="text-[10px] text-emerald-800 bg-emerald-100 border border-emerald-300 font-bold px-2 py-0.5 rounded font-mono">
                Завод-изготовитель
              </span>
            </div>
            <div className="text-xs text-slate-300 space-y-1 pt-1 border-t border-slate-200">
              <div className="flex items-center gap-2">
                <Mail className="w-3.5 h-3.5 text-teal-600 shrink-0" />
                <span className="font-mono text-teal-700 font-semibold">supplier@example.org</span>
                <span className="text-[10px] text-slate-600">(Отдел продаж)</span>
              </div>
              <div className="flex items-center gap-2">
                <Phone className="w-3.5 h-3.5 text-teal-600 shrink-0" />
                <span className="font-mono text-slate-800 font-semibold">Телефон уточняется</span>
                <span className="text-[10px] text-slate-600">(Прямой многоканальный)</span>
              </div>
            </div>
          </div>

          <div className="p-4 bg-slate-50/80 rounded-xl border border-slate-200 space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs font-bold text-slate-900 font-bold flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-teal-600" /> Дилер (учебный пример)
              </span>
              <span className="text-[10px] text-teal-800 bg-teal-100 border border-teal-300 font-bold px-2 py-0.5 rounded font-mono">
                Дилер — статус проверяется
              </span>
            </div>
            <div className="text-xs text-slate-300 space-y-1 pt-1 border-t border-slate-200">
              <div className="flex items-center gap-2">
                <Mail className="w-3.5 h-3.5 text-teal-600 shrink-0" />
                <span className="font-mono text-teal-700 font-semibold">dealer@example.org</span>
                <span className="text-[10px] text-slate-600">(Отдел оптовых закупок)</span>
              </div>
              <div className="flex items-center gap-2">
                <Phone className="w-3.5 h-3.5 text-teal-600 shrink-0" />
                <span className="font-mono text-slate-800 font-semibold">Телефон уточняется</span>
                <span className="text-[10px] text-slate-600">(Москва и ЦФО)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Pre-formatted Email Body */}
        <div className="bg-slate-50/90 p-4 rounded-xl border border-slate-200 space-y-3 font-sans text-xs">
          <div className="flex items-center justify-between border-b border-slate-200 pb-2">
            <span className="text-slate-700 font-semibold flex items-center gap-1.5 font-mono text-[11px]">
              <FileText className="w-3.5 h-3.5 text-teal-600" /> Тема: Запрос КП на поставку кабельной продукции
            </span>
            <span className="text-[10px] text-teal-600 font-mono">Сформировано ИИ</span>
          </div>

          <div className="text-slate-800 space-y-2 leading-relaxed font-mono text-[11px]">
            <p>Добрый день!</p>
            <p>Просим предоставить коммерческое предложение на следующую номенклатуру:</p>
            <div className="p-2.5 bg-white rounded-lg border border-slate-200 text-[11px] text-slate-900 font-mono shadow-2xs">
              1. Кабель ВВГнг-LS 3х2.5 (ГОСТ 31996-2012) — 5 000 метров<br />
              2. Кабель ВВГнг-LS 5х4.0 (ГОСТ 31996-2012) — 2 400 метров
            </div>
            <p>Просим указать: текущее наличие на складе, актуальную цену с НДС, условия доставки и приложить паспорта качества.</p>
            <p className="text-slate-600 font-semibold">С уважением, отдел снабжения.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
