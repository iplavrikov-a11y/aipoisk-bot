import type { MetadataRoute } from "next";

import {
  commercialPageLastModified,
  normalizedSiteUrl,
  seoPageLastModified,
} from "@/lib/seo";
import { KNOWLEDGE_ARTICLES } from "@/data/knowledge-base";

const siteUrl = normalizedSiteUrl();
const commercialUpdated = new Date(`${commercialPageLastModified}T00:00:00.000Z`);
const seoUpdated = new Date(`${seoPageLastModified}T00:00:00.000Z`);
const currentSeoUpdated = new Date("2026-10-01T00:00:00.000Z");
const growthUpdated = new Date("2026-10-01T00:00:00.000Z");
const legalUpdated = new Date("2026-09-21T00:00:00.000Z");

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: siteUrl,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${siteUrl}/poisk-postavshchikov-po-tz`,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 0.95,
    },
    {
      url: `${siteUrl}/podbor-tovara-i-analogov-po-tz`,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 0.95,
    },
    {
      url: `${siteUrl}/poisk-postavshchikov-dlya-tendera`,
      lastModified: currentSeoUpdated,
      changeFrequency: "weekly",
      priority: 0.9,
    },
    {
      url: `${siteUrl}/poisk-proizvoditeley-po-tz`,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 0.88,
    },
    {
      url: `${siteUrl}/postavshchiki-dlya-zaprosa-kp`,
      lastModified: currentSeoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/zapros-kp-po-tz`,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/analiz-zakupochnoi-dokumentacii`,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 0.75,
    },
    {
      url: `${siteUrl}/ocenka-riskov-zakupki`,
      lastModified: currentSeoUpdated,
      changeFrequency: "weekly",
      priority: 0.72,
    },
    {
      url: `${siteUrl}/analiz-rynka-44-fz`,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 0.71,
    },
    {
      url: `${siteUrl}/reestr-minpromtorga-v-zakupkah`,
      lastModified: currentSeoUpdated,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${siteUrl}/baza-znaniy`,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    ...KNOWLEDGE_ARTICLES.map((art) => ({
      url: `${siteUrl}/baza-znaniy/${art.slug}`,
      lastModified: growthUpdated,
      changeFrequency: "weekly" as const,
      priority: 0.85,
    })),
    {
      url: `${siteUrl}/about`,
      lastModified: growthUpdated,
      changeFrequency: "monthly",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/otrasli`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/otrasli/metalloprokat`,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/otrasli/kabel-i-provod`,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/otrasli/truboprovodnaya-armatura`,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/otrasli/stroitelnye-materialy`,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/otrasli/siz-i-specodezhda`,
      lastModified: growthUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/regiony/moskva`,
      lastModified: currentSeoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/sankt-peterburg`,
      lastModified: currentSeoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/ekaterinburg`,
      lastModified: currentSeoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/novosibirsk`,
      lastModified: currentSeoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/kazan`,
      lastModified: currentSeoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/nizhny-novgorod`,
      lastModified: currentSeoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/krasnodar`,
      lastModified: currentSeoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/samara`,
      lastModified: currentSeoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/legal`,
      lastModified: growthUpdated,
      changeFrequency: "monthly",
      priority: 0.3,
    },
    {
      url: `${siteUrl}/terms`,
      lastModified: legalUpdated,
      changeFrequency: "monthly",
      priority: 0.3,
    },
    {
      url: `${siteUrl}/privacy`,
      lastModified: growthUpdated,
      changeFrequency: "monthly",
      priority: 0.3,
    },
    {
      url: `${siteUrl}/personal-data`,
      lastModified: legalUpdated,
      changeFrequency: "monthly",
      priority: 0.3,
    },
  ];
}
