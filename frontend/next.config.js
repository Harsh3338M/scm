/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Required for Leaflet map images
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'unpkg.com' },
      { protocol: 'https', hostname: '*.tile.openstreetmap.org' },
    ],
  },
  // Environment variables exposed to the server
  env: {
    INTELLIGENCE_ENGINE_URL: process.env.INTELLIGENCE_ENGINE_URL ?? 'http://localhost:8080',
  },
}

module.exports = nextConfig
