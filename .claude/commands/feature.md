---
description: 새 phase (feature / infra / acceptance) 추가. phases/index.json + phases/<dir>/index.json 자동 생성, DAG 재검증, 백업까지. dutytable 의 /feature 와 동일 역할.
argument-hint: [<phase-dir>]
---

# /feature — 새 phase 추가

이 슬래시 명령은 `python3 -m fullstack_harness.harness add-phase` 를 호출하는 친화 wrapper 입니다. **새 feature / infra / acceptance phase** 를 추가합니다.

**호출 시점**: /stack-select 이후 언제든. 프로젝트 초기 phase 셋업 또는 중간에 새 기능을 추가할 때.

## 사전 점검

Bash:
```
test -f harness.json && python3 -m fullstack_harness.harness setup-status || echo "MISSING harness.json"
```

- MISSING → "먼저 /setup 을 실행하세요."
- `next=req-eng` / `next=ui-guide` / `next=stack-select` → 그 단계를 먼저 안내. 강행 가능하지만 비권장.
- `next=harness` → 정상.

## Step 1. phase 정보 인터뷰

사용자에게 묻기 (한 번에 하나씩):

1. **Phase 디렉토리 이름** — `$ARGUMENTS` 첫 단어가 있으면 그걸 default 로 제안. 영숫자 + `-`·`_` 만.
   - 컨벤션: feature 는 `N-feature-<name>` (예: `1-feature-auth`, `2-feature-billing`).
   - infra 는 `0-bootstrap`, `0-infra-<topic>` 같은 prefix.
   - acceptance 는 `99-acceptance`.

2. **Kind** — `feature` / `infra` / `acceptance` 중 하나.
   - dir 이름이 `0-...` 으로 시작하면 infra 추정, `99-...` 면 acceptance 추정, 나머지는 feature 추정. 사용자에게 확인.

3. **한 줄 설명** — phase 의 의도. 예: "사용자 인증 (이메일 + 소셜)".

4. **V-Model 여부** — kind 가 feature 면 default `true`, infra / acceptance 면 default `false`. 사용자 변경 가능.

5. **depends_on** — 어떤 phase 가 먼저 완료돼야 하는가?
   - 현재 phases/index.json 의 phase 목록을 Bash 로 조회해 보여주기:
     ```
     python3 -m fullstack_harness.harness status
     ```
   - 사용자가 의존 phase dir 들을 답함. acceptance 면 `all_features` 가 default.
   - 모르겠다면 `[]` 로 두고 나중에 `/harness-analyze-deps` 로 LLM 추론 시키도록 안내.

6. **insert_before** (선택) — 이 phase 앞에 삽입할 phase dir 이 있는가? 미지정 시 acceptance 직전 (있으면) 또는 끝.

## Step 2. 결과 미리보기 + 컨펌

다음 형식으로:

```
새 phase:
  dir:         1-feature-auth
  kind:        feature
  description: 사용자 인증
  v_model:     true
  depends_on:  [0-bootstrap]
  insert_before: (없음 → acceptance 직전)
```

> "이대로 진행할까요? (y/n)"

n → 종료. y → Step 3.

## Step 3. Python 호출

Bash:
```
python3 -m fullstack_harness.harness add-phase <dir> \
  --kind <kind> \
  --description "<desc>" \
  --v-model <true|false> \
  --depends-on <dep1> <dep2>   # 또는: --depends-on all_features
  [--insert-before <dir>]
```

> depends_on 이 비어 있으면 `--depends-on` 자체를 생략.
> 'all_features' 패턴이면 `--depends-on all_features` (단일 인자).

출력 그대로 사용자에게 보여줍니다 (백업 경로 / 새 phase index 경로 포함).

## Step 4. 후속 안내

```
✓ phase '<dir>' 추가 완료.

다음 액션 옵션:
  • spec.md 작성 시작: phases/<dir>/spec.md 를 새로 만들고 FR/NFR 인용
  • 의존성 추론: /harness-analyze-deps  (다른 phase 의 spec 도 같이 분석)
  • 진행: /harness run <dir>           (이 phase 의 step 1 시작)
```

## 추가 사용 시나리오

### 시나리오 A: 프로젝트 초기 phase 셋업

/stack-select 직후 `/feature` 를 여러 번 호출해서 초기 phase 들을 빠르게 등록:

```
/feature 0-bootstrap
/feature 1-feature-auth
/feature 2-feature-notes
/feature 99-acceptance
```

각 호출마다 동일 인터뷰 흐름.

### 시나리오 B: 프로젝트 중간 신규 기능 추가

이미 phase 진행 중인데 새 기능 (예: 결제) 이 추가됐을 때:

```
/feature 3-feature-billing
```

depends_on 으로 `1-feature-auth` 등 명시. 기존 phase 의 status 는 건드리지 않음.

## 안티 패턴

- ❌ phases/index.json 을 Edit 도구로 직접 수정. **반드시 add-phase subcommand 경유** (백업 + DAG 재검증).
- ❌ depends_on 을 LLM 이 임의 추측. **사용자가 답하지 않은 경우 `[]` 로 두고 /harness-analyze-deps 안내**.
- ❌ 한 번에 여러 phase 를 add-phase 한 줄로 추가하려고 시도. **add-phase 는 한 번에 한 phase**.
- ❌ V-Model 결정을 LLM 이 단독 결정. kind 기본값을 따르되 사용자에게 명시 확인.
- ❌ insert_before 를 임의 지정해서 순서를 망치기. 미지정 시 acceptance 직전이 안전한 default.
- ❌ kind 가 acceptance 인데 depends_on 을 `[]` 로 두기. acceptance 는 항상 `all_features` 가 디폴트.
