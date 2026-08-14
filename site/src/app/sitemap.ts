import type { MetadataRoute } from "next";

import {
  commercialPageLastModified,
  normalizedSiteUrl,
  seoPageLastModified,
} from "@/lib/seo";

const siteUrl = normalizedSiteUrl();
const commercialUpdated = new Date(`${commercialPageLastModified}T00:00:00.000Z`);
const seoUpdated = new Date(`${seoPageLastModified}T00:00:00.000Z`);
const legalUpdated = new Date("2026-07-17T00:00:00.000Z");

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: siteUrl,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${siteUrl}/poisk-postavshchikov-po-tz`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.95,
    },
    {
      url: `${siteUrl}/poisk-postavshchikov-dlya-tendera`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.9,
    },
    {
      url: `${siteUrl}/poisk-proizvoditeley-po-tz`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.88,
    },
    {
      url: `${siteUrl}/postavshchiki-dlya-zaprosa-kp`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/zapros-kp-po-tz`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/analiz-zakupochnoi-dokumentacii`,
      lastModified: commercialUpdated,
      changeFrequency: "weekly",
      priority: 0.75,
    },
    {
      url: `${siteUrl}/ocenka-riskov-zakupki`,
      lastModified: commercialUpdated,
      changeFrequency: "weekly",
      priority: 0.72,
    },
    {
      url: `${siteUrl}/analiz-rynka-44-fz`,
      lastModified: commercialUpdated,
      changeFrequency: "weekly",
      priority: 0.71,
    },
    {
      url: `${siteUrl}/reestr-minpromtorga-v-zakupkah`,
      lastModified: commercialUpdated,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${siteUrl}/baza-znaniy`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/baza-znaniy/kak-naiti-postavshchika-po-tz`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/baza-znaniy/analiz-riskov-zakupki-44-fz-223-fz`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/baza-znaniy/reestr-minpromtorga-postanovleniya-616-617`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/baza-znaniy/kak-sostavit-zapros-kp-postavshchiku`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/baza-znaniy/proverka-dilerskih-sertifikatov-b2b`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/about`,
      lastModified: seoUpdated,
      changeFrequency: "monthly",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/regiony`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/regiony/moskva`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/sankt-peterburg`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/ekaterinburg`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/novosibirsk`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/kazan`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/nizhny-novgorod`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/krasnodar`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/regiony/samara`,
      lastModified: seoUpdated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/legal`,
      lastModified: legalUpdated,
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
      lastModified: legalUpdated,
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
