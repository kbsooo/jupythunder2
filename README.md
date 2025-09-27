# jupythunder2

CLI 환경에서 계획 · 코드 생성 · 실행 · 디버깅까지 하나의 흐름으로 이어주는 노트북 에이전트입니다. Codex CLI, Gemini CLI처럼 단일 명령(`jt2`)으로 실행하면 전용 REPL이 뜨고, 자연어 요청과 코드 실행을 반복할 수 있습니다.

## Demo video
![영상](https://github.com/user-attachments/assets/adda3abd-174c-4992-a1ee-d24d67610701)

## 주요 기능 (MVP)
- ASCII 스플래시를 포함한 전용 REPL UI (`prompt_toolkit` + `rich`)
- `/auto`, `/exec`, `/reset` 등 명령어 기반 워크플로우 제어 (기본 자동 실행 ON)
- Jupyter 커널과 직접 통신하여 코드 셀 실행 및 결과/이미지 수집
- 실행 오류에 대한 휴리스틱 디버그 요약과 수정 힌트
- 세션 로그(`runs/<timestamp>/events.jsonl`) 및 아티팩트 저장, `codes/<mmddhhmm>.ipynb|.md`로 코드/설명을 기록
- 세션 시작 시 기존 코드북 선택 또는 새 코드북 생성(한 줄 요약 표시)
- 커널/에이전트 대기 동안 ASCII 애니메이션 상태 표시, 모듈 누락 시 설치 여부 안내
- Ollama(codegemma:7b) 연동을 위한 LLM 오케스트레이터 골격

## 빠른 시작
```bash
uv venv
source .venv/bin/activate
uv pip install .

# 데이터 분석 도구가 필요한 경우 (선택)
uv pip install .[analysis]

# 최초 실행 (LLM이 없어도 기본 명령어/커널 실행은 가능)
jt2
```

> ⚠️ Ollama가 실행 중이 아니면 LLM 기반 코드 제안은 비활성화되고, `/code` 명령으로 직접 코드를 실행할 수 있습니다.

## REPL 명령어
- `/help` : 사용 가능한 명령어 목록
- `/quit` : 세션 종료
- `/auto on|off` : 에이전트가 제안한 코드 자동 실행 토글
- `/reset` : Jupyter 커널 재시작
- `/cells` : 대기 중인 코드 셀 목록 확인
- `/exec <cell-id|all>` : 특정 셀 또는 전부 실행
- `/code <python>` : 즉시 실행할 파이썬 코드를 큐에 추가

## 설정
`~/.config/jt2/config.toml` 또는 프로젝트 루트의 `.jt2.toml`에서 기본 설정을 정의할 수 있습니다.

```toml
model = "codegemma:7b"
use_color = false
auto_execute = true
kernel_name = "python3"
codebook_root = "codes"
run_root = "runs"
max_execution_seconds = 60
history_limit = 10
llm_host = "http://localhost:11434"
llm_request_timeout = 30
```

`jt2 --config /path/to/config.toml` 형태로 다른 설정 파일을 지정할 수도 있습니다. `--dry-run` 옵션을 사용하면 설정만 출력하고 REPL에 진입하지 않습니다.

- 컬러 출력을 활성화하고 싶다면 설정에서 `use_color = true`로 바꾸거나 실행 시 `jt2 --color`를 사용하세요. `jt2 --no-color`로 일시적으로 끌 수도 있습니다.
- 커널이 발견되지 않는다면 `ipykernel` 설치 후 `kernel_name`을 해당 커널 이름으로 맞추거나 `python -m ipykernel install --user --name python3` 명령으로 기본 커널을 등록하세요.
- 각 세션은 `codes/<mmddhhmm>.ipynb`와 `codes/<mmddhhmm>.md` 한 쌍으로 기록됩니다. 노트북에는 실행된 코드와 출력이 저장되고, Markdown에는 사용자 요청·에이전트 계획·실행 결과 요약이 누적됩니다.
- 오류가 `ModuleNotFoundError`인 경우에는 `uv pip install <모듈>` 실행 여부를 묻고, 설치가 성공하면 즉시 재사용할 수 있습니다.

## 개발 노트
- 패키지 버전: Python 3.12
- 주요 라이브러리: Typer, prompt-toolkit, rich, jupyter-client, pydantic, ollama
- 테스트: `uv pip install .[dev]` 또는 `pip install -e .[dev]`로 개발 의존성을 설치한 뒤 `pytest`
- 린트/포맷: `ruff check .`, `ruff format .`

## 다음 단계 아이디어
1. LLM 응답 파서를 고도화하여 멀티 셀/워크플로우를 안정적으로 지원
2. `/plan`, `/workflow` 등 슬래시 명령 확장
3. `Textual` 기반 멀티 패널 TUI 실험
4. 코드 실행 결과(표/이미지)에 대한 요약 및 후속 액션 제안
5. LangChain 또는 자체 태스크 그래프를 활용한 멀티 스텝 리서치/실행
