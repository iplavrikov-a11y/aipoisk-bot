import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const ts = require("../site/node_modules/typescript");
const compiled = ts.transpileModule(readFileSync("site/src/lib/seo.ts", "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const module = { exports: {} };
new Function("module", "exports", compiled)(module, module.exports);
const seo = module.exports;

function assertNoInventedLocation(value) {
  if (!value || typeof value !== "object") return;
  for (const [key, child] of Object.entries(value)) {
    assert.ok(!["address", "geo", "serviceArea", "taxID", "legalName"].includes(key), `unverified business field: ${key}`);
    assertNoInventedLocation(child);
  }
}

const organization = seo.buildOrganizationJsonLd();
const service = seo.buildServiceJsonLd({ name: "Анализ", description: "Проверка", path: "/analiz-zakupochnoi-dokumentacii" });
const regional = seo.buildRegionalServiceJsonLd({ name: "Снабжение", description: "Онлайн-поиск", path: "/regiony/moskva", regionName: "Москва", regionLocality: "Москва", postalCode: "123317", geo: { latitude: 55.7, longitude: 37.5 } });
for (const value of [organization, service, regional]) assertNoInventedLocation(value);
assert.equal(regional.areaServed.name, "Москва");
assert.equal(service.provider["@id"], organization["@id"]);
assert.equal(service.offers, undefined, "unknown current price must not be declared zero");
assert.equal(regional.offers, undefined, "a service territory is not a free offer");
assert.equal(seo.buildSoftwareApplicationJsonLd().offers, undefined);
assert.equal(seo.buildSoftwareApplicationJsonLd({ trialEnabled: false }).offers, undefined);
assert.equal(seo.buildSoftwareApplicationJsonLd({ trialEnabled: true }).offers.price, "0");
console.log("PASS: schemas retain service territories without invented offices, geo or unconditional free offers");

assert.equal(seo.buildOrganizationJsonLd({botUrl:'https://t.me/test_product'}).contactPoint.url,'https://t.me/test_product');
assert.ok(seo.buildOrganizationJsonLd({botUrl:'https://t.me/test_product'}).sameAs.includes('https://t.me/test_product'));
assert.equal(seo.buildOrganizationJsonLd().contactPoint,undefined);
