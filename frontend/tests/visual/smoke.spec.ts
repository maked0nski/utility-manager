import type { APIRequestContext, Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

async function loginAsAdmin(page: Page, request: APIRequestContext) {
  const bootstrapResponse = await request.get("/api/auth/admin/bootstrap-info");
  const bootstrap = await bootstrapResponse.json();
  const username = bootstrap?.username || "admin";
  const password = bootstrap?.password || "admin123";
  const loginResponse = await request.post("/api/auth/admin/login", {
    data: { username, password },
  });
  expect(loginResponse.ok()).toBeTruthy();
  const login = await loginResponse.json();
  await page.addInitScript((token) => {
    window.localStorage.setItem("um_admin_token", token);
  }, login.access_token);
  return login.access_token as string;
}

test.describe("Visual smoke", () => {
  test("admin dashboard shell", async ({ page, request }) => {
    await loginAsAdmin(page, request);
    await page.goto("/admin", { waitUntil: "networkidle" });
    await expect(page.getByRole("button", { name: "Тарифи" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Автоматизації" })).toBeVisible();
  });

  test("electricity mode form transitions", async ({ page, request }) => {
    await loginAsAdmin(page, request);
    await page.goto("/admin", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Тарифи" }).click();
    await expect(page.getByRole("heading", { name: "Історія режимів електролічильника" })).toBeVisible();

    const modeSelect = page.getByRole("combobox", { name: "Режим" });
    await modeSelect.selectOption("single");
    await expect(page.getByRole("textbox", { name: "Назва послуги" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Стартовий показник total" })).toBeVisible();

    await modeSelect.selectOption("day_night");
    await expect(page.getByRole("textbox", { name: "Назва денного тарифу" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Назва нічного тарифу" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Стартовий day" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Стартовий night" })).toBeVisible();

    await modeSelect.selectOption("tri_zone");
    await expect(page.getByRole("textbox", { name: "Назва пікового тарифу" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Назва напівпікового тарифу" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Назва нічного тарифу" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Стартовий peak" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Стартовий semi_peak" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Стартовий off_peak" })).toBeVisible();
  });

  test("batch readings modal opens for current meter registers", async ({ page, request }) => {
    await loginAsAdmin(page, request);
    await page.goto("/admin", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Внести показники" }).click();
    await expect(page.getByRole("heading", { name: "Внести показники лічильника" })).toBeVisible();
    await expect(page.getByRole("combobox", { name: "Лічильник" })).toBeVisible();
    await expect(page.locator("text=режим:").first()).toBeVisible();
  });

  test("automation dry-run and manual cycle are visible in UI", async ({ page, request }) => {
    await loginAsAdmin(page, request);
    await page.goto("/admin", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Автоматизації" }).click();
    await page.getByRole("button", { name: "Dry-run циклу" }).click();
    await expect(page.getByRole("heading", { name: "Dry-run планового циклу" })).toBeVisible();
    await page.getByRole("button", { name: "Закрити" }).click();
    await expect(page.getByRole("cell", { name: "Dry-run" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Запустити плановий цикл" })).toBeVisible();
    await page.getByRole("button", { name: "Запустити плановий цикл" }).click();
    await expect(page.getByRole("cell", { name: "Ручний" }).first()).toBeVisible();
  });

  test("meter submit confirm flow dispatches and restores reading", async ({ page, request }, testInfo) => {
    test.skip(testInfo.project.name === "mobile", "Mutation flow runs only on desktop.");
    test.setTimeout(90000);
    const token = await loginAsAdmin(page, request);
    const apartmentsResponse = await request.get("/api/admin/dashboard/apartments", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const apartments = await apartmentsResponse.json();
    const apartment = apartments.find((item: { address?: string }) => item.address === "Івасюка 11, кв.195");
    expect(apartment).toBeTruthy();
    const automationsResponse = await request.get(`/api/admin/apartments/${apartment.apartment_id}/automations`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const automations = await automationsResponse.json();
    const automationSnapshots = automations
      .filter((item: { template_id?: number; provider_id?: number | null }) => item.template_id && item.provider_id)
      .map((item: Record<string, unknown>) => ({ ...item }));
    expect(automationSnapshots.length).toBeGreaterThan(0);
    let targetMeterId: number | null = null;
    let targetRegisterName = "total";
    let originalReading: number | null = null;

    try {
      for (const automation of automationSnapshots) {
        await request.put(`/api/admin/apartments/${apartment.apartment_id}/automations`, {
          headers: { Authorization: `Bearer ${token}` },
          data: {
            apartment_id: apartment.apartment_id,
            template_id: automation.template_id,
            provider_id: automation.provider_id || null,
            personal_account: automation.personal_account || null,
            cabinet_url: automation.cabinet_url || null,
            cabinet_login: automation.cabinet_login || null,
            cabinet_password: automation.cabinet_password || null,
            is_enabled: automation.is_enabled,
            accrual_enabled: automation.accrual_enabled,
            accrual_time: automation.accrual_time || "09:00",
            accrual_window_day_from: automation.accrual_window_day_from || 1,
            accrual_window_day_to: automation.accrual_window_day_to || 10,
            submit_enabled: true,
            submit_time: automation.submit_time || "09:00",
            submit_window_day_from: 28,
            submit_window_day_to: 15,
          },
        });
      }
      const detailResponse = await request.get(`/api/admin/dashboard/apartments/${apartment.apartment_id}?year=2026&month=2`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const detail = await detailResponse.json();
      const meteredRows = detail.rows.filter(
        (row: { meter_id?: number | null; current_reading?: string | number | null }) =>
          !!row.meter_id && row.current_reading !== null && row.current_reading !== undefined && row.current_reading !== "",
      );
      let targetRow: Record<string, unknown> | null = null;
      for (const row of meteredRows) {
        const registerName = String(row.meter_register || "total");
        const evalResponse = await request.get(
          `/api/admin/automations/meter-submit/evaluate?apartment_id=${encodeURIComponent(
            String(apartment.apartment_id),
          )}&meter_id=${encodeURIComponent(String(row.meter_id))}&register_name=${encodeURIComponent(registerName)}&year=2026&month=2`,
          {
            headers: { Authorization: `Bearer ${token}` },
          },
        );
        const evalResult = await evalResponse.json();
        if (evalResult.can_submit) {
          targetRow = row;
          break;
        }
      }
      expect(targetRow).toBeTruthy();
      originalReading = Number(targetRow?.current_reading);
      const nextReading = originalReading + 1;
      targetMeterId = Number(targetRow?.meter_id);
      targetRegisterName = String(targetRow?.meter_register || "total");
      const registersResponse = await request.get(
        `/api/admin/apartments/${apartment.apartment_id}/meters/${targetMeterId}/expected-registers?year=2026&month=2`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const registerMeta = await registersResponse.json();
      const registerIndex = Math.max(
        registerMeta.registers.findIndex((item: { register_name?: string }) => item.register_name === targetRegisterName),
        0,
      );

      await page.goto("/admin", { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "Внести показники" }).click();
      await expect(page.getByRole("heading", { name: "Внести показники лічильника" })).toBeVisible();
      await page.getByRole("combobox", { name: "Лічильник" }).selectOption(String(targetMeterId));
      const readingInput = page.getByRole("textbox", { name: "Поточний показник" }).nth(registerIndex);
      await readingInput.fill(String(nextReading));
      await expect(readingInput).toHaveValue(String(nextReading));
      await page.getByRole("button", { name: "Зберегти показники" }).click();
      await expect(page.getByRole("heading", { name: "Передати показник постачальнику" })).toBeVisible({ timeout: 15000 });
      await page.getByRole("button", { name: "Підтвердити" }).click();
      await expect(page.getByText(/передано/i).first()).toBeVisible();
    } finally {
      if (targetMeterId && originalReading !== null) {
        await request.post("/api/admin/readings", {
          headers: { Authorization: `Bearer ${token}` },
          data: {
            meter_id: targetMeterId,
            register_name: targetRegisterName || "total",
            year: 2026,
            month: 2,
            value: originalReading,
          },
        });
      }
      for (const automation of automationSnapshots) {
        await request.put(`/api/admin/apartments/${apartment.apartment_id}/automations`, {
          headers: { Authorization: `Bearer ${token}` },
          data: {
            apartment_id: apartment.apartment_id,
            template_id: automation.template_id,
            provider_id: automation.provider_id || null,
            personal_account: automation.personal_account || null,
            cabinet_url: automation.cabinet_url || null,
            cabinet_login: automation.cabinet_login || null,
            cabinet_password: automation.cabinet_password || null,
            is_enabled: automation.is_enabled,
            accrual_enabled: automation.accrual_enabled,
            accrual_time: automation.accrual_time || "09:00",
            accrual_window_day_from: automation.accrual_window_day_from || 1,
            accrual_window_day_to: automation.accrual_window_day_to || 10,
            submit_enabled: automation.submit_enabled,
            submit_time: automation.submit_time || "09:00",
            submit_window_day_from: automation.submit_window_day_from || 28,
            submit_window_day_to: automation.submit_window_day_to || 3,
          },
        });
      }
    }
  });

  test("admin login screen", async ({ page }) => {
    await page.goto("/admin", { waitUntil: "networkidle" });
    await expect(page).toHaveScreenshot("admin-login.png", { fullPage: true });
  });

  test("tenant login screen", async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle" });
    await expect(page).toHaveScreenshot("tenant-login.png", { fullPage: true });
  });
});
