"""harness.json + phases/index.json 로드 및 검증.

target project의 root에서 harness.json을 읽어 HarnessConfig를 만든다.
경로 해석은 모두 target_root 기준 (이 harness 자체 코드는 어디에 있든 무관).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


HARNESS_CONFIG_FILENAME = "harness.json"
SUPPORTED_HARNESS_VERSIONS = ("0.1",)


class HarnessConfigError(Exception):
    """harness.json 로드/검증 실패."""


@dataclass(frozen=True)
class HarnessConfig:
    target_root: Path
    raw: dict[str, Any]

    @property
    def project(self) -> str:
        return self.raw.get("project", "<unnamed>")

    @property
    def phases_dir(self) -> Path:
        return self.target_root / self.raw.get("phases_dir", "phases")

    @property
    def phases_index_path(self) -> Path:
        return self.phases_dir / "index.json"

    @property
    def discovery(self) -> dict[str, Any]:
        return self.raw.get("discovery", {}) or {}

    @property
    def discovery_required_files(self) -> list[Path]:
        files = self.discovery.get("required_files", []) or []
        return [self.target_root / f for f in files]

    @property
    def discovery_id_prefixes(self) -> dict[str, str]:
        return self.discovery.get("id_prefixes", {}) or {}

    @property
    def discovery_command(self) -> str:
        return self.discovery.get("command", "")

    @property
    def commands(self) -> dict[str, str]:
        return self.raw.get("commands", {}) or {}

    @property
    def worktree_base(self) -> Path:
        base = self.raw.get("worktree", {}).get("base_path", ".worktrees")
        return self.target_root / base

    @property
    def db_isolation(self) -> str:
        return self.raw.get("worktree", {}).get("db_isolation", "none")

    @property
    def v_model_default(self) -> bool:
        return bool(self.raw.get("v_model", {}).get("default", True))

    @property
    def v_model_steps(self) -> list[str]:
        steps = self.raw.get("v_model", {}).get("steps") or [
            "spec", "design", "test-first", "implement", "integrate", "accept",
        ]
        return list(steps)


def load_config(target_root: Path | None = None) -> HarnessConfig:
    """target_root/harness.json 을 로드. target_root None이면 현재 cwd 위 디렉토리에서 검색."""
    root = _resolve_root(target_root)
    config_path = root / HARNESS_CONFIG_FILENAME
    if not config_path.exists():
        raise HarnessConfigError(
            f"{HARNESS_CONFIG_FILENAME} 을 찾지 못했습니다. 경로: {config_path}\n"
            f"`fullstack_harness/templates/harness.json.template` 를 복사해서 시작하세요."
        )
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HarnessConfigError(f"{config_path} JSON 파싱 실패: {e}") from e

    _validate_raw(raw, config_path)
    return HarnessConfig(target_root=root, raw=raw)


def _resolve_root(target_root: Path | None) -> Path:
    if target_root is not None:
        return Path(target_root).resolve()
    # 현재 cwd부터 위로 올라가며 harness.json 검색 (최대 5단계)
    cur = Path.cwd().resolve()
    for _ in range(6):
        if (cur / HARNESS_CONFIG_FILENAME).exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    # 못 찾으면 cwd 반환 (이후 단계에서 명확한 에러)
    return Path.cwd().resolve()


def _validate_raw(raw: dict[str, Any], path: Path) -> None:
    ver = str(raw.get("harness_version", ""))
    if ver not in SUPPORTED_HARNESS_VERSIONS:
        raise HarnessConfigError(
            f"{path}: harness_version='{ver}' 는 지원되지 않습니다. "
            f"지원 버전: {SUPPORTED_HARNESS_VERSIONS}"
        )
    if not raw.get("project"):
        raise HarnessConfigError(f"{path}: 'project' 필드가 필요합니다.")


def read_phases_index(cfg: HarnessConfig) -> dict[str, Any]:
    """phases/index.json 로드."""
    p = cfg.phases_index_path
    if not p.exists():
        raise HarnessConfigError(
            f"{p} 없음. phases 디렉토리를 초기화하세요.\n"
            f"`fullstack_harness/templates/phases_index.json.template` 참조."
        )
    return json.loads(p.read_text(encoding="utf-8"))


def write_phases_index(cfg: HarnessConfig, data: dict[str, Any]) -> None:
    cfg.phases_index_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def read_phase_index(cfg: HarnessConfig, phase_dir: str) -> dict[str, Any]:
    p = cfg.phases_dir / phase_dir / "index.json"
    if not p.exists():
        raise HarnessConfigError(f"{p} 없음. phase '{phase_dir}' 초기화되지 않음.")
    return json.loads(p.read_text(encoding="utf-8"))


def write_phase_index(cfg: HarnessConfig, phase_dir: str, data: dict[str, Any]) -> None:
    p = cfg.phases_dir / phase_dir / "index.json"
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
