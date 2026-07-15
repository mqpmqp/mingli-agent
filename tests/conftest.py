from __future__ import annotations

import pytest

from mingli.test_gates import classify_test


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        item.add_marker(getattr(pytest.mark, classify_test(item.nodeid)))
