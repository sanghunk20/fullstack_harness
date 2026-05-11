---
description: phase spec.md / design.md 를 읽고 phase 간 의존성을 추론한 뒤, 사용자 컨펌 후 phases/index.json 의 depends_on 을 일괄 패치한다.
argument-hint: (인자 없음 — 모든 phase 분석)
---

# /harness-analyze-deps — 의존성 추론 + 컨펌 + 적용

이 슬래시 명령은 LLM 추론(여기서 너) + 사용자 컨펌 + Python harness 패치를 한 흐름으로 묶는다.

## 실행 순서

### Step 1. phase 목록 로드

Bash 로 다음 명령을 실행, JSON 으로 phase 목록 확인:

```
python3 -m fullstack_harness.harness status
```

출력에서 phase 들의 dir, kind, 현재 depends_on (있다면) 을 인지한다.

### Step 2. 각 phase 의 spec.md / design.md 읽기

`phases/<phase>/spec.md` 가 있으면 Read, 없으면 `design.md` 시도. 둘 다 없으면 해당 phase 는 추론 보류 (`<unknown>` 표시).

각 spec.md 에서 다음 신호를 찾는다:
- 다른 phase 의 entity / table / API 를 인용 (예: "1-feature-auth 의 user 테이블 사용")
- 다른 phase 의 FR-ID 인용
- "X 가 완료된 후" / "X 를 전제로" 같은 문장
- 다른 phase 의 컴포넌트 / 모듈 이름 import

### Step 3. 의존성 추론

각 phase 에 대해:
- `kind: "infra"` — 보통 의존성 없음 (`[]`). 단 spec.md 에서 명시적으로 다른 phase 인용 시 그대로.
- `kind: "feature"` — spec.md 분석으로 의존하는 phase dir 목록 산출.
- `kind: "acceptance"` — 거의 항상 `"all_features"` (모든 feature phase 의존). spec.md 에서 명시적으로 일부만 인용하면 그 목록을.

추론은 보수적으로. **확실하지 않은 의존성은 후보로만 표시하고, 강한 단정은 피한다.**

### Step 4. 결과 표 제시 + 사용자 컨펌

다음 형식으로 사용자에게 보여준다:

```
| phase           | 현재 deps   | 추론 deps      | 근거                                |
|-----------------|-------------|----------------|-------------------------------------|
| 0-bootstrap     | []          | []             | infra phase, 의존성 없음              |
| 1-auth          | []          | []             | spec.md 에 외부 phase 인용 없음        |
| 2-billing       | (없음)      | [1-auth]       | spec.md L23: "인증된 user 의 결제"    |
| 3-profile       | (없음)      | [1-auth]       | spec.md L15: "1-auth user 테이블 참조" |
| 99-accept       | (없음)      | all_features   | acceptance phase                     |
```

그 다음 사용자에게 확인 질문 1줄:

> 위 의존성을 적용할까요? (y / n / 수정)

- `y` → Step 5 로.
- `n` → 중단. "변경 없이 종료합니다." 출력.
- `수정` → 사용자가 수정 사항을 말하면 표를 갱신해서 다시 컨펌 받음.

### Step 5. 임시 JSON 작성 + Python 호출

사용자가 `y` 하면:

1. 임시 파일 작성 (Write 도구): `/tmp/fsh-deps-<timestamp>.json`
2. 내용은 추론 결과를 다음 형식으로:
   ```json
   {
     "<phase_dir>": ["<dep1>", ...] | "all_features",
     ...
   }
   ```
3. **변경된 phase 만** 포함 (기존 deps 와 동일한 phase 는 생략 — set-deps 가 idempotent 하지만 표 가독성 위함).
4. Bash 로 호출:
   ```
   python3 -m fullstack_harness.harness set-deps --json-file /tmp/fsh-deps-<timestamp>.json
   ```
5. 출력 그대로 사용자에게 보여준다.
6. 임시 파일은 그대로 둔다 (set-deps 의 백업과 별개로, 추론 결과 추적용).

### Step 6. 사후 확인

Bash 로 `python3 -m fullstack_harness.harness status` 다시 실행. 출력에 deps 표시가 정확히 반영됐는지 사용자가 확인할 수 있도록 보여준다.

## 안티 패턴

- ❌ 사용자 컨펌 없이 set-deps 호출. **무조건 Step 4 컨펌 후에만 Step 5.**
- ❌ spec.md 가 없는 phase 의 의존성을 추측으로 채움 (보수적으로 `<unknown>` 표시 후 사용자에게 묻기).
- ❌ Python set-deps 출력을 임의 요약. 그대로 보여줄 것.
- ❌ phases/index.json 을 Edit 도구로 직접 수정. **반드시 set-deps 서브커맨드 경유** (백업 + DAG 재검증을 위해).
- ❌ 한 phase 가 자기 자신을 의존하도록 추론.
- ❌ cycle 가능성 무시. 추론 단계에서 명백한 cycle 이 보이면 사용자에게 먼저 알린다.

## 예외 처리

- spec.md / design.md 둘 다 없는 phase → 표에 `<no spec>` 표시 + "이 phase 는 사용자가 수동으로 deps 를 명시해주세요" 안내.
- set-deps 가 DAG 검증으로 실패하면 (cycle 등) → 자동 롤백되었음을 알리고, 사용자에게 어떤 phase 가 문제인지 보여준 뒤 추론 재시도 또는 중단.
- harness.json / phases/index.json 없으면 → "먼저 harness 초기화 필요" 안내.
