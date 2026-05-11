# fullstack-harness

**범용 풀스택 웹/앱 개발용 harness.** Phase 기반 진행 + V-Model 산출물 + 의존성 DAG + 병렬 worktree dispatch + Claude Code 슬래시 명령 통합.

기술 스택 중립 — Next.js, Vue, SvelteKit, Flutter 등 어떤 스택이든 `harness.json` 만 채우면 그대로 적용.

## 핵심 개념

- **Phase**: 작업의 한 단위. infra / feature / acceptance 셋으로 분류.
- **V-Model 6 step**: `spec → design → test-first → implement → integrate → accept`. phase 안에서 좌측 산출물과 우측 테스트가 ID로 짝.
- **DAG 의존성**: phase 간 `depends_on` 으로 진행 순서 + 병렬 가능 여부 결정.
- **Worktree dispatch**: 병렬 가능한 phase 들을 `git worktree` 로 분리해서 별도 Claude Code 세션에서 동시 진행.
- **LLM-driven 의존성 inference**: 슬래시 명령이 phase spec.md 를 읽고 의존성 추론 → 사용자 컨펌 → Python harness 가 백업·DAG 재검증과 함께 적용.

## 디렉토리 구조

```
fullstack-harness/
├── README.md, AGENTS.md, .gitignore
├── fullstack_harness/   ← Python package
│   ├── harness.py       ← CLI entrypoint
│   ├── config.py, dag.py, status.py, parallel.py, lock.py
│   ├── merge_gate.py, set_deps.py, validation.py
│   └── __init__.py
├── templates/           ← project init용 JSON 템플릿
├── commands/            ← Claude Code 슬래시 명령 (.md)
└── docs/
    ├── USAGE.md         ← 사용 흐름
    └── SCHEMA.md        ← harness.json / phases/index.json 스키마
```

## 빠른 시작

대상 프로젝트 root 에서:

```bash
# 1. harness.json 생성
cp <fullstack-harness>/templates/harness.json.template ./harness.json

# 2. phases/index.json 생성
mkdir -p phases
cp <fullstack-harness>/templates/phases_index.json.template phases/index.json

# 3. 슬래시 명령 설치 (Claude Code 프로젝트)
mkdir -p .claude/commands
cp <fullstack-harness>/commands/*.md .claude/commands/

# 4. discovery 진행 → `/harness` 로 phase 시작
```

자세한 흐름은 [docs/USAGE.md](docs/USAGE.md). 스키마 레퍼런스는 [docs/SCHEMA.md](docs/SCHEMA.md).

## v0.1.x 범위

| 기능 | 상태 |
|---|---|
| 추상화 스키마 (harness.json + phase index) | ✅ |
| Python harness 핵심 (status / next / validate / discovery-complete) | ✅ |
| DAG 의존성 (depends_on + cycle detection + ready set + all_features expand) | ✅ |
| 병렬 phase 후보 + worktree 안내 (`next --parallel`, `worktree-plan`) | ✅ |
| Phase lock (`.lock` 파일, stale 감지, force takeover) | ✅ |
| Acceptance merge gate (`merge-gate`) | ✅ |
| `/harness` 슬래시 명령 | ✅ |
| LLM-driven 의존성 inference (`/harness-analyze-deps` + `set-deps` 백업+롤백) | ✅ |

## v0.2 이후 계획

- **v0.2**: phase executor 통합 (`/harness run <phase>` 실제 실행), DB 격리 옵션 (schema / docker-compose), tech-stack adapter plugin point.
- **v0.3**: CLI install 흐름 (예: `npx fullstack-harness init` 또는 `pip install fullstack-harness`).

## 기원

이 repo 는 dutytable 프로젝트의 V-Model phase 구조와 Python harness 를 추상화해서 출발했다. 이제 standalone repo 로 독립 진화한다.

## 컨벤션

- Python 3.11+, 표준 라이브러리만 (외부 의존성 회피).
- 기술 스택 중립 — 코드에 Next.js / Supabase / Vercel 등 특정 스택을 하드코딩하지 않는다.
- 커밋: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).

자세한 규칙은 [AGENTS.md](AGENTS.md).
