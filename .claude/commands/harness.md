---
description: 프로젝트 상태 점검 + setup chain 게이트 + DAG 기반 phase dispatcher + phase 실행 orchestrator. 인자 없이 호출하면 자동으로 다음 액션 안내.
argument-hint: [status | next [--parallel] | validate | worktree-plan <phase>... | merge-gate | run <phase> [--step name] [--force-stale-lock] | step-complete <phase> [--summary "..."] | phase-complete <phase> | release-lock <phase> [--force]]
---

# /harness — fullstack_harness dispatcher

이 슬래시 명령은 `fullstack_harness.harness` 모듈을 호출하는 얇은 wrapper입니다. 실제 로직은 Python harness 가 담당. 이 파일은 사용자 친화적인 흐름 + setup chain 안내를 담당.

## 사전 점검

Bash:
```
test -f harness.json && echo "OK" || echo "MISSING"
```

- `MISSING` → "먼저 `/setup` 을 호출해서 프로젝트를 초기화하세요." 출력 후 종료.
- 있으면 → Setup chain 게이트로 진행.

## Setup Chain 게이트 (인자 없을 때, v0.2)

Bash:
```
python3 -m fullstack_harness.harness setup-status
```

출력 한 줄을 파싱: `discovery=<...>\tui_guide=<...>\tstack=<...>\tnext=<req-eng|ui-guide|stack-select|harness>`.

### `next=req-eng`

discovery 미완. 출력:

```
  ⏸ 요구사항 정의가 끝나지 않았습니다.

다음 단계:
  /req-eng    — 기능/품질/제약 요구사항을 인터뷰로 수집

(완료 후 /harness 를 다시 호출하면 다음 단계로 진행)
```

종료.

### `next=ui-guide`

discovery 는 끝났는데 UI 가이드 미완. 출력:

```
  ⏸ UI / UX 가이드가 아직 작성되지 않았습니다.

다음 단계:
  /ui-guide   — 디자인 톤·컬러·타이포·컴포넌트 컨벤션 인터뷰

(완료 후 /harness 를 다시 호출하면 다음 단계로 진행)
```

종료.

### `next=stack-select`

discovery + ui_guide 끝났는데 stack 미설정. 출력:

```
  ⏸ 기술 스택이 아직 선택되지 않았습니다.

다음 단계:
  /stack-select   — 요구사항·제약·UI 가이드 기반 frontend/backend/DB 추천 + 선택

(완료 후 /harness 를 다시 호출하면 phase 진행이 시작됩니다)
```

종료.

### `next=harness`

모든 디스커버리 + 스택 결정 완료. 아래 "인자 파싱" 으로 진행.

## 인자 파싱

`$ARGUMENTS` 의 첫 단어로 분기.

### 인자 없음 (기본 모드)

setup chain 게이트가 next=harness 일 때만 도달.

1. Bash 로 `python3 -m fullstack_harness.harness status` 실행. 출력 그대로 보여준다.
2. 출력에 `blocked` / `error` phase 가 보이면:
   - **자동 진행 제안하지 말 것.** "위 이슈를 해결한 뒤 다시 `/harness` 를 호출하세요." 한 줄 안내 후 종료.
3. phases 가 0 개면:
   - "phase 가 아직 없습니다. `/feature` 로 첫 phase 를 추가하세요." 안내 후 종료.
4. 그렇지 않으면 Bash 로 `python3 -m fullstack_harness.harness next --parallel` 실행. 출력 그대로 보여준다.
5. **출력에 병렬 후보가 2개 이상**이면:
   - 사용자에게 묻기: "병렬 worktree 로 분리할까요? (A) 순차 / (B) 병렬"
   - (A) → 첫 phase 만 진행 안내. 종료.
   - (B) → 어떤 phase 를 worktree 로 뺄지 사용자에게 묻고, 선택된 phase 로 `worktree-plan <phase>...` 호출.
6. 후보가 1개면 그 phase 진행 안내 후 종료.
7. 후보가 0개면 "모두 완료" 안내.

### `status`
Bash 로 `python3 -m fullstack_harness.harness status` 실행, 출력 그대로.

### `next` — `next --parallel` 가능
Bash 로 `python3 -m fullstack_harness.harness next [--parallel]` 실행, 출력 그대로.

### `validate`
Bash 로 `python3 -m fullstack_harness.harness validate` 실행. exit 0 이면 "✓ Discovery 완전", 1 이면 "✗ 보완 필요" 한 줄 추가.

### `worktree-plan <phase>...`
Bash 로 `python3 -m fullstack_harness.harness worktree-plan <phase>...` 실행. 출력 그대로.

> 실제 `git worktree add` 는 **harness 가 실행하지 않는다.** 사용자가 출력된 명령을 직접 복사해서 실행. 새 worktree 에서 새 Claude Code 세션을 띄워야 컨텍스트가 깨끗하다.

### `merge-gate`
Bash 로 `python3 -m fullstack_harness.harness merge-gate` 실행. acceptance phase 진입 전 모든 feature 브랜치 merge 검증.

### `run <phase> [--step <name>] [--force-stale-lock]` (v0.2)

Phase 의 현재 step (또는 명시한 step) 으로 진입. **orchestrator only** 모드:

1. Bash 로 `python3 -m fullstack_harness.harness run <phase>` 실행.
2. 출력에는 다음이 포함된다:
   - 현재 V-Model step + 짝 (예: `spec ↔ accept`)
   - 권장 gate command (`typecheck`, `test_unit` 등 — stack adapter 와 harness.json.commands 머지 결과)
   - DB 격리 plan (setup/teardown 명령). 자동 실행하지 않음 — 사용자가 직접.
   - Lock 정보.
3. harness 가 해당 step 의 status 를 `in_progress` 로 마킹.
4. 사용자는 step 작업 수행 → 끝나면 `/harness step-complete <phase>`.

> **자동 진행 안 함.** 같은 worktree 안에서 step 사이 lock 이 자동 인수되지만, 작업 자체는 LLM/사용자가 수행. gate command 도 사용자가 직접 실행.

### `step-complete <phase> [--summary "..."]` (v0.2)

현재 in_progress step 을 completed 로 마킹.

1. Bash 로 `python3 -m fullstack_harness.harness step-complete <phase> [--summary "..."]` 실행.
2. 출력은 다음 step 안내 또는 phase 완료 가능 메시지.
3. 다음 step 이 있으면 `/harness run <phase>` 로 진입.
4. 모든 step 완료 시 `/harness phase-complete <phase>`.

### `phase-complete <phase>` (v0.2)

모든 step 이 completed 인 phase 를 종료. lock 해제, DB 격리 teardown 명령 안내.

1. Bash 로 `python3 -m fullstack_harness.harness phase-complete <phase>` 실행.
2. 출력에 teardown 명령이 있으면 사용자에게 실행 여부 확인 후 안내. **자동 실행 안 함.**

### `release-lock <phase> [--force]` (v0.2)

phase lock 수동 해제. stale 한 lock 청소용. `--force` 는 살아있는 lock 도 해제 (다른 worktree 가 진짜 점유 중인 경우만 사용).

### 그 외
"알 수 없는 서브커맨드: `<arg>`. 사용 가능: status, next, validate, worktree-plan, merge-gate, run, step-complete, phase-complete, release-lock, (인자 없음)."

## 안티 패턴

- ❌ harness.json 이 없는데 status 부터 시도. **setup chain 게이트가 먼저.**
- ❌ discovery / ui_guide / stack 미완인데 /req-eng, /ui-guide, /stack-select 를 자동 호출. **사용자가 직접 입력하도록 안내만.**
- ❌ phases 가 비어 있는데 `next` / `run` 시도. /feature 로 phase 추가 안내.
- ❌ 사용자 확인 없이 worktree 자동 생성 (`git worktree add` 직접 실행 금지)
- ❌ blocked / error 상태에서 자동 진행 제안
- ❌ Python harness 출력 임의 요약·재해석 (그대로 보여줄 것)
- ❌ 한 세션에서 cwd 만 바꿔 다른 worktree 작업 (컨텍스트 오염 — 반드시 새 세션)
- ❌ `run` 출력에 나온 gate command (typecheck/test 등) 를 LLM 이 자동 실행. **사용자 동의 후 실행.**
- ❌ DB 격리 setup/teardown 명령을 LLM 이 임의 실행. 사용자 컨펌 필수.
