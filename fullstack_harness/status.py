"""상태 출력 — phases/index.json 과 각 phase index.json 을 종합해 진행 상황 표시."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from .config import (
    HarnessConfig,
    read_phases_index,
    read_phase_index,
    HarnessConfigError,
)
from .validation import validate_discovery


ICONS = {
    "pending": "○",
    "in_progress": "◐",
    "completed": "✓",
    "blocked": "⏸",
    "error": "✗",
    "skipped": "—",
}

# 출력 stamp는 시스템 로컬 timezone 사용 (KST 가정 제거).
def _stamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def phase_progress(cfg: HarnessConfig, phase_dir: str) -> dict[str, Any]:
    try:
        idx = read_phase_index(cfg, phase_dir)
    except HarnessConfigError as e:
        return {"load_error": str(e)}
    steps = idx.get("steps", [])
    completed = [s for s in steps if s.get("status") == "completed"]
    pending = next((s for s in steps if s.get("status") == "pending"), None)
    blocked = next((s for s in steps if s.get("status") == "blocked"), None)
    error = next((s for s in steps if s.get("status") == "error"), None)
    return {
        "total": len(steps),
        "completed": len(completed),
        "next_pending": pending,
        "blocked_step": blocked,
        "error_step": error,
        "v_model": idx.get("v_model", False),
    }


def render_status(cfg: HarnessConfig) -> str:
    top = read_phases_index(cfg)
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 64)
    lines.append(f"  Harness Status — {cfg.project}")
    lines.append(f"  ({_stamp()})")
    lines.append("=" * 64)
    lines.append("")

    # Discovery
    disc_status = top.get("discovery_status", "pending")
    report = validate_discovery(cfg)
    lines.append(f"  {ICONS.get(disc_status, '?')} Discovery: {disc_status}")
    counts_str = "  ".join(f"{k}={v}" for k, v in report.counts.items())
    if counts_str:
        lines.append(f"     {counts_str}")
    if disc_status != "completed":
        for it in report.issues:
            lines.append(f"     • {it}")
        cmd = cfg.discovery_command or "(discovery command 미설정)"
        lines.append(f"     → {cmd} 실행 필요")
    else:
        ts = top.get("discovery_completed_at", "?")
        lines.append(f"     완료: {ts}")

    # Phases
    lines.append("")
    lines.append("  Phases:")
    for ph in top.get("phases", []):
        d = ph["dir"]
        ph_status = ph.get("status", "pending")
        prog = phase_progress(cfg, d)
        if "load_error" in prog:
            lines.append(f"    ✗ {d:32}  {prog['load_error'][:60]}")
            continue
        bar = f"{prog['completed']}/{prog['total']}"
        kind_label = {
            "infra": "[I]",
            "feature": "[F]",
            "acceptance": "[A]",
        }.get(ph.get("kind", ""), "[ ]")
        v_label = " V" if prog["v_model"] else "  "
        deps = ph.get("depends_on")
        deps_str = ""
        if isinstance(deps, list) and deps:
            deps_str = f"  deps=[{','.join(deps)}]"
        elif deps == "all_features":
            deps_str = "  deps=all_features"
        lines.append(
            f"    {ICONS.get(ph_status, '?')} {d:30} {kind_label}{v_label}  "
            f"steps {bar:6}  {ph_status}{deps_str}"
        )
        if prog["error_step"]:
            es = prog["error_step"]
            msg = (es.get("error_message") or "")[:80]
            lines.append(f"         ✗ step{es.get('step', '?')} ({es.get('name', '?')}): {msg}")
        elif prog["blocked_step"]:
            bs = prog["blocked_step"]
            msg = (bs.get("blocked_reason") or "")[:80]
            lines.append(f"         ⏸ step{bs.get('step', '?')} ({bs.get('name', '?')}): {msg}")
        elif prog["next_pending"] and ph_status != "completed":
            np = prog["next_pending"]
            lines.append(f"         → 다음 step{np.get('step', '?')}: {np.get('name', '?')}")

    lines.append("")
    return "\n".join(lines)
