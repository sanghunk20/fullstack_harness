"""Acceptance merge gate — acceptance phase 진입 전 모든 feature branch 가 main 에 merge 됐는지 검증.

병렬 worktree 흐름에서:
  1. feature phase 각각이 `phase/<dir>` 브랜치에서 작업.
  2. 작업 완료 후 PR → main merge.
  3. acceptance phase 진입 시 이 게이트가 "모든 phase/<dir> 브랜치가 main 에 머지됐는지" 확인.

검증 방식:
  - 각 feature phase 의 branch_name (`phase/<dir>` 규약) 이 git 에 존재하면 main 에 merge 됐는지 검사.
  - branch 가 존재하지 않으면 worktree 없이 main 에서 직접 작업한 것으로 간주 (skip).
  - merge 안 된 브랜치가 있으면 게이트 실패.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import HarnessConfig
from .dag import PhaseNode


@dataclass(frozen=True)
class MergeGateReport:
    ok: bool
    missing: list[str]      # 존재하지만 main 에 merge 안 된 브랜치
    unknown: list[str]      # phase 가 completed 인데 브랜치도 없고 main 에도 없는 경우 (정보용)
    main_branch: str


def _run_git(cfg: HarnessConfig, args: list[str]) -> tuple[int, str, str]:
    r = subprocess.run(
        ["git", *args],
        cwd=cfg.target_root,
        capture_output=True,
        text=True,
    )
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _detect_main_branch(cfg: HarnessConfig) -> str:
    """origin/HEAD 에서 main branch 추정. 실패 시 'main' 기본값."""
    rc, out, _ = _run_git(cfg, ["symbolic-ref", "refs/remotes/origin/HEAD"])
    if rc == 0 and out:
        # 예: refs/remotes/origin/main → main
        return out.rsplit("/", 1)[-1]
    return "main"


def _branch_exists(cfg: HarnessConfig, branch: str) -> bool:
    rc, _, _ = _run_git(cfg, ["rev-parse", "--verify", "--quiet", branch])
    return rc == 0


def _is_merged(cfg: HarnessConfig, branch: str, main: str) -> bool:
    """branch 의 tip 커밋이 main 의 조상인지 검사."""
    rc, _, _ = _run_git(
        cfg,
        ["merge-base", "--is-ancestor", branch, main],
    )
    return rc == 0


def check_acceptance_gate(
    cfg: HarnessConfig,
    feature_phases: list[PhaseNode],
    branch_prefix: str = "phase",
) -> MergeGateReport:
    """feature phase 들의 worktree branch 가 main 에 모두 merge 됐는지 검사."""
    main = _detect_main_branch(cfg)
    missing: list[str] = []
    unknown: list[str] = []

    for ph in feature_phases:
        branch = f"{branch_prefix}/{ph.dir}"
        if not _branch_exists(cfg, branch):
            # worktree 분리 없이 main 에서 직접 작업한 경우 — phase status 가 completed 면 OK
            if ph.status != "completed":
                unknown.append(f"{ph.dir} (branch '{branch}' 없음, status={ph.status})")
            continue
        if not _is_merged(cfg, branch, main):
            missing.append(branch)

    ok = not missing
    return MergeGateReport(ok=ok, missing=missing, unknown=unknown, main_branch=main)


def render_merge_gate(report: MergeGateReport) -> str:
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 64)
    lines.append("  Acceptance Merge Gate")
    lines.append("=" * 64)
    lines.append(f"  main branch: {report.main_branch}")
    lines.append("")

    if report.ok:
        lines.append("  ✓ 모든 feature 브랜치가 main 에 merge 됨.")
    else:
        lines.append("  ✗ 다음 브랜치가 아직 main 에 merge 되지 않았습니다:")
        for b in report.missing:
            lines.append(f"     • {b}")
        lines.append("")
        lines.append("  PR 생성 → review → merge 한 뒤 다시 시도하세요.")

    if report.unknown:
        lines.append("")
        lines.append("  참고 (worktree branch 미발견):")
        for u in report.unknown:
            lines.append(f"     • {u}")

    lines.append("")
    return "\n".join(lines)
