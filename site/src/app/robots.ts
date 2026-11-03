import type { MetadataRoute } from "next";

import { normalizedSiteUrl } from "@/lib/seo";

const siteUrl = normalizedSiteUrl();

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/cabinet"],
      },
      {
        userAgent: [
          "GPTBot",
          "ClaudeBot",
          "PerplexityBot",
          "YandexRenderBot",
          "Google-Extended",
          "Applebot-Extended",
          "Diffbot",
          "Bytespider",
          "CCBot",
          "Meta-ExternalAgent",
          "cohere-ai",
        ],
        allow: "/",
        disallow: ["/api/", "/cabinet"],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
