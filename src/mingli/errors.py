from __future__ import annotations


class MingLiError(Exception):
    """MingLi 运行时可安全展示给用户的基础错误。"""


class ModelValidationError(MingLiError, ValueError):
    """输入不符合严格数据模型。"""


class RuleValidationError(MingLiError, ValueError):
    """规则文件解析或校验失败。"""

    def __init__(self, issues: list[str] | tuple[str, ...]):
        self.issues = tuple(issues)
        super().__init__("；".join(self.issues))


class ForbiddenPhraseError(MingLiError, ValueError):
    """渲染内容含有禁止使用的保证性或有害表达。"""


class ChartProviderUnavailable(MingLiError, RuntimeError):
    """没有配置经过验证的排盘器。"""


class RouterError(MingLiError, ValueError):
    """路由规范无效或意图不受支持。"""
