# fullstack-harness

**범용 풀스택 웹/앱 개발용 harness.** Phase 기반 진행 + V-Model 산출물 + 의존성 DAG + 병렬 worktree dispatch + Claude Code 슬래시 명령 통합 + tech-stack adapter plugin.

기술 스택 중립 — Next.js, Vue, SvelteKit, Flutter 등 어떤 스택이든 `harness.json` 만 채우면 그대로 적용. 빌트인 adapter (`next_supabase`, `vue_firebase`) 가 stack 자동 매칭으로 권장 명령·gate 제공.

## 핵심 개념

- **Phase**: 작업의 한 단위. infra / feature / acceptance 셋으로 분류.
- **V-Model 6 step**: `spec → design → test-first → implement → integrate → accept`. phase 안에서 좌측 산출물과 우측 테스트가 ID로 짝.
- **DAG 의존성**: phase 간 `depends_on` 으로 진행 순서 + 병렬 가능 여부 결정.
- **Worktree dispatch**: 병렬 가능한 phase 들을 `git worktree` 로 분리해서 별도 Claude Code 세션에서 동시 진행.
- **LLM-driven 의존성 inference**: 슬래시 명령이 phase spec.md 를 읽고 의존성 추론 → 사용자 컨펌 → Python harness 가 백업·DAG 재검증과 함께 적용.
- **Phase executor (v0.2)**: `/harness run <phase>` 로 V-Model step 진입, `step-complete` / `phase-complete` 로 진행. orchestrator only — LLM/사용자가 작업, harness 는 안내·상태·lock 관리.
- **DB 격리 (v0.2)**: `worktree.db_isolation` = `none` / `schema` / `compose`. 각 모드 별 setup/teardown 명령을 stack-neutral 하게 안내.
- **Tech-stack adapter (v0.2)**: 빌트인 + `<target>/.harness/adapters/*.py` 로 사용자 어댑터 추가. stack 매칭으로 `commands` defaults + V-Model `step_gates` 자동 결정.

## 디렉토리 구조

```
fullstack-harness/
├── README.md, AGENTS.md, .gitignore
├── fullstack_harness/   ← Python package
│   ├── harness.py       ← CLI entrypoint
│   ├── config.py, dag.py, status.py, parallel.py, lock.py
│   ├── merge_gate.py, set_deps.py, validation.py
│   ├── executor.py      ← v0.2: phase/step orchestrator
│   ├── db_iso.py        ← v0.2: DB 격리 plan (none/schema/compose)
│   ├── adapters/        ← v0.2: stack-adapter plugin point
│   │   ├── _default.py, next_supabase.py, vue_firebase.py
│   └── __init__.py
├── templates/           ← project init용 JSON 템플릿
├── commands/            ← Claude Code 슬래시 명령 (.md)
├── examples/            ← v0.2: config-only fixtures (nextjs-supabase, vue-firebase)
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

# 4. discovery 진행 → `/harness` 로 phase 시작 → `/harness run <phase>` 로 step 진입
```

자세한 흐름은 [docs/USAGE.md](docs/USAGE.md). 스키마 레퍼런스는 [docs/SCHEMA.md](docs/SCHEMA.md). fixture 예제는 [examples/](examples/).

## 기능 상태

| 기능 | 도입 | 상태 |
|---|---|---|
| 추상화 스키마 (harness.json + phase index) | v0.1 | ✅ |
| Python harness 핵심 (status / next / validate / discovery-complete) | v0.1 | ✅ |
| DAG 의존성 (depends_on + cycle detection + ready set + all_features expand) | v0.1 | ✅ |
| 병렬 phase 후보 + worktree 안내 (`next --parallel`, `worktree-plan`) | v0.1 | ✅ |
| Phase lock (`.lock` 파일, stale 감지, force takeover) | v0.1 | ✅ |
| Acceptance merge gate (`merge-gate`) | v0.1 | ✅ |
| `/harness` 슬래시 명령 | v0.1 | ✅ |
| LLM-driven 의존성 inference (`/harness-analyze-deps` + `set-deps` 백업+롤백) | v0.1 | ✅ |
| Phase executor (`run` / `step-complete` / `phase-complete` / `release-lock`) | v0.2 | ✅ |
| DB 격리 plan (`none` / `schema` / `compose`) | v0.2 | ✅ |
| Tech-stack adapter plugin point + 빌트인 어댑터 2개 | v0.2 | ✅ |
| Config-only fixtures (examples/) | v0.2 | ✅ |

## 로드맵

- **v0.3**: 격리된 phase 자동 실행 (gate command auto-run + advance), CLI install 흐름. PyPI 배포는 옵셔널 — git clone + PYTHONPATH 흐름이 1차.
- **v0.4**: worktree 자동 spawn (사용자 컨펌 후), 멀티 머신 (remote phase dispatch) 검토.

## 기원

이 repo 는 dutytable 프로젝트의 V-Model phase 구조와 Python harness 를 추상화해서 출발했다. standalone repo 로 독립 진화 — git clone 후 `PYTHONPATH` 추가 또는 직접 `--target` 으로 사용.

## 컨벤션

- Python 3.11+, 표준 라이브러리만 (외부 의존성 회피).
- 기술 스택 중립 — 코드에 Next.js / Supabase / Vercel 등 특정 스택을 하드코딩하지 않는다. stack-specific 동작은 adapter (`fullstack_harness/adapters/*.py`) 또는 harness.json.commands 로 분리.
- 커밋: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).

자세한 규칙은 [AGENTS.md](AGENTS.md).
