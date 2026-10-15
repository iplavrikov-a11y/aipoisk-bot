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
    "pravo.gov.ru", "ips.pravo.gov.ru", "publication.pravo.gov.ru", "zakupki.gov.ru", "pub.fsa.gov.ru", "protect.gost.ru",
    "eec.eaeunion.org", "egrul.nalog.ru", "pb.nalog.ru", "bo.nalog.gov.ru", "kad.arbitr.ru",
    "rosstat.gov.ru", "fas.gov.ru", "minstroyrf.gov.ru", "customs.gov.ru", "rostransnadzor.gov.ru",
    "rostrud.gov.ru", "corpmsp.ru", "minpromtorg.gov.ru", "gisp.gov.ru", "reestr.digital.gov.ru",
    "roszdravnadzor.gov.ru", "goszakupki.eaeunion.org", "minfin.gov.ru", "www.swrit.ru", "sfr.gov.ru", "iccwbo.org", "mchs.gov.ru",
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
  if (KNOWLEDGE_ARTICLES.length !== 57) failures.push(`expected 57 articles, got ${KNOWLEDGE_ARTICLES.length}`);
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
    if (!article.moduleLink || !article.moduleLink.label || !["/poisk-postavshchikov-po-tz", "/podbor-tovara-i-analogov-po-tz", "/analiz-zakupochnoi-dokumentacii"].includes(article.moduleLink.href)) failures.push(`${article.slug}: missing relevant module link`);
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
  if (failures.length) throw new Error(failures.join("\n"));
  console.log(`PASS: ${KNOWLEDGE_ARTICLES.length} articles have described source links, nonempty content, related links and a relevant module link`);
} finally {
  rmSync(directory, { recursive: true, force: true });
}
