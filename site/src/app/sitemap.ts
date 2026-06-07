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
