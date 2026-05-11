---
description: 프로젝트의 기능 요구사항(FR) / 품질 요구사항(NFR) / 제약사항(CON) 을 인터뷰 형식으로 도출하고 docs/*.md 에 표 형식으로 기록. 기존 docs 가 있으면 revision 모드 (추가/수정/삭제) 지원.
argument-hint: (인자 없음)
---

# /req-eng — 요구사항 엔지니어링 인터뷰

이 슬래시 명령은 프로젝트의 **사용자 요구사항·품질 요구사항·제약사항** 을 사용자와의 대화로 추출하고, `docs/REQUIREMENTS.md` / `docs/QUALITY.md` / `docs/CONSTRAINTS.md` 에 표 형식으로 저장합니다.

**호출 시점**: `/setup` 직후, `/harness` 가 안내해주는 단계. 프로젝트 중간에 재호출도 가능 (revision 모드).

## 사전 점검

Bash:
```
test -f harness.json && echo "harness.json 있음" || echo "MISSING"
```

- MISSING → "먼저 /setup 을 실행하세요." 종료.
- 있으면 진행.

## Step 0. 모드 판정

다음 3 파일 중 하나라도 비어 있지 않게 존재 → **revision 모드**.
- `docs/REQUIREMENTS.md`
- `docs/QUALITY.md`
- `docs/CONSTRAINTS.md`

모두 없거나 비어 있음 → **신규 모드**.

### Revision 모드 진입 시

`python3 -m fullstack_harness.harness status` 출력에서 FR/NFR/CON 카운트를 보고 사용자에게:

```
현재 요구사항 상태:
  docs/REQUIREMENTS.md   FR-NNN 개수: N
  docs/QUALITY.md        NFR-NNN 개수: N
  docs/CONSTRAINTS.md    CON-NNN 개수: N

어떻게 진행할까요?
  (1) 보기만        — 현재 내용 출력 후 종료
  (2) 항목 추가     — 카테고리별로 신규 항목 인터뷰
  (3) 항목 수정     — ID 골라서 갱신
  (4) 항목 삭제     — ID 골라서 제거 (의존하는 phase 가 있을 수 있음 → 사용자 확인)
  (5) 전체 재작성   — 백업 후 처음부터 (위험)
```

변경 흐름:
- Read 로 해당 파일 로드.
- 변경 전: `cp docs/<FILE>.md docs/<FILE>.md.bak.<timestamp>`.
- 변경 후: Write 로 저장.
- Bash 로 `python3 -m fullstack_harness.harness discovery-reopen` → 작성·갱신 → `discovery-complete` 로 재마킹.

## Step 1. 컨텍스트 로드 (신규 / 추가 모드)

Read 로:
- `harness.json` — project 이름, description, archetype_hint
- (revision 모드면) 기존 docs/REQUIREMENTS.md / QUALITY.md / CONSTRAINTS.md

description / archetype_hint 를 인터뷰 첫 메시지에 명시해서 사용자가 컨텍스트를 인지하게 함.

## Step 2. 인터뷰 — 기능 요구사항 (FR)

다음 질문들을 **한 번에 하나씩** 사용자에게 묻습니다. 답마다 paraphrase 로 확인.

질문 예시:
1. 핵심 사용자(primary user persona) 는 누구입니까? (예: 1인 프리랜서, 5~10인 팀 리더, 일반 소비자)
2. 가장 중요한 사용 시나리오 3개를 알려주세요. (예: "로그인 후 자기 노트를 작성", "동료 초대해서 노트 공유", ...)
3. 그 외 부수적인 기능들 (검색, 알림, 통계, 결제 등) 중 v1 에 꼭 필요한 것은?
4. 사용자가 절대 못 하게 해야 하는 일은? (예: 다른 사용자의 노트 수정)

**보수적 모드.** 사용자가 모르겠다고 하면 강제로 끌어내지 말고 "추가 후 사용자가 채울 placeholder" 로 두는 것을 제안.

각 응답에서 FR 항목들을 추출. ID 는 `FR-001`, `FR-002` ... 순차. (revision 모드 추가 시 기존 max ID + 1 부터.)

## Step 3. 인터뷰 — 품질 요구사항 (NFR)

질문 예시:
1. 응답 속도 / 가용성 기준이 있다면? (예: "로그인 1초 내", "월 99% uptime")
2. 보안 요구사항? (예: HTTPS 필수, 비밀번호 해시, MFA, 감사 로그)
3. 접근성 / 국제화 / 모바일 대응?
4. 운영 / 모니터링 요구사항?

ID 는 `NFR-001`, ...

## Step 4. 인터뷰 — 제약사항 (CON)

질문 예시:
1. 예산 제약? (예: "월 호스팅 비용 $20 이하", "유료 SaaS 사용 금지")
2. 팀 보유 기술 / 학습 부담 제한? (예: "TypeScript 만 가능", "Rust 배우기 싫음")
3. 법적·규제 (GDPR, KISA, HIPAA 등)?
4. 일정 제약? 출시 마감?
5. 호스팅 / 인프라 환경 제약? (예: "온프레미스만", "Vercel 외에는 가능", "AWS 만 가능")
6. 의존하면 안 되는 기술? (예: "Java 백엔드 금지", "MongoDB 금지")

ID 는 `CON-001`, ...

> 이 섹션은 /stack-select 가 적극 참고합니다. **꼼꼼히 받아둘수록 스택 추천 품질이 올라갑니다.**

## Step 5. 결과 표 정리 + 컨펌

각 카테고리별로 markdown 표 작성 후 사용자에게 보여줍니다:

```markdown
| ID | 설명 | 우선순위 |
|---|---|---|
| FR-001 | ... | P0 |
| FR-002 | ... | P1 |
| ... |
```

우선순위는 P0 (필수) / P1 (중요) / P2 (선택) 정도로 구분 — 사용자에게 묻기.

> "위 정리가 정확한가요? (y / 수정)"

- 수정 → 항목 갱신 후 재컨펌.
- y → Step 6.

## Step 6. 파일 작성

revision 모드면 변경 전 백업 (`cp docs/X.md docs/X.md.bak.<timestamp>`) 후 Write. 신규 모드면 바로 Write.

### `docs/REQUIREMENTS.md`
```markdown
# 사용자 요구사항 (Functional Requirements)

| ID | 설명 | 우선순위 |
|---|---|---|
| FR-001 | ... | P0 |
| ... |
```

### `docs/QUALITY.md`
```markdown
# 품질 요구사항 (Non-Functional Requirements)

| ID | 설명 | 측정 기준 |
|---|---|---|
| NFR-001 | ... | ... |
| ... |
```

### `docs/CONSTRAINTS.md`
```markdown
# 제약사항 (Constraints)

| ID | 설명 | 카테고리 |
|---|---|---|
| CON-001 | ... | budget |
| CON-002 | ... | tech |
| ... |
```

> 카테고리는 `budget` / `tech` / `legal` / `schedule` / `infra` / `team` 정도로 일관되게 사용.

## Step 7. discovery 마킹

신규 모드: Bash `python3 -m fullstack_harness.harness discovery-complete`.

Revision 모드:
1. `python3 -m fullstack_harness.harness discovery-reopen` (이미 호출했으면 skip)
2. 변경 작성
3. `python3 -m fullstack_harness.harness discovery-complete`

성공 (exit 0) → Step 8.
실패 (validate 미통과 — placeholder 가 남았거나 표가 비었거나) → 사용자에게 어떤 항목이 부족한지 알리고 보강.

## Step 8. 다음 단계 안내

- 신규 모드: "다음 단계: `/ui-guide` — design / UI 가이드 인터뷰."
- Revision 모드 (mid-project): "변경이 기존 phase 산출물에 영향을 줄 수 있습니다. 영향 받는 phase 의 spec.md / design.md / test 코드를 검토하세요. 그 후 `/harness` 로 계속."

## 안티 패턴

- ❌ 모든 카테고리 질문을 한 번에 쏟아내기. **하나씩, 답 받고 paraphrase 확인.**
- ❌ 사용자가 답하지 않은 항목을 LLM 이 추측해서 추가. **모르면 placeholder + 사용자 확인 필요 표시.**
- ❌ 표를 markdown 외 형식으로 작성. **validation.py 가 markdown 표 첫 컬럼의 `FR-NNN` 만 카운트** — 이 규약 깨면 discovery-complete 실패.
- ❌ ID 가 표가 아닌 본문 산문에 등장 — 카운트 안 됨. 표 안에 있어야 인식됨.
- ❌ Revision 모드에서 백업 없이 덮어쓰기.
- ❌ Revision 모드에서 ID 재사용 (예: FR-001 을 삭제 후 다른 FR 을 FR-001 로 다시 부여). 삭제된 ID 는 그대로 두고 새 항목은 max+1 부터.
- ❌ /stack-select 의 영역인 frontend/backend/DB 추천을 여기서 시도. 여기서는 **제약 ("Java 금지")** 만 받고 추천은 다음 단계.
