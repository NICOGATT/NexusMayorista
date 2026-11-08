import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Permite levantar un segundo servidor (pruebas) sin pisar el `.next` del `npm run dev` principal.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
