import { describe, expect, it } from "vitest";

import {
  buildChatGptPrompt,
  buildCompactChartText,
  buildFullJson,
  formatLuckStartAge,
  mapChartCalculationError,
  type ChartPresentationData,
} from "../src/presentation";

const chartResult = {
  method_id: "bazi-deterministic-lichun-jie-noaa-v0.1",
  calculation_version: "0.1.0",
  calendar: {
    input_calendar: "solar",
    input_date: "2000-01-07",
    solar_date: "2000-01-07",
    input_datetime: "2000-01-07T12:00:00+08:00",
    corrected_datetime: "2000-01-07T12:00:00+08:00",
    timezone: "Asia/Shanghai",
    longitude: 121.4737,
    latitude: 31.2304,
    true_solar_time_applied: false,
    true_solar_correction_minutes: 0,
    equation_of_time_minutes: -5.8,
  },
  pillars: { year: "己卯", month: "丁丑", day: "甲子", hour: "庚午" },
  boundaries: {
    lichun_utc: "2000-02-04T12:40:00+00:00",
    active_month_term: "xiaohan",
    active_month_term_utc: "2000-01-06T01:00:00+00:00",
  },
  luck: {
    direction: "forward",
    start_age_years: 2.545911,
    adjacent_jie: "lichun",
    adjacent_jie_utc: "2000-02-04T12:40:00+00:00",
  },
  warnings: ["longitude_missing_true_solar_time_not_applied"],
  prediction_validity: "not_evaluated",
};

const presentation: ChartPresentationData = {
  result: chartResult,
  canonicalHash: `sha256:${"1".repeat(64)}`,
  gitSha: "4fc75751354300dd417c0d28e4f1879e797973b5",
  wheelSha256: "aed1ef4b21f8118eb2df6bb1d8d9e83a5073d4d4fbbb86cba1c5e8b01ca37958",
};

const forbiddenDerivedTerms = ["喜忌", "喜用神", "格局", "流年", "大运"];

describe("ChartCalculationError 中文提示", () => {
  it.each([
    ["INVALID_INPUT", /输入.*结构|结构.*输入/u],
    ["INVALID_DATE", /日期/u],
    ["INVALID_TIME", /时间/u],
    ["INVALID_CALENDAR", /历法/u],
    ["INVALID_GENDER", /性别/u],
    ["INVALID_LUNAR_DATE", /农历.*(?:月份|日期)|(?:月份|日期).*农历/u],
    ["MISSING_LONGITUDE", /经度/u],
    ["INVALID_COORDINATE", /经度|纬度|坐标/u],
    ["INVALID_TIMEZONE", /时区/u],
    ["NONEXISTENT_LOCAL_TIME", /本地时间|夏令时/u],
    ["SOLAR_TERM_UNCERTAIN", /节气/u],
    ["UNSUPPORTED_YEAR", /年份|年度|1901|2099/u],
    ["INVALID_LEAP_MONTH", /闰月/u],
    ["INVALID_FOLD", /fold|重叠时间|夏令时/u],
    ["INTERNAL_SOLAR_TERM", /内部.*计算|计算.*失败/u],
  ])("为 %s 返回中文、可操作的提示", (code, subject) => {
    const message = mapChartCalculationError(code);

    expect(message).toMatch(/[\u3400-\u9fff]/u);
    expect(message).toMatch(subject);
    expect(message).toMatch(/请|需要|改用|确认|重新/u);
  });

  it("节气边界不确定时显式要求人工复核，不继续给出确定四柱", () => {
    const message = mapChartCalculationError("SOLAR_TERM_UNCERTAIN");

    expect(message).toContain("REVIEW_REQUIRED");
    expect(message).toMatch(/人工复核|重新选择/u);
  });

  it("INVALID_LUNAR_DATE 指引用户检查月份、日期与闰月且不暴露内部文本", () => {
    const message = mapChartCalculationError("INVALID_LUNAR_DATE");

    expect(message).toMatch(/农历/u);
    expect(message).toMatch(/月份/u);
    expect(message).toMatch(/日期/u);
    expect(message).toMatch(/闰月/u);
    expect(message).toMatch(/检查|确认/u);
    expect(message).not.toContain("INVALID_LUNAR_DATE");
    expect(message).not.toMatch(/Traceback|\.py|line \d+/iu);
  });

  it("INTERNAL_SOLAR_TERM 明确内部失败并给出重新加载与重复报告建议", () => {
    const message = mapChartCalculationError("INTERNAL_SOLAR_TERM");

    expect(message).toMatch(/内部.*(?:计算|失败)|(?:计算|失败).*内部/u);
    expect(message).toMatch(/重新加载|刷新/u);
    expect(message).toMatch(/重复.*(?:输入范围|版本).*报告|报告.*(?:输入范围|版本)/u);
    expect(message).not.toContain("INTERNAL_SOLAR_TERM");
  });

  it("未知错误码安全失败关闭，不回显内部代码或 Python 异常", () => {
    const code = "SYNTHETIC_UNKNOWN_INTERNAL_CODE";
    const message = mapChartCalculationError(code);

    expect(message).toMatch(/停止|未完成|失败/u);
    expect(message).toMatch(/请|重新|刷新/u);
    expect(message).not.toContain(code);
    expect(message).not.toMatch(/Traceback|\.py|line \d+/iu);
  });
});

describe("结果展示与导出", () => {
  it("同时保留起运年龄原始小数和易读近似", () => {
    expect(formatLuckStartAge(2.545911)).toBe("2.545911 岁（约 2 年 7 个月）");
  });

  it("简版排盘只展示引擎返回事实与构建溯源，不补算字段", () => {
    const text = buildCompactChartText(presentation);

    expect(text).toContain("己卯 丁丑 甲子 庚午");
    expect(text).toContain("2.545911 岁（约 2 年 7 个月）");
    expect(text).toContain(chartResult.method_id);
    expect(text).toContain(presentation.canonicalHash);
    for (const term of forbiddenDerivedTerms) expect(text).not.toContain(term);
  });

  it("完整 JSON 是输入结果与溯源的无损序列化，不增加推断字段", () => {
    const parsed = JSON.parse(buildFullJson(presentation));

    expect(parsed).toEqual(presentation);
    for (const term of forbiddenDerivedTerms) expect(buildFullJson(presentation)).not.toContain(term);
  });

  it("标准 ChatGPT 提示词只引用真实返回字段，不要求或声称额外命理计算", () => {
    const prompt = buildChatGptPrompt(presentation);

    expect(prompt).toContain("己卯");
    expect(prompt).toContain("not_evaluated");
    expect(prompt).toContain(chartResult.method_id);
    expect(prompt).toContain(presentation.canonicalHash);
    for (const term of forbiddenDerivedTerms) expect(prompt).not.toContain(term);
  });
});
