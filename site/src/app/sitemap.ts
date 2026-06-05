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
  ];
}
