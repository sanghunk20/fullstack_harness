# fullstack-harness 사용법 (v0.2)

## 설치 (clone-as-skeleton 흐름, 권장)

```bash
git clone https://github.com/sanghunk20/fullstack_harness.git my-new-app
cd my-new-app

# Python harness 를 PYTHONPATH 에 노출 (clone 위치를 직접 가리킴)
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Claude Code 실행
claude
```

`.claude/commands/` 가 이미 채워져 있으므로 첫 슬래시 명령부터 바로 사용 가능.

> repo 자체를 프로젝트 root 로 쓰는 흐름입니다. clone 직후 `.git` 을 원격 fork 로 옮기거나 새로 init 해서 사용하세요.

## 설치 (install-into-existing-project 흐름)

이미 있는 프로젝트에 harness 만 끼워 넣고 싶다면:

```bash
git clone https://github.com/sanghunk20/fullstack_harness.git ~/projects/fullstack-harness
FH=~/projects/fullstack-harness

cd <target-project>

# 슬래시 명령 복사
mkdir -p .claude/commands
cp "$FH/.claude/commands/"*.md .claude/commands/

# Python harness 를 PYTHONPATH 에 노출
export PYTHONPATH="$FH:$PYTHONPATH"

# Claude Code 실행 → /setup
claude
```

이후 흐름은 동일.

## 한 줄 정리: chain

```
/setup → /req-eng → /ui-guide → /stack-select → /feature ... → /harness
```

`/harness` 는 위 단계 중 미완 단계가 있으면 그쪽으로 안내 + 종료. 모두 끝나면 phase dispatch 흐름.

## 시나리오별

### 새 프로젝트 시작

```
/setup            — 프로젝트 이름·한 줄 설명만 입력 (요구사항 인터뷰 X)
/harness          — "다음: /req-eng" 안내
/req-eng          — FR / NFR / CON 인터뷰 → docs/REQUIREMENTS.md / QUALITY.md / CONSTRAINTS.md
/harness          — "다음: /ui-guide" 안내
/ui-guide         — 톤·컬러·타이포·컴포넌트 컨벤션 → docs/UI_GUIDE.md
/harness          — "다음: /stack-select" 안내
/stack-select     — frontend/backend/DB 추천 2~3 옵션 → 선택 → harness.json 업데이트
/harness          — phase 가 없으므로 "/feature 로 첫 phase 추가" 안내
/feature 1-feature-auth   — 첫 feature phase 추가 (kind/depends_on/description 인터뷰)
/feature 2-feature-...
/harness          — 진행 가능 phase 안내
/harness run 1-feature-auth   — V-Model step 1 (spec) 진입
... step 작업 ...
/harness step-complete 1-feature-auth --summary "spec.md 작성"
/harness run 1-feature-auth   — step 2 (design)
... 반복 ...
/harness phase-complete 1-feature-auth   — phase 완료, lock 해제
```

### Mid-project: 요구사항 변경

```
/req-eng          — revision 모드 진입 → (1) 보기 (2) 추가 (3) 수정 (4) 삭제 (5) 전체 재작성
                    → 변경 적용 → discovery-complete 재마킹
                    → 영향 받는 phase 의 spec.md / design.md 검토 안내
```

### Mid-project: UI 가이드 변경

```
/ui-guide         — revision 모드 진입 → 추가/수정/삭제/재작성
                    → 영향 받는 phase 검토
```

### Mid-project: 새 feature phase 추가

```
/feature 3-feature-billing
                  — dir / kind / description / v_model / depends_on 인터뷰
                  → phases/index.json + phases/3-feature-billing/index.json 자동 생성
                  → DAG 재검증 + 백업
                  → /harness 로 진행
```

### 여러 phase 가 병렬 진행 가능할 때

`/harness next --parallel` 출력:

```
  진행 가능 phase 2개 — 병렬 worktree 분리 가능.
    • 2-billing                       feature    (deps: 1-auth)
    • 3-profile                       feature    (deps: 1-auth)
```

(B) 병렬 선택 시:

```bash
python3 -m fullstack_harness.harness worktree-plan 2-billing 3-profile
```

출력된 `git worktree add ...` 명령을 직접 실행 → 각 worktree 에서 새 Claude Code 세션 → 그 세션에서 `/harness run <phase>`.

> **반드시 새 세션을 띄울 것.** 한 세션에서 cwd 만 바꾸면 컨텍스트 오염.

### phase 작업 완료 후

- 해당 worktree 에서 `/harness phase-complete <phase>`.
- PR 생성 → main merge.
- 모든 feature phase 완료 → `/harness merge-gate` 로 모든 브랜치 merge 검증.
- acceptance phase 진행.

### blocked / error 발생 시

- harness 가 자동 진행 제안을 멈춤.
- 사용자가 phase 의 `index.json` 에서 `blocked_reason` / `error_message` 확인.
- 원인 해결 후 status 를 `pending` 으로 되돌리고 다시 `/harness`.

### Lock 문제

- 같은 worktree 안에서 step 사이 lock 자동 인수됨 (Bash spawn 마다 새 pid).
- 다른 worktree 가 잡은 lock 은 `release-lock --force` 또는 그쪽 종료 대기.

```bash
python3 -m fullstack_harness.harness release-lock <phase> [--force]
```

## DB 격리 (`worktree.db_isolation`)

| 모드 | 동작 | 필요 설정 |
|---|---|---|
| `none` | 격리 안 함. 모든 worktree 가 같은 DB 공유. | 없음 |
| `schema` | 단일 DB 안에서 worktree 별 schema. | `commands.create_schema`, `commands.drop_schema` (`${SCHEMA}` 변수 사용 가능). |
| `compose` | worktree 별 docker-compose stack. | `worktree.compose_template` 가 가리키는 yml. `${PHASE}`, `${PORT_OFFSET}`, `${PROJECT_NAME}` 등 변수 치환. |

**harness 는 명령을 실행하지 않습니다 — 사용자에게 plan 만 안내.** 자동 실행은 v0.3 이후.

## Tech-stack Adapter

`harness.json.stack.framework` + `stack.db` 가 빌트인 어댑터와 매칭되면 자동 선택:

| 어댑터 | 매칭 조건 |
|---|---|
| `next_supabase` | framework ∈ {next, nextjs} AND db == supabase |
| `vue_firebase` | framework ∈ {vue, vuejs, nuxt} AND db ∈ {firebase, firestore} |
| `_default` | 위 모두 미스 시 fallback |

사용자 어댑터: `<target-project>/.harness/adapters/<name>.py`

```python
NAME = "svelte_drizzle"
def match(stack):
    return stack.get("framework") == "svelte" and stack.get("db") == "drizzle"
def commands_defaults():
    return {"dev": "npm run dev", "test_unit": "vitest run"}
def step_gates():
    return {"implement": ["typecheck", "test_unit"]}
```

명시 선택은 `harness.json.stack.adapter` 에 이름 지정.

## 명령 레퍼런스

### 슬래시 명령 (Claude Code)

| 명령 | 용도 |
|---|---|
| `/setup` | 프로젝트 초기화 (이름·설명만) |
| `/req-eng` | FR/NFR/CON 인터뷰 (revision 모드 지원) |
| `/ui-guide` | 디자인 가이드 인터뷰 (revision 모드 지원) |
| `/stack-select` | 스택 추천 + 선택 |
| `/feature [<dir>]` | 새 phase 추가 |
| `/harness [<sub>]` | 상태 점검 + dispatcher (아래 sub 참조) |
| `/harness-analyze-deps` | phase spec 기반 의존성 LLM 추론 |

### Python harness CLI

```
python3 -m fullstack_harness.harness [--target <path>] <subcommand>

서브커맨드:
  status                       전체 상태 출력
  setup-status                 머신 파서블 chain 게이트 상태
  next [--parallel]            다음 phase 안내
  validate                     discovery 충실도 검사
  discovery-complete           discovery_status 를 completed 로 마킹
  discovery-reopen             discovery_status 를 pending 으로 되돌림 (revision 모드)
  ui-guide-complete            ui_guide_status 를 completed 로 마킹
  ui-guide-reopen              ui_guide_status 를 pending 으로 되돌림 (revision 모드)
  worktree-plan <phase>...     선택 phase 들의 worktree 명령
  merge-gate                   feature 브랜치 main merge 검증
  set-deps [--json-file <p>]   depends_on 일괄 패치
  add-phase <dir> --kind ...   새 phase 추가 (/feature 가 호출)
  run <phase>                  phase 의 현재/지정 step 진입
    [--step <name>]
    [--force-stale-lock]
  step-complete <phase>        현재 step 완료 마킹
    [--summary "..."]
  phase-complete <phase>       phase 자체 완료 + lock 해제
  release-lock <phase>         lock 수동 해제
    [--force]
```

`--target` 생략 시 cwd 또는 상위 디렉토리에서 `harness.json` 검색.

## 한계 (v0.2)

- **Gate 자동 실행 안 함**: `run` 이 권장 gate 명령을 출력하지만 실행은 사용자가. v0.3 에서 `--auto-advance` 검토.
- **DB 격리 setup 자동 실행 안 함**: plan 만 출력. compose 모드는 yml 만 자동 생성.
- **Inference 정확도**: spec.md 가 충실하지 않으면 추론도 빈약. 컨펌 단계에서 사용자가 보정.
- **Worktree 자동 spawn 안 함**: 명령 안내만, 사용자가 git worktree add 실행.
- **Chain 강제 X**: /harness 가 다음 명령을 안내하지만 사용자가 직접 입력. 자동 호출은 v0.3 이후 검토.
