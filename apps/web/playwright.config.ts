import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run the production build against the real API and database.
 *
 * Locally: start PostgreSQL (docker compose), seed it once, then `npm run test:e2e`.
 * An API already running on :8000 is reused; otherwise Playwright starts one.
 * In CI the workflow prepares the database and Playwright starts both servers.
 */
const WEB_PORT = 3100;
const isCI = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./test/e2e",
  fullyParallel: false, // tests share one database; keep them predictable
  workers: 1,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
      testIgnore: /mobile\.spec\.ts/,
    },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: [
    {
      command: "node ../../scripts/api.mjs dev",
      url: "http://localhost:8000/health",
      reuseExistingServer: !isCI,
      timeout: 60_000,
      stdout: "ignore",
    },
    {
      command: `npm run start -- --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: !isCI,
      timeout: 60_000,
      env: {
        API_URL: process.env.API_URL ?? "http://localhost:8000",
        TINDAWISE_ORG_ID: process.env.TINDAWISE_ORG_ID ?? "00000000-0000-4000-8000-000000000001",
      },
    },
  ],
});
