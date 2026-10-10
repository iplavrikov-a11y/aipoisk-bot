"use client";

import { useState } from "react";
import { Check, Copy, Terminal, Code2, Cpu } from "lucide-react";

type CodeLang = "curl" | "python" | "nodejs" | "1c";

const CODE_EXAMPLES: Record<CodeLang, { label: string; icon: string; code: string }> = {
  curl: {
    label: "cURL",
    icon: "terminal",
    code: `# 1. Поиск поставщиков по ТЗ
curl -X POST https://tenderlex.ru/api/v1/mcp/suppliers/search \\
  -H "Authorization: Bearer tl_live_YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "specification": "Кабель ВВГнг-LS 3х2.5 ГОСТ 31996-2012, 1200 м",
    "city": "Москва",
    "target_count": 5,
    "search_policy": "minprom_registry_priority"
  }'

# 2. Подбор товара и аналогов по ТЗ
curl -X POST https://tenderlex.ru/api/v1/mcp/products/exact-analogs \\
  -H "Authorization: Bearer tl_live_YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "specification": "Насос центробежный консольный подача 50 м3/ч напор 32м",
    "procurement_title": "Поставка насосного агрегата"
  }'

# 3. Анализ документации и рисков закупки
curl -X POST https://tenderlex.ru/api/v1/mcp/procurements/analyze \\
  -H "Authorization: Bearer tl_live_YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "document_text": "Проект контракта: срок поставки 5 рабочих дней, штраф 0.5% в день..."
  }'`,
  },
  python: {
    label: "Python",
    icon: "code",
    code: `import httpx

API_KEY = "tl_live_YOUR_API_KEY"
BASE_URL = "https://tenderlex.ru/api/v1/mcp"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# Поиск поставщиков и заводов по ТЗ
with httpx.Client(timeout=60.0) as client:
    response = client.post(
        f"{BASE_URL}/suppliers/search",
        headers=HEADERS,
        json={
            "specification": "Кабель ВВГнг-LS 3х2.5 ГОСТ 31996-2012, 1200 м",
            "city": "Москва",
            "target_count": 5,
            "search_policy": "normal",
        },
    )
    data = response.json()
    if data.get("ok"):
        print(f"Найдено поставщиков: {data['total_found']}")
        for supplier in data["suppliers"]:
            print(f"- {supplier['company_name']} (ИНН {supplier['inn']})")
            print(f"  Сайт: {supplier['site']} | Тел: {supplier['phone']} | Email: {supplier['email']}")
`,
  },
  nodejs: {
    label: "Node.js",
    icon: "code",
    code: `const API_KEY = "tl_live_YOUR_API_KEY";
const BASE_URL = "https://tenderlex.ru/api/v1/mcp";

async function findSuppliers() {
  const res = await fetch(\`\${BASE_URL}/suppliers/search\`, {
    method: "POST",
    headers: {
      "Authorization": \`Bearer \${API_KEY}\`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      specification: "Кабель ВВГнг-LS 3х2.5 ГОСТ 31996-2012, 1200 м",
      city: "Москва",
      target_count: 5,
    }),
  });

  const data = await res.json();
  if (data.ok) {
    console.log(\`Найдено поставщиков: \${data.total_found}\`);
    data.suppliers.forEach(s => {
      console.log(\`\${s.company_name} | ИНН: \${s.inn} | Email: \${s.email}\`);
    });
  }
}

findSuppliers().catch(console.error);`,
  },
  "1c": {
    label: "1C:Предприятие 8.3",
    icon: "cpu",
    code: `// Пример интеграции TenderLex в конфигурацию 1С (ERP / КА / УТ)
&НаСервере
Процедура ЗапроситьПоставщиковПоТЗ(ТекстСпецификации, ГородПоставки)
    
    Сервер = "tenderlex.ru";
    Ресурс = "/api/v1/mcp/suppliers/search";
    Токен  = "tl_live_YOUR_API_KEY";
    
    SSL = Новый ЗащищенноеСоединениеOpenSSL();
    HTTPСоединение = Новый HTTPСоединение(Сервер, 443, , , , 60, SSL);
    
    Заголовки = Новый Соответствие();
    Заголовки.Вставить("Authorization", "Bearer " + Токен);
    Заголовки.Вставить("Content-Type", "application/json; charset=utf-8");
    
    // Формируем тело запроса
    ТелоСтруктура = Новый Структура();
    ТелоСтруктура.Вставить("specification", ТекстСпецификации);
    ТелоСтруктура.Вставить("city", ГородПоставки);
    ТелоСтруктура.Вставить("target_count", 5);
    
    ЗаписьJSON = Новый ЗаписьJSON();
    ЗаписьJSON.УстановитьСтроку();
    ЗаписатьJSON(ЗаписьJSON, ТелоСтруктура);
    СтрокаТела = ЗаписьJSON.Закрыть();
    
    HTTPЗапрос = Новый HTTPЗапрос(Ресурс, Заголовки);
    HTTPЗапрос.УстановитьТелоИзСтроки(СтрокаТела, КодировкаТекста.UTF8);
    
    Ответ = HTTPСоединение.ОтправитьДляОбработки(HTTPЗапрос);
    Если Ответ.КодСостояния = 200 Тогда
        ЧтениеJSON = Новый ЧтениеJSON();
        ЧтениеJSON.УстановитьСтроку(Ответ.ПолучитьТелоКакСтроку());
        Данные = ПрочитатьJSON(ЧтениеJSON);
        ЧтениеJSON.Закрыть();
        
        Для Каждого Поставщик Из Данные.suppliers Цикл
            Сообщить("Компания: " + Поставщик.company_name + " | ИНН: " + Поставщик.inn + " | Email: " + Поставщик.email);
        КонецЦикла;
    Иначе
        Сообщить("Ошибка вызова API TenderLex: " + Строка(Ответ.КодСостояния));
    КонецЕсли;
    
КонецПроцедуры`,
  },
};

export function ApiCodeTabs() {
  const [activeTab, setActiveTab] = useState<CodeLang>("curl");
  const [copied, setCopied] = useState(false);

  const currentExample = CODE_EXAMPLES[activeTab];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(currentExample.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden font-sans">
      {/* Code Header with language tabs */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-slate-800 bg-slate-950/70">
        <div className="flex items-center gap-1.5 overflow-x-auto">
          {(Object.keys(CODE_EXAMPLES) as CodeLang[]).map((lang) => {
            const item = CODE_EXAMPLES[lang];
            const isActive = activeTab === lang;
            return (
              <button
                key={lang}
                type="button"
                onClick={() => {
                  setActiveTab(lang);
                  setCopied(false);
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 shrink-0 ${
                  isActive
                    ? "bg-teal-500/20 text-teal-300 border border-teal-500/40 shadow-xs"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                }`}
              >
                {lang === "curl" && <Terminal size={13} />}
                {(lang === "python" || lang === "nodejs") && <Code2 size={13} />}
                {lang === "1c" && <Cpu size={13} />}
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer shrink-0 border border-slate-700/80"
          aria-label="Скопировать код"
        >
          {copied ? <Check size={13} className="text-teal-400" /> : <Copy size={13} />}
          <span>{copied ? "Скопировано!" : "Копировать код"}</span>
        </button>
      </div>

      {/* Code Snippet */}
      <div className="p-4 sm:p-5 overflow-x-auto">
        <pre className="font-mono text-xs sm:text-[12.5px] leading-relaxed text-slate-200 selection:bg-teal-500/30">
          <code>{currentExample.code}</code>
        </pre>
      </div>

      {/* Footer bar */}
      <div className="px-4 py-2.5 bg-slate-950/50 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>https://tenderlex.ru/api/v1/mcp</span>
        </div>
        <span>Формат ответов: JSON UTF-8</span>
      </div>
    </div>
  );
}
