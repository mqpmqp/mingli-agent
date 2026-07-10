from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from .errors import ChartProviderUnavailable
from .models import ChartInput


@runtime_checkable
class ChartProvider(Protocol):
    def calculate(self, chart_input: ChartInput | Mapping[str, object]) -> Mapping[str, object]:
        """由经过验证的外部实现提供排盘结果。"""
        ...


class UnavailableChartProvider:
    def calculate(self, chart_input: ChartInput | Mapping[str, object]) -> Mapping[str, object]:
        del chart_input
        raise ChartProviderUnavailable(
            "未配置可靠排盘器；不可生成四柱或旺衰；不会使用硬编码示例盘冒充结果。"
        )
