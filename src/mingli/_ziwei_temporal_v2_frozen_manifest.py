"""Independent semantic manifest for the fixed Ziwei temporal V2 ruleset.

These literal hashes deliberately do not derive from the executable rule templates.
Changing rule semantics under the same content version must therefore fail closed.
"""

from __future__ import annotations

from types import MappingProxyType


FROZEN_ZIWEI_TEMPORAL_V2_RULESET_VERSION = (
    "ziwei-temporal-combination-rules@2.0.0"
)
FROZEN_ZIWEI_TEMPORAL_V2_RULE_HASHES = MappingProxyType(
    {
        "ziwei-temporal-v2:brightness:wealth-mixed-state": (
            "sha256:6742ef1ab4527372e992e3ef8b2f4afb549d6e7bb1994d5385a93a296eb93585"
        ),
        "ziwei-temporal-v2:four-transformations:lu-quan-colocated": (
            "sha256:ef7d4a5a09e9aee57bbe948e50872792ec8f6f072f5960def473234533ae154f"
        ),
        "ziwei-temporal-v2:geometry:life-arch": (
            "sha256:2ccd7650ad497e97c1b4d99eeb5ac105c4291eb738db68cd5b334dda2e265bf6"
        ),
        "ziwei-temporal-v2:geometry:life-convergence": (
            "sha256:ee3fb75fdb4184d9ac590fa29fb0a76a4134ee97c6a76263657c3c29d0101491"
        ),
        "ziwei-temporal-v2:geometry:life-four-orthogonals": (
            "sha256:8edca15cae86fea4aa9c224205a66ba044f2b4e67c37bd0251a54e1ee379faee"
        ),
        "ziwei-temporal-v2:geometry:life-migration-aspect": (
            "sha256:c196f3f361c84fdf4e88e615182ed173534c0c7e59e94692dfa03aaea29376e5"
        ),
        "ziwei-temporal-v2:geometry:life-sandwich": (
            "sha256:e7be286b123db4069921a564522d0c2921799bd704ce899396beed957603d329"
        ),
        "ziwei-temporal-v2:life-body:same-palace": (
            "sha256:5ee32e555d115d0bbb9fc5ded7b161ab051dae8409abaa07e63a1d130598f508"
        ),
        "ziwei-temporal-v2:overlay:decade-career": (
            "sha256:bcdcc826d8efcc7480471b1f32af15fe55078a37491e795ed11647844e1fbd9d"
        ),
        "ziwei-temporal-v2:overlay:month-relationship-family": (
            "sha256:6d1501186527d721c9ac4e1f9d31c49f14adcd20d8d3ec24b01ea9227599e6a0"
        ),
        "ziwei-temporal-v2:overlay:year-wealth-study": (
            "sha256:cfbd9660b42954f2fc27e42fe0d7a0426dede38f9e6890bfe1075fa26b2132d1"
        ),
        "ziwei-temporal-v2:primary-supporting:wealth-study-assist": (
            "sha256:d582e5c8c77bbe3e7060683b51423641a6dcfc3fb7c799ffa98f52e6c27e4b4a"
        ),
    }
)
FROZEN_ZIWEI_TEMPORAL_V2_RULE_IDS = frozenset(
    FROZEN_ZIWEI_TEMPORAL_V2_RULE_HASHES
)


__all__ = [
    "FROZEN_ZIWEI_TEMPORAL_V2_RULE_HASHES",
    "FROZEN_ZIWEI_TEMPORAL_V2_RULE_IDS",
    "FROZEN_ZIWEI_TEMPORAL_V2_RULESET_VERSION",
]
