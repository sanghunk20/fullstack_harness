#!/usr/bin/env python3
"""fullstack_harness CLI entrypoint.

사용:
    python3 -m fullstack_harness.harness status
    python3 -m fullstack_harness.harness next [--run] [--parallel]
    python3 -m fullstack_harness.harness validate
    python3 -m fullstack_harness.harness discovery-complete

target project은 cwd 또는 상위 디렉토리에 harness.json 이 있어야 한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import HarnessConfig, HarnessConfigError, load_config, read_phases_index, write_phases_index
from .dag import DAGError, build_dag, ready_phases, blocked_or_error
from .executor import (
    ExecutorError,
    begin_phase,
    phase_complete,
    release_phase_lock,
    render_phase_complete,
    render_step_complete,
    render_step_guidance,
    step_complete,
)
from .merge_gate import check_acceptance_gate, render_merge_gate
from .parallel import plan_worktrees, render_parallel_summary, render_worktree_dispatch
from .set_deps import SetDepsError, apply_deps, load_deps_input, render_report
from .status import render_status, _stamp
from .validation import validate_discovery


def cmd_status(_args, cfg: HarnessConfig) -> int:
    print(render_status(cfg))
    return 0


def cmd_validate(_args, cfg: HarnessConfig) -> int:
    report = validate_discovery(cfg)
    print("\n  Discovery 충실도 검사:")
    for cat, n in report.counts.items():
        print(f"    {cat:12}: {n} 개")
    if report.issues:
        print("\n  Issues:")
        for it in report.issues:
            print(f"    • {it}")
    else:
        print("\n  ✓ 모든 검사 통과")
    print()
    return 0 if report.ok else 1


def cmd_discovery_complete(_args, cfg: HarnessConfig) -> int:
    report = validate_discovery(cfg)
    if not report.ok:
        print("✗ Discovery 미완. 다음 항목을 해결해야 합니다:")
        for it in report.issues:
            print(f"  • {it}")
        cmd = cfg.discovery_command or "(discovery command)"
        print(f"\n  {cmd} 를 추가 실행하여 보완 후 다시 시도하세요.")
        return 1

    top = read_phases_index(cfg)
    top["discovery_status"] = "completed"
    top["discovery_completed_at"] = _stamp()
    write_phases_index(cfg, top)
    print(f"✓ Discovery completed at {top['discovery_completed_at']}")
    counts_str = "  ".join(f"{k}={v}" for k, v in report.counts.items())
    if counts_str:
        print(f"  {counts_str}")
    if report.issues:
        print("\n  경고 (선택적 항목):")
        for it in report.issues:
            print(f"    • {it}")
    return 0


def cmd_next(args, cfg: HarnessConfig) -> int:
    """DAG 기반 다음 진행 가능 phase 안내.

    --parallel 플래그: 병렬 후보까지 출력 + worktree 명령 제안.
    --parallel 없음:  ready 중 첫 번째만 안내 (순차 모드).
    """
    top = read_phases_index(cfg)

    # discovery 미완이면 거기서 멈춤
    if top.get("discovery_status") != "completed":
        print("\n  Discovery 미완료. 먼저 discovery 를 끝내세요.")
        print(f"    명령: {cfg.discovery_command or '(harness.json 의 discovery.command 미설정)'}")
        print(f"    완료 후: python3 -m fullstack_harness.harness discovery-complete\n")
        return 1

    try:
        nodes = build_dag(top.get("phases", []))
    except DAGError as e:
        print(f"\n  ✗ DAG 오류: {e}\n", file=sys.stderr)
        return 2

    blocked = blocked_or_error(nodes)
    ready = ready_phases(nodes)

    if getattr(args, "parallel", False):
        print(render_parallel_summary(cfg, ready, blocked))
        return 0

    # 순차 모드
    if blocked:
        print("\n  ⏸  먼저 해결할 phase:")
        for n in blocked:
            print(f"     • {n.dir} ({n.status})")
        print()
        return 1
    if not ready:
        print("\n  진행 가능 phase 없음 (모두 완료되었거나 의존성 미충족).\n")
        return 0
    n = ready[0]
    print(f"\n  다음 진행 phase: {n.dir} ({n.kind})")
    print(f"  실행: /harness run {n.dir}")
    print(f"  병렬 후보까지 보려면: /harness next --parallel\n")
    return 0


def cmd_worktree_plan(args, cfg: HarnessConfig) -> int:
    """선택된 phase 들에 대한 worktree dispatch 안내.

    --phase 인자로 받은 phase dir 목록 각각에 대해 git worktree add 명령 + 새 세션 안내 출력.
    실제 git worktree 실행은 하지 않음 (사용자가 직접 실행).
    """
    top = read_phases_index(cfg)
    try:
        nodes = build_dag(top.get("phases", []))
    except DAGError as e:
        print(f"\n  ✗ DAG 오류: {e}\n", file=sys.stderr)
        return 2

    requested: list[str] = args.phase or []
    if not requested:
        print("\n  사용법: /harness worktree-plan <phase-dir> [<phase-dir> ...]\n")
        return 2

    chosen = []
    for d in requested:
        if d not in nodes:
            print(f"  ✗ 알 수 없는 phase: {d}", file=sys.stderr)
            return 2
        n = nodes[d]
        if n.status not in ("pending", "in_progress"):
            print(f"  ⚠  {d}: 상태가 '{n.status}' — worktree 분리 대상이 아닐 수 있음.")
        chosen.append(n)

    plans = plan_worktrees(cfg, chosen)
    print(render_worktree_dispatch(plans))
    return 0


def cmd_set_deps(args, cfg: HarnessConfig) -> int:
    """JSON 입력으로 phases 의 depends_on 일괄 패치 (with 백업 + DAG 재검증)."""
    src = Path(args.json_file) if args.json_file else None
    try:
        deps = load_deps_input(src)
        report = apply_deps(cfg, deps)
    except SetDepsError as e:
        print(f"\n  ✗ {e}\n", file=sys.stderr)
        return 1
    print(render_report(report))
    return 0


def cmd_run(args, cfg: HarnessConfig) -> int:
    """`/harness run <phase>` — phase 의 현재 step 시작 (orchestrator only)."""
    try:
        g = begin_phase(
            cfg,
            phase_dir=args.phase,
            step_name=args.step,
            force_stale_lock=args.force_stale_lock,
        )
    except ExecutorError as e:
        print(f"\n  ✗ {e}\n", file=sys.stderr)
        return 1
    print(render_step_guidance(g))
    return 0


def cmd_step_complete(args, cfg: HarnessConfig) -> int:
    """`/harness step-complete <phase>` — 현재 step 완료 마킹."""
    try:
        result = step_complete(cfg, phase_dir=args.phase, summary=args.summary or "")
    except ExecutorError as e:
        print(f"\n  ✗ {e}\n", file=sys.stderr)
        return 1
    print(render_step_complete(result, args.phase))
    return 0


def cmd_phase_complete(args, cfg: HarnessConfig) -> int:
    """`/harness phase-complete <phase>` — phase 종료 + lock 해제 + teardown 안내."""
    try:
        result = phase_complete(cfg, phase_dir=args.phase)
    except ExecutorError as e:
        print(f"\n  ✗ {e}\n", file=sys.stderr)
        return 1
    print(render_phase_complete(result, args.phase))
    return 0


def cmd_release_lock(args, cfg: HarnessConfig) -> int:
    """`/harness release-lock <phase>` — 수동 lock 해제."""
    try:
        ok = release_phase_lock(cfg, phase_dir=args.phase, force=args.force)
    except ExecutorError as e:
        print(f"\n  ✗ {e}\n", file=sys.stderr)
        return 1
    if ok:
        print(f"\n  ✓ phase '{args.phase}' lock 해제됨.\n")
        return 0
    print(f"\n  (phase '{args.phase}' 에 lock 없음.)\n")
    return 0


def cmd_merge_gate(_args, cfg: HarnessConfig) -> int:
    """acceptance phase 진입 전 모든 feature 브랜치 merge 검증."""
    top = read_phases_index(cfg)
    try:
        nodes = build_dag(top.get("phases", []))
    except DAGError as e:
        print(f"\n  ✗ DAG 오류: {e}\n", file=sys.stderr)
        return 2
    features = [n for n in nodes.values() if n.kind == "feature"]
    report = check_acceptance_gate(cfg, features)
    print(render_merge_gate(report))
    return 0 if report.ok else 1


SUBCOMMANDS = {
    "status": cmd_status,
    "validate": cmd_validate,
    "discovery-complete": cmd_discovery_complete,
    "next": cmd_next,
    "worktree-plan": cmd_worktree_plan,
    "merge-gate": cmd_merge_gate,
    "set-deps": cmd_set_deps,
    "run": cmd_run,
    "step-complete": cmd_step_complete,
    "phase-complete": cmd_phase_complete,
    "release-lock": cmd_release_lock,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fullstack_harness",
        description="범용 풀스택 개발 harness — 상태 점검 + DAG 기반 진행 dispatcher",
    )
    parser.add_argument(
        "--target", type=Path, default=None,
        help="대상 프로젝트 root 경로 (생략 시 cwd 또는 상위에서 harness.json 검색)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="전체 진행 상황 출력")
    n = sub.add_parser("next", help="다음 진행 가능 phase 안내")
    n.add_argument("--run", action="store_true")
    n.add_argument("--parallel", action="store_true", help="병렬 phase 후보까지 출력 (v0.1)")
    sub.add_parser("validate", help="discovery 충실도 검사")
    sub.add_parser("discovery-complete", help="discovery_status를 completed로 마킹")

    wp = sub.add_parser("worktree-plan", help="선택 phase 들의 worktree 생성 명령 + 새 세션 안내 출력")
    wp.add_argument("phase", nargs="+", help="병렬로 분리할 phase dir 목록")

    sub.add_parser("merge-gate", help="acceptance phase 진입 전 모든 feature 브랜치 merge 검증")

    sd = sub.add_parser(
        "set-deps",
        help="JSON 입력으로 phases 의 depends_on 일괄 패치 (백업 + DAG 재검증)",
    )
    sd.add_argument(
        "--json-file", type=str, default=None,
        help="JSON 입력 파일. 생략 시 stdin 에서 읽음.",
    )

    r = sub.add_parser("run", help="phase 의 현재/지정 step 진입 (orchestrator only)")
    r.add_argument("phase", help="phase 디렉토리 이름")
    r.add_argument("--step", default=None, help="특정 step 이름으로 진입 (생략 시 자동)")
    r.add_argument(
        "--force-stale-lock", action="store_true",
        help="lock 보유 프로세스가 죽었으면 강제 인수",
    )

    sc = sub.add_parser("step-complete", help="현재 in_progress step 을 completed 로 마킹")
    sc.add_argument("phase", help="phase 디렉토리 이름")
    sc.add_argument("--summary", default=None, help="step 한 줄 요약 (선택)")

    pc = sub.add_parser("phase-complete", help="모든 step 완료된 phase 의 status 를 completed 로 마킹")
    pc.add_argument("phase", help="phase 디렉토리 이름")

    rl = sub.add_parser("release-lock", help="phase lock 수동 해제 (stale 시)")
    rl.add_argument("phase", help="phase 디렉토리 이름")
    rl.add_argument("--force", action="store_true", help="살아있는 lock 도 강제 해제")

    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.target)
    except HarnessConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    handler = SUBCOMMANDS.get(args.cmd)
    if handler is None:
        parser.print_help()
        return 2
    return handler(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
