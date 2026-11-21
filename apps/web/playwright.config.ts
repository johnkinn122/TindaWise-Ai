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
    // Signs in as each demo role once and saves the sessions for the projects below.
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        storageState: "test/e2e/.auth/owner.json",
      },
      testIgnore: /(mobile|cashier|pos)\.spec\.ts/,
      dependencies: ["setup"],
    },
    {
      name: "cashier",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        storageState: "test/e2e/.auth/cashier.json",
      },
      testMatch: /(cashier|pos)\.spec\.ts/,
      dependencies: ["setup"],
    },
    {
      name: "mobile",
      use: { ...devices["Pixel 7"], storageState: "test/e2e/.auth/owner.json" },
      testMatch: /mobile\.spec\.ts/,
      dependencies: ["setup"],
    },
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
      },
    },
  ],
});
