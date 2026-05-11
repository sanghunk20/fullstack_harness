# vue-firebase fixture

Vue + Firebase 스택의 최소 harness 설정 예시.

```bash
python3 -m fullstack_harness.harness --target examples/vue-firebase status
```

## 일반성 검증 의도

이 fixture 의 목적은 harness 가 Next.js 외의 스택에서도 그대로 동작함을 보이는 것이다. `stack.framework: "vue"` + `stack.db: "firebase"` 매칭으로 built-in `vue_firebase` adapter 가 자동 선택된다.

## DB 격리

Firestore 는 schema 개념이 없고 멀티-프로젝트로 격리한다. v0.2 의 `compose` 모드와 의미가 다르므로 이 fixture 는 `db_isolation: "none"` 을 사용한다.

future: emulator 기반 격리 모드 (`firestore_emulator`) 는 v0.3 이상에서 검토 가능.
