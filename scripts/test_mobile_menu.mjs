import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const siteRequire = createRequire(new URL('../site/package.json', import.meta.url));
const ts = siteRequire('typescript');
const React = siteRequire('react');
const {renderToStaticMarkup} = siteRequire('react-dom/server');
let payload;
const navigationHandlers = [];
function load(path, mocks = {}) {
 const js = ts.transpileModule(readFileSync(path, 'utf8'), {compilerOptions: {module:ts.ModuleKind.CommonJS, target:ts.ScriptTarget.ES2022, jsx:ts.JsxEmit.ReactJSX}}).outputText;
 const module = {exports:{}};
 const customRequire = name => {
  if (name in mocks) return mocks[name];
  if (name === '@/lib/site-data') return {getSiteData:async()=>payload};
  if (name === '@/lib/seo') return new Proxy({}, {get:()=>()=>({})});
  if (name === '@/components/ui/button') return {Button:({children})=>React.createElement(React.Fragment,null,children)};
  if (name.startsWith('@/components/')) return new Proxy({}, {get:()=>()=>null});
  if (name === 'next/link') return {default:({children,...props})=>{
   if (props.onClick) navigationHandlers.push(props.onClick);
   return React.createElement('a',props,children);
  }};
  return siteRequire(name);
 };
 new Function('module','exports','require','fetch', js)(module,module.exports,customRequire,mocks.fetch || globalThis.fetch);
 return module.exports;
}
const context = load('site/src/lib/public-site-settings.tsx');
const header = load('site/src/components/site-header.tsx', {'@/lib/public-site-settings':context}).SiteHeader;
payload = {contacts:{email:'test-contact@example.org',telegram_url:'https://t.me/test_support'},bot:{telegram_url:'https://t.me/test_product'}};
const html = renderToStaticMarkup(React.createElement(context.PublicSiteSettingsProvider,{settings:payload},React.createElement(header)));
const mobile = html.match(/<details[^>]*class="[^"]*lg:hidden[^" ]*[^"]*"[^>]*>([\s\S]*?)<\/details>/);
assert.ok(mobile,'a native expandable mobile navigation must exist below the lg breakpoint');
assert.match(mobile[1],/<summary[^>]*>[^<]*(?:<[^>]*>[^<]*<\/[^>]*>)*[\s\S]*?Меню/);
assert.match(mobile[1],/<nav[^>]*aria-label="Мобильная навигация"/);
const paths = ['/poisk-postavshchikov-po-tz','/podbor-tovara-i-analogov-po-tz','/analiz-zakupochnoi-dokumentacii','/#pricing','/baza-znaniy'];
let last = -1;
for (const path of paths) {const at = mobile[1].indexOf('href="'+path+'"');assert.ok(at>last,'mobile module order and destination: '+path);last=at;}
for(const value of ['mailto:test-contact@example.org','https://t.me/test_support','https://t.me/test_product']) assert.ok(html.includes(value));
assert.equal(navigationHandlers.length, 5, 'each mobile destination closes the expanded menu');
for (const handler of navigationHandlers) {
 let closed = false;
 handler({currentTarget:{closest: selector => {
  assert.equal(selector, 'details');
  return {removeAttribute: name => {assert.equal(name, 'open'); closed = true;}};
 }}});
 assert.ok(closed, 'choosing a destination closes its menu');
 assert.doesNotThrow(() => handler({currentTarget:{closest: () => null}}));
}
console.log('PASS: actual React SSR native mobile menu has accessible summary/nav, all five destinations in module order, and public contact overrides');
