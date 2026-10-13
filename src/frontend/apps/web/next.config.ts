import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/core/i18n/request.ts");

const nextConfig: NextConfig = {
  /* config options here */
  reactStrictMode: false,
  transpilePackages: ["@automl/domain", "@automl/api"],
  images: {
    domains: [
      "developers.google.com",
      "avatars.githubusercontent.com",
      "github.com",
      "contrib.rocks",
    ],
    remotePatterns: [
      {
        protocol: "https",
        hostname: "cdn.prod.website-files.com",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "avatars.githubusercontent.com",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "github.com",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "contrib.rocks",
        pathname: "/**",
      },
    ],
  },
};

export default withNextIntl(nextConfig);
