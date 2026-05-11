# fullstack-harness

**범용 풀스택 웹/앱 개발용 harness.** Phase 기반 진행 + V-Model 산출물 + 의존성 DAG + 병렬 worktree dispatch + Claude Code 슬래시 명령 통합 + tech-stack adapter plugin.

기술 스택 중립 — Next.js, Vue, SvelteKit, Flutter 등 어떤 스택이든 `harness.json` 만 채우면 그대로 적용. 빌트인 adapter (`next_supabase`, `vue_firebase`) 가 stack 자동 매칭으로 권장 명령·gate 제공.

## 빠른 시작 (v0.2 chain)

```bash
git clone https://github.com/sanghunk20/fullstack_harness.git my-new-app
cd my-new-app
claude
```

Claude Code 안에서:

```
/setup            → 프로젝트 이름·한 줄 설명만 입력하고 초기화
/req-eng          → 기능/품질/제약 요구사항 인터뷰 → docs/*.md
/ui-guide         → 디자인 톤·컬러·타이포·컴포넌트 컨벤션 인터뷰 → docs/UI_GUIDE.md
/stack-select     → 위 분석 기반 frontend/backend/DB 추천 + 선택 → harness.json 업데이트
/feature          → 신규 feature/infra/acceptance phase 추가 (반복 호출 가능)
/harness          → 상태 점검 + 다음 액션 안내 (위 단계가 끝나야 phase 진입)
```

각 명령은 다음 명령을 안내해줍니다. `/req-eng` 와 `/ui-guide` 는 **mid-project 수정** (추가/수정/삭제/재작성) 모드도 지원.

## 핵심 개념

- **Project-level discovery (1회)**: `/setup → /req-eng → /ui-guide → /stack-select`. mid-project 에 /req-eng / /ui-guide 재호출하면 revision 모드.
- **Phase**: 작업의 단위. infra / feature / acceptance 셋으로 분류. `/feature` 로 추가.
- **V-Model 6 step** (feature phase 내부): `spec → design → test-first → implement → integrate → accept`. 좌측 산출물과 우측 테스트가 ID 로 짝.
- **DAG 의존성**: phase 간 `depends_on` 으로 진행 순서 + 병렬 가능 여부 결정.
- **Worktree dispatch**: 병렬 가능한 phase 들을 `git worktree` 로 분리해서 별도 Claude Code 세션에서 동시 진행.
- **LLM-driven 의존성 inference**: `/harness-analyze-deps` 가 phase spec.md 를 읽고 의존성 추론 → 사용자 컨펌 → Python harness 가 백업·DAG 재검증과 함께 적용.
- **Phase executor**: `/harness run <phase>` 로 V-Model step 진입, `step-complete` / `phase-complete` 로 진행. orchestrator only — LLM/사용자가 작업, harness 는 안내·상태·lock 관리.
- **DB 격리**: `worktree.db_isolation` = `none` / `schema` / `compose`. 각 모드 별 setup/teardown 명령을 stack-neutral 하게 안내.
- **Tech-stack adapter**: 빌트인 + `<target>/.harness/adapters/*.py` 로 사용자 어댑터 추가. stack 매칭으로 `commands` defaults + V-Model `step_gates` 자동 결정.

## 디렉토리 구조

```
fullstack-harness/
├── README.md, AGENTS.md, .gitignore
├── .claude/commands/    ← Claude Code 슬래시 명령 (clone 직후 바로 사용 가능)
│   ├── setup.md, req-eng.md, ui-guide.md, stack-select.md, feature.md
│   ├── harness.md, harness-analyze-deps.md
├── fullstack_harness/   ← Python package
│   ├── harness.py       ← CLI entrypoint
│   ├── config.py, dag.py, status.py, parallel.py, lock.py
│   ├── merge_gate.py, set_deps.py, add_phase.py, validation.py
│   ├── executor.py      ← phase/step orchestrator
│   ├── db_iso.py        ← DB 격리 plan
│   ├── adapters/        ← stack-adapter plugin point
│   │   ├── _default.py, next_supabase.py, vue_firebase.py
│   └── __init__.py
├── templates/           ← project init용 JSON 템플릿
├── examples/            ← config-only fixtures (nextjs-supabase, vue-firebase)
└── docs/
    ├── USAGE.md         ← 사용 흐름
    └── SCHEMA.md        ← harness.json / phases/index.json 스키마
```

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
| LLM-driven 의존성 inference (`/harness-analyze-deps` + `set-deps`) | v0.1 | ✅ |
| Phase executor (`run` / `step-complete` / `phase-complete` / `release-lock`) | v0.2 | ✅ |
| DB 격리 plan (`none` / `schema` / `compose`) | v0.2 | ✅ |
| Tech-stack adapter plugin point + 빌트인 어댑터 2개 | v0.2 | ✅ |
| Config-only fixtures (examples/) | v0.2 | ✅ |
| Project-level discovery chain (/setup → /req-eng → /ui-guide → /stack-select) | v0.2 | ✅ |
| /req-eng + /ui-guide revision-aware (mid-project 수정) | v0.2 | ✅ |
| /feature — 신규 phase 추가 (백업 + DAG 재검증) | v0.2 | ✅ |
| /harness chain gate (각 단계 미완 시 다음 명령 안내) | v0.2 | ✅ |

## 로드맵

- **v0.3**: gate command 자동 실행 옵션 (`--auto-advance`), worktree 자동 spawn, 격리 setup 자동 실행 옵션. PyPI 배포는 옵셔널 — git clone 흐름이 1차.
- **v0.4**: 멀티 머신 (remote phase dispatch), 사용자 정의 chain step 등록.

## 기원

이 repo 는 dutytable 프로젝트의 V-Model phase 구조와 Python harness 를 추상화해서 출발했다. dutytable 의 `/setup` / `/req-eng` / `/ui-guide` / `/feature` 흐름을 일반화. standalone repo 로 독립 진화 — git clone 후 `PYTHONPATH` 추가 또는 직접 `--target` 으로 사용.

## 컨벤션

- Python 3.11+, 표준 라이브러리만 (외부 의존성 회피).
- 기술 스택 중립 — 코드에 Next.js / Supabase / Vercel 등 특정 스택을 하드코딩하지 않는다. stack-specific 동작은 adapter (`fullstack_harness/adapters/*.py`) 또는 harness.json.commands 로 분리.
- 커밋: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).

자세한 규칙은 [AGENTS.md](AGENTS.md).
