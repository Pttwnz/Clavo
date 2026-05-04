import type { NextConfig } from "next";
import { gastroTabletAccesoUrl } from "./src/lib/gastro-site";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      { source: "/login", destination: "/ingreso", permanent: false },
      {
        source: "/tablet",
        destination: `${gastroTabletAccesoUrl()}?reauth=1`,
        permanent: false,
      },
      { source: "/qr/carta", destination: "/carta/es", permanent: false },
    ];
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
        pathname: "/**",
      },
    ],
  },
};

export default nextConfig;
