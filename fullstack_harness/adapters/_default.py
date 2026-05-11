"""Default adapter — no-op pass-through.

기술 스택을 모르거나 explicit adapter 가 없을 때 fallback.
harness.json.commands 에 명시된 그대로 사용. 별도 fallback 없음.

step_gates 는 일반적인 V-Model 경로의 권장 매핑만 제공 (없는 command 키는 자동 skip).
"""

from __future__ import annotations

from typing import Any


NAME = "_default"


def match(stack: dict[str, Any]) -> bool:
    # default 는 명시적 매칭 안 함 (resolver 의 fallback 으로만 사용).
    return False


def commands_defaults() -> dict[str, str]:
    return {}


def step_gates() -> dict[str, list[str]]:
    """V-Model step 별 권장 gate command 키 (harness.json.commands 의 키).

    실제 실행 시 harness.json.commands 에 해당 키가 비어 있으면 자동 skip.
    """
    return {
        "spec": [],
        "design": [],
        "test-first": ["lint"],
        "implement": ["typecheck", "lint", "test_unit"],
        "integrate": ["build", "test_integration"],
        "accept": ["test_e2e"],
    }
