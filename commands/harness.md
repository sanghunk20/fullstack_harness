---
description: 프로젝트 상태 점검 + DAG 기반 다음 단계 dispatcher. 인자 없이 호출하면 status → 병렬 후보 분석 → 사용자 확인.
argument-hint: [status | next [--parallel] | validate | worktree-plan <phase>... | merge-gate]
---

# /harness — fullstack_harness dispatcher

이 슬래시 명령은 `fullstack_harness/scripts/harness.py` 를 호출하는 얇은 wrapper다. 실제 로직은 Python harness 가 담당, 이 파일은 사용자 친화적인 흐름을 안내한다.

대상 프로젝트 root 에 `harness.json` 이 있어야 한다. 없으면 `fullstack_harness/templates/harness.json.template` 를 복사해서 시작.

## 인자 파싱

`$ARGUMENTS` 의 첫 단어로 분기.

### 인자 없음 (기본 모드)

가장 자주 쓰이는 흐름:

1. Bash 로 `python3 -m fullstack_harness.harness status` 실행. 출력 그대로 보여준다.
2. 출력에 `blocked` / `error` phase 가 보이거나 discovery 미완이면:
   - **자동 진행 제안하지 말 것.** "위 이슈를 해결한 뒤 다시 `/harness` 를 호출하세요." 한 줄 안내 후 종료.
3. 그렇지 않으면 Bash 로 `python3 -m fullstack_harness.harness next --parallel` 실행. 출력 그대로 보여준다.
4. **출력에 병렬 후보가 2개 이상**이면:
   - 사용자에게 묻기: "병렬 worktree 로 분리할까요? (A) 순차 / (B) 병렬"
   - (A) → 첫 phase 만 진행 안내. 종료.
   - (B) → 어떤 phase 를 worktree 로 뺄지 사용자에게 묻고, 선택된 phase 로 `worktree-plan <phase>...` 호출.
5. 후보가 1개면 그 phase 진행 안내 후 종료.
6. 후보가 0개면 "모두 완료" 안내.

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

### 그 외
"알 수 없는 서브커맨드: `<arg>`. 사용 가능: status, next, validate, worktree-plan, merge-gate, (인자 없음)."

## 안티 패턴

- ❌ 사용자 확인 없이 worktree 자동 생성 (`git worktree add` 직접 실행 금지)
- ❌ blocked / error 상태에서 자동 진행 제안
- ❌ Python harness 출력 임의 요약·재해석 (그대로 보여줄 것)
- ❌ discovery 미완인데 `/req-eng` 같은 discovery 명령을 임의 호출 (안내만, 실행은 사용자가)
- ❌ 한 세션에서 cwd 만 바꿔 다른 worktree 작업 (컨텍스트 오염 — 반드시 새 세션)
