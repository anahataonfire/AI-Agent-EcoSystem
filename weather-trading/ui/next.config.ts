import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: [
    "http://192.168.4.20:3000",
    "http://192.168.4.23:3000",
    "http://192.168.4.35:3000",
  ],
};

export default nextConfig;
