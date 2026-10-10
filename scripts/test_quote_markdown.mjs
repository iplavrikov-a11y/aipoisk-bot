import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const ts = require('../site/node_modules/typescript');
const path = 'site/src/app/cabinet/cabinet-client.tsx';
const source = ts.createSourceFile(path, readFileSync(path, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const names = ['escapeHtml', 'formatInlineMarkdown', 'quoteMarkdownToHtml', 'normalizeQuoteTableRows', 'quoteHeaderKey', 'quotePlainText'];
const functions = source.statements.filter(n => ts.isFunctionDeclaration(n) && names.includes(n.name?.text)).map(n => n.getText(source)).join('\n');
assert.equal(functions.match(/function /g)?.length, names.length);
const js = ts.transpileModule(functions, {compilerOptions: {target:ts.ScriptTarget.ES2022}}).outputText;
const render = new Function(`${js}\nreturn quoteMarkdownToHtml;`)();
for (const payload of ['<img src=x onerror=alert(1)>', '<script>alert(1)</script>', '<svg onload=alert(1)>', '**<img src=x onerror=alert(1)>**', '| Name | Value |\n| --- | --- |\n| <svg onload=alert(1)> | test |', '# <iframe srcdoc="<script>alert(1)</script>">']) {
  const html = render(payload);
  assert.doesNotMatch(html, /<(?:img|script|svg|iframe)\b/i, `unsafe tag in ${payload}`);
  assert.match(html, /&lt;/, 'untrusted HTML must be escaped');
}
assert.equal(render('**важно**'), '<p><strong>важно</strong></p>');
assert.match(render('| Товар | Количество |\n|---|---|\n| Насос | 2 |'), /<td[^>]*>Насос<\/td>/);
assert.equal(render('- проверка\n- источник'), '<ul><li>проверка</li><li>источник</li></ul>');
console.log('PASS: malicious HTML escaped; Markdown lists, emphasis and tables preserved');
