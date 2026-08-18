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
      accent: "#059669",
      badge: "Шаг 1: Семантический парсинг",
      metrics: [
        { label: "Скорость распознавания", value: "2.4 сек" },
        { label: "Точность извлечения позиций", value: "99.4%" },
        { label: "Выделено требований", value: "14 параметров" },
      ],
      visualScene: (
        <div className="w-full h-full flex flex-col items-center justify-center p-4 sm:p-6 relative">
          <div className="relative w-full max-w-md bg-white/95 backdrop-blur-md rounded-2xl border-2 border-emerald-100 p-6 shadow-xl shadow-emerald-950/5 text-slate-800">
            <div className="flex items-center justify-between border-b border-emerald-100 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-rose-400" />
                <div className="w-3 h-3 rounded-full bg-amber-400" />
                <div className="w-3 h-3 rounded-full bg-emerald-500" />
                <span className="text-xs font-mono ml-2 font-semibold text-slate-700">
                  ТЗ_Закупка_Кабель_и_Трубы.pdf
                </span>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200">
                44-ФЗ
              </span>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="p-3 bg-emerald-50/50 rounded-xl border border-emerald-200/80 text-slate-800">
                <div className="text-[11px] text-slate-500 mb-1">Позиция 1 (распознано):</div>
                <div className="font-bold text-emerald-900">
                  Кабель ВВГнг(А)-LS 3х2.5 ок (N, PE) - 0.66кВ
                </div>
                <div className="text-[10px] mt-1.5 flex gap-2">
                  <span className="px-2 py-0.5 rounded font-sans font-semibold bg-white border border-emerald-200 text-emerald-900">
                    ГОСТ 31996-2012
                  </span>
                  <span className="px-2 py-0.5 rounded font-sans font-semibold bg-white border border-emerald-200 text-emerald-900">
                    5 000 метров
                  </span>
                </div>
              </div>

              <div className="p-3 bg-emerald-50/50 rounded-xl border border-emerald-200/80 text-slate-800">
                <div className="text-[11px] text-slate-500 mb-1">Позиция 2 (распознано):</div>
                <div className="font-bold text-emerald-900">
                  Труба профильная 80х80х4 ст3сп
                </div>
                <div className="text-[10px] mt-1.5 flex gap-2">
                  <span className="px-2 py-0.5 rounded font-sans font-semibold bg-white border border-emerald-200 text-emerald-900">
                    ГОСТ 8639-82
                  </span>
                  <span className="px-2 py-0.5 rounded font-sans font-semibold bg-white border border-emerald-200 text-emerald-900">
                    24.5 тонн
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-emerald-100 flex items-center justify-between text-xs text-slate-600">
              <span className="flex items-center gap-1.5 font-bold text-emerald-700">
                <Sparkles className="w-3.5 h-3.5 text-emerald-600 animate-pulse" /> Спецификация структурирована
              </span>
              <span className="font-mono font-bold text-slate-700">100% готовность</span>
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
      accent: "#059669",
      badge: "Шаг 2: Экспресс-аудит безопасности",
      metrics: [
        { label: "Сверка штрафов", value: "ПП РФ № 1042" },
        { label: "Нацрежим / Реестр", value: "ПП 616 / 617" },
        { label: "Оценка риска заявки", value: "Безопасно" },
      ],
      visualScene: (
        <div className="w-full h-full flex flex-col items-center justify-center p-4 sm:p-6 relative">
          <div className="relative w-full max-w-md bg-white/95 backdrop-blur-md rounded-2xl border-2 border-emerald-100 p-6 shadow-xl shadow-emerald-950/5 text-slate-800">
            <div className="flex items-center justify-between border-b border-emerald-100 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span className="text-xs font-bold text-slate-900">
                  Отчет экспресс-аудита рисков
                </span>
              </div>
              <span className="text-[10px] bg-emerald-50 text-emerald-800 font-bold px-2 py-0.5 rounded border border-emerald-200">
                Индекс риска: 15% (Низкий)
              </span>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="p-3 bg-amber-50/90 rounded-xl border border-amber-200 text-amber-950 flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-[11px]">Срок поставки: 7 календарных дней</div>
                  <div className="text-[10px] text-amber-900/80 mt-0.5">
                    Требуется подтвержденный складской запас у дилера перед подачей заявки.
                  </div>
                </div>
              </div>

              <div className="p-3 bg-emerald-50/90 rounded-xl border border-emerald-200 text-emerald-950 flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-[11px]">Штрафы соответствуют ПП № 1042</div>
                  <div className="text-[10px] text-emerald-900/80 mt-0.5">
                    Неправомерных штрафных санкций и кабальных условий не выявлено.
                  </div>
                </div>
              </div>

              <div className="p-3 bg-teal-50/90 rounded-xl border border-teal-200 text-teal-950 flex items-start gap-2.5">
                <Building2 className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-[11px]">Реестр Минпромторга (ПП 616/617)</div>
                  <div className="text-[10px] text-teal-900/80 mt-0.5">
                    Ограничений допуска нет. Разрешена поставка аналогов с сертификатом ГОСТ.
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-emerald-100 flex items-center justify-between text-xs text-slate-600">
              <span>Правовая проверка завершена</span>
              <span className="text-emerald-700 font-bold">Допуск к торгам: Рекомендован</span>
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
      accent: "#059669",
      badge: "Шаг 3: Федеральный скан поставщиков",
      metrics: [
        { label: "База предприятий", value: "350 000+ заводов" },
        { label: "Регионы охвата", value: "89 субъектов РФ" },
        { label: "Исключение наценок", value: "Прямой сбыт" },
      ],
      visualScene: (
        <div className="w-full h-full flex flex-col items-center justify-center p-4 sm:p-6 relative">
          <div className="relative w-full max-w-md bg-white/95 backdrop-blur-md rounded-2xl border-2 border-emerald-100 p-6 shadow-xl shadow-emerald-950/5 text-slate-800">
            <div className="flex items-center justify-between border-b border-emerald-100 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4 text-emerald-600" />
                <span className="text-xs font-bold text-slate-900">
                  Найденные производители и дилеры
                </span>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-900 border border-emerald-200">
                12 прямых контактов
              </span>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3.5 bg-emerald-50/50 rounded-xl border border-emerald-200 text-slate-800">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold flex items-center gap-1.5 text-slate-900">
                    <Factory className="w-3.5 h-3.5 text-emerald-700" /> ООО &quot;Кавказкабель&quot;
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded font-bold bg-emerald-100 text-emerald-900 border border-emerald-300">
                    Завод-изготовитель
                  </span>
                </div>
                <div className="text-[11px] text-slate-600">
                  Россия, КБР (Прямой выпуск по ГОСТ 31996)
                </div>
                <div className="mt-2.5 pt-2 border-t border-emerald-200/80 flex items-center justify-between text-[11px]">
                  <span className="font-mono font-bold text-emerald-700">sales@kavkazkabel.ru</span>
                  <span className="font-mono text-slate-700">+7 (866) 240-77-11</span>
                </div>
              </div>

              <div className="p-3.5 bg-emerald-50/50 rounded-xl border border-emerald-200 text-slate-800">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold flex items-center gap-1.5 text-slate-900">
                    <Building2 className="w-3.5 h-3.5 text-teal-700" /> ООО &quot;Севкабель-Дистрибуция&quot;
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded font-bold bg-teal-100 text-teal-900 border border-teal-300">
                    Официальный дилер
                  </span>
                </div>
                <div className="text-[11px] text-slate-600">
                  Москва (Центральный распределительный склад)
                </div>
                <div className="mt-2.5 pt-2 border-t border-emerald-200/80 flex items-center justify-between text-[11px]">
                  <span className="font-mono font-bold text-emerald-700">msk@sevkabel.ru</span>
                  <span className="font-mono text-slate-700">+7 (495) 120-44-88</span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-emerald-100 flex items-center justify-between text-xs text-slate-600">
              <span>Сортировка по логистике</span>
              <span className="font-bold text-emerald-700">Охват 100% позиций</span>
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
      accent: "#059669",
      badge: "Шаг 4: Автоматизация запросов цен",
      metrics: [
        { label: "Время составления RFQ", value: "Мгновенно" },
        { label: "Адресатов в рассылке", value: "до 15 компаний" },
        { label: "Средний отклик", value: "от 40 минут" },
      ],
      visualScene: (
        <div className="w-full h-full flex flex-col items-center justify-center p-4 sm:p-6 relative">
          <div className="relative w-full max-w-md bg-white/95 backdrop-blur-md rounded-2xl border-2 border-emerald-100 p-6 shadow-xl shadow-emerald-950/5 text-slate-800">
            <div className="flex items-center justify-between border-b border-emerald-100 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-emerald-600" />
                <span className="text-xs font-bold text-slate-900">
                  Автоматически сгенерированный Запрос КП
                </span>
              </div>
              <span className="text-[10px] bg-emerald-100 text-emerald-900 font-bold px-2 py-0.5 rounded border border-emerald-200">
                Готов к отправке
              </span>
            </div>

            <div className="p-3.5 bg-emerald-50/50 rounded-xl border border-emerald-200 text-xs font-sans space-y-2 leading-relaxed text-slate-700">
              <div className="font-bold text-slate-900">
                Тема: Запрос коммерческого предложения: Кабель ВВГнг-LS и трубы (ТЗ №24-08/1)
              </div>
              <div className="text-[11px] text-slate-600">
                «Здравствуйте! Просим выставить КП на поставку позиций согласно спецификации:
              </div>
              <div className="p-2.5 bg-white rounded-lg border border-emerald-200 text-[11px] font-mono text-emerald-950">
                1. Кабель ВВГнг(А)-LS 3х2.5 (ГОСТ 31996) — 5 000 м<br />
                2. Труба профильная 80х80х4 ст3сп (ГОСТ 8639) — 24.5 т
              </div>
              <div className="text-[11px] text-slate-600">
                Просим указать: цены с НДС, склад отгрузки, срок изготовления и условия оплаты.»
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-emerald-100 flex items-center justify-between text-xs text-slate-600">
              <span className="flex items-center gap-1.5 text-emerald-800 font-bold">
                <Send className="w-3.5 h-3.5 text-emerald-600" /> 8 адресатов выбрано
              </span>
              <span className="font-bold text-slate-800">Экспорт в 1 клик</span>
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
      accent: "#059669",
      badge: "Финал: Успешная сдача и маржа",
      metrics: [
        { label: "Экономия бюджета", value: "до 22%" },
        { label: "Сокращение времени поиска", value: "в 10 раз" },
        { label: "Защита от штрафов", value: "100%" },
      ],
      visualScene: (
        <div className="w-full h-full flex flex-col items-center justify-center p-4 sm:p-6 relative">
          <div className="relative w-full max-w-md bg-gradient-to-br from-emerald-50 via-white to-teal-50 rounded-3xl border-2 border-emerald-400 p-7 shadow-xl shadow-emerald-950/5 text-center overflow-hidden">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center justify-center mb-4 shadow-sm">
              <Sparkles className="w-7 h-7 text-emerald-700" />
            </div>

            <span className="text-[11px] font-bold uppercase tracking-widest px-3 py-1 rounded-full border bg-emerald-100 text-emerald-900 border-emerald-300">
              Контракт защищен и укомплектован
            </span>

            <h3 className="text-2xl font-black mt-3 mb-2 tracking-tight text-slate-900">
              Экономия 412 000 ₽ на партии
            </h3>

            <p className="text-xs leading-relaxed max-w-xs mx-auto mb-6 text-slate-600">
              Прямой контакт с заводом позволил снизить закупочную цену на 18.4% ниже НМЦК без риска срыва сроков.
            </p>

            <div className="space-y-2.5">
              <Button
                asChild
                size="lg"
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold h-12 text-sm shadow-md shadow-emerald-600/20 rounded-xl"
              >
                <Link href="/cabinet">
                  <Sparkles className="w-4 h-4 mr-2" />
                  Попробовать бесплатно на своем ТЗ
                </Link>
              </Button>

              <Button
                asChild
                variant="ghost"
                size="default"
                className="w-full text-xs text-slate-600 hover:text-slate-900 hover:bg-emerald-50/50"
              >
                <a href="https://t.me/tenderlex_bot" target="_blank" rel="noreferrer">
                  <Send className="w-3.5 h-3.5 mr-1.5 text-emerald-700" />
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
    <div className="relative w-full bg-white text-slate-800 rounded-3xl border-2 border-emerald-100 shadow-xl shadow-emerald-950/5 overflow-hidden">
      {/* Top Bar inside the interactive block */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-emerald-100 bg-emerald-50/60 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-white border border-emerald-200 text-emerald-900 text-xs font-bold shadow-2xs">
            <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
            <span>Пошаговый процесс закупки</span>
          </div>
          <span className="text-emerald-300 text-xs hidden sm:inline">•</span>
          <span className="text-slate-600 text-xs hidden sm:inline font-medium">
            От загрузки сырого ТЗ до прямого контакта с заводами
          </span>
        </div>

        {/* Navigation pills */}
        <div className="flex items-center gap-1.5 p-1 bg-white rounded-xl border border-emerald-200 shadow-2xs">
          {sections.map((sec, idx) => (
            <button
              key={sec.id}
              onClick={() => handleScrollToSection(idx)}
              className={`px-3 py-1 text-xs font-bold rounded-lg transition-all ${
                activeSection === idx
                  ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/20 scale-105"
                  : "text-slate-600 hover:text-emerald-900 hover:bg-emerald-50"
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
        <div className="lg:col-span-5 p-6 sm:p-10 flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-emerald-100 bg-gradient-to-b from-white via-emerald-50/20 to-slate-50 text-slate-800">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs font-bold">
              <span className="w-2 h-2 rounded-full bg-emerald-600" />
              <span>{current.badge}</span>
            </div>

            <div className="text-[11px] font-mono tracking-widest uppercase text-emerald-700 font-extrabold">
              ЭТАП {current.stepNum} ИЗ 05 — {current.eyebrow}
            </div>

            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 leading-tight tracking-tight">
              {current.title}
            </h2>

            <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
              {current.body}
            </p>

            {/* Tags */}
            <div className="flex flex-wrap gap-2 pt-2">
              {current.tags.map((tag, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-white text-slate-700 border border-emerald-200/80 shadow-2xs flex items-center gap-1.5"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  {tag}
                </span>
              ))}
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-3 gap-2.5 pt-4 border-t border-emerald-100">
              {current.metrics.map((m, i) => (
                <div key={i} className="p-2.5 rounded-xl bg-white border border-emerald-100 shadow-2xs">
                  <div className="text-xs font-black text-emerald-700">{m.value}</div>
                  <div className="text-[10px] mt-0.5 leading-tight text-slate-500 font-medium">{m.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Stepper Navigation Controls */}
          <div className="pt-8 flex items-center justify-between border-t border-emerald-100 mt-6">
            <div className="flex gap-2">
              <button
                onClick={() => handleScrollToSection(Math.max(0, activeSection - 1))}
                disabled={activeSection === 0}
                className="px-3.5 py-2 text-xs font-bold rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 disabled:opacity-40 disabled:pointer-events-none transition-all shadow-2xs"
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
                className="px-4 py-2 text-xs font-bold rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20 disabled:opacity-40 disabled:pointer-events-none transition-all flex items-center gap-1.5"
              >
                <span>Далее</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="text-xs font-mono text-slate-500">
              Кликайте шаги 01–05
            </div>
          </div>
        </div>

        {/* Right Column: 3D Stage / Visual Scene */}
        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="lg:col-span-7 bg-emerald-50/30 relative flex items-center justify-center overflow-y-auto p-4 sm:p-8"
        >
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#05966910_1px,transparent_1px),linear-gradient(to_bottom,#05966910_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none" />

          {/* Active Visual Container */}
          <div className="relative w-full max-w-xl transition-all duration-300 ease-out transform">
            {current.visualScene}
          </div>
        </div>
      </div>

      {/* Bottom Progress Bar */}
      <div className="h-1.5 bg-emerald-100 w-full">
        <div
          className="h-full bg-gradient-to-r from-emerald-500 via-teal-500 to-emerald-600 transition-all duration-200"
          style={{ width: `${((activeSection + 1) / sections.length) * 100}%` }}
        />
      </div>
    </div>
  );
}
