---
description: fullstack-harness를 새 프로젝트로 초기화. 프로젝트 이름·한 줄 설명만 받고 harness.json + phases/index.json을 생성. (요구사항 인터뷰는 /req-eng 가 담당.)
argument-hint: (인자 없음)
---

# /setup — 프로젝트 초기 세팅

이 슬래시 명령은 fullstack-harness 를 **새 프로젝트로 변환**합니다. 깊은 요구사항 인터뷰는 하지 않습니다 — 그건 `/req-eng` 의 역할.

## 사용 흐름

```
git clone https://github.com/sanghunk20/fullstack_harness.git my-new-app
cd my-new-app
claude
> /setup
```

## Step 1. 사전 점검

Bash 로 다음을 확인:

```
ls -la harness.json 2>&1 || echo "harness.json 없음 (정상)"
```

- `harness.json` 이 이미 있고 `"project": "<PROJECT_NAME>"` 같은 플레이스홀더가 **남아 있지 않다면** → 이미 설정된 프로젝트. 사용자에게 묻기: "기존 설정을 덮어쓸까요? (y/N)"
- `harness.json` 이 없거나 플레이스홀더가 남아 있으면 → 진행.

## Step 2. 프로젝트 메타 인터뷰 (가볍게)

**오직 두 가지만 물어봅니다.** 깊은 요구사항은 /req-eng 가 합니다.

1. **프로젝트 이름** (영문 short slug 권장, 예: `my-saas`, `notes-app`)
2. **한 줄 설명** (예: "팀 단위 노트 공유 SaaS")

선택적 (강제 X):
3. 프로젝트 archetype 힌트 — `web` / `mobile` / `desktop` / `cli` / 모르겠음. 이건 /stack-select 가 추후 참고할 메모 용. 모르면 비워둠.

## Step 3. harness.json 작성

`templates/harness.json.template` 을 베이스로 읽어 (Read), 다음 필드를 채운 뒤 프로젝트 root 에 `harness.json` 으로 저장 (Write):

- `project`: 사용자가 답한 이름
- `description`: 사용자가 답한 한 줄 설명
- `stack`: 명시적으로 비워둠 (placeholder 유지) — /stack-select 가 채울 자리
  ```json
  "stack": {
    "language": null,
    "framework": null,
    "db": null,
    "deploy": null,
    "adapter": null,
    "archetype_hint": "<Step 2 의 archetype 답이 있으면 기록, 없으면 null>"
  }
  ```
- `commands`: 전부 빈 문자열로 둠 — /stack-select 가 stack 결정 시 채움
- `discovery`: 템플릿 기본값 유지 (`/req-eng` 가 호출될 흐름)
- `worktree.db_isolation`: `"none"` 기본값 — /stack-select 가 stack 따라 업그레이드 권장
- `v_model`: 기본값 유지

## Step 4. phases/index.json 작성

`templates/phases_index.json.template` 그대로 복사해 `phases/index.json` 생성 (`mkdir -p phases` 먼저). 단 `discovery_status: "pending"` 인지 확인.

## Step 5. phase skeleton

`0-bootstrap` 과 `99-acceptance` phase 디렉토리만 만듭니다. feature phase 는 /req-eng / /stack-select 이후 사용자가 추가:

```bash
mkdir -p phases/0-bootstrap phases/99-acceptance docs
```

- `phases/0-bootstrap/index.json`: `templates/phase_index_linear.json.template` 복사 + `name`: "0-bootstrap" 으로 치환. status pending.
- `phases/99-acceptance/index.json`: 동일하게 linear template 복사 + `name`: "99-acceptance".

## Step 6. 클린업 (선택)

사용자에게 한 번 묻기:

> "harness 의 examples/ 디렉토리와 README/AGENTS 같은 harness 메타 파일을 지울까요? (Y/n)"

- Y → 다음을 삭제 / 정리:
  - `examples/` 디렉토리 (fixture 들. 사용자 프로젝트에는 불필요)
  - `templates/` 디렉토리 (이미 harness.json / phases/index.json 으로 복사됨)
- N → 그대로 둠 (참고용).

> **삭제는 Bash 의 `rm -rf` 로 명시적으로 path 만 지운다.** `*.md` 와이드카드 금지.

## Step 7. .gitignore 보강

대상 프로젝트의 `.gitignore` 에 다음 항목이 없으면 append (이미 있으면 skip):

```
# fullstack_harness runtime
.worktrees/
phases/*/.lock
```

이 항목이 이미 있는 경우 변경 없음.

## Step 8. 완료 안내

다음 메시지를 출력하고 종료:

```
✓ Setup 완료.

  project:     <name>
  description: <desc>
  stack:       (미설정 — /stack-select 에서 선택)

다음 단계:
  /harness       — 상태 확인 + 다음 액션 안내
                   현재 상태: discovery 미완 → /req-eng 호출 안내가 떠야 함
```

## 안티 패턴

- ❌ /setup 단계에서 사용자에게 frontend/backend/DB 를 물어보지 말 것. 그건 /stack-select 의 일.
- ❌ /setup 단계에서 FR/NFR/CON 인터뷰 시도 금지. 그건 /req-eng 의 일.
- ❌ 사용자 컨펌 없이 examples/ / templates/ 삭제.
- ❌ harness.json 의 `commands.*` 를 임의로 채우지 말 것 (/stack-select 가 stack 결정 후 채움).
- ❌ `git init` / `git config` 같은 git 메타 명령 임의 실행. 사용자가 결정.
