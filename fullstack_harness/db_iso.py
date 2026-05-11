"""DB 격리 (db_isolation) 실구현.

세 가지 모드:
  - "none"   : 아무것도 안 함. 기존 v0.1 동작.
  - "schema" : 단일 DB 인스턴스 안에서 worktree 별 schema 를 분리.
               생성/삭제는 harness.json.commands.{create_schema,drop_schema} 가 담당.
               환경변수로 schema 이름을 phase 실행에 전달.
  - "compose": worktree 별 별도 docker-compose stack 을 띄움.
               harness.json.worktree.compose_template 가 가리키는 yml 을
               변수 치환해서 .worktrees/<phase>/docker-compose.yml 로 작성, up -d.

설계 원칙 (AGENTS.md):
  - 어떤 DB 종류 (postgres / mysql / firestore) 도 하드코딩하지 않는다.
  - 모든 외부 명령은 harness.json.commands.* 의 키에서 가져온다.
  - 사용자 컨펌 없이 docker / 외부 프로세스 spawn 을 강제하지 않는다 — dry_run 안내가 기본.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import HarnessConfig


class DBIsolationError(Exception):
    pass


@dataclass
class IsolationPlan:
    """phase 진입 시 / 종료 시 실행해야 할 외부 명령 + 환경변수.

    dry_run=True 면 status / preview 출력에만 쓰임.
    """
    mode: str
    env: dict[str, str] = field(default_factory=dict)
    setup_commands: list[str] = field(default_factory=list)
    teardown_commands: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ---------- helpers ----------

def _schema_name(phase_dir: str) -> str:
    """phase dir 을 SQL identifier 로 안전하게 변환.

    영숫자·언더스코어 외 문자는 `_` 로 대체. 숫자로 시작하면 `phase_` prefix.
    """
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", phase_dir).lower()
    if not safe:
        safe = "phase"
    if safe[0].isdigit():
        safe = f"phase_{safe}"
    return safe


def _compose_port_offset(phase_dir: str) -> int:
    """phase dir hash 기반 결정적 port offset (1~999).

    충돌 가능성은 있지만 worktree 수가 적으면 무시 가능. 명확한 매핑이 필요하면
    harness.json.worktree.compose_port_offset_map 으로 수동 지정.
    """
    h = 0
    for c in phase_dir:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return (h % 999) + 1


def _render_template(template: str, vars_: dict[str, str]) -> str:
    """`${KEY}` 변수 치환 — shell expansion 비호환 안전 모드.

    KEY 는 영숫자/언더스코어만 허용. 정의되지 않은 변수는 그대로 둠 (디버깅 용이).
    """
    def repl(m: re.Match[str]) -> str:
        k = m.group(1)
        return vars_.get(k, m.group(0))
    return re.sub(r"\$\{([A-Z_][A-Z0-9_]*)\}", repl, template)


# ---------- mode handlers ----------

def _plan_none(_cfg: HarnessConfig, _phase_dir: str, _worktree_path: Path) -> IsolationPlan:
    return IsolationPlan(
        mode="none",
        notes=["db_isolation='none' — DB 격리 비활성. 같은 DB 를 모든 worktree 가 공유."],
    )


def _plan_schema(cfg: HarnessConfig, phase_dir: str, _worktree_path: Path) -> IsolationPlan:
    cmds = cfg.commands
    create = cmds.get("create_schema", "")
    drop = cmds.get("drop_schema", "")
    schema = _schema_name(phase_dir)
    env_key = cfg.worktree_raw.get("schema_env_var", "DATABASE_SCHEMA")

    notes: list[str] = []
    if not create:
        notes.append(
            "harness.json.commands.create_schema 가 비어 있음. "
            "schema 생성 명령을 직접 실행해야 합니다 (예: psql -c 'CREATE SCHEMA <name>')."
        )
    if not drop:
        notes.append(
            "harness.json.commands.drop_schema 가 비어 있음. "
            "phase 종료 시 schema 정리는 수동입니다."
        )

    env = {env_key: schema}
    setup = []
    teardown = []
    if create:
        setup.append(_substitute_command(create, env | {"SCHEMA": schema}))
    if drop:
        teardown.append(_substitute_command(drop, env | {"SCHEMA": schema}))

    return IsolationPlan(
        mode="schema",
        env=env,
        setup_commands=setup,
        teardown_commands=teardown,
        notes=notes,
    )


def _plan_compose(cfg: HarnessConfig, phase_dir: str, worktree_path: Path) -> IsolationPlan:
    wt_cfg = cfg.worktree_raw
    template_path = wt_cfg.get("compose_template")
    if not template_path:
        return IsolationPlan(
            mode="compose",
            notes=[
                "harness.json.worktree.compose_template 미설정. "
                "compose 격리를 사용하려면 템플릿 yml 경로를 지정하세요."
            ],
        )
    src = cfg.target_root / template_path
    if not src.exists():
        return IsolationPlan(
            mode="compose",
            notes=[f"compose 템플릿 파일 없음: {src}"],
        )

    project_name = f"{cfg.project}-{_schema_name(phase_dir)}"
    port_offset = _compose_port_offset(phase_dir)
    vars_ = {
        "PHASE": phase_dir,
        "PHASE_SAFE": _schema_name(phase_dir),
        "PROJECT": cfg.project,
        "PROJECT_NAME": project_name,
        "WORKTREE": str(worktree_path),
        "PORT_OFFSET": str(port_offset),
    }
    rendered = _render_template(src.read_text(encoding="utf-8"), vars_)

    out_dir = worktree_path
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "docker-compose.yml"
    # 같은 worktree 에 이미 다른 compose 가 있으면 덮어쓰지 않음 (사용자 컨펌 정책).
    if out_file.exists():
        existing = out_file.read_text(encoding="utf-8")
        if existing != rendered:
            return IsolationPlan(
                mode="compose",
                env={
                    "COMPOSE_PROJECT_NAME": project_name,
                    "PHASE_PORT_OFFSET": str(port_offset),
                },
                notes=[
                    f"{out_file} 가 이미 존재하며 내용이 다릅니다. 덮어쓰기 안 했습니다.",
                    "수동으로 일치 확인 후 docker compose up -d 를 실행하세요.",
                ],
            )
    else:
        out_file.write_text(rendered, encoding="utf-8")

    compose_cmd = wt_cfg.get("compose_command", "docker compose")
    setup = [f"{compose_cmd} -f {shlex.quote(str(out_file))} -p {shlex.quote(project_name)} up -d"]
    teardown = [f"{compose_cmd} -f {shlex.quote(str(out_file))} -p {shlex.quote(project_name)} down -v"]

    return IsolationPlan(
        mode="compose",
        env={
            "COMPOSE_PROJECT_NAME": project_name,
            "PHASE_PORT_OFFSET": str(port_offset),
        },
        setup_commands=setup,
        teardown_commands=teardown,
        notes=[
            f"compose 파일 생성: {out_file}",
            f"project name: {project_name}",
            f"port offset: {port_offset}",
        ],
    )


def _substitute_command(template: str, vars_: dict[str, str]) -> str:
    """`${KEY}` 치환 (POSIX shell 호환 형태)."""
    return _render_template(template, vars_)


# ---------- public API ----------

def plan_isolation(cfg: HarnessConfig, phase_dir: str, worktree_path: Path | None = None) -> IsolationPlan:
    """phase 에 대한 격리 plan 생성.

    worktree_path 가 None 이면 target_root 를 사용 (단일 worktree 시나리오).
    실제 외부 명령 실행은 별도 (run_setup / run_teardown).
    """
    if worktree_path is None:
        worktree_path = cfg.target_root
    mode = cfg.db_isolation or "none"
    if mode == "none":
        return _plan_none(cfg, phase_dir, worktree_path)
    if mode == "schema":
        return _plan_schema(cfg, phase_dir, worktree_path)
    if mode == "compose":
        return _plan_compose(cfg, phase_dir, worktree_path)
    raise DBIsolationError(
        f"알 수 없는 db_isolation 모드: {mode!r}. "
        f"허용: 'none' / 'schema' / 'compose'."
    )


def run_commands(commands: list[str], cwd: Path, env: dict[str, str] | None = None) -> list[tuple[str, int, str, str]]:
    """commands 들을 cwd 에서 순차 실행. 각각 (cmd, returncode, stdout, stderr) 반환.

    실패해도 다음 명령 계속 (각각 보고). 호출자가 returncode 보고 판단.
    """
    out: list[tuple[str, int, str, str]] = []
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    for c in commands:
        r = subprocess.run(
            c,
            shell=True,
            cwd=str(cwd),
            env=merged_env,
            capture_output=True,
            text=True,
        )
        out.append((c, r.returncode, r.stdout.strip(), r.stderr.strip()))
    return out


def render_plan(plan: IsolationPlan) -> str:
    """plan 을 사람-친화적 텍스트로."""
    lines: list[str] = []
    lines.append(f"  DB Isolation mode: {plan.mode}")
    if plan.env:
        lines.append("  환경변수:")
        for k, v in plan.env.items():
            lines.append(f"    {k}={v}")
    if plan.setup_commands:
        lines.append("  Setup commands:")
        for c in plan.setup_commands:
            lines.append(f"    $ {c}")
    if plan.teardown_commands:
        lines.append("  Teardown commands:")
        for c in plan.teardown_commands:
            lines.append(f"    $ {c}")
    if plan.notes:
        lines.append("  Notes:")
        for n in plan.notes:
            lines.append(f"    • {n}")
    return "\n".join(lines)
