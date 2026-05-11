# examples/ — harness fixture 모음

여기에는 **실제 소스 코드가 없는 config-only fixture** 가 들어 있다. 목적은:

1. 일반성 검증 — 한 harness 가 서로 다른 스택 (Next.js/Supabase, Vue/Firebase) 에 동작하는지 확인.
2. 사용자 문서화 — `harness.json` / `phases/index.json` 을 어떻게 채워야 하는지 실물 예시 제공.
3. 자동 스모크 테스트 — CI 에서 `python3 -m fullstack_harness.harness --target examples/<name> status` 가 깨지지 않는지 확인.

## fixture 목록

| 디렉토리 | stack | adapter | db_isolation |
|---|---|---|---|
| [nextjs-supabase/](nextjs-supabase/) | Next.js + Supabase | `next_supabase` (built-in) | `schema` |
| [vue-firebase/](vue-firebase/) | Vue + Firebase | `vue_firebase` (built-in) | `none` |

## 사용 예

```bash
# repo root 에서
python3 -m fullstack_harness.harness --target examples/vue-firebase status
python3 -m fullstack_harness.harness --target examples/nextjs-supabase status
```

## 새 stack 추가하기

새 스택을 검증하려면:

1. `examples/<stack-name>/` 디렉토리 생성.
2. `harness.json` (이 디렉토리들의 형식 참고).
3. `phases/index.json` 작성.
4. (선택) `examples/<stack-name>/.harness/adapters/<adapter>.py` 로 어댑터 추가.
5. `python3 -m fullstack_harness.harness --target examples/<stack-name> status` 가 통과해야 함.
