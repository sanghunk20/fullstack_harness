"""Vue + Firebase 어댑터 (built-in, 예시).

stack.framework == "vue" + stack.db == "firebase" 매칭.
일반성 검증용 두 번째 어댑터로 의도.
"""

from __future__ import annotations

from typing import Any


NAME = "vue_firebase"


def match(stack: dict[str, Any]) -> bool:
    fw = (stack.get("framework") or "").lower()
    db = (stack.get("db") or "").lower()
    return fw in ("vue", "vuejs", "vue.js", "nuxt") and db in ("firebase", "firestore")


def commands_defaults() -> dict[str, str]:
    return {
        "dev": "npm run dev",
        "build": "npm run build",
        "typecheck": "npm run typecheck",
        "lint": "npm run lint",
        "test_unit": "npm run test:unit",
        "test_integration": "npm run test:integration",
        "test_e2e": "npm run test:e2e",
        "migrate": "firebase deploy --only firestore:rules,firestore:indexes",
        "format": "npm run format",
    }


def step_gates() -> dict[str, list[str]]:
    return {
        "spec": [],
        "design": [],
        "test-first": ["lint"],
        "implement": ["typecheck", "test_unit"],
        "integrate": ["build", "test_integration"],
        "accept": ["test_e2e"],
    }
