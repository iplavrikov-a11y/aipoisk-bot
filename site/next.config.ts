import type { NextConfig } from "next";

const apiBaseUrl = (process.env.AIPOISK_SITE_API_BASE_URL || "http://127.0.0.1:8088").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:asset(favicon.ico|favicon.svg|favicon.png|icon.png|apple-touch-icon.png|tenderlex-logo.png|tenderlex-product-preview.png)",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=604800, stale-while-revalidate=86400",
          },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiBaseUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
