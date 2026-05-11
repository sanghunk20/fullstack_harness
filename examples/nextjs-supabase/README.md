# nextjs-supabase fixture

Next.js + Supabase 스택의 최소 harness 설정 예시.

```bash
python3 -m fullstack_harness.harness --target examples/nextjs-supabase status
```

이 fixture 는 실제 소스 코드 없이 harness 설정만 들어 있다. `harness.json` 의 `stack.adapter` 가 비어 있어도 built-in `next_supabase` adapter 가 stack.framework=`next` + stack.db=`supabase` 매칭으로 자동 선택된다.

## DB 격리

`worktree.db_isolation: "schema"` — 같은 Supabase Postgres 안에서 worktree 별 schema 를 분리하는 설정 예시.

`commands.create_schema` / `commands.drop_schema` 가 정의돼 있어야 phase 진입 시 setup/teardown 명령이 안내된다.
