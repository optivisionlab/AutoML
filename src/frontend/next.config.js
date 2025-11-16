/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // Ensure proper CSS handling
  webpack: (config, { isServer }) => {
    // Fix for CSS modules
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
      };
    }
    return config;
  },

  // Environment variables that should be available on the client side
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9999',
    NEXT_PUBLIC_GRADIO_URL: process.env.NEXT_PUBLIC_GRADIO_URL || 'http://localhost:7860',
  },

  // Disable telemetry
  telemetry: {
    disabled: true,
  },

  // Allow external images if needed
  images: {
    domains: ['localhost'],
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '',
        pathname: '/**',
      },
    ],
  },

  // Compiler options for better performance
  compiler: {
    // Remove console logs in production
    removeConsole: process.env.NODE_ENV === 'production',
  },

  // Experimental features
  experimental: {
    // Enable server actions if needed
    serverActions: {
      enabled: true,
    },
  },

  // Output configuration
  output: 'standalone',

  // PoweredByHeader
  poweredByHeader: false,

  // Compression
  compress: true,
};

module.exports = nextConfig;
