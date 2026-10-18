import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A local hardware-backed API; results are read from disk on every request.
  cacheComponents: false,
};

export default nextConfig;
