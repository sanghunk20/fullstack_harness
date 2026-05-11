# AGENTS.md — AI agent 작업 규칙

Claude Code 같은 AI agent 가 이 repo 에서 작업할 때 지켜야 할 규칙.

## 절대 규칙 (CRITICAL)

1. **기술 스택 중립.** Next.js · Supabase · Vercel · React · Django 등 특정 스택 이름을 코드/스키마에 하드코딩하지 않는다.
   - 프레임워크별 동작은 **config 또는 plugin** 으로 분리.
   - 예: "migration 실행 명령" 은 `harness.json.commands.migrate` 에서 가져옴 — 코드에 `supabase db reset` 하드코딩 금지.
   - 단 예시·문서·README 에서 특정 스택을 거론하는 것은 허용 (`harness.json` 채우는 법 설명 시 등).

2. **외부 의존 금지.** Python 코드는 표준 라이브러리만 사용. 부득이한 경우만 명시적 검토 후 `requirements.txt` (또는 `pyproject.toml`) 에 추가.

3. **언어/런타임.** harness 자체는 Python 3.11+ 로 작성. 대상 프로젝트의 런타임과 독립.

4. **커밋 컨벤션.** [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` 새 기능 (서브커맨드 추가, 스키마 필드 등)
   - `fix:` 버그 수정
   - `docs:` 문서·주석·README 수정
   - `refactor:` 동작 변경 없는 코드 정리
   - `chore:` 빌드·CI·메타 (예: gitignore 수정)
   - 광범위 `git add -A` / `git add .` 금지 — 항상 명시적 path 로 add.

## 권장 규칙

- 새 기능 추가 시 `templates/` 의 스키마 → `fullstack_harness/` 코드 → `examples/` fixture → `docs/` 문서 순으로 작업.
- 모든 변경은 `examples/<stack>/` 의 config-only fixture 로 스모크 테스트 가능해야 함. 추가 임시 시나리오는 `/tmp/<fixture>` 패턴 권장.
- 새 서브커맨드는 `harness.py` 의 `SUBCOMMANDS` 와 `argparse` 양쪽에 등록 필요.
- 외부 명령 호출 (subprocess) 은 모두 `harness.json.commands.*` 에서 가져오기. 하드코딩 금지.
- Stack-specific 기본값은 `fullstack_harness/adapters/<name>.py` 에 정의. 코드 본체에는 stack 이름 분기 금지.

## 자기검증 체크리스트

새 파일·기존 파일 수정 시:

- [ ] 이 파일에 특정 스택 이름이 하드코딩되어 있지 않은가? (문서·예시 제외)
- [ ] 새 의존성을 도입하지 않았는가? (표준 라이브러리만 사용)
- [ ] 다른 프로젝트(예: Vue + Firebase) 에도 그대로 적용 가능한가?
- [ ] 커밋 메시지가 Conventional Commits 인가?
- [ ] fixture 로 동작 검증을 했는가?

## 디렉토리 책임 분리

| 디렉토리 | 역할 | 변경 빈도 |
|---|---|---|
| `fullstack_harness/` | Python 코드. 모듈 간 relative import. | 자주 |
| `fullstack_harness/adapters/` | stack-adapter plugin 모듈들. 각 모듈은 NAME / match / commands_defaults / step_gates contract. | 새 스택 지원 시 |
| `templates/` | project init 시 사용자가 복사할 JSON 템플릿. 스키마와 1:1. | 스키마 변경 시 |
| `commands/` | Claude Code 슬래시 명령 (.md). LLM 측 흐름. | 슬래시 명령 추가/수정 시 |
| `examples/` | config-only fixture. 일반성 검증 + 사용자 예시. 실제 소스 코드는 두지 않음. | 새 스택 fixture 추가 시 |
| `docs/` | 사용자 문서. USAGE = 흐름, SCHEMA = 레퍼런스. | 동작 변경 시 |

## 안티 패턴

- ❌ 슬래시 명령 (.md) 가 phases/index.json 을 직접 수정. 반드시 Python 서브커맨드 (예: `set-deps`) 경유.
- ❌ 새 외부 라이브러리 도입 (PyYAML, requests, click, etc.). 표준 라이브러리로 가능하면 그것을 사용.
- ❌ Python 코드가 `os.system` 으로 git 호출. `subprocess.run` 사용.
- ❌ 사용자 컨펌 없이 destructive 작업 (worktree 자동 생성, phases/index.json 임의 덮어쓰기 등). 백업 + 컨펌 필수.
- ❌ LLM 이 `/harness run` 출력에 나온 gate / DB 격리 setup 명령을 사용자 동의 없이 자동 실행. orchestrator only 원칙 위반.
- ❌ adapter 모듈에서 외부 라이브러리 import. adapter 도 표준 라이브러리만.
