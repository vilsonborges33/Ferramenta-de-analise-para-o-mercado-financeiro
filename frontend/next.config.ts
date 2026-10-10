import type { NextConfig } from "next";

const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const config: NextConfig = {
  output: "standalone",
  // O navegador fala só com o Next; /api/* é repassado ao FastAPI (cookies de sessão na mesma origem).
  async rewrites() {
    return [{ source: "/api/:caminho*", destination: `${backend}/:caminho*` }];
  },
};

export default config;
