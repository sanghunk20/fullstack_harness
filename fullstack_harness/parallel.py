"""병렬 phase 후보 계산 + git worktree 안내.

핵심 흐름:
  1. DAG에서 ready 집합 계산.
  2. ready 가 1개면 단일 phase로 안내 (worktree 불필요).
  3. ready 가 2개 이상이면 병렬 후보로 제시 — 사용자가 어떻게 나눌지 선택.
  4. 선택된 phase 각각에 대해 `git worktree add` 명령 + 새 Claude Code 세션 안내 출력.

서브에이전트 직접 dispatch는 v0.1 범위 외 (사용자 결정: 새 세션 안내 1차).
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import HarnessConfig
from .dag import PhaseNode


@dataclass(frozen=True)
class WorktreePlan:
    phase_dir: str
    worktree_path: Path
    branch_name: str
    git_command: str
    session_hint: str


def plan_worktrees(
    cfg: HarnessConfig,
    phases: Iterable[PhaseNode],
    branch_prefix: str = "phase",
) -> list[WorktreePlan]:
    """선택된 phase들에 대해 worktree 생성 명령을 생성.

    한 phase 당:
    - worktree path: <target_root>/<worktree.base_path>/<phase_dir>
    - branch name: <branch_prefix>/<phase_dir>
    - git command: `git worktree add <path> -b <branch>` (현재 HEAD 기준)
    - session hint: 새 터미널에서 실행할 안내 메시지
    """
    base = cfg.worktree_base
    out: list[WorktreePlan] = []
    for ph in phases:
        wt_path = base / ph.dir
        branch = f"{branch_prefix}/{ph.dir}"
        # 안전한 shell 인용을 위해 shlex.quote 사용
        cmd = (
            f"git worktree add {shlex.quote(str(wt_path))} "
            f"-b {shlex.quote(branch)}"
        )
        session_hint = (
            f"새 터미널에서:\n"
            f"  cd {shlex.quote(str(wt_path))}\n"
            f"  claude  # 또는 사용하시는 Claude Code 실행 명령\n"
            f"세션 안에서:\n"
            f"  /harness run {ph.dir}"
        )
        out.append(WorktreePlan(
            phase_dir=ph.dir,
            worktree_path=wt_path,
            branch_name=branch,
            git_command=cmd,
            session_hint=session_hint,
        ))
    return out


def render_parallel_summary(
    cfg: HarnessConfig,
    ready: list[PhaseNode],
    blocked: list[PhaseNode],
) -> str:
    """ready/blocked phase 목록을 사용자 친화적으로 출력.

    next --parallel 의 첫 출력. 실제 dispatch는 컨펌 후.
    """
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 64)
    lines.append("  병렬 진행 후보 분석")
    lines.append("=" * 64)
    lines.append("")

    if blocked:
        lines.append("  ⏸  먼저 해결할 phase (blocked/error):")
        for n in blocked:
            reason = n.raw.get("blocked_reason") or n.raw.get("error_message") or ""
            lines.append(f"     • {n.dir} ({n.status}){' — ' + reason[:60] if reason else ''}")
        lines.append("")
        lines.append("  위 phase 를 먼저 unblock 한 뒤 다시 호출하세요.")
        lines.append("")
        return "\n".join(lines)

    if not ready:
        lines.append("  진행 가능한 phase 없음. 모든 phase 가 completed 이거나 의존성 미충족.")
        lines.append("")
        return "\n".join(lines)

    if len(ready) == 1:
        n = ready[0]
        lines.append(f"  진행 가능 phase 1개 — 병렬 worktree 불필요.")
        lines.append("")
        lines.append(f"    → {n.dir} ({n.kind}, {n.status})")
        lines.append("")
        lines.append(f"  현재 worktree에서 바로 진행:")
        lines.append(f"    /harness run {n.dir}")
        lines.append("")
        return "\n".join(lines)

    # 2개 이상 — 병렬 후보
    lines.append(f"  진행 가능 phase {len(ready)}개 — 병렬 worktree 분리 가능.")
    lines.append("")
    for n in ready:
        deps_str = f" (deps: {', '.join(n.depends_on)})" if n.depends_on else ""
        desc = n.raw.get("description", "")[:50]
        lines.append(f"    • {n.dir:30}  {n.kind:10}{deps_str}")
        if desc:
            lines.append(f"      {desc}")
    lines.append("")
    lines.append("  옵션:")
    lines.append("    (A) 모두 현재 worktree에서 순차 진행 — `/harness run <phase>` 하나씩")
    lines.append("    (B) 일부/전부를 별도 worktree로 분리해서 병렬 진행")
    lines.append("")
    lines.append("  (B) 선택 시 worktree 명령은:")
    plans = plan_worktrees(cfg, ready)
    for p in plans:
        lines.append(f"    # {p.phase_dir}")
        lines.append(f"    {p.git_command}")
    lines.append("")
    lines.append("  주의:")
    lines.append("    • worktree 마다 별도 Claude Code 세션을 띄우세요 (한 세션에서 cwd만 바꾸면 컨텍스트 오염).")
    lines.append(f"    • db_isolation = '{cfg.db_isolation}' — 'none' 이면 DB 충돌 위험. 마이그레이션 phase 는 worktree 분리 비권장.")
    lines.append("    • 작업 후 main 브랜치로 merge 필요 (`99-acceptance` phase 전에 모두 merge되어야 함).")
    lines.append("")

    return "\n".join(lines)


def render_worktree_dispatch(plans: list[WorktreePlan]) -> str:
    """사용자가 (B) 옵션 선택 후 실제 worktree 명령 + 세션 안내 출력."""
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 64)
    lines.append("  Worktree Dispatch 안내")
    lines.append("=" * 64)
    lines.append("")
    for i, p in enumerate(plans, 1):
        lines.append(f"  [{i}/{len(plans)}] {p.phase_dir}")
        lines.append(f"    Worktree 생성:")
        lines.append(f"      {p.git_command}")
        lines.append("")
        lines.append(f"    {p.session_hint}")
        lines.append("")
        lines.append("-" * 64)
        lines.append("")
    lines.append("  모든 worktree 가 작업 완료되면 각각 PR 생성 → main 으로 merge.")
    lines.append("  acceptance phase 는 모든 feature phase 가 main 에 merge 된 후만 진행 가능.")
    lines.append("")
    return "\n".join(lines)
