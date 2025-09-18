# jupythunder2

`jupythunder2`는 터미널에서 실행되는 Jupyter Notebook 코딩 에이전트입니다. 코드 기획부터 실행, 디버깅, 워크플로우 자동화까지 일관된 CLI 경험을 제공하는 것을 목표로 합니다.

## 주요 기능

- **LLM 기반 계획 수립**: `plan` 명령을 통해 고수준 목표를 주면 LangChain + Ollama (`codegemma:7b`)을 활용해 단계별 실행 계획을 생성합니다.
- **상호작용형 코드 실행**: `execute` 명령으로 Jupyter 커널을 직접 제어하며, stdout/stderr/결과 및 display 데이터를 CLI에 맞게 표시합니다.
- **컨텍스트 인지 디버깅**: 실행 오류 발생 시 최근 히스토리와 스택트레이스를 바탕으로 수정 제안을 제공합니다.
- **워크플로우 자동화**: 자주 사용하는 계획/실행 단계를 워크플로우로 저장하고 `workflow run`을 통해 재사용합니다.

## 빠른 시작

### 요구 사항

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (권장)
- [Ollama](https://ollama.com/) 또는 호환 LLM 서버 (`codegemma:7b` 모델)

### 설치 및 실행

```bash
uv venv
source .venv/bin/activate
uv pip install -e .  # 개발 모드 설치
# 개발용 도구까지 설치하려면: uv pip install -e .[dev]

# CLI 실행
python -m jupythunder2 --help
```

### 명령어 개요

```bash
jupythunder2 plan "데이터 분석 파이프라인을 설계해줘"
jupythunder2 execute --code "print(sum(range(10)))" --history-file history.json

jupythunder2 workflow add-plan demo --goal "매출 데이터 분석" --context "CSV in ./data"
jupythunder2 workflow add-exec demo --path scripts/load_data.py
jupythunder2 workflow move-step demo --from 2 --to 1
jupythunder2 workflow remove-step demo --index 3
jupythunder2 workflow run demo --history-file history.json

# 기본 설정 관리
jupythunder2 config show
jupythunder2 config set-agent --provider ollama --model codegemma:7b
jupythunder2 config set-runtime --history-file ~/.cache/jupythunder2/history.json
```

## 환경 변수

| 변수 | 설명 | 기본값 |
| ---- | ---- | ------ |
| `JUPYTHUNDER2_PROVIDER` | 계획/디버깅에 사용할 LLM 제공자 | `ollama` |
| `JUPYTHUNDER2_MODEL` | 기본 모델 이름 | `codegemma:7b` |
| `JUPYTHUNDER2_BASE_URL` | Ollama와 호환되는 HTTP 엔드포인트 | 로컬 기본값 |
| `JUPYTHUNDER2_TEMPERATURE` | LLM temperature 값 | `0.1` |
| `JUPYTHUNDER2_ALLOW_FALLBACK` | 실패 시 더미 응답 사용 여부 (`true`/`false`) | `true` |
| `JUPYTHUNDER2_HISTORY_FILE` | 기본 히스토리 파일 경로 | 설정 파일/없음 |
| `JUPYTHUNDER2_HISTORY_LIMIT` | 히스토리 보관 기본 개수 | `50` |
| `JUPYTHUNDER2_WORKFLOWS_DIR` | 워크플로우 JSON 저장 디렉터리 | `~/.config/jupythunder2/workflows` |

## 테스트

```bash
uv run --extra dev pytest
```

## 라이선스

MIT License. 자세한 내용은 [LICENSE](LICENSE)를 참고하세요.
