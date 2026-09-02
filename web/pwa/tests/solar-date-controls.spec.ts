import { expect, test } from "@playwright/test";

test.describe("direct solar date controls", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/runtime/**", (route) => route.abort("failed"));
    await page.goto("/");
  });

  test("allows an old birth year to be entered directly without paging a native calendar", async ({ page }) => {
    const year = page.getByTestId("solar-year");
    const month = page.getByTestId("solar-month");
    const day = page.getByTestId("solar-day");
    const nativeDate = page.getByTestId("birth-date");

    await expect(year).toBeVisible();
    await expect(year).toHaveAttribute("type", "number");
    await expect(year).toHaveAttribute("min", "1901");
    await expect(year).toHaveAttribute("max", "2099");
    await expect(month).toHaveAttribute("min", "1");
    await expect(month).toHaveAttribute("max", "12");
    await expect(day).toHaveAttribute("min", "1");
    await expect(day).toHaveAttribute("max", "31");

    await year.fill("1980");
    await month.fill("6");
    await day.fill("15");

    await expect(nativeDate).toHaveValue("1980-06-15");
  });

  test("keeps the direct fields and the native date picker synchronized", async ({ page }) => {
    const nativeDate = page.getByTestId("birth-date");
    await nativeDate.fill("1972-12-03");

    await expect(page.getByTestId("solar-year")).toHaveValue("1972");
    await expect(page.getByTestId("solar-month")).toHaveValue("12");
    await expect(page.getByTestId("solar-day")).toHaveValue("3");
  });

  test("clears and disables solar quick inputs when switching to lunar mode", async ({ page }) => {
    const year = page.getByTestId("solar-year");
    const month = page.getByTestId("solar-month");
    const day = page.getByTestId("solar-day");

    await year.fill("1980");
    await month.fill("6");
    await day.fill("15");
    await page.getByTestId("calendar-lunar").check({ force: true });

    await expect(page.getByTestId("solar-date-row")).toBeHidden();
    await expect(year).toBeDisabled();
    await expect(month).toBeDisabled();
    await expect(day).toBeDisabled();
    await expect(year).toHaveValue("");
    await expect(month).toHaveValue("");
    await expect(day).toHaveValue("");

    await page.getByTestId("calendar-solar").check({ force: true });
    await expect(page.getByTestId("solar-date-row")).toBeVisible();
    await expect(year).toBeEnabled();
    await expect(month).toBeEnabled();
    await expect(day).toBeEnabled();
  });
});
