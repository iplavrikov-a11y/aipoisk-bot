import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(join(root, 'site/package.json'));
const ts = require('typescript');
const temporary = mkdtempSync(join(tmpdir(), 'tenderlex-knowledge-'));
try {
  const source = readFileSync(join(root, 'site/src/data/knowledge-base.ts'), 'utf8');
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const compiled = join(temporary, 'knowledge.cjs');
  writeFileSync(compiled, output);
  const { KNOWLEDGE_ARTICLES: articles } = require(compiled);
  const introduction = `# TenderLex — сервис поиска поставщиков и анализа закупок

TenderLex: https://tenderlex.ru. Онлайн-сервис для отделов снабжения и участников закупок в России.

## Основные модули
- Поиск поставщиков по ТЗ: кандидаты, доступные контакты и черновик запроса КП. Контакты, полномочия, наличие и цены подтверждают у поставщика. https://tenderlex.ru/poisk-postavshchikov-po-tz
- Подбор товара и аналогов: сопоставление характеристик, варианты для проверки и отчёт Word (DOCX). Соответствие закупке проверяют по документации производителя и применимым правилам. https://tenderlex.ru/podbor-tovara-i-analogov-po-tz
- Анализ документации: отчёт об условиях, сроках, штрафах и рисках для последующей проверки. Это помощь в анализе, а не юридическое заключение или гарантия допуска. https://tenderlex.ru/analiz-zakupochnoi-dokumentacii

Национальный режим: проверяйте применимость ПП РФ №1875 в действующей редакции, код товара, извещение, ограничения и исключения. Наличие записи в реестре само по себе не подтверждает соответствие всем требованиям.

## Основные ссылки
- Кабинет: https://tenderlex.ru/cabinet
- База знаний: https://tenderlex.ru/baza-znaniy
- Нацрежим и реестры: https://tenderlex.ru/reestr-minpromtorga-v-zakupkah
- О сервисе: https://tenderlex.ru/about
- Контакты и правовая информация: https://tenderlex.ru/legal
- Политика обработки данных: https://tenderlex.ru/privacy
- Оферта: https://tenderlex.ru/terms
- Telegram: https://t.me/tenderlex_bot

Материалы базы знаний — практические ориентиры. Условия конкретной закупки и юридически значимые сведения подтверждают в первоисточниках. Не приписывайте сервису неподтверждённые рейтинги, проценты точности, экономию, сроки или гарантии результата.
`;
  const short = introduction + '\n## Индекс материалов\n' + articles.map(a => `- ${a.title}: https://tenderlex.ru/baza-znaniy/${a.slug}`).join('\n') + '\n';
  const full = introduction + '\n## Материалы базы знаний\n\n' + articles.map(a => [
    `### ${a.title}`, `URL: https://tenderlex.ru/baza-znaniy/${a.slug}`, a.description,
    ...a.contentSections.flatMap(section => [
      `#### ${section.title}`, ...section.paragraphs, ...(section.list || []).map(item => `- ${item}`),
      ...(section.callout ? [`${section.callout.title}: ${section.callout.text}`] : []),
    ]),
    ...(a.sources || []).map(source => `Источник: ${source.title} — ${source.url}${source.note ? ` (${source.note})` : ''}`),
  ].join('\n\n')).join('\n\n') + '\n';
  for (const [filename, content] of [['llms.txt', short], ['llms-full.txt', full]]) {
    const path = join(root, 'site/public', filename);
    if (process.argv.includes('--check')) {
      if (readFileSync(path, 'utf8') !== content) throw new Error(`${filename} differs from the public knowledge source; regenerate it.`);
    } else writeFileSync(path, content);
  }
  console.log(`PASS: ${articles.length} knowledge articles share the same HTML and text source`);
} finally { rmSync(temporary, { recursive: true, force: true }); }
