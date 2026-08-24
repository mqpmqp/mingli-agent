import { describe, expect, it } from "vitest";

import {
  isLeapMonthVisible,
  validateChartForm,
  type ChartFormValues,
} from "../src/form";

function validForm(overrides: Partial<ChartFormValues> = {}): ChartFormValues {
  return {
    gender: "male",
    calendar: "solar",
    birthDate: "2000-01-07",
    birthTime: "12:00",
    timezone: "Asia/Shanghai",
    birthLocationNote: "上海",
    longitude: "121.4737",
    latitude: "31.2304",
    trueSolarTime: false,
    isLeapMonth: false,
    fold: "0",
    ...overrides,
  };
}

describe("八字输入表单校验", () => {
  it("拒绝缺少性别、历法、日期、时间或时区的提交", () => {
    const result = validateChartForm(
      validForm({
        gender: "",
        calendar: "",
        birthDate: "",
        birthTime: "",
        timezone: "",
      }),
    );

    expect(result.valid).toBe(false);
    expect(result.errors).toMatchObject({
      gender: expect.stringMatching(/[\u3400-\u9fff]/u),
      calendar: expect.stringMatching(/[\u3400-\u9fff]/u),
      birthDate: expect.stringMatching(/[\u3400-\u9fff]/u),
      birthTime: expect.stringMatching(/[\u3400-\u9fff]/u),
      timezone: expect.stringMatching(/[\u3400-\u9fff]/u),
    });
    expect(result.input).toBeUndefined();
  });

  it("只在农历模式显示并提交闰月字段，清除阳历模式的隐藏旧值", () => {
    expect(isLeapMonthVisible("solar")).toBe(false);
    expect(isLeapMonthVisible("lunar")).toBe(true);

    const solar = validateChartForm(validForm({ calendar: "solar", isLeapMonth: true }));
    expect(solar.valid).toBe(true);
    expect(solar.input).not.toHaveProperty("is_leap_month");

    const lunar = validateChartForm(
      validForm({ calendar: "lunar", birthDate: "2023-02-01", isLeapMonth: true }),
    );
    expect(lunar.valid).toBe(true);
    expect(lunar.input).toMatchObject({ calendar: "lunar", is_leap_month: true });
  });

  it("启用真太阳时时必须填写经度", () => {
    const result = validateChartForm(validForm({ trueSolarTime: true, longitude: "" }));

    expect(result.valid).toBe(false);
    expect(result.errors.longitude).toMatch(/真太阳时.*经度|经度.*真太阳时/u);
    expect(result.input).toBeUndefined();
  });

  it.each([
    ["longitude", "180.0001"],
    ["longitude", "-180.0001"],
    ["latitude", "90.0001"],
    ["latitude", "-90.0001"],
  ] as const)("拒绝越界坐标 %s=%s", (field, value) => {
    const result = validateChartForm(validForm({ [field]: value }));

    expect(result.valid).toBe(false);
    expect(result.errors[field]).toMatch(/范围|介于/u);
    expect(result.input).toBeUndefined();
  });

  it("接受经纬度闭区间边界并转换为数字", () => {
    const eastNorth = validateChartForm(validForm({ longitude: "180", latitude: "90" }));
    const westSouth = validateChartForm(validForm({ longitude: "-180", latitude: "-90" }));

    expect(eastNorth.valid).toBe(true);
    expect(eastNorth.input).toMatchObject({ longitude: 180, latitude: 90 });
    expect(westSouth.valid).toBe(true);
    expect(westSouth.input).toMatchObject({ longitude: -180, latitude: -90 });
  });

  it("拒绝不是有效 IANA 名称的时区", () => {
    const result = validateChartForm(validForm({ timezone: "UTC+08:00" }));

    expect(result.valid).toBe(false);
    expect(result.errors.timezone).toMatch(/时区/u);
    expect(result.input).toBeUndefined();
  });

  it.each(["-1", "2", "not-a-fold"])("拒绝 fold=%s，只允许 0 或 1", (fold) => {
    const result = validateChartForm(validForm({ fold }));

    expect(result.valid).toBe(false);
    expect(result.errors.fold).toMatch(/0.*1|1.*0/u);
    expect(result.input).toBeUndefined();
  });

  it.each(["0", "1"])("接受 fold=%s 并转换为引擎所需数字", (fold) => {
    const result = validateChartForm(validForm({ fold }));

    expect(result.valid).toBe(true);
    expect(result.input).toMatchObject({ fold: Number(fold) });
  });
});
