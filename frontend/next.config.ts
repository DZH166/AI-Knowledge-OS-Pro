import type { NextConfig } from "next";

const apiProxyTarget = process.env.API_PROXY_TARGET?.replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    if (!apiProxyTarget) {
      return [];
    }

    return [
      {
        source: "/api-proxy/:path*",
        destination: `${apiProxyTarget}/:path*`
      }
    ];
  }
};

export default nextConfig;

