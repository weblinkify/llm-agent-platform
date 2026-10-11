import { expect, test, type Page } from "@playwright/test";

const lastAnswer = (page: Page) => page.getByTestId("assistant-message").last();

async function waitForFinal(page: Page) {
  await expect(lastAnswer(page).getByTestId("status")).toBeVisible({ timeout: 15_000 });
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Telco AI Operations Console")).toBeVisible();
});

test("shows backend info and the four demo scenarios", async ({ page }) => {
  await expect(page.getByText(/LLM: mock/)).toBeVisible();
  for (const i of [1, 2, 3, 4]) await expect(page.getByTestId(`scenario-${i}`)).toBeVisible();
});

test("knowledge question streams a cited answer with expandable sources", async ({ page }) => {
  await page.getByTestId("scenario-2").click();
  await waitForFinal(page);
  await expect(lastAnswer(page)).toContainText("4 hours");
  await expect(lastAnswer(page).getByTestId("status")).toHaveText("completed");
  await expect(page.getByTestId("agent-knowledge")).toHaveAttribute("data-state", "done");
  const citation = page.getByTestId("citation").first();
  await expect(citation).toContainText("DOC-001");
  await citation.getByRole("button").click();
  await expect(citation).toContainText("similarity");
  await expect(page.getByTestId("tool-timeline")).toContainText("search_knowledge_base");
});

test("incident investigation calls MCP tools without approval", async ({ page }) => {
  await page.getByTestId("scenario-1").click();
  await waitForFinal(page);
  await expect(lastAnswer(page)).toContainText("INC-1003");
  await expect(page.getByTestId("tool-timeline")).toContainText("get_network_status");
  await expect(page.getByTestId("tool-timeline")).toContainText("search_incidents");
});

test("customer troubleshooting explains the failed 5G checks", async ({ page }) => {
  await page.getByTestId("scenario-3").click();
  await waitForFinal(page);
  await expect(lastAnswer(page)).toContainText("5G-compatible SIM");
  await expect(lastAnswer(page)).toContainText("MOB-5G-PLUS");
});

test("action requires approval from a different role, then executes", async ({ page }) => {
  await page.getByTestId("role-SUPPORT_AGENT").click();
  await page.getByTestId("scenario-4").click();
  await waitForFinal(page);
  await expect(lastAnswer(page).getByTestId("status")).toHaveText("pending approval");

  const card = page.getByTestId("approval-card").first();
  await expect(card).toBeVisible();
  await expect(card.getByTestId("approval-hint")).toContainText("Separation of duties");

  await page.getByTestId("role-ADMIN").click();
  await expect(card.getByTestId("approve-button")).toBeVisible();
  await card.getByTestId("approve-button").click();
  await expect(lastAnswer(page)).toContainText("Created incident INC-", { timeout: 15_000 });
  await expect(page.getByTestId("tool-timeline")).toContainText("create_notification");
});

test("read-only role is denied customer data", async ({ page }) => {
  await page.getByTestId("role-READ_ONLY_USER").click();
  await page.getByTestId("scenario-3").click();
  await waitForFinal(page);
  await expect(lastAnswer(page).getByTestId("status")).toHaveText("denied");
});

test("poisoned document is quarantined and no tool is triggered", async ({ page }) => {
  await page.getByTestId("scenario-5").click();
  await waitForFinal(page);
  await expect(page.getByTestId("security-panel")).toContainText("Quarantined DOC-099");
  await expect(page.getByTestId("tool-timeline")).not.toContainText("create_incident");
});
