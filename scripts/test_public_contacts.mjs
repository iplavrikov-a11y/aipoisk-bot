import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const siteRequire = createRequire(new URL('../site/package.json', import.meta.url));
const ts = siteRequire('typescript');
const React = siteRequire('react');
const {renderToStaticMarkup} = siteRequire('react-dom/server');
let payload;
function load(path, mocks = {}) {
 const js = ts.transpileModule(readFileSync(path, 'utf8'), {compilerOptions: {module:ts.ModuleKind.CommonJS, target:ts.ScriptTarget.ES2022, jsx:ts.JsxEmit.ReactJSX}}).outputText;
 const module = {exports:{}};
 const customRequire = name => {
  if (name in mocks) return mocks[name];
  if (name === '@/lib/site-data') return {getSiteData:async()=>payload};
  if (name === '@/lib/seo') return new Proxy({}, {get:()=>()=>({})});
  if (name === '@/components/ui/button') return {Button:({children})=>React.createElement(React.Fragment,null,children)};
  if (name.startsWith('@/components/')) return new Proxy({}, {get:()=>()=>null});
  if (name === 'next/link') return {default:({children,...props})=>React.createElement('a',props,children)};
  return siteRequire(name);
 };
 new Function('module','exports','require','fetch', js)(module,module.exports,customRequire,mocks.fetch || globalThis.fetch);
 return module.exports;
}
const settings = load('site/src/lib/site-data.ts', {fetch:async()=>{throw new Error('network unavailable')}});
const fallback = await settings.getSiteData();
assert.equal(fallback.trial.enabled,false);
assert.deepEqual(fallback.tariffs,[]);
assert.ok(Object.values(fallback.tariff_groups).every(a=>a.length===0));
const section = load('site/src/components/contact-section.tsx').ContactSection;
const about = load('site/src/app/about/page.tsx').default;
for(const enabled of [false,true]) {
 payload = {...fallback, contacts:{...fallback.contacts,email:'test-contact@example.org',telegram_url:'https://t.me/test_support'},bot:{telegram_url:'https://t.me/test_product'},trial:{...fallback.trial,enabled}};
 const html = renderToStaticMarkup(await section({}));
 assert.equal(/бесплат/i.test(html),enabled);
 for(const value of ['mailto:test-contact@example.org','https://t.me/test_support','https://t.me/test_product']) {
  assert.ok(html.includes(value));
  assert.ok(renderToStaticMarkup(await about()).includes(value));
 }
 assert.ok(!html.includes('mailto:info@tenderlex.ru'));
}
const healthy = load('site/src/lib/site-data.ts', {fetch:async()=>({ok:true,json:async()=>payload})});
assert.deepEqual(await healthy.getSiteData(),payload);
console.log('PASS: rendered contacts follow admin overrides; free access conditional; network failure hides trial and prices');

const context = load('site/src/lib/public-site-settings.tsx');
const header = load('site/src/components/site-header.tsx', {'@/lib/public-site-settings':context}).SiteHeader;
const headerHtml = renderToStaticMarkup(React.createElement(context.PublicSiteSettingsProvider,{settings:payload},React.createElement(header)));
for(const value of ['mailto:test-contact@example.org','https://t.me/test_support','https://t.me/test_product']) assert.ok(headerHtml.includes(value));
assert.ok(!headerHtml.includes('https://t.me/lexelence'));
payload.trial.enabled=false;
const article = load('site/src/components/knowledge-article-layout.tsx').KnowledgeArticleLayout;
const articleHtml = renderToStaticMarkup(await article({title:'Проверка',subtitle:'Документы',tag:'Учебный',breadcrumbSchema:{},toc:[],children:'Текст'}));
assert.doesNotMatch(articleHtml,/бесплат/i);
assert.ok(articleHtml.includes('https://t.me/test_product'));
for(const slug of ['poisk-postavshchikov-po-tz','podbor-tovara-i-analogov-po-tz','analiz-zakupochnoi-dokumentacii']) {
 const page = load(`site/src/app/${slug}/page.tsx`).default;
 const html = renderToStaticMarkup(await page());
 assert.ok(html.includes('https://t.me/test_product'),slug);
 assert.ok(!html.includes('https://t.me/tenderlex_bot'),slug);
}
console.log('PASS: actual Header, article layout and three commercial page renderers use the same public contacts');

const publicLink = load('site/src/components/public-site-link.tsx', {'@/lib/public-site-settings':context}).PublicSiteLink;
for (const [channel,value] of [['bot','https://t.me/test_product'],['telegram','https://t.me/test_support'],['email','mailto:test-contact@example.org']]) {
 const html = renderToStaticMarkup(React.createElement(context.PublicSiteSettingsProvider,{settings:payload},React.createElement(publicLink,{channel})));
 assert.ok(html.includes(value),channel);
}
console.log('PASS: shared public contact links render admin overrides for all channels');
