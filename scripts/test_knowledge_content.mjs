import { existsSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ts = require("../site/node_modules/typescript/lib/typescript.js");
const directory = mkdtempSync(join(tmpdir(), "tenderlex-knowledge-test-"));

try {
  const source = readFileSync("site/src/data/knowledge-base.ts", "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const compiledPath = join(directory, "knowledge.cjs");
  writeFileSync(compiledPath, compiled);
  const { KNOWLEDGE_ARTICLES, ARTICLE_CLAIM_SOURCE_MAP, getRelatedArticles } = require(compiledPath);
  const allowedHosts = new Set([
    "v8.1c.ru", "modelcontextprotocol.io", "pravo.gov.ru", "ips.pravo.gov.ru", "publication.pravo.gov.ru", "zakupki.gov.ru", "pub.fsa.gov.ru", "protect.gost.ru",
    "eec.eaeunion.org", "egrul.nalog.ru", "pb.nalog.ru", "bo.nalog.gov.ru", "kad.arbitr.ru",
    "rosstat.gov.ru", "fas.gov.ru", "minstroyrf.gov.ru", "customs.gov.ru", "rostransnadzor.gov.ru",
    "rostrud.gov.ru", "corpmsp.ru", "minpromtorg.gov.ru", "gisp.gov.ru", "reestr.digital.gov.ru",
    "roszdravnadzor.gov.ru", "goszakupki.eaeunion.org", "minfin.gov.ru", "www.swrit.ru", "sfr.gov.ru", "iccwbo.org", "mchs.gov.ru", "kamchatka.roskazna.gov.ru",
  ]);
  const slugs = new Set(KNOWLEDGE_ARTICLES.map((article) => article.slug));
  const downloadableArticleSlugs = new Set(["kak-sostavit-zapros-kp-postavshchiku", "proverka-dostovernosti-predostavlennyh-kp-dlya-nmck"]);
  const failures = [];
  const inbound = new Map(KNOWLEDGE_ARTICLES.map(article => [article.slug, 0]));
  for (const article of KNOWLEDGE_ARTICLES) {
    const related = getRelatedArticles(article.slug);
    if (related.length !== 3 || new Set(related.map(a => a.slug)).size !== 3 || related.some(a => a.slug === article.slug || !slugs.has(a.slug))) failures.push(`${article.slug}: rendered related links must be unique, valid and not self links`);
    for (const target of related) inbound.set(target.slug, inbound.get(target.slug) + 1);
  }
  for (const [slug, count] of inbound) if (!count) failures.push(`${slug}: no incoming related-article link`);
  if (KNOWLEDGE_ARTICLES.length < 58) failures.push(`existing article inventory regressed: expected at least 58, got ${KNOWLEDGE_ARTICLES.length}`);
  for (const article of KNOWLEDGE_ARTICLES) {
    if (!article.contentSections?.length || !article.contentSections.some((section) => section.paragraphs?.some(Boolean))) failures.push(`${article.slug}: empty useful content`);
    if (!article.sources?.length) failures.push(`${article.slug}: no source`);
    for (const source of article.sources ?? []) {
      let parsed;
      try { parsed = new URL(source.url); } catch { failures.push(`${article.slug}: invalid source URL`); continue; }
      if (parsed.protocol !== "https:" || !allowedHosts.has(parsed.hostname) || !source.title) failures.push(`${article.slug}: source must be an approved source URL`);
      if (!source.note?.trim()) failures.push(`${article.slug}: source must state what it confirms and its limit`);
      if (source.note?.startsWith("Используется для проверки:")) failures.push(`${article.slug}: generic source note is prohibited`);
    }
    const claimSources = ARTICLE_CLAIM_SOURCE_MAP?.[article.slug] ?? [];
    // Only manually checked factual claims belong here; a generic bibliography is not claim proof.
    for (const claimSource of claimSources) {
      if (!article.contentSections.some(section => section.id === claimSource.sectionId) || !claimSource.claimScope || !claimSource.limitation || !article.sources.some((source) => source.url === claimSource.sourceUrl)) {
        failures.push(`${article.slug}: invalid claim-source mapping`);
      }
    }
    if (!article.relatedSlugs?.length || article.relatedSlugs.some((slug) => !slugs.has(slug) || slug === article.slug)) failures.push(`${article.slug}: invalid related article link`);
    if (!article.moduleLink || !article.moduleLink.label || !["/poisk-postavshchikov-po-tz", "/podbor-tovara-i-analogov-po-tz", "/analiz-zakupochnoi-dokumentacii", "/monitoring-cen-postavshchikov-po-tz", "/zapros-kp-po-tz"].includes(article.moduleLink.href)) failures.push(`${article.slug}: missing relevant module link`);
    if (downloadableArticleSlugs.has(article.slug)) {
      if (!article.downloads?.length) failures.push(`${article.slug}: missing useful downloads`);
      for (const download of article.downloads ?? []) {
        if (!download.href.startsWith("/materialy/") || download.href.includes("..") || !download.label || !download.description) failures.push(`${article.slug}: unsafe or undocumented download`);
        const localPath = `site/public${download.href}`;
        if (!existsSync(localPath) || statSync(localPath).size < 100) failures.push(`${article.slug}: missing or empty public asset`);
      }
    }
  }
  const articlePage = readFileSync("site/src/app/baza-znaniy/[slug]/page.tsx", "utf8");
  if (!articlePage.includes("article.downloads") || !articlePage.includes("download")) failures.push("article page: download block or download attribute missing");
  const rfqArticle = KNOWLEDGE_ARTICLES.find((article) => article.slug === "kak-sostavit-zapros-kp-postavshchiku");
  if (rfqArticle?.moduleLink?.href !== "/zapros-kp-po-tz") failures.push("request-for-quote article must link to request preparation");
  if (!articlePage.includes("heroDownload={")) failures.push("request template must be available near the article heading");
  const apiGuide = KNOWLEDGE_ARTICLES.find((article) => article.contentSections.some((section) => section.id === "1c-integration-example"));
  if (!apiGuide?.contentSections.some((section) => section.links?.some((link) => link.href === "/api-integracii"))) failures.push("1C guide must link to API documentation within the content");
  if (!articlePage.includes("datePublished: article.publishedDate,")) failures.push("structured publication date must be sourced independently of revisions");
  const rfqPage = readFileSync("site/src/app/zapros-kp-po-tz/page.tsx", "utf8");
  if (!rfqPage.includes('href="/cabinet?scenario=supplier_search"')) failures.push("request-for-quote CTA must select the supplier search scenario");
  const monitoringPage = readFileSync("site/src/app/monitoring-cen-postavshchikov-po-tz/page.tsx", "utf8");
  if (monitoringPage.includes("за 3 минуты") || monitoringPage.includes("Каждая позиция содержит 3–5 цен")) failures.push("monitoring landing must not promise fixed processing time or full price coverage");
  if (failures.length) throw new Error(failures.join("\n"));
  console.log(`PASS: ${KNOWLEDGE_ARTICLES.length} articles have described source links, nonempty content, related links and a relevant module link`);
} finally {
  rmSync(directory, { recursive: true, force: true });
}
