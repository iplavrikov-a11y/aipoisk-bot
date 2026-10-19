import type { MetadataRoute } from "next";

import { normalizedSiteUrl } from "@/lib/seo";

const siteUrl = normalizedSiteUrl();

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/cabinet", "/v2", "/test-buttons", "/demo-buttons", "/demo-design", "/demo-world"],
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
        disallow: ["/api/", "/cabinet", "/v2", "/test-buttons", "/demo-buttons", "/demo-design", "/demo-world"],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
