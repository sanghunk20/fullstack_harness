# Harness Schema (v0.2)

대상 프로젝트가 이 harness를 사용하려면 다음 파일들이 필요하다.

```
<target-project>/
  harness.json              ← project-level config (기술 스택 중립)
  phases/
    index.json              ← phase 목록 + 의존성 DAG
    <phase-dir>/
      index.json            ← 개별 phase 진행 상태
      spec.md, design.md, ... (V-Model 산출물)
  docs/                     ← discovery 산출물 (REQUIREMENTS, QUALITY, CONSTRAINTS 등 — 파일명은 config에서 지정)
```

---

## 1. `harness.json` (project root)

프로젝트 메타데이터 + tech-stack 명령어 + harness 설정. **기술 스택 중립**의 핵심.

```json
{
  "harness_version": "0.2",
  "project": "my-app",
  "description": "한 줄 프로젝트 설명",

  "stack": {
    "language": "typescript",
    "framework": "next",
    "db": "supabase",
    "deploy": "vercel",
    "adapter": null
  },

  "commands": {
    "dev": "npm run dev",
    "build": "npm run build",
    "typecheck": "npm run typecheck",
    "lint": "npm run lint",
    "test_unit": "npm run test",
    "test_integration": "npm run test:integration",
    "test_e2e": "npm run test:e2e",
    "migrate": "supabase db reset",
    "format": "npm run format",
    "create_schema": "psql \"$DATABASE_URL\" -c 'CREATE SCHEMA IF NOT EXISTS ${SCHEMA};'",
    "drop_schema": "psql \"$DATABASE_URL\" -c 'DROP SCHEMA IF EXISTS ${SCHEMA} CASCADE;'"
  },

  "discovery": {
    "command": "/req-eng",
    "required_files": [
      "docs/REQUIREMENTS.md",
      "docs/QUALITY.md",
      "docs/CONSTRAINTS.md"
    ],
    "id_prefixes": {
      "functional": "FR",
      "quality": "NFR",
      "constraint": "CON"
    }
  },

  "phases_dir": "phases",

  "worktree": {
    "base_path": ".worktrees",
    "db_isolation": "schema",
    "schema_env_var": "DATABASE_SCHEMA",
    "compose_template": null,
    "compose_command": "docker compose"
  },

  "v_model": {
    "default": true,
    "steps": ["spec", "design", "test-first", "implement", "integrate", "accept"],
    "step_gates": {}
  }
}
```

### 필드 설명

| 필드 | 의미 |
|---|---|
| `harness_version` | 이 config가 호환되는 harness 버전 (semver). harness가 mismatch 시 경고. |
| `project` | 프로젝트 이름. UI 표시용. |
| `stack.framework`, `stack.db` | tech-stack adapter 자동 매칭에 사용. 다른 필드는 정보용. |
| `stack.adapter` | (v0.2) adapter 명시 선택. 비어 있으면 framework+db 로 자동 매칭. |
| `commands.*` | harness가 phase 실행 중 호출하는 외부 명령들. 모두 optional — 정의된 것만 사용. `commands.create_schema`, `commands.drop_schema` 는 `db_isolation: "schema"` 시 사용 (변수: `${SCHEMA}`). |
| `discovery.command` | discovery 단계 진입 시 사용자에게 안내할 슬래시 명령. |
| `discovery.required_files` | discovery 완료 검증 시 존재·내용 검사할 파일 목록. |
| `discovery.id_prefixes` | 표 첫 컬럼에서 카운트할 ID prefix. 비어 있으면 해당 카테고리 검증 skip. |
| `phases_dir` | phase 디렉토리 루트. 기본 `phases`. |
| `worktree.base_path` | 병렬 phase용 git worktree 생성 위치. repo 안 권장(`.worktrees`). |
| `worktree.db_isolation` | (v0.2) `none` / `schema` / `compose`. 모두 plan 만 출력 — 사용자가 직접 실행. |
| `worktree.schema_env_var` | (v0.2) schema 모드에서 환경변수 이름. 기본 `DATABASE_SCHEMA`. |
| `worktree.compose_template` | (v0.2) compose 모드에서 사용할 yml 템플릿 경로. 변수: `${PHASE}`, `${PROJECT_NAME}`, `${PORT_OFFSET}` 등. |
| `worktree.compose_command` | (v0.2) compose 호출 명령. 기본 `docker compose`. |
| `v_model.default` | phase의 `v_model` 필드가 누락된 경우 기본값. |
| `v_model.steps` | step 이름 순서. harness가 이 이름으로 검증. |
| `v_model.step_gates` | (v0.2) step 별 권장 gate command 키 매핑. 비어 있으면 adapter 의 step_gates 사용. |

---

## 2. `phases/index.json`

phase 목록과 phase 간 의존성 DAG + project-level discovery 상태.

```json
{
  "discovery_status": "completed",
  "discovery_completed_at": "2026-05-05T22:07:15+0900",
  "ui_guide_status": "completed",
  "ui_guide_completed_at": "2026-05-05T22:30:00+0900",

  "phases": [
    {
      "dir": "0-bootstrap",
      "name": "0-bootstrap",
      "description": "인프라 셋업",
      "kind": "infra",
      "v_model": false,
      "depends_on": [],
      "status": "completed",
      "completed_at": "2026-05-07T00:38:00+0900"
    },
    {
      "dir": "1-feature-auth",
      "name": "1-feature-auth",
      "description": "사용자 인증",
      "kind": "feature",
      "v_model": true,
      "depends_on": ["0-bootstrap"],
      "status": "pending"
    },
    {
      "dir": "2-feature-billing",
      "name": "2-feature-billing",
      "description": "결제",
      "kind": "feature",
      "v_model": true,
      "depends_on": ["1-feature-auth"],
      "status": "pending"
    },
    {
      "dir": "3-feature-profile",
      "name": "3-feature-profile",
      "description": "프로필",
      "kind": "feature",
      "v_model": true,
      "depends_on": ["1-feature-auth"],
      "status": "pending"
    },
    {
      "dir": "99-acceptance",
      "name": "99-acceptance",
      "kind": "acceptance",
      "v_model": false,
      "depends_on": "all_features",
      "status": "pending"
    }
  ]
}
```

### 필드 설명

| 필드 | 의미 |
|---|---|
| `discovery_status` | `pending` / `completed`. harness.json의 `discovery.required_files` 검증 후 마킹. /req-eng 가 책임. |
| `ui_guide_status` | (v0.2) `pending` / `completed`. `docs/UI_GUIDE.md` 존재 + 비어있지 않으면 completed 가능. /ui-guide 가 책임. |
| `phases[].dir` | phase 디렉토리 이름. `phases_dir/<dir>` 경로. unique. |
| `phases[].name` | 표시용 이름. 보통 dir과 동일. |
| `phases[].description` | 한 줄 설명. |
| `phases[].kind` | `infra` / `feature` / `acceptance`. acceptance phase는 모든 feature 완료 후만 진입. |
| `phases[].v_model` | true면 V-Model 6 step 강제. false면 free-form steps. |
| `phases[].depends_on` | string[] 또는 `"all_features"` 특수값. 다른 phase의 dir 이름. **acceptance phase는 `"all_features"` 사용 권장.** |
| `phases[].status` | `pending` / `in_progress` / `completed` / `blocked` / `error`. |

### 의존성 DAG 규칙

- `depends_on`에 나열된 phase가 **모두 completed** 여야 해당 phase가 ready 상태.
- 순환 의존성은 harness가 detect → 즉시 error.
- `"all_features"` 특수값은 `kind: "feature"`인 모든 phase의 completed를 요구.
- 같은 ready 집합 안 여러 phase는 **병렬 진행 가능 후보**.

---

## 3. `phases/<phase-dir>/index.json`

개별 phase의 step 진행 상태.

```json
{
  "name": "1-feature-auth",
  "v_model": true,
  "completed_at": null,
  "steps": [
    {
      "step": 1,
      "name": "spec",
      "status": "pending",
      "summary": "",
      "started_at": null,
      "completed_at": null
    },
    {
      "step": 2,
      "name": "design",
      "status": "pending"
    },
    { "step": 3, "name": "test-first", "status": "pending" },
    { "step": 4, "name": "implement", "status": "pending" },
    { "step": 5, "name": "integrate", "status": "pending" },
    { "step": 6, "name": "accept", "status": "pending" }
  ]
}
```

### V-Model phase

`v_model: true`인 phase는 `steps`가 정확히 6개, `name` 순서는 `harness.json`의 `v_model.steps`와 일치해야 함. harness가 검증.

### 비 V-Model phase

`v_model: false`인 phase (infra, acceptance, hotfix 등)는 free-form steps. 이름·개수 자유. harness는 status만 검사.

---

## 4. `<phase-dir>/.lock` (런타임 생성)

phase가 worktree에서 작업 중이면 생성. 다른 worktree·세션이 같은 phase를 잡으려 하면 abort.

```json
{
  "worktree_path": "/abs/path/to/.worktrees/1-feature-auth",
  "session_id": "claude-2026-05-11-xxx",
  "acquired_at": "2026-05-11T14:00:00+0900",
  "pid": 12345
}
```

stale lock 청소 규칙:
- `pid`가 살아있지 않으면 stale.
- `acquired_at`이 24시간 이상 지났으면 경고 + 사용자에게 확인.

---

## v0.1.x 디자인 노트

### 왜 `harness.json` 과 `phases/index.json` 을 분리했나?

- `harness.json` 은 **프로젝트 메타** — 기술 스택, 명령어, discovery 설정. 거의 안 바뀜.
- `phases/index.json` 은 **상태** — phase 진행 상황, 의존성. 자주 바뀜.
- 분리하면 진행 상태가 변할 때 메타 config 가 dirty 해지지 않고, 그 반대도 성립.

### 왜 `kind` 필드?

- `infra` / `feature` / `acceptance` 셋으로 명시. dir 이름 컨벤션 (`0-bootstrap`, `99-acceptance`) 에 의존하지 않기 위함.
- harness 가 acceptance phase 의 `depends_on: "all_features"` 를 정확히 expand 할 수 있게 함.

### 왜 `depends_on` 을 명시 필요?

- 순차 진행만 가정하면 병렬 worktree dispatch 가 불가능.
- DAG 로 모델링해야 ready set 계산 + cycle 감지 가능.
- 명시 부담은 v0.1.1 의 `/harness-analyze-deps` (LLM 추론 + 사용자 컨펌) 으로 완화.

## Setup Chain (v0.2)

새 프로젝트 디스커버리 흐름. `python3 -m fullstack_harness.harness setup-status` 가 다음을 한 줄로 출력:

```
discovery=<pending|completed>\tui_guide=<pending|completed>\tstack=<configured|tbd>\tnext=<req-eng|ui-guide|stack-select|harness>
```

`/harness` 가 이 출력을 파싱해서 사용자에게 다음 명령을 안내. 상태 전이:

| 상태 | next | 책임 명령 |
|---|---|---|
| discovery=pending | req-eng | `/req-eng` |
| discovery=completed, ui_guide=pending | ui-guide | `/ui-guide` |
| 위 둘 완료, stack=tbd | stack-select | `/stack-select` |
| 모두 만족 | harness | `/harness` (정상 phase dispatch) |

revision 모드는 `discovery-reopen` / `ui-guide-reopen` 으로 status 를 pending 으로 되돌린 뒤 재작성 → `discovery-complete` / `ui-guide-complete` 로 다시 마킹.

## v0.2 디자인 노트

### 왜 executor 를 "orchestrator only" 로?

- 자동 gate 실행 + step advance 는 매력적이지만, gate 실패 시 사용자가 끼어들 지점이 모호해진다.
- 첫 출시는 안내·상태·lock 만 책임지고 실제 작업·검증은 LLM/사용자가 하는 모델이 깨끗.
- v0.3 에서 `--auto-advance` 같은 flag 로 자동화 모드 추가 검토.

### 왜 adapter 를 module-as-plugin?

- 외부 의존성 없이 stdlib `importlib` 만 사용 가능.
- adapter 추가는 파일 1개. config / DSL 없이 Python 으로 직접 표현.
- 사용자 어댑터는 `<target>/.harness/adapters/*.py` — repo 안 commit 안 해도 동작.

### 왜 DB 격리를 "plan only" 로?

- 격리 명령 (psql, docker compose) 자동 실행은 환경마다 권한·인증·side effect 가 다름.
- harness 가 명령을 출력만 하고 사용자가 컨펌·실행하는 게 v0.2 안전 영역.
- v0.3 에서 `--auto-isolate` flag 검토.
