/**
 * Records README media (not part of the test run):
 *   CAPTURE_DIR=../../docs/media npx playwright test --project=capture
 * Frames are stitched into a GIF by scripts/make_gif.py.
 */
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";

const OUT = process.env.CAPTURE_DIR ?? "capture";
const FRAMES = join(OUT, "frames");

class Recorder {
  private running = false;
  private loop: Promise<void> = Promise.resolve();
  constructor(private page: Page) {}
  start() {
    this.running = true;
    this.loop = (async () => {
      while (this.running) {
        await this.page.screenshot({ path: join(FRAMES, `${Date.now()}.png`) });
        await this.page.waitForTimeout(90);
      }
    })();
  }
  async hold(ms: number) {
    await this.page.waitForTimeout(ms);
  }
  async stop() {
    this.running = false;
    await this.loop;
  }
}

const final = (page: Page) =>
  expect(page.getByTestId("assistant-message").last().getByTestId("status")).toBeVisible({ timeout: 20_000 });

test("record approval-flow GIF and screenshots", async ({ page }) => {
  test.setTimeout(120_000);
  mkdirSync(FRAMES, { recursive: true });
  await page.goto("/");
  await expect(page.getByText(/LLM: mock/)).toBeVisible();

  const rec = new Recorder(page);
  rec.start();
  await rec.hold(1200);

  await page.getByTestId("scenario-4").click();
  await final(page);
  await rec.hold(2200);

  await page.getByTestId("role-ADMIN").click();
  await rec.hold(1200);
  await page.getByTestId("approval-card").first().locator("input").fill("Verified impact on customer 10002");
  await rec.hold(600);
  await page.getByTestId("approve-button").first().click();
  await expect(page.getByTestId("assistant-message").last()).toContainText("Created incident INC-");
  await rec.hold(2800);
  await rec.stop();
  await page.screenshot({ path: join(OUT, "approval-flow.png") });

  for (const [scenario, name] of [
    ["scenario-2", "knowledge-rag"],
    ["scenario-3", "customer-troubleshooting"],
    ["scenario-5", "prompt-injection"],
  ] as const) {
    await page.goto("/");
    await page.getByTestId(scenario).click();
    await final(page);
    if (name !== "prompt-injection") await page.getByTestId("citation").first().getByRole("button").click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: join(OUT, `${name}.png`) });
  }
});
