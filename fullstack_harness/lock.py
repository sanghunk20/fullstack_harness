"""Phase lock — 동시에 같은 phase 를 두 worktree 가 잡지 못하게.

lock 파일: <phases_dir>/<phase>/.lock (JSON)
{
  "worktree_path": "/abs/path",
  "session_id": "...",
  "acquired_at": "ISO timestamp",
  "pid": 12345
}

acquire/release/inspect API 제공.
- pid 가 살아있지 않으면 stale 로 간주, 경고와 함께 강제 해제 가능.
- acquire 는 race condition을 최소화하기 위해 O_EXCL 로 생성.
"""

from __future__ import annotations

import errno
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import HarnessConfig


LOCK_FILENAME = ".lock"


class LockError(Exception):
    pass


class LockBusy(LockError):
    """다른 워커가 이미 점유."""
    def __init__(self, lock_info: dict[str, Any]):
        super().__init__(f"phase 이미 점유 중: {lock_info}")
        self.lock_info = lock_info


@dataclass(frozen=True)
class LockInfo:
    worktree_path: str
    session_id: str
    acquired_at: str
    pid: int
    raw: dict[str, Any]


def _lock_path(cfg: HarnessConfig, phase_dir: str) -> Path:
    return cfg.phases_dir / phase_dir / LOCK_FILENAME


def _pid_alive(pid: int) -> bool:
    """POSIX 환경 가정 — kill(pid, 0) 으로 존재 확인."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # 권한이 없어도 process 는 존재
        return True
    return True


def acquire_lock(
    cfg: HarnessConfig,
    phase_dir: str,
    worktree_path: str,
    session_id: str,
    force_stale: bool = False,
) -> LockInfo:
    """phase 에 대한 lock 획득.

    이미 잡혀 있으면:
    - stale (pid 죽음) + force_stale=True: 기존 lock 덮어쓰고 획득.
    - stale + force_stale=False: LockBusy(stale 표시) 발생.
    - 살아있음: LockBusy 발생.
    """
    lp = _lock_path(cfg, phase_dir)
    lp.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "worktree_path": worktree_path,
        "session_id": session_id,
        "acquired_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pid": os.getpid(),
    }

    try:
        # O_EXCL — 이미 존재하면 FileExistsError
        fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        existing = inspect_lock(cfg, phase_dir)
        if existing is None:
            # 경합으로 사라짐 — 재시도
            return acquire_lock(cfg, phase_dir, worktree_path, session_id, force_stale)
        alive = _pid_alive(existing.pid)
        if alive:
            raise LockBusy(existing.raw)
        # stale
        if not force_stale:
            info = dict(existing.raw)
            info["_stale"] = True
            raise LockBusy(info)
        # force_stale: 덮어쓰기
        lp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return LockInfo(**payload, raw=payload)  # type: ignore[arg-type]

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        # 쓰기 실패 시 빈 lock 정리
        try:
            lp.unlink()
        except FileNotFoundError:
            pass
        raise

    return LockInfo(**payload, raw=payload)  # type: ignore[arg-type]


def inspect_lock(cfg: HarnessConfig, phase_dir: str) -> LockInfo | None:
    lp = _lock_path(cfg, phase_dir)
    if not lp.exists():
        return None
    try:
        raw = json.loads(lp.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return LockInfo(
        worktree_path=raw.get("worktree_path", ""),
        session_id=raw.get("session_id", ""),
        acquired_at=raw.get("acquired_at", ""),
        pid=int(raw.get("pid", 0)),
        raw=raw,
    )


def release_lock(
    cfg: HarnessConfig,
    phase_dir: str,
    session_id: str,
    force: bool = False,
) -> bool:
    """session_id 가 일치하거나 force=True 면 lock 제거.

    Returns: 실제로 제거했으면 True.
    """
    info = inspect_lock(cfg, phase_dir)
    if info is None:
        return False
    if not force and info.session_id != session_id:
        raise LockError(
            f"phase '{phase_dir}' lock 의 session_id 가 일치하지 않습니다. "
            f"보유자: {info.session_id}, 요청자: {session_id}. force=True 로 강제 해제 가능."
        )
    _lock_path(cfg, phase_dir).unlink(missing_ok=True)
    return True


def is_stale(info: LockInfo) -> bool:
    return not _pid_alive(info.pid)
