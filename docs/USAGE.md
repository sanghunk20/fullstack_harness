# fullstack-harness 사용법 (v0.2.0)

## 설치

PyPI 배포는 도입 미정. git clone + PYTHONPATH 흐름이 1차다.

```bash
# 0. fullstack-harness repo 를 clone
git clone <fullstack-harness-repo-url> ~/projects/fullstack-harness
FH=~/projects/fullstack-harness

# 1. 대상 프로젝트로 이동
cd <target-project>

# 2. harness.json 을 프로젝트 root 에 생성
cp "$FH/templates/harness.json.template" ./harness.json
# 편집해서 project, stack, commands 등 채우기

# 3. phases/index.json 생성
mkdir -p phases
cp "$FH/templates/phases_index.json.template" phases/index.json

# 4. 슬래시 명령 설치 (Claude Code 프로젝트의 경우)
mkdir -p .claude/commands
cp "$FH/commands/"*.md .claude/commands/

# 5. Python harness 를 PYTHONPATH 에 노출 (또는 alias)
export PYTHONPATH="$FH:$PYTHONPATH"
# 영구화하려면 .bashrc / .zshrc 에 추가.
```

## 일상적인 흐름

매 세션 시작 때 `/harness` 만 호출하면 된다.

```
/harness
```

이 명령은:
1. 현재 상태 출력 (`status`).
2. blocked / error 가 없으면 다음 진행 가능 phase 분석 (`next --parallel`).
3. 병렬 후보가 2개 이상이면 사용자에게 어떻게 나눌지 묻고, 선택에 따라 worktree 명령 출력.

진행 가능 phase 가 정해지면:

```
/harness run <phase>      # 현재 step 진입 → 권장 gate command + DB 격리 안내 출력
/harness step-complete <phase> --summary "..."   # step 끝났을 때
/harness phase-complete <phase>                  # 모든 step 끝났을 때
```

## 시나리오별

### 새 프로젝트 시작

1. 위 "설치" 따라 `harness.json` + `phases/index.json` 생성.
2. discovery 단계 진행:
   - `harness.json` 의 `discovery.command` 실행 (예: `/req-eng`).
   - 필요한 docs 파일들 (`docs/REQUIREMENTS.md` 등) 채우기.
3. discovery 완료 마킹:
   ```bash
   python3 -m fullstack_harness.harness discovery-complete
   ```
4. 첫 phase 추가 (수동):
   - `phases/<dir>/index.json` 생성 (template 사용).
   - `phases/index.json` 의 `phases` 배열에 entry 추가, `depends_on` 명시.
5. `/harness` 호출 → 진행.

### Phase 실행 (v0.2 executor)

`/harness run <phase>` 호출 흐름:

```
$ /harness run 1-feature-auth

  ▶ Phase 1-feature-auth (feature)
  ▶ V-Model step 1/6: spec
    (V-Model 쌍: spec ↔ accept)
  ▶ Status: in_progress

  이 step 에 권장 gate 없음 (문서 작성/스펙 단계).

    DB Isolation mode: schema
    환경변수:
      DATABASE_SCHEMA=phase_1_feature_auth
    Setup commands:
      $ psql "$DATABASE_URL" -c 'CREATE SCHEMA IF NOT EXISTS phase_1_feature_auth;'
    Teardown commands:
      $ psql "$DATABASE_URL" -c 'DROP SCHEMA IF EXISTS phase_1_feature_auth CASCADE;'

  Lock 획득: pid=12345, session=host-12345

  step 작업이 끝나면:
    /harness step-complete 1-feature-auth [--summary "<한 줄 요약>"]
```

이 출력에서 사용자가 인지·실행해야 하는 것:
- Setup commands 가 있으면 **사용자가 직접 실행**. harness 는 안내만.
- step 의 산출물 (spec.md 등) 을 작성.
- 권장 gate 가 있는 step 이면 그 명령들을 통과시킨 뒤 step-complete.

step 끝나면:
```
$ /harness step-complete 1-feature-auth --summary "FR-001~003 spec 작성"

  ✓ step 'spec' completed.
  → 다음 step: design
    /harness run 1-feature-auth  (다음 step 진입)
```

마지막 step (`accept`) 까지 끝나면:
```
$ /harness step-complete 1-feature-auth --summary "E2E pass"

  ✓ step 'accept' completed.
  ✓ 모든 step 완료. phase 종료 준비됨.
    /harness phase-complete 1-feature-auth
```

phase-complete 호출:
```
$ /harness phase-complete 1-feature-auth

  ✓ phase '1-feature-auth' completed at 2026-05-12T00:21:44+0900
  ✓ lock 해제됨.

  DB 격리 teardown 명령 (필요 시 직접 실행):
    $ psql "$DATABASE_URL" -c 'DROP SCHEMA IF EXISTS phase_1_feature_auth CASCADE;'
```

### 여러 phase 가 병렬 진행 가능할 때

`/harness next --parallel` 출력 예:

```
  진행 가능 phase 2개 — 병렬 worktree 분리 가능.

    • 2-billing                       feature    (deps: 1-auth)
    • 3-profile                       feature    (deps: 1-auth)

  옵션:
    (A) 모두 현재 worktree에서 순차 진행
    (B) 일부/전부를 별도 worktree로 분리해서 병렬 진행
```

(B) 선택 시:

```bash
python3 -m fullstack_harness.harness worktree-plan 2-billing 3-profile
```

출력된 `git worktree add ...` 명령을 직접 실행 → 각 worktree 에서 새 Claude Code 세션 띄움 → 그 세션에서 `/harness run <phase>`.

> **주의**: 한 세션에서 cwd 만 바꿔 다른 worktree 로 가지 말 것. 컨텍스트가 섞여 phase 산출물 품질이 떨어진다. **반드시 새 세션을 띄울 것.**

### phase 작업 완료 후

- 해당 worktree 에서 `/harness phase-complete <phase>`.
- PR 생성.
- main 에 merge.
- (모든 feature phase 완료 시) `/harness merge-gate` 로 모든 브랜치가 merge 됐는지 검증.
- acceptance phase 진행.

### blocked / error 발생 시

- harness 가 자동 진행 제안을 멈춤.
- 사용자가 phase 의 `index.json` 에서 `blocked_reason` / `error_message` 확인.
- 원인 해결 후 status 를 `pending` 으로 되돌리고 다시 `/harness`.

### Lock 문제

- 같은 worktree 안에서 step 사이 lock 자동 인수됨 (Bash spawn 마다 새 pid 임).
- 다른 worktree 가 잡은 lock 은 `release-lock --force` 또는 그쪽 종료 대기.

```bash
python3 -m fullstack_harness.harness release-lock <phase> [--force]
```

## DB 격리 (`worktree.db_isolation`)

세 가지 모드:

| 모드 | 동작 | 필요 설정 |
|---|---|---|
| `none` | 격리 안 함. 모든 worktree 가 같은 DB 공유. | 없음 |
| `schema` | 단일 DB 안에서 worktree 별 schema. | `commands.create_schema`, `commands.drop_schema`. `${SCHEMA}` 변수 사용 가능. |
| `compose` | worktree 별 docker-compose stack. | `worktree.compose_template` 가 가리키는 yml. `${PHASE}`, `${PORT_OFFSET}`, `${PROJECT_NAME}` 등 변수 치환. |

**harness 는 명령을 실행하지 않는다 — 사용자에게 plan 만 안내**한다. 자동 실행은 v0.3 이후.

## Tech-stack Adapter

`harness.json.stack.framework` + `stack.db` 가 빌트인 어댑터와 매칭되면 자동 선택:

| 어댑터 | 매칭 조건 |
|---|---|
| `next_supabase` | framework ∈ {next, nextjs} AND db == supabase |
| `vue_firebase` | framework ∈ {vue, vuejs, nuxt} AND db ∈ {firebase, firestore} |
| `_default` | 위 모두 미스 시 fallback (no-op) |

매칭된 adapter 가 제공하는 것:
- `commands_defaults()`: `harness.json.commands` 에 비어 있는 키의 기본값.
- `step_gates()`: V-Model step 별 권장 gate 명령 키 목록 (예: `implement` → `["typecheck", "test_unit"]`).

사용자 어댑터를 추가하려면 `<target-project>/.harness/adapters/<name>.py` 작성:

```python
# .harness/adapters/svelte_drizzle.py
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

```
python3 -m fullstack_harness.harness [--target <path>] <subcommand>

서브커맨드:
  status                       전체 상태 출력
  next [--parallel]            다음 phase 안내 (--parallel: 병렬 후보까지)
  validate                     discovery 충실도 검사
  discovery-complete           discovery_status 를 completed 로 마킹
  worktree-plan <phase>...     선택 phase 들의 worktree 명령 + 새 세션 안내
  merge-gate                   feature 브랜치 main merge 검증
  set-deps [--json-file <p>]   JSON 입력으로 depends_on 일괄 패치 (백업 + DAG 재검증)
  run <phase>                  phase 의 현재/지정 step 진입 (v0.2)
    [--step <name>]            특정 step 으로 진입
    [--force-stale-lock]       lock 강제 인수
  step-complete <phase>        현재 in_progress step 완료 마킹 (v0.2)
    [--summary "..."]
  phase-complete <phase>       phase 자체를 completed 로 마킹 + lock 해제 (v0.2)
  release-lock <phase>         lock 수동 해제 (v0.2)
    [--force]
```

`--target` 생략 시 cwd 또는 상위 디렉토리에서 `harness.json` 검색.

## 의존성 inference 흐름 (v0.1.1+)

`depends_on` 을 phase 마다 손으로 채우기 번거로우면 `/harness-analyze-deps` 슬래시 명령 사용:

1. Claude Code 가 각 phase 의 `spec.md` / `design.md` 를 읽음.
2. phase 간 인용·참조 신호로 의존성 추론.
3. 사용자에게 추론 결과를 표로 보여주고 컨펌 요청.
4. 컨펌되면 임시 JSON 작성 → `set-deps` 호출.
5. `set-deps` 는 백업 → 패치 → DAG 재검증 (cycle 등 발견 시 자동 롤백).

수동으로 직접 호출하고 싶으면:

```bash
echo '{"2-billing": ["1-auth"], "3-profile": ["1-auth"], "99-accept": "all_features"}' \
  | python3 -m fullstack_harness.harness set-deps
```

## 한계 (v0.2.0)

- **Gate 자동 실행 안 함**: `run` 이 권장 gate 명령을 출력하지만 실행은 사용자가. v0.3 에서 `--auto-advance` 옵션 검토.
- **DB 격리 setup 자동 실행 안 함**: plan 만 출력. 사용자가 컨펌 후 직접 실행. compose 모드는 yml 만 자동 생성.
- **Inference 정확도**: spec.md 가 충실하지 않으면 추론도 빈약. 컨펌 단계에서 사용자가 보정해야 함.
- **Worktree 자동 spawn 안 함**: 명령 안내만, 사용자가 git worktree add 실행.
