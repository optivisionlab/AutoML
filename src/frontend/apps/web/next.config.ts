import path from "path";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/core/i18n/request.ts");

const nextConfig: NextConfig = {
  /* config options here */
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname, "../.."),
  reactStrictMode: false,
  transpilePackages: ["@automl/domain", "@automl/api", "@automl/assets"],
  experimental: {
    optimizePackageImports: ["lucide-react", "recharts", "date-fns"],
  },
  webpack(config, { isServer }) {
    config.module.rules.push({
      test: /\.(mp4|webm|ogg)$/i,
      type: "asset/resource",
      generator: {
        filename: "[name].[hash][ext]",
        outputPath: isServer ? "../static/media/" : "static/media/",
        publicPath: "/_next/static/media/",
      },
    });
    return config;
  },
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
