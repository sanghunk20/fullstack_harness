"""Tech-stack adapter plugin point.

각 adapter 는 하나의 module 로, 다음 contract 를 제공:

    NAME: str                            # 어댑터 식별자
    def match(stack: dict) -> bool: ...  # harness.json.stack 으로 자동 매칭
    def commands_defaults() -> dict[str, str]: ...
        # harness.json.commands 에 비어 있는 키의 fallback
    def step_gates() -> dict[str, list[str]]: ...
        # V-Model step name -> 권장 gate command 키 목록 (harness.json.commands 기준)

adapter resolution:
1. harness.json.stack.adapter 가 지정돼 있으면 그 이름의 adapter 우선 사용.
2. 아니면 built-in + user-local adapter 들을 순회하며 match(stack) 가 True 인 첫 adapter.
3. 어느 것도 매칭 안 되면 `_default` (no-op pass-through).

user-local adapter 위치:
    <target_root>/.harness/adapters/*.py
이 위치의 .py 파일들은 importlib 로 동적 로드. 같은 NAME 이 있으면 user-local 우선.
"""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


@dataclass(frozen=True)
class AdapterInfo:
    name: str
    module: ModuleType
    source: str  # "builtin" | "user"

    def commands_defaults(self) -> dict[str, str]:
        fn = getattr(self.module, "commands_defaults", None)
        return dict(fn() if callable(fn) else {})

    def step_gates(self) -> dict[str, list[str]]:
        fn = getattr(self.module, "step_gates", None)
        return dict(fn() if callable(fn) else {})


def _iter_builtin_adapters() -> list[AdapterInfo]:
    """fullstack_harness.adapters 패키지 안의 모듈들을 순회. `_` prefix 모듈은 제외."""
    out: list[AdapterInfo] = []
    pkg_path = Path(__file__).parent
    for info in pkgutil.iter_modules([str(pkg_path)]):
        name = info.name
        if name.startswith("_protocol"):
            continue
        mod = importlib.import_module(f"fullstack_harness.adapters.{name}")
        adapter_name = getattr(mod, "NAME", name)
        out.append(AdapterInfo(name=adapter_name, module=mod, source="builtin"))
    return out


def _iter_user_adapters(target_root: Path) -> list[AdapterInfo]:
    """<target_root>/.harness/adapters/*.py 의 모듈들을 동적 로드.

    절대 경로 기반 importlib.spec_from_file_location 사용. import 부작용은 최소화.
    """
    out: list[AdapterInfo] = []
    user_dir = target_root / ".harness" / "adapters"
    if not user_dir.is_dir():
        return out
    for py in sorted(user_dir.glob("*.py")):
        if py.name.startswith("_"):
            continue
        mod_name = f"_user_adapter_{py.stem}"
        spec = importlib.util.spec_from_file_location(mod_name, py)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            # adapter 로딩 실패는 전체 흐름을 망치지 않도록 swallow.
            # debugging 용으로 stderr 에 한 줄 안내 가능 (TODO v0.3).
            continue
        adapter_name = getattr(mod, "NAME", py.stem)
        out.append(AdapterInfo(name=adapter_name, module=mod, source="user"))
    return out


def list_adapters(target_root: Path) -> list[AdapterInfo]:
    """모든 adapter 나열. user-local 이 builtin 보다 우선."""
    user = _iter_user_adapters(target_root)
    builtin = _iter_builtin_adapters()
    seen: set[str] = set()
    out: list[AdapterInfo] = []
    for a in [*user, *builtin]:
        if a.name in seen:
            continue
        seen.add(a.name)
        out.append(a)
    return out


def resolve_adapter(target_root: Path, stack: dict[str, Any], explicit: str | None = None) -> AdapterInfo:
    """harness.json.stack 으로 적합한 adapter 선택.

    1. explicit (보통 stack.adapter) 가 있으면 그 이름의 adapter.
    2. 아니면 match(stack) 가 True 인 첫 adapter.
    3. 모두 미스면 `_default`.
    """
    all_adapters = list_adapters(target_root)
    if explicit:
        for a in all_adapters:
            if a.name == explicit:
                return a
        # 명시 이름이 못 찾으면 default 로 떨어지되 호출자가 인지할 수 있도록 _missing flag 부착
        # (현재는 단순히 default 로 fallback)
    for a in all_adapters:
        match_fn = getattr(a.module, "match", None)
        if callable(match_fn):
            try:
                if match_fn(stack):
                    return a
            except Exception:
                continue
    # default
    for a in all_adapters:
        if a.name == "_default":
            return a
    # _default 도 없으면 빈 adapter (이론상 도달 안 함)
    raise RuntimeError("No adapter resolved and _default missing from builtins")
