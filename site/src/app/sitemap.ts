import type { MetadataRoute } from "next";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://tenderlex.ru";

export default function sitemap(): MetadataRoute.Sitemap {
  const updated = new Date();
  return [
    {
      url: siteUrl,
      lastModified: updated,
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${siteUrl}/poisk-postavshchikov-po-tz`,
      lastModified: updated,
      changeFrequency: "weekly",
      priority: 0.95,
    },
    {
      url: `${siteUrl}/poisk-postavshchikov-dlya-tendera`,
      lastModified: updated,
      changeFrequency: "weekly",
      priority: 0.9,
    },
    {
      url: `${siteUrl}/poisk-proizvoditeley-po-tz`,
      lastModified: updated,
      changeFrequency: "weekly",
      priority: 0.88,
    },
    {
      url: `${siteUrl}/postavshchiki-dlya-zaprosa-kp`,
      lastModified: updated,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${siteUrl}/zapros-kp-po-tz`,
      lastModified: updated,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/analiz-zakupochnoi-dokumentacii`,
      lastModified: updated,
      changeFrequency: "weekly",
      priority: 0.75,
    },
    {
      url: `${siteUrl}/reestr-minpromtorga-v-zakupkah`,
      lastModified: updated,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${siteUrl}/terms`,
      lastModified: updated,
      changeFrequency: "monthly",
      priority: 0.3,
    },
    {
      url: `${siteUrl}/privacy`,
      lastModified: updated,
      changeFrequency: "monthly",
      priority: 0.3,
    },
    {
      url: `${siteUrl}/personal-data`,
      lastModified: updated,
      changeFrequency: "monthly",
      priority: 0.3,
    },
  ];
}
