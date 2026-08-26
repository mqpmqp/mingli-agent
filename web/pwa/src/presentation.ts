export type ChartResult = {
  method_id: string;
  calculation_version: string;
  calendar: {
    input_calendar: string;
    input_date: string;
    solar_date: string;
    input_datetime: string;
    corrected_datetime: string;
    timezone: string;
    longitude: number | null;
    latitude: number | null;
    true_solar_time_applied: boolean;
    true_solar_correction_minutes: number;
    equation_of_time_minutes: number;
  };
  pillars: { year: string; month: string; day: string; hour: string };
  boundaries: {
    lichun_utc: string;
    active_month_term: string;
    active_month_term_utc: string;
  };
  luck: {
    direction: string;
    start_age_years: number;
    adjacent_jie: string;
    adjacent_jie_utc: string;
  };
  warnings: string[];
  prediction_validity: string;
};

export type ChartPresentationData = {
  result: ChartResult;
  canonicalHash: string;
  gitSha: string;
  wheelSha256: string;
};

const ERROR_MESSAGES: Readonly<Record<string, string>> = {
  INVALID_INPUT: "输入结构无效，请检查必填字段与选项后重新提交。",
  INVALID_DATE: "出生日期无效，请确认日期后重新填写。",
  INVALID_TIME: "出生时间无效，请按 24 小时制确认后重新填写。",
  INVALID_CALENDAR: "历法选项无效，请重新选择阳历或农历。",
  INVALID_GENDER: "性别选项无效，请重新选择。",
  INVALID_LUNAR_DATE: "农历月份或日期无效，请检查月份、日期和闰月选项后重新提交。",
  MISSING_LONGITUDE: "启用真太阳时需要填写经度，请确认后重新提交。",
  INVALID_COORDINATE: "经度、纬度或坐标无效，请确认范围后重新填写。",
  INVALID_TIMEZONE: "时区无效，请确认 IANA 时区名称后重新填写。",
  NONEXISTENT_LOCAL_TIME: "该本地时间受夏令时影响而不存在，请确认时间或改用相邻有效时刻。",
  SOLAR_TERM_UNCERTAIN:
    "REVIEW_REQUIRED：输入时刻位于节气边界的不确定区间，需要人工复核；请重新选择明确时刻后再试。",
  UNSUPPORTED_YEAR: "年份超出支持范围（1901 至 2099 年），请确认后重新填写。",
  INVALID_LEAP_MONTH: "闰月信息无效，请确认农历月份后重新选择。",
  INVALID_FOLD: "重叠时间的 fold 无效，请确认夏令时情况并选择 0 或 1。",
  INTERNAL_SOLAR_TERM:
    "内部节气计算失败，请重新加载页面；若重复出现，请记录输入范围和版本信息后报告。",
};

export function mapChartCalculationError(code: string): string {
  return ERROR_MESSAGES[code] ?? "排盘计算未完成，请检查输入后重新尝试。";
}

export function formatLuckStartAge(startAgeYears: number): string {
  if (!Number.isFinite(startAgeYears) || startAgeYears < 0) return "数据无效";
  const totalMonths = Math.round(startAgeYears * 12);
  const years = Math.floor(totalMonths / 12);
  const months = totalMonths % 12;
  return `${startAgeYears} 岁（约 ${years} 年 ${months} 个月）`;
}

export function buildCompactChartText(data: ChartPresentationData): string {
  const { result } = data;
  return [
    `四柱：${result.pillars.year} ${result.pillars.month} ${result.pillars.day} ${result.pillars.hour}`,
    `出生时间：${result.calendar.input_datetime}`,
    `校正时间：${result.calendar.corrected_datetime}`,
    `起运方向：${result.luck.direction}`,
    `起运年龄：${formatLuckStartAge(result.luck.start_age_years)}`,
    `相邻节：${result.luck.adjacent_jie}（${result.luck.adjacent_jie_utc}）`,
    `当前月节：${result.boundaries.active_month_term}（${result.boundaries.active_month_term_utc}）`,
    `method_id：${result.method_id}`,
    `calculation_version：${result.calculation_version}`,
    `prediction_validity：${result.prediction_validity}`,
    `git_sha：${data.gitSha}`,
    `wheel_sha256：${data.wheelSha256}`,
    `canonical_result_hash：${data.canonicalHash}`,
  ].join("\n");
}

export function buildFullJson(data: ChartPresentationData): string {
  return JSON.stringify(data, null, 2);
}

export function buildChatGptPrompt(data: ChartPresentationData): string {
  return [
    "请让 ChatGPT 基于下面确定性排盘引擎返回的 JSON 做谨慎、通俗的中文解读。",
    "只引用真实返回字段，不补算未提供的信息；请区分排盘事实、解释和不确定性，并保留 prediction_validity 的原始含义。",
    `method_id：${data.result.method_id}`,
    `calculation_version：${data.result.calculation_version}`,
    `canonical_result_hash：${data.canonicalHash}`,
    "```json",
    JSON.stringify(data.result, null, 2),
    "```",
  ].join("\n");
}
