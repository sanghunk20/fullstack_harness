---
description: 요구사항·제약 분석 후 frontend/backend/DB/deploy 스택 조합을 2~3개 추천. 사용자가 선택하면 harness.json.stack + commands를 그에 맞춰 업데이트.
argument-hint: (인자 없음)
---

# /stack-select — 기술 스택 추천 + 선택

이 슬래시 명령은 `/req-eng` 단계에서 수집한 요구사항·제약을 읽어 **frontend / backend / DB / deploy 조합** 을 추천하고, 사용자가 선택하면 `harness.json` 을 그대로 업데이트합니다.

**호출 시점**: `/req-eng` 완료 후, `/harness` 가 안내해주는 단계.

## 사전 점검

Bash:
```
python3 -m fullstack_harness.harness status
```

- discovery_status 가 completed 가 아니면 → "먼저 /req-eng 를 완료하세요." 안내 후 종료.
- 이미 stack 이 모두 채워져 있다면 (`framework`, `db` 가 null 아님) → "이미 스택이 선택되어 있습니다. 변경하려면 harness.json 을 직접 수정하거나 다시 진행하시겠습니까? (y/N)" 묻기. N 이면 종료.

## Step 1. 입력 컨텍스트 로드

Read 로:
- `harness.json` (특히 `stack.archetype_hint`, `description`)
- `docs/REQUIREMENTS.md` — 기능 핵심 (실시간 / 멀티유저 / 결제 / 미디어 등 시그널)
- `docs/QUALITY.md` — 성능·보안·접근성 시그널
- `docs/CONSTRAINTS.md` — 가장 중요. category 별로 분류:
  - `budget` — 호스팅 비용 상한
  - `tech` — 사용/금지 기술
  - `legal` — 컴플라이언스
  - `infra` — 호스팅 환경
  - `team` — 보유 기술
  - `schedule` — 시간 압박

## Step 2. 제약 정리 한 번 보여주기

다음 표로 사용자에게 컨텍스트 확인:

```
| 카테고리 | 핵심 제약 / 시그널 |
|---|---|
| 예산   | 월 호스팅 $20 이하 (CON-001) |
| 기술   | TypeScript only (CON-005), Java 금지 (CON-006) |
| 인프라 | Vercel 또는 Cloudflare 권장 (CON-008) |
| 팀    | React 경험 풍부, Vue 미경험 (CON-010) |
| 기능   | 실시간 협업 (FR-003), 결제 (FR-007) |
| 품질   | 99% uptime (NFR-002) |
```

사용자가 "정확함" 확인하면 Step 3.

## Step 3. 스택 추천 (2~3 조합)

제약을 만족하는 **명시적으로 다른 trade-off 의 조합** 2~3개를 표로 제시:

```
| 옵션 | Frontend | Backend(BaaS/Server) | DB | Deploy | 적합도 |
|---|---|---|---|---|---|
| A | Next.js 15 (App Router) | Supabase (auth + db + storage) | Postgres (Supabase) | Vercel | ★★★★★ — 팀 React 경험, 실시간 지원, 비용 적합 |
| B | SvelteKit | Cloudflare Workers + D1 | D1 (SQLite) | Cloudflare Pages | ★★★★ — 가장 저렴, 학습 부담 약간 |
| C | Next.js | Firebase (auth + firestore) | Firestore | Vercel + Firebase | ★★★ — 실시간 강함, 단 SQL 부재 |
```

각 옵션에 대해 한 문단:
- **장점**: 어떤 제약을 잘 만족하는지
- **단점 / 리스크**: 어떤 제약은 빠듯한지
- **빌트인 adapter 매칭**: 어떤 builtin adapter 가 자동 매칭되는지 (`next_supabase` / `vue_firebase` / `_default`)

## Step 4. 사용자 선택

질문:

> "어느 옵션으로 진행할까요? (A / B / C / 직접 입력)"

- A/B/C → 그 조합 채택.
- "직접 입력" → 사용자가 framework / db / deploy 를 자유 입력.

선택 후 추가 질문 (선택적):
- 언어: 보통 typescript / javascript. 모바일이면 dart / swift / kotlin 도.
- adapter: builtin 과 매칭되면 자동, 안 되면 명시할지 묻기 (예: `svelte_d1`).

## Step 5. harness.json 패치

다음 순서로 Bash + Write 결합:

1. 백업: `cp harness.json harness.json.bak.<timestamp>`
2. Read 로 현재 harness.json 로드.
3. 다음 필드 수정:
   - `stack.language`: 사용자 답
   - `stack.framework`: 선택 옵션의 frontend
   - `stack.db`: 선택 옵션의 db
   - `stack.deploy`: 선택 옵션의 deploy
   - `stack.adapter`: builtin 매칭 시 그 이름 (예: `"next_supabase"`), 아니면 null
   - `commands.*`: builtin adapter 가 매칭되면 commands_defaults 가 자동 채워지므로 비워둠. **매칭 안 되는 stack** 이면 사용자에게 묻거나 일반적 default 를 제시 후 확인:
     - `dev`, `build`, `typecheck`, `lint`, `test_unit`, `test_integration`, `test_e2e`, `format`, `migrate`
   - `worktree.db_isolation`: stack 에 따라 권장값 조정:
     - SQL DB (Postgres, MySQL) → `"schema"` 권장 (사용자 동의 시)
     - 그 외 (Firestore, D1, MongoDB) → `"none"` 유지
   - `worktree.compose_template`: db_isolation 이 compose 이고 사용자가 docker-compose 사용 의향 있으면 경로 입력 받음. 아니면 null.
4. Write 로 저장.

## Step 6. 검증

Bash:
```
python3 -m fullstack_harness.harness status
```

출력에서 `stack adapter: <name>` 이 사용자가 의도한 adapter (또는 `_default`) 인지 확인. 다르면 사용자에게 알리고 수정.

## Step 7. 0-bootstrap phase 안내

`/setup` 이 만들어둔 `phases/0-bootstrap/index.json` 을 stack 기반으로 보강 안내 (직접 채우지 말고 사용자에게 다음 step 안내):

```
✓ 스택 선택 완료.

  Frontend: <framework>
  Backend:  <db/service>
  Deploy:   <deploy>
  Adapter:  <adapter or _default>

이제 첫 phase 부터 진행하실 차례입니다:

  /harness            — 다음 액션 안내 (보통 0-bootstrap 진입)
  /harness run 0-bootstrap   — 인프라 셋업 phase 시작
```

bootstrap phase 의 step 은 비-V-Model linear 입니다. 사용자가 0-bootstrap/index.json 의 steps 를 stack 에 맞게 정의 (예: `npx create-next-app`, `supabase init` 등).

## 안티 패턴

- ❌ 한 가지 옵션만 강력 추천. **항상 trade-off 가 다른 2~3 옵션을 제시.**
- ❌ 사용자 컨펌 없이 harness.json 수정. **백업 → 변경 → 출력 표시.**
- ❌ `harness.json.commands.*` 를 stack-specific 으로 하드코딩한 뒤 사용자에게 안 보여주기. 변경 사항을 표로 제시.
- ❌ feature phase 를 임의 추가. feature phase 추가는 사용자 결정 (이건 prd 또는 후속 슬래시 명령의 영역).
- ❌ /req-eng 완료 안 됐는데 강행. discovery_status: completed 가 전제 조건.
- ❌ archetype_hint 무시. /setup 에서 사용자가 "mobile" 이라고 했으면 Next.js 만 추천 X.
