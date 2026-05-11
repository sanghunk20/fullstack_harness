"""Discovery 문서 충실도 검증.

ID prefix 와 required files 경로를 harness.json 에서 읽어, markdown 표의 ID 들을 카운트한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import HarnessConfig


@dataclass
class DiscoveryReport:
    ok: bool
    counts: dict[str, int] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)


def _extract_table_ids(content: str, prefix: str) -> set[str]:
    """markdown 표 첫 컬럼의 `| <PREFIX>-NNN |` 형식 ID만 추출.

    본문 내 인용(백틱 안), placeholder(PREFIX-XXX) 등은 제외.
    """
    pattern = rf"^\s*\|\s*({re.escape(prefix)}-\d{{3,}})\b"
    return set(re.findall(pattern, content, re.MULTILINE))


def validate_discovery(cfg: HarnessConfig) -> DiscoveryReport:
    """harness.json 의 discovery 설정에 따라 required_files 의 ID 충실도 검사."""
    report = DiscoveryReport(ok=True)

    required = cfg.discovery_required_files
    prefixes = cfg.discovery_id_prefixes

    if not required:
        report.issues.append(
            "harness.json 에 discovery.required_files 가 비어 있음. discovery 검증을 건너뜁니다."
        )
        return report

    # required_files 와 id_prefixes 를 순서대로 zip. 길이가 다르면 가능한 만큼만 카운트.
    # 더 명시적이려면 required_files 를 [{path, prefix, category}] 객체 배열로 받을 수도 있음 (v0.2).
    files_by_category = _pair_files_to_prefixes(required, prefixes)

    for category, (file_path, prefix) in files_by_category.items():
        if not file_path.exists():
            report.ok = False
            report.issues.append(f"{file_path.relative_to(cfg.target_root)} 파일 없음 ({category})")
            report.counts[category] = 0
            continue
        if not prefix:
            report.counts[category] = 0
            continue
        ids = _extract_table_ids(file_path.read_text(encoding="utf-8"), prefix)
        report.counts[category] = len(ids)
        if not ids:
            # functional 카테고리는 critical, 나머지는 권장
            if category == "functional":
                report.ok = False
            report.issues.append(
                f"{file_path.relative_to(cfg.target_root)} 표에 {prefix}-NNN 항목 없음 "
                f"(placeholder {prefix}-XXX 는 무시)"
            )

    return report


def _pair_files_to_prefixes(
    required: list[Path], prefixes: dict[str, str]
) -> dict[str, tuple[Path, str]]:
    """required_files 배열과 id_prefixes 매핑.

    v0.1 단순 규칙:
    - id_prefixes 의 키 순서대로 required_files 와 1:1 매칭.
    - 더 짧은 쪽 길이만큼만 매칭.
    """
    out: dict[str, tuple[Path, str]] = {}
    prefix_items = list(prefixes.items())
    for i, file_path in enumerate(required):
        if i < len(prefix_items):
            cat, prefix = prefix_items[i]
            out[cat] = (file_path, prefix)
        else:
            out[f"extra_{i}"] = (file_path, "")
    return out
