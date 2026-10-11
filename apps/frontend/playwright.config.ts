import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: { baseURL, trace: "retain-on-failure", viewport: { width: 1440, height: 900 } },
  projects: [
    { name: "e2e", testMatch: /console\.spec\.ts/, use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "capture", testMatch: /capture\.spec\.ts/, use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 860 } } },
  ],
});
