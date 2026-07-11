# Bazi Calculation Conventions v0.1

This document is the reproducibility contract for `bazi-deterministic-lichun-jie-noaa-v0.1`. It describes calculation choices, not prediction claims.

## Calendar and pillar boundaries

1. **Year pillar:** changes at the exact instant of Li Chun (solar longitude 315 degrees), not at Lunar New Year or Spring Festival.
2. **Month pillar:** changes at the twelve `jie`: Xiao Han, Li Chun, Jing Zhe, Qing Ming, Li Xia, Mang Zhong, Xiao Shu, Li Qiu, Bai Lu, Han Lu, Li Dong, and Da Xue. The intervening `qi` do not start a month pillar.
3. **Day pillar:** changes at 00:00 in civil local time, or at 00:00 in corrected local apparent solar time when true-solar correction is enabled.
4. **Zi hour:** 23:00-00:59 is Zi hour. This method does not split early and late Zi hour and does not advance the day pillar at 23:00.

## True solar time

The correction in minutes is:

```text
4 × (longitude_east − standard_meridian_east)
+ equation_of_time
− daylight_saving_minutes
```

`standard_meridian_east = standard_UTC_offset_hours × 15`. The equation of time uses the NOAA fractional-year approximation. Positive longitude is east. IANA time zones and explicit offsets such as `+08:00` are accepted. IANA daylight-saving rules are applied through Python `zoneinfo`; the Windows build installs `tzdata` because Windows does not provide an IANA database to `zoneinfo`.

Longitude is mandatory when correction is requested. Missing longitude fails with `MISSING_LONGITUDE`; the engine never claims that correction was completed. Latitude is range-checked and retained for traceability but is not used by this longitude/EoT formula. Year and month pillars use the actual birth instant against the solar-term instant; corrected wall time determines the day and hour pillars.

## Lunar dates and leap months

Lunar input uses `birth_date=YYYY-MM-DD` plus an explicit boolean `is_leap_month`. Month lengths and leap-month placement cover lunar years 1900-2099 so that supported input years 1901-2099 can be converted. A leap flag for a non-leap month fails with `INVALID_LEAP_MONTH`; a day outside the selected lunar month fails with `INVALID_LUNAR_DATE`. Lunar New Year does not replace the Li Chun year-pillar boundary.

## Luck direction and start age

- Yang-year male and yin-year female charts run forward; yin-year male and yang-year female charts run in reverse. Polarity is taken from the calculated year stem.
- Forward charts measure from birth to the next `jie`; reverse charts measure back to the previous `jie`.
- Elapsed days are divided by three and returned as decimal `start_age_years`. This is method-specific and is not silently interchangeable with minute-based or other schools.

## Method identity, range, and uncertainty

- `method_id`: `bazi-deterministic-lichun-jie-noaa-v0.1`
- supported input years: 1901-2099 inclusive
- solar-term method: low-precision NOAA/Meeus apparent solar longitude with bisection
- observed maximum difference against sxtwl 2.0.7 across the supported range: 12.93 minutes
- safety boundary: inputs within 15 minutes of a calculated `jie` fail with `SOLAR_TERM_UNCERTAIN` instead of selecting a pillar silently
- equation-of-time method: NOAA fractional-year approximation
- day boundary: 00:00
- early/late Zi distinction: disabled

The engine returns `method_id`, `conventions`, warnings, input/corrected datetimes, and `prediction_validity=not_evaluated` on every successful chart. A successful calculation means only that the declared arithmetic contract completed; it does not demonstrate predictive validity.

## Verification sources

- [Hong Kong Observatory Gregorian-Lunar conversion tables](https://www.hko.gov.hk/en/gts/time/conversion.htm), 1901-2100.
- [Hong Kong Observatory 24 Solar Terms](https://www.hko.gov.hk/en/gts/time/24solarterms.htm).
- [Hong Kong Observatory Heavenly Stems and Earthly Branches](https://www.hko.gov.hk/en/gts/time/stemsandbranches.htm), including the day-stem/hour-stem relationship.
- [NOAA General Solar Position Calculations](https://gml.noaa.gov/grad/solcalc/solareqns.PDF), equation-of-time formula.
- `sxtwl==2.0.7` and `lunar_python==1.4.8`, installed only as offline independent benchmark oracles. They are not runtime dependencies.
