import { defineConfig, devices } from "@playwright/test";

// Os testes de ponta a ponta esperam o frontend e o backend no ar (ex.: `docker compose up`).
// PW_CHROMIUM permite usar um Chromium já instalado em vez de baixar navegadores.
const executablePath = process.env.PW_CHROMIUM;

export default defineConfig({
  testDir: "e2e",
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    launchOptions: executablePath ? { executablePath } : {},
  },
  projects: [
    { name: "celular-375", use: { ...devices["Desktop Chrome"], viewport: { width: 375, height: 812 } } },
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } },
  ],
});
