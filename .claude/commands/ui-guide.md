---
description: 디자인·UI·UX 가이드라인 인터뷰. /req-eng 다음 단계. 기존 docs/UI_GUIDE.md 가 있으면 revision 모드 (추가/수정/삭제) 지원.
argument-hint: (인자 없음)
---

# /ui-guide — UI / UX 가이드 인터뷰

이 슬래시 명령은 프로젝트의 **디자인 시스템·UI 컨벤션·UX 원칙** 을 사용자와의 대화로 추출하고 `docs/UI_GUIDE.md` 에 저장합니다.

**호출 시점**: `/req-eng` 완료 후, `/harness` 가 안내하는 단계. 프로젝트 중간에도 재호출 가능 (revision 모드).

## 사전 점검

Bash:
```
test -f harness.json && python3 -m fullstack_harness.harness setup-status || echo "MISSING harness.json"
```

- harness.json 없음 → "먼저 /setup 을 실행하세요." 종료.
- `discovery=pending` → "먼저 /req-eng 를 완료하세요." 종료.
- 아니면 진행.

## Step 0. 모드 판정

`docs/UI_GUIDE.md` 존재 + 비어 있지 않음 → **revision 모드**.
없거나 비어 있음 → **신규 모드**.

### Revision 모드 진입 시

사용자에게 묻기:

```
docs/UI_GUIDE.md 이 이미 존재합니다 (작성일: <ui_guide_completed_at>).

어떻게 진행할까요?
  (1) 보기만        — 현재 내용 출력 후 종료
  (2) 항목 추가     — 새 가이드 항목 인터뷰 후 append
  (3) 항목 수정     — 기존 항목 중 골라서 갱신
  (4) 항목 삭제     — 기존 항목 중 골라서 제거
  (5) 전체 재작성   — 처음부터 다시 (위험. 백업 후 진행)
```

- (1) → Read 로 보여주고 종료.
- (2)~(5) → 해당 흐름으로 진행. 변경 후엔 Bash 로 `python3 -m fullstack_harness.harness ui-guide-reopen` 호출해서 status 를 pending 으로 → 변경 작성 → `ui-guide-complete` 로 다시 마킹.

> 백업: 변경 전 `cp docs/UI_GUIDE.md docs/UI_GUIDE.md.bak.<timestamp>` 한 번.

## Step 1. 컨텍스트 로드 (신규 / 추가 모드)

Read:
- `harness.json` — description / archetype_hint
- `docs/REQUIREMENTS.md`, `docs/QUALITY.md`, `docs/CONSTRAINTS.md` — 디자인 관련 시그널 추출:
  - 접근성 NFR
  - 모바일/데스크톱 archetype
  - 브랜드·톤 제약

## Step 2. 인터뷰 — 한 번에 하나씩

다음 카테고리를 순서대로 물어봅니다. 답마다 paraphrase 로 확인.

### A. 디자인 톤 & 브랜드
1. 프로젝트의 톤(tone)은? (예: 미니멀, 따뜻함, 전문적, 친근함, 유쾌함)
2. 레퍼런스 사이트/앱이 있다면 1~3개. (없으면 skip)
3. 브랜드 컬러 결정됐다면? (primary / secondary / accent — HEX 또는 "TBD")

### B. 컬러 시스템
1. 다크모드 지원 여부? (yes / no / TBD)
2. 시맨틱 컬러 — success / warning / error / info 의 톤?
3. 텍스트 컬러 — primary / secondary / muted 단계 필요한가?

### C. 타이포그래피
1. 본문 폰트 결정됐나? (예: Inter, Pretendard, SF Pro, system-ui)
2. 헤딩 폰트가 별도인가? 동일한가?
3. 폰트 사이즈 스케일 — 사용할 단계 수 (예: xs / sm / base / lg / xl / 2xl / 3xl)?

### D. 간격 & 레이아웃
1. spacing scale (예: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64)?
2. 콘텐츠 max-width? (예: 1280px / 1440px / full)
3. 모바일 breakpoint? (예: 640 / 768 / 1024 / 1280)

### E. 컴포넌트 컨벤션
1. UI 라이브러리 / 디자인 시스템 사용 의향? (예: shadcn/ui, Radix, Headless UI, Material UI, Chakra, 자체 제작)
2. 아이콘 세트? (예: lucide, heroicons, phosphor, 자체)
3. 폼 UX — 인라인 에러 vs 토스트 vs 모달?
4. 로딩 상태 — skeleton vs spinner vs progress?
5. 모달 vs 사이드 패널 vs 전체 페이지 — 어떤 상황에 무엇?

### F. UX 원칙
1. 핵심 사용자 흐름은? (Onboarding / Daily use / Power user)
2. 단축키 / 키보드 네비게이션 우선순위?
3. 빈 상태(empty state) 처리 — 일러스트 / 텍스트 / CTA 조합?
4. 에러 상태 — 사용자 친화적 메시지 톤?
5. 권한 / 빈 데이터 / 권한 없음 상태의 표시?

### G. 접근성 (NFR 에서 시그널 받았으면 명시)
1. WCAG 준수 레벨? (AA / AAA / 미정)
2. 색상 대비 가이드?
3. 키보드 only 사용 시나리오 보장?

각 카테고리에서 사용자가 "TBD" / "모르겠음" 답해도 OK — placeholder 로 기록.

## Step 3. 결과 정리 + 컨펌

다음 형식으로 사용자에게 표시:

```markdown
# UI / UX Guide

## Tone & Brand
- 톤: ...
- 레퍼런스: ...
- 브랜드 컬러: primary `#xxx`, secondary `#xxx`

## Color System
| Token | Light | Dark |
|---|---|---|
| bg-primary | ... | ... |
| ...

## Typography
- body: ...
- heading: ...
- scale: xs / sm / ...

## Spacing & Layout
- spacing scale: ...
- max-width: ...
- breakpoints: ...

## Components
- UI library: ...
- icons: ...
- form errors: ...
- loading: ...

## UX Principles
- onboarding: ...
- empty state: ...
- error state: ...

## Accessibility
- WCAG: ...
- contrast: ...
```

사용자에게:

> "위 가이드가 정확한가요? (y / 수정)"

## Step 4. 파일 저장

Write `docs/UI_GUIDE.md` 로 저장. revision 모드면 백업 후 갱신.

## Step 5. 완료 마킹

Bash:
```
python3 -m fullstack_harness.harness ui-guide-complete
```

성공 → Step 6.

## Step 6. 다음 단계 안내

- 신규 모드: "다음 단계: `/stack-select`"
- Revision 모드 (mid-project): "변경이 phase 산출물에 영향을 줄 수 있습니다. 영향 받는 phase 의 design.md / spec.md 를 검토하세요. 그 후 `/harness` 로 계속 진행."

## 안티 패턴

- ❌ 모든 카테고리 질문을 한 번에 쏟아내기. **하나씩, 답 받고 paraphrase.**
- ❌ 사용자가 "TBD" 라고 한 항목을 LLM 이 임의로 채움. placeholder 유지.
- ❌ 컬러 / 폰트 등을 트렌드 기반으로 자동 추천 (Inter / Pretendard 등) — **사용자가 명시한 경우에만**.
- ❌ Revision 모드에서 백업 없이 덮어쓰기.
- ❌ docs/UI_GUIDE.md 외 다른 위치에 작성. validation 흐름이 이 경로를 기준.
- ❌ ui-guide-complete 실패 (파일 없음 / 비어 있음) 시 강제로 phases/index.json 직접 수정. 반드시 Python subcommand 경유.
