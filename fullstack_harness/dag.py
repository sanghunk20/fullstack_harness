"""Phase 의존성 DAG.

phases/index.json 의 depends_on 필드를 그래프로 해석.
- cycle detection
- ready set 계산 (모든 deps가 completed 인 pending phase)
- "all_features" 특수값 처리 (kind=='feature' 인 모든 phase를 의존성으로 expand)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class DAGError(Exception):
    pass


@dataclass(frozen=True)
class PhaseNode:
    dir: str
    kind: str
    status: str
    depends_on: tuple[str, ...]  # expanded (all_features 풀린 상태)
    raw: dict[str, Any]


def build_dag(phases: list[dict[str, Any]]) -> dict[str, PhaseNode]:
    """phases/index.json 의 phases 배열로부터 DAG 노드 맵을 빌드.

    - depends_on: list[str] | "all_features" | None
    - "all_features" 는 kind=='feature' 인 모든 phase dir 로 expand.
    - 알 수 없는 dir 참조는 DAGError.
    - cycle detection 수행 (있으면 DAGError).
    """
    by_dir: dict[str, dict[str, Any]] = {}
    for ph in phases:
        d = ph.get("dir")
        if not d:
            raise DAGError(f"phase entry missing 'dir' field: {ph}")
        if d in by_dir:
            raise DAGError(f"duplicate phase dir: {d}")
        by_dir[d] = ph

    feature_dirs = [d for d, ph in by_dir.items() if ph.get("kind") == "feature"]

    nodes: dict[str, PhaseNode] = {}
    for d, ph in by_dir.items():
        deps_raw = ph.get("depends_on")
        if deps_raw is None or deps_raw == []:
            deps: list[str] = []
        elif deps_raw == "all_features":
            # acceptance phase 패턴. 자기 자신은 제외.
            deps = [fd for fd in feature_dirs if fd != d]
        elif isinstance(deps_raw, list):
            deps = list(deps_raw)
        else:
            raise DAGError(
                f"phase '{d}': depends_on 은 list 또는 'all_features' 문자열이어야 합니다. "
                f"받은 값: {deps_raw!r}"
            )

        for dep in deps:
            if dep not in by_dir:
                raise DAGError(f"phase '{d}': depends_on 에 알 수 없는 phase '{dep}' 참조")
            if dep == d:
                raise DAGError(f"phase '{d}': 자기 자신을 의존할 수 없습니다.")

        nodes[d] = PhaseNode(
            dir=d,
            kind=ph.get("kind", ""),
            status=ph.get("status", "pending"),
            depends_on=tuple(deps),
            raw=ph,
        )

    _detect_cycle(nodes)
    return nodes


def _detect_cycle(nodes: dict[str, PhaseNode]) -> None:
    """DFS 기반 cycle detection.

    WHITE(0) = 미방문, GRAY(1) = 현재 경로, BLACK(2) = 완료.
    GRAY 상태의 노드를 다시 만나면 cycle.
    """
    color: dict[str, int] = {d: 0 for d in nodes}
    path: list[str] = []

    def visit(d: str) -> None:
        if color[d] == 1:
            cycle = " → ".join(path[path.index(d):] + [d])
            raise DAGError(f"순환 의존성 감지: {cycle}")
        if color[d] == 2:
            return
        color[d] = 1
        path.append(d)
        for dep in nodes[d].depends_on:
            visit(dep)
        path.pop()
        color[d] = 2

    for d in nodes:
        if color[d] == 0:
            visit(d)


def ready_phases(nodes: dict[str, PhaseNode]) -> list[PhaseNode]:
    """pending 이면서 모든 의존성이 completed 인 phase 목록.

    blocked/error 상태인 phase가 있으면 그 의존자는 ready로 치지 않음 (deps 미충족).
    같은 ready set 안의 phase는 병렬 진행 후보.
    """
    out: list[PhaseNode] = []
    for d, node in nodes.items():
        if node.status not in ("pending", "in_progress"):
            continue
        if all(nodes[dep].status == "completed" for dep in node.depends_on):
            out.append(node)
    return out


def blocked_or_error(nodes: dict[str, PhaseNode]) -> list[PhaseNode]:
    """blocked / error 상태인 phase 목록 (사용자 개입 필요)."""
    return [n for n in nodes.values() if n.status in ("blocked", "error")]


def all_completed(nodes: dict[str, PhaseNode], kind_filter: str | None = None) -> bool:
    pool = [n for n in nodes.values() if kind_filter is None or n.kind == kind_filter]
    if not pool:
        return False
    return all(n.status == "completed" for n in pool)
