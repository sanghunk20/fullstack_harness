# fullstack-harness 사용법 (v0.1.1)

## 설치

CLI install 흐름은 v0.3 에서 추가 예정. v0.1.x 에서는 수동 복사:

```bash
# 0. fullstack-harness repo 를 clone (또는 이미 받았다면 경로 기억)
git clone <fullstack-harness-repo-url> ~/projects/fullstack-harness
FH=~/projects/fullstack-harness

# 1. 대상 프로젝트로 이동
cd <target-project>

# 2. harness.json 을 프로젝트 root 에 생성
cp "$FH/templates/harness.json.template" ./harness.json
# 편집해서 project, stack, commands 등 채우기

# 3. phases/index.json 생성
mkdir -p phases
cp "$FH/templates/phases_index.json.template" phases/index.json

# 4. 슬래시 명령 설치 (Claude Code 프로젝트의 경우)
mkdir -p .claude/commands
cp "$FH/commands/"*.md .claude/commands/

# 5. Python harness 를 PYTHONPATH 에 노출 (또는 alias)
export PYTHONPATH="$FH:$PYTHONPATH"
# 영구화하려면 .bashrc / .zshrc 에 추가.
```

## 일상적인 흐름

매 세션 시작 때 `/harness` 만 호출하면 된다.

```
/harness
```

이 명령은:
1. 현재 상태 출력 (`status`).
2. blocked / error 가 없으면 다음 진행 가능 phase 분석 (`next --parallel`).
3. 병렬 후보가 2개 이상이면 사용자에게 어떻게 나눌지 묻고, 선택에 따라 worktree 명령 출력.

## 시나리오별

### 새 프로젝트 시작

1. 위 "설치" 따라 `harness.json` + `phases/index.json` 생성.
2. discovery 단계 진행:
   - `harness.json` 의 `discovery.command` 실행 (예: `/req-eng`).
   - 필요한 docs 파일들 (`docs/REQUIREMENTS.md` 등) 채우기.
3. discovery 완료 마킹:
   ```bash
   python3 -m fullstack_harness.harness discovery-complete
   ```
4. 첫 phase 추가 (수동):
   - `phases/<dir>/index.json` 생성 (template 사용).
   - `phases/index.json` 의 `phases` 배열에 entry 추가, `depends_on` 명시.
5. `/harness` 호출 → 진행.

### 여러 phase 가 병렬 진행 가능할 때

`/harness next --parallel` 출력 예:

```
  진행 가능 phase 2개 — 병렬 worktree 분리 가능.

    • 2-billing                       feature    (deps: 1-auth)
    • 3-profile                       feature    (deps: 1-auth)

  옵션:
    (A) 모두 현재 worktree에서 순차 진행
    (B) 일부/전부를 별도 worktree로 분리해서 병렬 진행
```

(B) 선택 시:

```bash
python3 -m fullstack_harness.harness worktree-plan 2-billing 3-profile
```

출력된 `git worktree add ...` 명령을 직접 실행 → 각 worktree 에서 새 Claude Code 세션 띄움 → 그 세션에서 `/harness run <phase>` 또는 직접 phase 작업.

> **주의**: 한 세션에서 cwd 만 바꿔 다른 worktree 로 가지 말 것. 컨텍스트가 섞여 phase 산출물 품질이 떨어진다. **반드시 새 세션을 띄울 것.**

### phase 작업 완료 후

- 해당 worktree 에서 PR 생성.
- main 에 merge.
- (모든 feature phase 완료 시) `/harness merge-gate` 로 모든 브랜치가 merge 됐는지 검증.
- acceptance phase 진행.

### blocked / error 발생 시

- harness 가 자동 진행 제안을 멈춤.
- 사용자가 phase 의 `index.json` 에서 `blocked_reason` / `error_message` 확인.
- 원인 해결 후 status 를 `pending` 으로 되돌리고 다시 `/harness`.

## 명령 레퍼런스

```
python3 -m fullstack_harness.harness [--target <path>] <subcommand>

서브커맨드:
  status                       전체 상태 출력
  next [--parallel]            다음 phase 안내 (--parallel: 병렬 후보까지)
  validate                     discovery 충실도 검사
  discovery-complete           discovery_status 를 completed 로 마킹
  worktree-plan <phase>...     선택 phase 들의 worktree 명령 + 새 세션 안내
  merge-gate                   feature 브랜치 main merge 검증
  set-deps [--json-file <p>]   JSON 입력으로 depends_on 일괄 패치 (백업 + DAG 재검증)
```

`--target` 생략 시 cwd 또는 상위 디렉토리에서 `harness.json` 검색.

## 의존성 inference 흐름 (v0.1.1)

`depends_on` 을 phase 마다 손으로 채우기 번거로우면 `/harness-analyze-deps` 슬래시 명령 사용:

1. Claude Code 가 각 phase 의 `spec.md` / `design.md` 를 읽음.
2. phase 간 인용·참조 신호로 의존성 추론.
3. 사용자에게 추론 결과를 표로 보여주고 컨펌 요청.
4. 컨펌되면 임시 JSON 작성 → `set-deps` 호출.
5. `set-deps` 는 백업 → 패치 → DAG 재검증 (cycle 등 발견 시 자동 롤백).

수동으로 직접 호출하고 싶으면:

```bash
echo '{"2-billing": ["1-auth"], "3-profile": ["1-auth"], "99-accept": "all_features"}' \
  | python3 -m fullstack_harness.harness set-deps
```

## 한계 (v0.1.1)

- **Phase 실행 미구현**: `/harness run <phase>` 가 실제 phase step 을 실행하는 부분은 v0.1 범위 밖. v0.2 에서 별도 executor 통합 예정.
- **DB 격리 미구현**: `worktree.db_isolation` 옵션은 schema 에만 존재. `schema` / `compose` 동작은 v0.2.
- **Hot reload / 동시성 lock 통합 안 됨**: `lock.py` 모듈은 작성됐지만 phase 실행 흐름과 통합은 executor 가 만들어진 뒤에 가능.
- **Inference 정확도**: spec.md 가 충실하지 않으면 추론도 빈약. 컨펌 단계에서 사용자가 보정해야 함.

## v0.1.x 이후

- **v0.2**: DB 격리 (schema / docker-compose), phase executor 통합, tech-stack adapter plugin point.
- **v0.3**: 별도 repo 추출 + CLI install 흐름 (예: `npx fullstack-harness init` 또는 `pip install fullstack-harness`).
