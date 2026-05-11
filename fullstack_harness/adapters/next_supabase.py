"""Next.js + Supabase 어댑터 (built-in, 예시).

이 adapter 는 default value 만 제공한다. 실제 명령은 사용자의 harness.json.commands
에서 덮어쓰기 가능. harness.json.commands 가 우선.
"""

from __future__ import annotations

from typing import Any


NAME = "next_supabase"


def match(stack: dict[str, Any]) -> bool:
    fw = (stack.get("framework") or "").lower()
    db = (stack.get("db") or "").lower()
    return fw in ("next", "nextjs", "next.js") and db == "supabase"


def commands_defaults() -> dict[str, str]:
    return {
        "dev": "npm run dev",
        "build": "npm run build",
        "typecheck": "npm run typecheck",
        "lint": "npm run lint",
        "test_unit": "npm run test",
        "test_integration": "npm run test:integration",
        "test_e2e": "npm run test:e2e",
        "migrate": "npx supabase db reset",
        "format": "npm run format",
    }


def step_gates() -> dict[str, list[str]]:
    return {
        "spec": [],
        "design": [],
        "test-first": ["lint"],
        "implement": ["typecheck", "lint", "test_unit"],
        "integrate": ["build", "test_integration"],
        "accept": ["test_e2e"],
    }
