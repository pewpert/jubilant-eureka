/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { hostname: "*.suumo.jp" },
      { hostname: "*.homes.co.jp" },
      { hostname: "*.chintai.net" },
    ],
  },
};

module.exports = nextConfig;
