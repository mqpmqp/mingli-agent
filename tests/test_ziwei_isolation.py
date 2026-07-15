from __future__ import annotations

from mingli.ziwei import build_temporal_context, build_ziwei_chart
from mingli.ziwei_isolation import (
    ScopedZiweiCache,
    ZiweiResultGate,
    ZiweiScope,
    make_pair_context_hash,
)


def chart(date: str) -> dict[str, object]:
    return build_ziwei_chart(
        {
            "calendar_type": "solar",
            "birth_date": date,
            "birth_time": "12:00",
            "timezone": "Asia/Shanghai",
            "longitude": 121.4737,
            "latitude": 31.2304,
            "solar_time_mode": "civil",
            "late_zi_policy": "midnight",
            "gender": "female",
        }
    )


def test_cache_isolated_by_chart_user_case_and_temporal_context() -> None:
    cache = ScopedZiweiCache()
    scope_a = ZiweiScope(user_scope="user-a", case_scope="case-a", cache_namespace="ziwei-v1")
    scope_b = ZiweiScope(user_scope="user-b", case_scope="case-a", cache_namespace="ziwei-v1")
    scope_c = ZiweiScope(user_scope="user-a", case_scope="case-b", cache_namespace="ziwei-v1")
    annual = build_temporal_context("annual", year=2028)
    annual_2 = build_temporal_context("annual", year=2029)
    chart_a = chart("2000-01-07")
    chart_b = chart("2001-01-07")

    cache.put(scope_a, chart_a["chart_fingerprint"], annual, {"value": "A"})

    assert cache.get(scope_a, chart_a["chart_fingerprint"], annual) == {"value": "A"}
    assert cache.get(scope_a, chart_b["chart_fingerprint"], annual) is None
    assert cache.get(scope_b, chart_a["chart_fingerprint"], annual) is None
    assert cache.get(scope_c, chart_a["chart_fingerprint"], annual) is None
    assert cache.get(scope_a, chart_a["chart_fingerprint"], annual_2) is None


def test_old_async_request_cannot_overwrite_new_context_or_chart() -> None:
    gate = ZiweiResultGate()
    first_chart = chart("2000-01-07")["chart_fingerprint"]
    second_chart = chart("2001-01-07")["chart_fingerprint"]
    annual = build_temporal_context("annual", year=2028)

    gate.switch_chart(first_chart)
    old = gate.issue_request(annual)
    newer = gate.issue_request(build_temporal_context("annual", year=2029))
    assert gate.accepts(old) is False
    assert gate.accepts(newer) is True

    gate.switch_chart(second_chart)
    assert gate.accepts(newer) is False
    current = gate.issue_request(annual)
    assert current.chart_revision > old.chart_revision
    assert gate.accepts(current) is True


def test_pair_analysis_hash_is_order_and_identity_sensitive() -> None:
    a = chart("2000-01-07")["chart_fingerprint"]
    b = chart("2001-01-07")["chart_fingerprint"]
    c = chart("2002-01-07")["chart_fingerprint"]

    assert make_pair_context_hash(a, b) != make_pair_context_hash(b, a)
    assert make_pair_context_hash(a, b) != make_pair_context_hash(a, c)

