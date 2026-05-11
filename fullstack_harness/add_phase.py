"""add-phase — 새 phase 를 phases/index.json + phases/<dir>/index.json 에 추가.

흐름:
  1. 입력 검증 (dir 충돌 / kind 유효성 / depends_on 존재 여부).
  2. 백업.
  3. phases/index.json 에 entry 추가.
  4. phases/<dir>/ 디렉토리 + index.json 생성 (V-Model or linear template).
  5. DAG 재검증. 실패 시 자동 롤백.

/feature 슬래시 명령이 이 모듈을 통해 phase 를 자동 추가합니다.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import HarnessConfig, read_phases_index, write_phases_index
from .dag import DAGError, build_dag


class AddPhaseError(Exception):
    pass


@dataclass
class AddPhaseReport:
    backup_path: Path
    added_dir: str
    added_kind: str
    v_model: bool
    depends_on: list[str] | str
    phase_index_path: Path


VALID_KINDS = ("infra", "feature", "acceptance")


def _stamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")


def _backup_index(cfg: HarnessConfig) -> Path:
    bak = cfg.phases_index_path.with_suffix(f".json.bak.{_stamp()}")
    shutil.copy2(cfg.phases_index_path, bak)
    return bak


def _v_model_template(name: str, steps_names: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "v_model": True,
        "completed_at": None,
        "steps": [
            {"step": i + 1, "name": sn, "status": "pending", "summary": ""}
            for i, sn in enumerate(steps_names)
        ],
    }


def _linear_template(name: str, step_name: str = "main") -> dict[str, Any]:
    return {
        "name": name,
        "v_model": False,
        "completed_at": None,
        "steps": [{"step": 1, "name": step_name, "status": "pending", "summary": ""}],
    }


def add_phase(
    cfg: HarnessConfig,
    dir_: str,
    kind: str,
    description: str = "",
    v_model: bool | None = None,
    depends_on: list[str] | str | None = None,
    insert_before: str | None = None,
) -> AddPhaseReport:
    """새 phase 추가.

    Args:
      dir_: phase 디렉토리 이름. 영숫자+하이픈+언더스코어만.
      kind: 'infra' | 'feature' | 'acceptance'.
      description: 한 줄 설명.
      v_model: True 이면 V-Model 6 step, False 면 linear 1 step. None 이면 kind 에 따라:
               feature → True, infra/acceptance → False.
      depends_on: phase dir 리스트 또는 'all_features' (acceptance 전용 패턴).
                  None 이면 kind 에 따라:
                  acceptance → 'all_features',
                  나머지 → [] (사용자가 나중에 /harness-analyze-deps 로 보강).
      insert_before: 지정 시 그 dir 앞에 삽입. 미지정이면 acceptance 직전 (있으면) 또는 끝.
    """
    if kind not in VALID_KINDS:
        raise AddPhaseError(f"kind 는 {VALID_KINDS} 중 하나여야 합니다. 받은: {kind!r}")
    if not dir_ or not all(c.isalnum() or c in "-_" for c in dir_):
        raise AddPhaseError(
            f"phase dir 은 영숫자·`-`·`_` 만 허용. 받은: {dir_!r}"
        )

    top = read_phases_index(cfg)
    phases = top.get("phases", [])
    existing_dirs = {p.get("dir") for p in phases}
    if dir_ in existing_dirs:
        raise AddPhaseError(f"phase dir '{dir_}' 가 이미 존재합니다.")

    if v_model is None:
        v_model = kind == "feature"

    if depends_on is None:
        if kind == "acceptance":
            depends_on = "all_features"
        else:
            depends_on = []

    # depends_on validation
    if isinstance(depends_on, list):
        unknown = [d for d in depends_on if d not in existing_dirs]
        if unknown:
            raise AddPhaseError(
                f"depends_on 에 알 수 없는 phase: {unknown}. 기존 phases: {sorted(existing_dirs)}"
            )
    elif depends_on != "all_features":
        raise AddPhaseError(
            f"depends_on 은 list 또는 'all_features' 여야 합니다. 받은: {depends_on!r}"
        )

    backup = _backup_index(cfg)

    # 새 entry
    new_entry = {
        "dir": dir_,
        "name": dir_,
        "description": description,
        "kind": kind,
        "v_model": v_model,
        "depends_on": depends_on,
        "status": "pending",
    }

    # 삽입 위치 결정
    if insert_before:
        idx = next((i for i, p in enumerate(phases) if p.get("dir") == insert_before), None)
        if idx is None:
            shutil.copy2(backup, cfg.phases_index_path)
            raise AddPhaseError(f"insert_before='{insert_before}' phase 가 없습니다.")
        phases.insert(idx, new_entry)
    else:
        # acceptance 직전 (있으면) 또는 끝
        accept_idx = next(
            (i for i, p in enumerate(phases) if p.get("kind") == "acceptance"),
            None,
        )
        if accept_idx is not None and kind != "acceptance":
            phases.insert(accept_idx, new_entry)
        else:
            phases.append(new_entry)

    top["phases"] = phases

    # 새 phase 디렉토리 + index.json
    phase_dir_path = cfg.phases_dir / dir_
    phase_dir_path.mkdir(parents=True, exist_ok=False)
    if v_model:
        steps_names = cfg.v_model_steps
        idx_data = _v_model_template(dir_, steps_names)
    else:
        idx_data = _linear_template(dir_)
    phase_index_path = phase_dir_path / "index.json"
    phase_index_path.write_text(
        json.dumps(idx_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # phases/index.json 쓰기 + DAG 재검증
    write_phases_index(cfg, top)
    try:
        build_dag(phases)
    except DAGError as e:
        # rollback
        shutil.copy2(backup, cfg.phases_index_path)
        phase_index_path.unlink(missing_ok=True)
        try:
            phase_dir_path.rmdir()
        except OSError:
            pass
        raise AddPhaseError(
            f"phase 추가 후 DAG 검증 실패 → 백업 복원. 원인: {e}"
        ) from e

    return AddPhaseReport(
        backup_path=backup,
        added_dir=dir_,
        added_kind=kind,
        v_model=v_model,
        depends_on=depends_on,
        phase_index_path=phase_index_path,
    )


def render_add_phase(report: AddPhaseReport) -> str:
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 64)
    lines.append("  Phase 추가 완료")
    lines.append("=" * 64)
    lines.append(f"  dir:         {report.added_dir}")
    lines.append(f"  kind:        {report.added_kind}")
    lines.append(f"  v_model:     {report.v_model}")
    deps = report.depends_on
    deps_s = "[]" if deps == [] else (deps if isinstance(deps, str) else "[" + ", ".join(deps) + "]")
    lines.append(f"  depends_on:  {deps_s}")
    lines.append(f"  phase index: {report.phase_index_path}")
    lines.append(f"  백업:        {report.backup_path}")
    lines.append("")
    return "\n".join(lines)
