"""set-deps — phases/index.json 의 depends_on 일괄 패치.

입력: JSON 파일 또는 stdin.
형식:
{
  "<phase_dir>": ["<dep1>", "<dep2>", ...] | "all_features",
  ...
}

동작:
1. phases/index.json 백업 → phases/index.json.bak.<timestamp>
2. 각 phase 의 depends_on 을 입력대로 패치
3. build_dag 로 재검증 (cycle / 미지 참조 등)
4. 실패 시 백업에서 자동 복원 + 에러
5. 성공 시 변경된 phase 목록 출력

이 모듈은 LLM-driven 의존성 inference 흐름의 Python-side 마무리 단계다.
실제 추론은 슬래시 명령 (/harness analyze-deps) 에서 LLM 이 수행.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import HarnessConfig, read_phases_index, write_phases_index
from .dag import DAGError, build_dag


class SetDepsError(Exception):
    pass


@dataclass
class SetDepsReport:
    backup_path: Path
    changed: list[tuple[str, list[str] | str, list[str] | str]]  # (phase, old, new)
    unchanged: list[str]


def load_deps_input(path: Path | None) -> dict[str, Any]:
    """JSON 입력 로드. path 가 None 이면 stdin 에서 읽음."""
    if path is None:
        raw = sys.stdin.read()
        if not raw.strip():
            raise SetDepsError("입력이 비어 있습니다 (stdin).")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise SetDepsError(f"stdin JSON 파싱 실패: {e}") from e
    if not path.exists():
        raise SetDepsError(f"입력 파일이 없습니다: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SetDepsError(f"{path} JSON 파싱 실패: {e}") from e


def _backup_path(cfg: HarnessConfig) -> Path:
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    return cfg.phases_index_path.with_suffix(f".json.bak.{ts}")


def _validate_input_shape(deps: dict[str, Any]) -> None:
    if not isinstance(deps, dict):
        raise SetDepsError(f"입력은 객체여야 합니다. 받은 타입: {type(deps).__name__}")
    for phase, val in deps.items():
        if not isinstance(phase, str):
            raise SetDepsError(f"phase 키는 문자열이어야 합니다: {phase!r}")
        if val == "all_features":
            continue
        if isinstance(val, list):
            for v in val:
                if not isinstance(v, str):
                    raise SetDepsError(
                        f"phase '{phase}': depends_on 리스트의 항목은 문자열이어야 합니다. 받은: {v!r}"
                    )
            continue
        raise SetDepsError(
            f"phase '{phase}': depends_on 은 list 또는 'all_features' 문자열이어야 합니다. 받은: {val!r}"
        )


def apply_deps(cfg: HarnessConfig, deps: dict[str, Any]) -> SetDepsReport:
    """deps 입력을 phases/index.json 에 적용.

    백업 → 패치 → DAG 재검증. 검증 실패 시 백업 복원.
    """
    _validate_input_shape(deps)

    top = read_phases_index(cfg)
    phases = top.get("phases", [])
    known_dirs = {p.get("dir") for p in phases}

    # 입력의 phase 들이 모두 알려진 phase 인지 확인
    unknown = [p for p in deps if p not in known_dirs]
    if unknown:
        raise SetDepsError(
            f"입력에 알 수 없는 phase 가 있습니다: {unknown}. phases/index.json 에 존재하지 않습니다."
        )

    # 백업
    backup = _backup_path(cfg)
    shutil.copy2(cfg.phases_index_path, backup)

    # 패치
    changed: list[tuple[str, Any, Any]] = []
    unchanged: list[str] = []
    for p in phases:
        d = p.get("dir")
        if d not in deps:
            continue
        old = p.get("depends_on")
        new = deps[d]
        # 정규화 비교
        old_norm = old if old is not None else []
        if _normalize(old_norm) == _normalize(new):
            unchanged.append(d)
            continue
        p["depends_on"] = new
        changed.append((d, old, new))

    if not changed:
        # 변경 없으면 백업 제거 후 종료
        backup.unlink(missing_ok=True)
        return SetDepsReport(backup_path=backup, changed=[], unchanged=unchanged)

    # 임시 쓰기 후 DAG 검증
    write_phases_index(cfg, top)
    try:
        build_dag(top.get("phases", []))
    except DAGError as e:
        # 롤백
        shutil.copy2(backup, cfg.phases_index_path)
        raise SetDepsError(
            f"적용 후 DAG 검증 실패 → 백업에서 복원했습니다.\n"
            f"  원인: {e}\n"
            f"  백업 위치: {backup}"
        ) from e

    return SetDepsReport(backup_path=backup, changed=changed, unchanged=unchanged)


def _normalize(v: Any) -> Any:
    """비교를 위한 정규화. list 는 정렬, 'all_features' 는 그대로."""
    if isinstance(v, list):
        return sorted(v)
    return v


def render_report(report: SetDepsReport) -> str:
    lines: list[str] = []
    lines.append("")
    if not report.changed:
        lines.append("  (변경 사항 없음 — 입력이 기존 값과 동일)")
        lines.append("")
        return "\n".join(lines)
    lines.append("=" * 64)
    lines.append("  set-deps 결과")
    lines.append("=" * 64)
    lines.append(f"  백업: {report.backup_path}")
    lines.append("")
    lines.append(f"  변경된 phase ({len(report.changed)}개):")
    for d, old, new in report.changed:
        old_s = _fmt(old)
        new_s = _fmt(new)
        lines.append(f"    • {d:30}  {old_s}  →  {new_s}")
    if report.unchanged:
        lines.append("")
        lines.append(f"  변경 없음 ({len(report.unchanged)}개): {', '.join(report.unchanged)}")
    lines.append("")
    return "\n".join(lines)


def _fmt(v: Any) -> str:
    if v is None or v == []:
        return "[]"
    if v == "all_features":
        return "all_features"
    if isinstance(v, list):
        return "[" + ", ".join(v) + "]"
    return str(v)
