"use client";

import React, { useRef, useState } from "react";
import Link from "next/link";
import {
  FileText,
  Search,
  Building2,
  ShieldCheck,
  Send,
  ArrowRight,
  Sparkles,
  Layers,
  ChevronDown,
  CheckCircle2,
  AlertTriangle,
  Factory,
  Mail,
  Phone,
  BarChart3,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export interface ScrollWorldSection {
  id: string;
  label: string;
  stepNum: string;
  eyebrow: string;
  title: string;
  body: string;
  tags: string[];
  accent: string;
  badge: string;
  metrics: { label: string; value: string }[];
  visualScene: React.ReactNode;
}

export function ScrollWorldViewer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [activeSection, setActiveSection] = useState(0);

  const sections: ScrollWorldSection[] = [
    {
      id: "raw_tz",
      label: "1. ТЗ и спецификация",
      stepNum: "01",
      eyebrow: "ИСХОДНЫЙ ДОКУМЕНТ",
      title: "Загрузка сложного ТЗ или сметы",
      body: "Система мгновенно принимает PDF, Word или Excel любого объема. Нейросеть распознает номенклатуру, вычленяет маркоразмеры, ГОСТы, чертежи и скрытые технические требования заказчика.",
      tags: ["Парсинг 44-ФЗ / 223-ФЗ", "Любые форматы (PDF, Excel, Docx)", "Извлечение ГОСТ и марок"],
      accent: "#0d9488", // teal-600
      badge: "Шаг 1: Семантический парсинг",
      metrics: [
        { label: "Скорость распознавания", value: "2.4 сек" },
        { label: "Точность извлечения позиций", value: "99.4%" },
        { label: "Выделено требований", value: "14 параметров" },
      ],
      visualScene: (
        <div className="w-full h-full flex flex-col items-center justify-center p-6 relative">
          <div className="relative w-full max-w-md bg-slate-900/90 backdrop-blur-md rounded-2xl border border-teal-500/30 p-6 shadow-2xl shadow-teal-950/50 text-white overflow-hidden">
            <div className="absolute -top-12 -right-12 w-36 h-36 bg-teal-500/20 rounded-full blur-2xl pointer-events-none" />
            
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-rose-500/80" />
                <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                <span className="text-xs font-mono text-slate-400 ml-2">ТЗ_Закупка_Кабель_и_Трубы.pdf</span>
              </div>
              <span className="text-[10px] bg-teal-500/20 text-teal-300 font-bold px-2 py-0.5 rounded border border-teal-500/30">
                44-ФЗ
              </span>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                <div className="text-slate-400 text-[11px] mb-1">Позиция 1 (распознано):</div>
                <div className="text-teal-300 font-bold">Кабель ВВГнг(А)-LS 3х2.5 ок (N, PE) - 0.66кВ</div>
                <div className="text-slate-400 text-[10px] mt-1 flex gap-2">
                  <span className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">ГОСТ 31996-2012</span>
                  <span className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">5 000 метров</span>
                </div>
              </div>

              <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                <div className="text-slate-400 text-[11px] mb-1">Позиция 2 (распознано):</div>
                <div className="text-teal-300 font-bold">Труба профильная 80х80х4 ст3сп</div>
                <div className="text-slate-400 text-[10px] mt-1 flex gap-2">
                  <span className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">ГОСТ 8639-82</span>
                  <span className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">24.5 тонн</span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
              <span className="flex items-center gap-1.5 text-emerald-400">
                <Sparkles className="w-3.5 h-3.5 animate-spin" style={{ animationDuration: "3s" }} /> Спецификация структурирована
              </span>
              <span className="font-mono">100% готовность</span>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "ai_risk_lab",
      label: "2. Аудит рисков 44-ФЗ",
      stepNum: "02",
      eyebrow: "ЛАБОРАТОРИЯ АНАЛИЗА",
      title: "Аудит ловушек, штрафов и Минпромторга",
      body: "Автоматическая юридическая сверка проекта контракта: проверка на скрытые штрафы (ПП РФ № 1042), нереалистичные сроки поставки (3–5 дней), требования нацрежима (ПП 616/617) и риски попадания в РНП.",
      tags: ["Защита от РНП", "Сверка со ст. 34 44-ФЗ", "Проверка реестра Минпромторга"],
      accent: "#e11d48", // rose-600
      badge: "Шаг 2: Экспресс-аудит безопасности",
      metrics: [
        { label: "Сверка штрафов", value: "ПП РФ № 1042" },
        { label: "Нацрежим / Реестр", value: "ПП 616 / 617" },
        { label: "Оценка риска заявки", value: "Безопасно" },
      ],
      visualScene: (
        <div className="w-full h-full flex flex-col items-center justify-center p-6 relative">
          <div className="relative w-full max-w-md bg-slate-900/90 backdrop-blur-md rounded-2xl border border-rose-500/30 p-6 shadow-2xl shadow-rose-950/50 text-white overflow-hidden">
            <div className="absolute -top-12 -right-12 w-36 h-36 bg-rose-500/20 rounded-full blur-2xl pointer-events-none" />

            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-rose-400" />
                <span className="text-xs font-bold text-slate-200">Отчет экспресс-аудита рисков</span>
              </div>
              <span className="text-[10px] bg-rose-500/20 text-rose-300 font-bold px-2 py-0.5 rounded border border-rose-500/30">
                Индекс риска: 15% (Низкий)
              </span>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="p-3 bg-amber-950/30 rounded-xl border border-amber-500/30 text-amber-200 flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-[11px] text-amber-300">Срок поставки: 7 календарных дней</div>
                  <div className="text-[10px] text-amber-200/80 mt-0.5">Требуется подтвержденный складской запас у дилера перед подачей заявки.</div>
                </div>
              </div>

              <div className="p-3 bg-emerald-950/30 rounded-xl border border-emerald-500/30 text-emerald-200 flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-[11px] text-emerald-300">Штрафы соответствуют ПП № 1042</div>
                  <div className="text-[10px] text-emerald-200/80 mt-0.5">Неправомерных штрафных санкций и кабальных условий не выявлено.</div>
                </div>
              </div>

              <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-slate-300 flex items-start gap-2.5">
                <Building2 className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-[11px] text-teal-300">Реестр Минпромторга (ПП 616/617)</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">Ограничений допуска нет. Разрешена поставка аналогов с сертификатом ГОСТ.</div>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
              <span>Правовая проверка завершена</span>
              <span className="text-emerald-400 font-bold">Допуск к торгам: Рекомендован</span>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "supplier_radar",
      label: "3. Радар заводов и дилеров",
      stepNum: "03",
      eyebrow: "ГЕО-РАДАР ПОСТАВЩИКОВ",
      title: "Поиск производителей и дилеров по всей РФ",
      body: "Алгоритм опрашивает федеральную базу производственных предприятий и дистрибьюторов. Извлекаются прямые контакты отделов сбыта, коммерческих директоров и персональных менеджеров без перекупщиков.",
      tags: ["Прямые заводы РФ", "Официальные дилеры", "Телефоны и email сбыта"],
      accent: "#2563eb", // blue-600
      badge: "Шаг 3: Федеральный скан поставщиков",
      metrics: [
        { label: "База предприятий", value: "350 000+ заводов" },
        { label: "Регионы охвата", value: "89 субъектов РФ" },
        { label: "Исключение наценок", value: "Прямой сбыт" },
      ],
      visualScene: (
        <div className="w-full h-full flex flex-col items-center justify-center p-6 relative">
          <div className="relative w-full max-w-md bg-slate-900/90 backdrop-blur-md rounded-2xl border border-blue-500/30 p-6 shadow-2xl shadow-blue-950/50 text-white overflow-hidden">
            <div className="absolute -top-12 -right-12 w-36 h-36 bg-blue-500/20 rounded-full blur-2xl pointer-events-none" />

            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4 text-blue-400" />
                <span className="text-xs font-bold text-slate-200">Найденные производители и дилеры</span>
              </div>
              <span className="text-[10px] bg-blue-500/20 text-blue-300 font-bold px-2 py-0.5 rounded border border-blue-500/30">
                12 прямых контактов
              </span>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 bg-slate-950/80 rounded-xl border border-blue-500/30 relative">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-slate-100 flex items-center gap-1.5">
                    <Factory className="w-3.5 h-3.5 text-blue-400" /> ООО &quot;Кавказкабель&quot;
                  </span>
                  <span className="text-[10px] bg-teal-500/20 text-teal-300 px-1.5 py-0.5 rounded font-bold">
                    Завод-изготовитель
                  </span>
                </div>
                <div className="text-[11px] text-slate-400">Россия, КБР (Прямой выпуск по ГОСТ 31996)</div>
                <div className="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                  <span className="text-blue-300 font-mono">sales@kavkazkabel.ru</span>
                  <span className="text-slate-300 font-mono">+7 (866) 240-77-11</span>
                </div>
              </div>

              <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800 relative">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-slate-100 flex items-center gap-1.5">
                    <Building2 className="w-3.5 h-3.5 text-amber-400" /> ООО &quot;Севкабель-Дистрибуция&quot;
                  </span>
                  <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded font-bold">
                    Официальный дилер
                  </span>
                </div>
                <div className="text-[11px] text-slate-400">Москва (Центральный распределительный склад)</div>
                <div className="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                  <span className="text-blue-300 font-mono">msk@sevkabel.ru</span>
                  <span className="text-slate-300 font-mono">+7 (495) 120-44-88</span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
              <span>Сортировка по логистическому плечу</span>
              <span className="text-blue-400 font-bold">Охват 100% позиций</span>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "rfq_dispatch",
      label: "4. Генерация Запросов КП (RFQ)",
      stepNum: "04",
      eyebrow: "АВТО-ГЕНЕРАТОР ЗАПРОСОВ",
      title: "Формирование и веерная рассылка запросов цен",
      body: "Платформа автоматически генерирует профессиональное официальное письмо-запрос с подробной номенклатурной таблицей, объемами партии, условиями доставки и запросом сертификатов качества.",
      tags: ["Официальный бланк RFQ", "Веерный запрос КП", "Таблица с ГОСТами"],
      accent: "#7c3aed", // violet-600
      badge: "Шаг 4: Автоматизация запросов цен",
      metrics: [
        { label: "Время составления RFQ", value: "Мгновенно" },
        { label: "Адресатов в рассылке", value: "до 15 компаний" },
        { label: "Средний отклик", value: "от 40 минут" },
      ],
      visualScene: (
        <div className="w-full h-full flex flex-col items-center justify-center p-6 relative">
          <div className="relative w-full max-w-md bg-slate-900/90 backdrop-blur-md rounded-2xl border border-violet-500/30 p-6 shadow-2xl shadow-violet-950/50 text-white overflow-hidden">
            <div className="absolute -top-12 -right-12 w-36 h-36 bg-violet-500/20 rounded-full blur-2xl pointer-events-none" />

            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-violet-400" />
                <span className="text-xs font-bold text-slate-200">Автоматически сгенерированный Запрос КП</span>
              </div>
              <span className="text-[10px] bg-violet-500/20 text-violet-300 font-bold px-2 py-0.5 rounded border border-violet-500/30">
                Готов к отправке
              </span>
            </div>

            <div className="p-3.5 bg-slate-950/80 rounded-xl border border-violet-500/30 text-xs font-sans space-y-2 text-slate-300 leading-relaxed">
              <div className="font-bold text-slate-100">
                Тема: Запрос коммерческого предложения: Кабель ВВГнг-LS и трубы (ТЗ №24-08/1)
              </div>
              <div className="text-[11px] text-slate-400">
                «Здравствуйте! Просим выставить КП на поставку позиций согласно спецификации:
              </div>
              <div className="bg-slate-900 p-2 rounded border border-slate-800 text-[11px] font-mono text-violet-200">
                1. Кабель ВВГнг(А)-LS 3х2.5 (ГОСТ 31996) — 5 000 м<br />
                2. Труба профильная 80х80х4 ст3сп (ГОСТ 8639) — 24.5 т
              </div>
              <div className="text-[11px] text-slate-400">
                Просим указать: цены с НДС, склад отгрузки, срок изготовления и условия оплаты.»
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
              <span className="flex items-center gap-1.5 text-violet-400">
                <Send className="w-3.5 h-3.5" /> 8 адресатов выбрано
              </span>
              <span className="text-slate-300 font-bold">Экспорт в 1 клик</span>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "won_contract",
      label: "5. Выигранный контракт и экономия",
      stepNum: "05",
      eyebrow: "ФИНАЛЬНЫЙ РЕЗУЛЬТАТ",
      title: "Победа в тендере с маржинальностью +18%",
      body: "Вы получаете актуальные оптовые цены напрямую с заводов, снижаете себестоимость закупки, исключаете риски штрафов и выигрываете контракт с максимальной прибылью.",
      tags: ["Экономия до 22% на закупке", "100% соблюдение ГОСТ", "Готовый комплект документов"],
      accent: "#059669", // emerald-600
      badge: "Финал: Успешная сдача и маржа",
      metrics: [
        { label: "Экономия бюджета", value: "до 22%" },
        { label: "Сокращение времени поиска", value: "в 10 раз" },
        { label: "Защита от штрафов", value: "100%" },
      ],
      visualScene: (
        <div className="w-full h-full flex flex-col items-center justify-center p-6 relative">
          <div className="relative w-full max-w-md bg-gradient-to-br from-slate-900 via-teal-950/80 to-slate-900 rounded-3xl border-2 border-emerald-500/50 p-7 shadow-2xl shadow-emerald-950/60 text-white text-center overflow-hidden">
            <div className="absolute inset-0 bg-radial from-emerald-500/10 via-transparent to-transparent pointer-events-none" />

            <div className="w-14 h-14 mx-auto rounded-2xl bg-emerald-500/20 border border-emerald-400/40 text-emerald-400 flex items-center justify-center mb-4 shadow-lg shadow-emerald-950">
              <Sparkles className="w-7 h-7" />
            </div>

            <span className="text-[11px] font-bold uppercase tracking-widest text-emerald-400 bg-emerald-950/60 border border-emerald-500/30 px-3 py-1 rounded-full">
              Контракт защищен и укомплектован
            </span>

            <h3 className="text-2xl font-black mt-3 mb-2 text-white tracking-tight">
              Экономия 412 000 ₽ на партии
            </h3>

            <p className="text-xs text-slate-300 leading-relaxed max-w-xs mx-auto mb-6">
              Прямой контакт с заводом позволил снизить закупочную цену на 18.4% ниже НМЦК без риска срыва сроков.
            </p>

            <div className="space-y-2.5">
              <Button asChild size="lg" className="w-full bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-extrabold h-12 shadow-lg shadow-emerald-500/20 text-sm">
                <a href="/cabinet">
                  <Sparkles className="w-4 h-4 mr-2" />
                  Попробовать бесплатно на своем ТЗ
                </a>
              </Button>

              <Button asChild variant="ghost" size="default" className="w-full text-slate-300 hover:text-white hover:bg-slate-800/60 text-xs">
                <a href="https://t.me/tenderlex_bot" target="_blank" rel="noreferrer">
                  <Send className="w-3.5 h-3.5 mr-1.5 text-teal-400" />
                  Открыть в Telegram @tenderlex_bot
                </a>
              </Button>
            </div>
          </div>
        </div>
      ),
    },
  ];

  const current = sections[activeSection];

  const handleScrollToSection = (idx: number) => {
    setActiveSection(idx);
    const container = containerRef.current;
    if (container) {
      const sectionHeight = container.scrollHeight / sections.length;
      container.scrollTo({
        top: idx * sectionHeight,
        behavior: "smooth",
      });
    }
  };

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    const totalScroll = target.scrollHeight - target.clientHeight;
    if (totalScroll <= 0) return;
    const progress = target.scrollTop / totalScroll;
    setScrollProgress(progress);
    const newIdx = Math.min(
      sections.length - 1,
      Math.floor(progress * sections.length + 0.15)
    );
    setActiveSection(newIdx);
  };

  return (
    <div className="relative w-full bg-slate-950 text-slate-100 rounded-3xl border border-slate-800 shadow-2xl overflow-hidden">
      {/* Top Bar inside the interactive block */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-teal-500/10 border border-teal-500/30 text-teal-400 text-xs font-bold">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Интерактивный WOW-сценарий</span>
          </div>
          <span className="text-slate-500 text-xs hidden sm:inline">•</span>
          <span className="text-slate-400 text-xs hidden sm:inline">
            Путь заявки: от сырого ТЗ до прямой поставки и маржи
          </span>
        </div>

        {/* Navigation pills */}
        <div className="flex items-center gap-1.5">
          {sections.map((sec, idx) => (
            <button
              key={sec.id}
              onClick={() => handleScrollToSection(idx)}
              className={`px-3 py-1 text-xs font-bold rounded-lg transition-all ${
                activeSection === idx
                  ? "bg-teal-500 text-slate-950 shadow-md shadow-teal-500/20 scale-105"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              {sec.stepNum}
            </button>
          ))}
        </div>
      </div>

      {/* Main Interactive Stage */}
      <div className="grid lg:grid-cols-12 min-h-[580px] lg:min-h-[640px] items-stretch">
        {/* Left Column: Context & Explanations */}
        <div className="lg:col-span-5 p-6 sm:p-10 flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-slate-800/80 bg-gradient-to-b from-slate-900/40 via-slate-950 to-slate-900/40">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-slate-300 text-xs font-semibold">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: current.accent }}
              />
              <span className="text-slate-200">{current.badge}</span>
            </div>

            <div className="text-[11px] font-mono tracking-widest text-slate-400 uppercase">
              ЭТАП {current.stepNum} ИЗ 05 — {current.eyebrow}
            </div>

            <h2 className="text-2xl sm:text-3xl font-extrabold text-white leading-tight tracking-tight">
              {current.title}
            </h2>

            <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
              {current.body}
            </p>

            {/* Tags */}
            <div className="flex flex-wrap gap-2 pt-2">
              {current.tags.map((tag, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 text-xs font-medium bg-slate-900/80 text-slate-300 rounded-lg border border-slate-800 flex items-center gap-1.5"
                >
                  <CheckCircle2 className="w-3 h-3 text-teal-400" />
                  {tag}
                </span>
              ))}
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-3 gap-2.5 pt-4 border-t border-slate-800/80">
              {current.metrics.map((m, i) => (
                <div key={i} className="p-2.5 bg-slate-900/60 rounded-xl border border-slate-800">
                  <div className="text-xs font-black text-teal-400">{m.value}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5 leading-tight">{m.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Stepper Navigation Controls */}
          <div className="pt-8 flex items-center justify-between border-t border-slate-800/80 mt-6">
            <div className="flex gap-2">
              <button
                onClick={() => handleScrollToSection(Math.max(0, activeSection - 1))}
                disabled={activeSection === 0}
                className="px-3.5 py-2 text-xs font-bold rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:pointer-events-none transition-all"
              >
                Назад
              </button>
              <button
                onClick={() =>
                  handleScrollToSection(
                    Math.min(sections.length - 1, activeSection + 1)
                  )
                }
                disabled={activeSection === sections.length - 1}
                className="px-4 py-2 text-xs font-bold rounded-xl bg-teal-600 hover:bg-teal-500 text-white shadow-md shadow-teal-600/20 disabled:opacity-40 disabled:pointer-events-none transition-all flex items-center gap-1.5"
              >
                <span>Далее</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="text-xs text-slate-500 font-mono">
              Скролльте или кликайте шаги
            </div>
          </div>
        </div>

        {/* Right Column: 3D Stage / Diorama Visual Preview */}
        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="lg:col-span-7 bg-slate-950 relative flex items-center justify-center overflow-y-auto p-4 sm:p-8"
        >
          {/* Ambient Lighting & Grid */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b15_1px,transparent_1px),linear-gradient(to_bottom,#1e293b15_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none" />
          <div className="absolute inset-0 bg-radial from-teal-500/5 via-transparent to-transparent pointer-events-none" />

          {/* Active 3D Rendered Mockup Container */}
          <div className="relative w-full max-w-xl transition-all duration-300 ease-out transform">
            {current.visualScene}
          </div>
        </div>
      </div>

      {/* Bottom Progress Bar */}
      <div className="h-1 bg-slate-800 w-full">
        <div
          className="h-full bg-gradient-to-r from-teal-500 via-blue-500 to-emerald-500 transition-all duration-150"
          style={{ width: `${((activeSection + 1) / sections.length) * 100}%` }}
        />
      </div>
    </div>
  );
}
