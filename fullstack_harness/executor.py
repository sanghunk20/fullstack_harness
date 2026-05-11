"""Phase executor — orchestrator only 모드.

흐름:
  1. /harness run <phase>
       - phase 의 in_progress 또는 첫 pending step 을 찾음.
       - lock 획득 (phase 이미 다른 worktree 가 잡고 있으면 abort).
       - DB 격리 plan 준비 → setup 명령을 사용자에게 안내 (자동 실행은 안 함, 사용자 컨펌).
       - 현재 step 을 in_progress 로 마킹.
       - step 안내문 + 기대되는 gate command 출력 후 종료.
  2. (사용자/LLM 이 step 작업 수행)
  3. /harness step-complete <phase> [--summary "..."]
       - 현재 in_progress step 을 completed 로 마킹.
       - 다음 step 안내 출력 (있으면).
       - 모든 step 완료 시 phase 자체가 completed 준비됨 → phase-complete 안내.
  4. /harness phase-complete <phase>
       - phase status 를 completed 로 마킹.
       - lock 해제.
       - DB 격리 teardown 안내 (자동 실행 안 함).

설계 원칙:
  - "orchestrator only" — 외부 명령 자동 실행 안 함. 모두 사용자가 직접.
  - phase index.json / phases/index.json 의 status 만 harness 가 직접 변경.
  - lock 은 phase 진입 시 획득, phase 종료/release-lock 시 해제.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import (
    HarnessConfig,
    read_phase_index,
    read_phases_index,
    resolve_effective_commands,
    resolve_effective_step_gates,
    write_phase_index,
    write_phases_index,
)
from .db_iso import plan_isolation, render_plan
from .lock import LockBusy, LockInfo, acquire_lock, inspect_lock, is_stale, release_lock


class ExecutorError(Exception):
    pass


@dataclass
class StepGuidance:
    phase_dir: str
    phase_kind: str
    v_model: bool
    step_index: int            # 1-based
    step_total: int
    step_name: str
    step_status: str
    gate_command_keys: list[str]
    gate_commands: dict[str, str]  # key -> resolved command (from effective commands)
    isolation_text: str
    paired_with: str | None    # V-Model 쌍 (spec↔accept 등)
    lock: LockInfo | None
    notes: list[str]


V_MODEL_PAIRS = {
    "spec": "accept",
    "design": "integrate",
    "test-first": "implement",
    "implement": "test-first",
    "integrate": "design",
    "accept": "spec",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def _session_id() -> str:
    """현재 프로세스를 식별하는 best-effort 문자열.

    호스트명 + pid. claude session id 가 별도로 있으면 future hook 으로 받게 할 것.
    """
    return f"{socket.gethostname()}-{os.getpid()}"


def _find_phase(top: dict[str, Any], phase_dir: str) -> dict[str, Any]:
    for p in top.get("phases", []):
        if p.get("dir") == phase_dir:
            return p
    raise ExecutorError(f"phase '{phase_dir}' 를 phases/index.json 에서 찾을 수 없습니다.")


def _resolve_step(steps: list[dict[str, Any]], explicit: str | None) -> tuple[int, dict[str, Any]]:
    """현재 작업해야 할 step 결정.

    explicit 가 주어지면 그 이름의 step.
    아니면: in_progress 가 있으면 그것, 없으면 첫 pending.
    """
    if explicit:
        for i, s in enumerate(steps):
            if s.get("name") == explicit:
                return i, s
        raise ExecutorError(f"step '{explicit}' 를 찾을 수 없습니다.")
    for i, s in enumerate(steps):
        if s.get("status") == "in_progress":
            return i, s
    for i, s in enumerate(steps):
        if s.get("status") == "pending":
            return i, s
    # 모두 completed
    raise ExecutorError("모든 step 이 completed 입니다. /harness phase-complete <phase> 로 phase 종료.")


def _filter_resolved_gates(gate_keys: list[str], commands: dict[str, str]) -> dict[str, str]:
    """gate 키 중 commands 에 비어 있지 않은 것만 resolve."""
    out: dict[str, str] = {}
    for k in gate_keys:
        v = commands.get(k, "")
        if v:
            out[k] = v
    return out


def begin_phase(
    cfg: HarnessConfig,
    phase_dir: str,
    step_name: str | None = None,
    force_stale_lock: bool = False,
) -> StepGuidance:
    """`/harness run <phase>` 본체.

    - phase status 가 pending → in_progress 로 자동 승격.
    - lock 획득.
    - 현재 step 을 in_progress 로 마킹.
    - guidance 반환.
    """
    top = read_phases_index(cfg)
    ph = _find_phase(top, phase_dir)

    if ph.get("status") == "completed":
        raise ExecutorError(f"phase '{phase_dir}' 는 이미 completed 입니다.")
    if ph.get("status") in ("blocked", "error"):
        raise ExecutorError(
            f"phase '{phase_dir}' 상태가 '{ph.get('status')}' 입니다. "
            f"먼저 해당 사유를 해결한 뒤 status 를 pending 으로 되돌리세요."
        )

    idx = read_phase_index(cfg, phase_dir)
    steps = idx.get("steps", [])
    if not steps:
        raise ExecutorError(f"phase '{phase_dir}' 의 index.json 에 steps 가 비어 있습니다.")

    step_i, step = _resolve_step(steps, step_name)

    # lock
    existing = inspect_lock(cfg, phase_dir)
    lock_info: LockInfo
    if existing is not None and existing.pid == os.getpid():
        # 같은 프로세스가 이미 잡고 있음 (재진입). 그대로 사용.
        lock_info = existing
    else:
        # 같은 worktree (target_root) 의 이전 프로세스 lock 이면 자동 인수 (Bash spawn 매번
        # 새 pid 가 되므로). 다른 worktree 의 lock 이면 충돌로 본다.
        same_worktree_stale = (
            existing is not None
            and existing.worktree_path == str(cfg.target_root)
        )
        try:
            lock_info = acquire_lock(
                cfg,
                phase_dir,
                worktree_path=str(cfg.target_root),
                session_id=_session_id(),
                force_stale=force_stale_lock or same_worktree_stale,
            )
        except LockBusy as e:
            info = e.lock_info
            stale_marker = " (stale)" if info.get("_stale") else ""
            raise ExecutorError(
                f"phase '{phase_dir}' lock 이 이미 점유 중입니다{stale_marker}.\n"
                f"  보유자: worktree={info.get('worktree_path')} session={info.get('session_id')} pid={info.get('pid')}\n"
                f"  같은 worktree 면 자동 인수됩니다. 다른 worktree 면 그쪽 작업 종료를 기다리거나\n"
                f"  /harness run {phase_dir} --force-stale-lock 로 강제 인수하세요."
            ) from e

    # phase 자체를 in_progress 로 마킹 (아직 아니면)
    if ph.get("status") != "in_progress":
        ph["status"] = "in_progress"
        ph["started_at"] = _now()
        write_phases_index(cfg, top)

    # step 을 in_progress 로
    if step.get("status") != "in_progress":
        step["status"] = "in_progress"
        step["started_at"] = step.get("started_at") or _now()
        idx["steps"] = steps
        write_phase_index(cfg, phase_dir, idx)

    # gate 안내
    gates_map = resolve_effective_step_gates(cfg)
    gate_keys = gates_map.get(step.get("name", ""), [])
    commands = resolve_effective_commands(cfg)
    resolved_gates = _filter_resolved_gates(gate_keys, commands)

    # V-Model pair
    paired = V_MODEL_PAIRS.get(step.get("name", "")) if idx.get("v_model") else None

    # isolation plan
    iso_plan = plan_isolation(cfg, phase_dir, worktree_path=Path(lock_info.worktree_path))
    iso_text = render_plan(iso_plan)

    return StepGuidance(
        phase_dir=phase_dir,
        phase_kind=ph.get("kind", ""),
        v_model=bool(idx.get("v_model", False)),
        step_index=step_i + 1,
        step_total=len(steps),
        step_name=step.get("name", ""),
        step_status=step.get("status", ""),
        gate_command_keys=gate_keys,
        gate_commands=resolved_gates,
        isolation_text=iso_text,
        paired_with=paired,
        lock=lock_info,
        notes=iso_plan.notes,
    )


def step_complete(
    cfg: HarnessConfig,
    phase_dir: str,
    summary: str = "",
) -> dict[str, Any]:
    """현재 in_progress step 을 completed 로 마킹. 다음 step 가이드 반환.

    반환: {"completed_step": <name>, "next_step": <name or None>, "phase_done": bool}
    """
    top = read_phases_index(cfg)
    _find_phase(top, phase_dir)  # 존재 검증

    idx = read_phase_index(cfg, phase_dir)
    steps = idx.get("steps", [])

    cur_i = next((i for i, s in enumerate(steps) if s.get("status") == "in_progress"), None)
    if cur_i is None:
        raise ExecutorError(
            f"phase '{phase_dir}' 에 in_progress step 이 없습니다. "
            f"/harness run {phase_dir} 으로 시작하세요."
        )
    cur = steps[cur_i]
    cur["status"] = "completed"
    cur["completed_at"] = _now()
    if summary:
        cur["summary"] = summary

    # 다음 step
    nxt = None
    for s in steps[cur_i + 1 :]:
        if s.get("status") == "pending":
            nxt = s
            break

    phase_done = nxt is None and all(s.get("status") == "completed" for s in steps)

    idx["steps"] = steps
    write_phase_index(cfg, phase_dir, idx)

    return {
        "completed_step": cur.get("name"),
        "next_step": nxt.get("name") if nxt else None,
        "phase_done_eligible": phase_done,
    }


def phase_complete(cfg: HarnessConfig, phase_dir: str) -> dict[str, Any]:
    """모든 step 이 completed 이면 phase status 를 completed 로. lock 해제.

    반환: {"isolation_teardown": [...], "lock_released": bool, "completed_at": str}
    """
    top = read_phases_index(cfg)
    ph = _find_phase(top, phase_dir)

    idx = read_phase_index(cfg, phase_dir)
    steps = idx.get("steps", [])
    if not all(s.get("status") == "completed" for s in steps):
        not_done = [s.get("name") for s in steps if s.get("status") != "completed"]
        raise ExecutorError(
            f"phase '{phase_dir}' 의 모든 step 이 완료되지 않았습니다. "
            f"남은 step: {not_done}"
        )

    ph["status"] = "completed"
    ph["completed_at"] = _now()
    idx["completed_at"] = ph["completed_at"]
    write_phases_index(cfg, top)
    write_phase_index(cfg, phase_dir, idx)

    # isolation teardown 안내
    iso_plan = plan_isolation(cfg, phase_dir, worktree_path=cfg.target_root)

    # lock 해제 (best effort — session id 무관 force)
    released = release_lock(cfg, phase_dir, session_id=_session_id(), force=True)

    return {
        "isolation_teardown": iso_plan.teardown_commands,
        "isolation_notes": iso_plan.notes,
        "lock_released": released,
        "completed_at": ph["completed_at"],
    }


def release_phase_lock(cfg: HarnessConfig, phase_dir: str, force: bool = False) -> bool:
    """수동 lock 해제 (`/harness release-lock <phase>`)."""
    info = inspect_lock(cfg, phase_dir)
    if info is None:
        return False
    if not force and not is_stale(info):
        raise ExecutorError(
            f"lock 이 살아있는 프로세스 (pid={info.pid}) 가 잡고 있습니다. "
            f"강제 해제하려면 --force."
        )
    return release_lock(cfg, phase_dir, session_id=info.session_id, force=True)


def render_step_guidance(g: StepGuidance) -> str:
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 64)
    lines.append(f"  ▶ Phase {g.phase_dir} ({g.phase_kind})")
    if g.v_model:
        lines.append(f"  ▶ V-Model step {g.step_index}/{g.step_total}: {g.step_name}")
        if g.paired_with:
            lines.append(f"    (V-Model 쌍: {g.step_name} ↔ {g.paired_with})")
    else:
        lines.append(f"  ▶ Step {g.step_index}/{g.step_total}: {g.step_name}")
    lines.append(f"  ▶ Status: {g.step_status}")
    lines.append("=" * 64)
    lines.append("")

    # 기대되는 gate command
    if g.gate_command_keys:
        lines.append("  이 step 의 권장 gate command (step-complete 전 통과 권장):")
        if not g.gate_commands:
            lines.append("    (harness.json.commands 에 해당 키 모두 빈 값 — 적용 안 됨)")
        for k, v in g.gate_commands.items():
            lines.append(f"    [{k}] $ {v}")
        # commands 에 비어 있는 key 들도 알려준다
        missing = [k for k in g.gate_command_keys if k not in g.gate_commands]
        if missing:
            lines.append(f"    (skip — commands 미정의: {', '.join(missing)})")
        lines.append("")
    else:
        lines.append("  이 step 에 권장 gate 없음 (문서 작성/스펙 단계).")
        lines.append("")

    # isolation
    lines.append("  " + g.isolation_text.replace("\n", "\n  "))
    lines.append("")

    if g.lock:
        lines.append(f"  Lock 획득: pid={g.lock.pid}, session={g.lock.session_id}")
        lines.append("")

    lines.append("  step 작업이 끝나면:")
    lines.append(f"    /harness step-complete {g.phase_dir} [--summary \"<한 줄 요약>\"]")
    lines.append("")
    return "\n".join(lines)


def render_step_complete(result: dict[str, Any], phase_dir: str) -> str:
    lines: list[str] = []
    lines.append("")
    lines.append(f"  ✓ step '{result['completed_step']}' completed.")
    nxt = result.get("next_step")
    if nxt:
        lines.append(f"  → 다음 step: {nxt}")
        lines.append(f"    /harness run {phase_dir}  (다음 step 진입)")
    elif result.get("phase_done_eligible"):
        lines.append("  ✓ 모든 step 완료. phase 종료 준비됨.")
        lines.append(f"    /harness phase-complete {phase_dir}")
    lines.append("")
    return "\n".join(lines)


def render_phase_complete(result: dict[str, Any], phase_dir: str) -> str:
    lines: list[str] = []
    lines.append("")
    lines.append(f"  ✓ phase '{phase_dir}' completed at {result['completed_at']}")
    if result["lock_released"]:
        lines.append("  ✓ lock 해제됨.")
    teardown = result.get("isolation_teardown") or []
    if teardown:
        lines.append("")
        lines.append("  DB 격리 teardown 명령 (필요 시 직접 실행):")
        for c in teardown:
            lines.append(f"    $ {c}")
    notes = result.get("isolation_notes") or []
    if notes:
        for n in notes:
            lines.append(f"    • {n}")
    lines.append("")
    return "\n".join(lines)
