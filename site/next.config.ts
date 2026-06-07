import type { NextConfig } from "next";

const apiBaseUrl = (process.env.AIPOISK_SITE_API_BASE_URL || "http://127.0.0.1:8088").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
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
