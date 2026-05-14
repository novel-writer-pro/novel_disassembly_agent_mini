import { test, expect } from "@playwright/test";

const BASE = process.env.WRITER_STUDIO_BASE || "http://localhost:4173";

test.describe("Writer Studio — F3 E2E", () => {
  test("empty branch shows import CTA", async ({ page }) => {
    await page.goto(`${BASE}/writer`);
    await expect(page.getByText("还没有作品")).toBeVisible();
    await expect(page.getByRole("link", { name: "前往导入" })).toBeVisible();
  });

  test("branch route renders three-pane studio layout", async ({ page }) => {
    await page.goto(`${BASE}/writer/demo-branch`);
    await expect(page.getByTestId("studio-layout")).toBeVisible();
    await expect(page.getByTestId("studio-sider-left")).toBeVisible();
    await expect(page.getByTestId("studio-canvas")).toBeVisible();
    await expect(page.getByTestId("studio-sider-right")).toBeVisible();
    await expect(page.getByText("Writer Studio · demo-branch")).toBeVisible();
  });

  test("editor canvas accepts input and shows save status", async ({ page }) => {
    await page.goto(`${BASE}/writer/demo-branch`);
    const textarea = page.getByTestId("editor-textarea");
    await expect(textarea).toBeVisible();
    await textarea.fill("第一章 测试段落\n\n这是一段测试文本。");
    await page.waitForTimeout(700);
    await expect(page.getByText(/已保存|未保存/)).toBeVisible();
  });

  test("right pane Loom and Copilot tabs both reachable", async ({ page }) => {
    await page.goto(`${BASE}/writer/demo-branch`);
    await expect(page.getByRole("tab", { name: "Loom 信号" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "AI 副驾" })).toBeVisible();

    await page.getByRole("tab", { name: "AI 副驾" }).click();
    const copilotIframe = page.getByTestId("copilot-iframe");
    const tokenWarning = page.getByText("NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN");
    await expect(copilotIframe.or(tokenWarning)).toBeVisible();
  });

  test("legacy Workbench shell is NOT loaded under /writer/*", async ({ page }) => {
    await page.goto(`${BASE}/writer/demo-branch`);
    const html = await page.content();
    expect(html).not.toContain("WorkbenchApp");
    expect(html).not.toContain("WorkbenchLayout");
  });
});
