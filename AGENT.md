# jupythunder2

`jupythunder2`는 CLI 환경에서 구동되는 차세대 Jupyter Notebook 코딩 에이전트입니다. 기존의 GUI 기반 코딩 툴에 챗봇을 부가하는 형태를 넘어, 코드의 **기획, 리서치, 생성, 실행, 디버깅**에 이르는 전 과정을 터미널 내에서 유기적으로 통합하는 새로운 개발 경험을 제공하는 것을 목표로 합니다. (claude code, codex cli, gemini cli 와 같이 cli 환경에서 실행하는 프로그램입니다.)

## 1. 핵심 기능 (Core Features)

-   **에이전트 기반 코드 기획 (Agent-Driven Code Planning)**
    -   사용자가 "S&P 500 기업들의 주가 데이터를 분석하고, 업종별 평균 수익률을 시각화해줘" 와 같이 상위 수준의 목표를 제시하면, 에이전트가 `langchain-ai/open_deep_research` 등의 리서치 프레임워크를 활용하여 필요한 라이브러리(e.g., `yfinance`, `pandas`, `matplotlib`)를 식별하고, 데이터 수집부터 처리, 시각화에 이르는 단계별 실행 계획을 코드와 함께 제안합니다.

-   **대화형 코드 셀 생성 및 실행 (Interactive Code Cell Generation & Execution)**
    -   단순 코드 생성을 넘어, 사용자와의 대화를 통해 코드 셀을 점진적으로 완성합니다. 생성된 코드는 즉시 Jupyter 커널을 통해 실행되며, 결과(출력, 에러, 이미지 등)는 CLI에 최적화된 형태로 표시됩니다.

-   **컨텍스트 인지형 디버깅 (Context-Aware Debugging)**
    -   코드 실행 중 에러가 발생하면, 에이전트는 단순히 Traceback을 출력하는 데 그치지 않습니다. 에러 메시지, 코드 스택, 그리고 이전 셀에서 생성된 변수와 상태까지 종합적으로 분석하여 **에러의 원인을 진단하고 수정된 코드 스니펫을 능동적으로 제안**합니다.

-   **워크플로우 자동화 (Workflow Automation)**
    -   자주 사용하는 일련의 작업(e.g., 데이터 로드 → 전처리 → 모델 학습)을 하나의 '워크플로우'로 저장하고, 간단한 명령어로 재사용할 수 있는 기능을 제공합니다.

-   **ASCII 아트 시작 화면 (ASCII Art Splash Screen)**
    -   프로그램 시작 시, 사용자가 직접 디자인한 `jupythunder2`의 로고가 담긴 ASCII 아트가 출력됩니다. (영역 확보)

## 2. 기술 스택 및 아키텍처 (Tech Stack & Architecture)

-   **언어 (Language):** Python 3.11+
-   **가상환경 및 패키지 관리 (Virtual Env & Package Manager):** `uv`
-   **LLM (Large Language Model):** `codegemma:7b` (로컬 환경에서 [Ollama](https://ollama.com/) 등을 통해 실행)
-   **CLI 프레임워크 (CLI Framework):** `Typer` (직관적인 명령어 구조화)
-   **Jupyter 연동 (Jupyter Integration):** `jupyter_client` (백그라운드에서 Jupyter 커널과 직접 통신)
-   **에이전트 로직 (Agent Logic):** `LangChain` 또는 직접 구현 (LLM과의 상호작용 및 워크플로우 관리)
-   **실행 환경 (Execution Environment):** macOS (Apple Silicon M4, 16GB RAM) 에 최적화

## 3. 개발 환경 설정 (Development Environment Setup)

-   **가상환경 생성 및 활성화:**
    ```bash
    # 프로젝트 루트에서 가상환경 생성
    uv venv
    
    # 가상환경 활성화 (macOS/Linux)
    source .venv/bin/activate
    ```

-   **의존성 패키지 설치:**
    -   핵심 의존성은 `requirements.txt`에, 개발용 의존성(테스트, 린팅)은 `requirements.dev.txt`에 분리하여 관리합니다.
    ```bash
    # 핵심 의존성 설치
    uv pip install -r requirements.txt
    
    # 개발용 의존성 설치
    uv pip install -r requirements.dev.txt
    ```

-   **로컬 LLM 설정:**
    -   [Ollama](https://ollama.com/)를 설치하고, `codegemma:7b` 모델을 미리 다운로드합니다.
    ```bash
    ollama pull codegemma:7b
    ```

## 4. 개발 워크플로우 (Development Workflow)

`jupythunder2`의 기능 개발은 GPT의 Codex(또는 유사한 코드 생성 AI)를 적극 활용하여 생산성을 극대화합니다.

1.  **기능 정의:** `AGENT.md`의 핵심 기능을 바탕으로 구현할 기능의 요구사항과 동작 방식을 명확히 정의합니다.
2.  **Codex를 활용한 프로토타이핑:** Codex에 기능의 핵심 로직 구현을 요청하여 초안 코드를 빠르게 작성합니다.
3.  **코드 리팩토링 및 통합:** 생성된 코드를 프로젝트의 구조와 코딩 컨벤션에 맞게 다듬고, 기존 코드 베이스에 통합합니다.
4.  **테스트 코드 작성:** `pytest`를 사용하여 기능이 의도대로 동작하는지 검증하는 단위 테스트 및 통합 테스트를 추가합니다.
5.  **문서화:** 코드 내에 Docstring을 작성하고, 필요한 경우 README나 관련 문서를 업데이트합니다.

## 5. 테스트 및 린팅 안내 (Testing & Linting Instructions)

-   **전체 테스트 실행:**
    -   프로젝트의 모든 테스트를 실행하여 안정성을 확인합니다.
    ```bash
    pytest
    ```

-   **특정 테스트 실행:**
    -   개발 중인 기능과 관련된 테스트만 집중적으로 실행할 수 있습니다.
    ```bash
    pytest -k "<테스트 함수 이름의 일부>"
    ```

-   **린팅 및 코드 포맷팅:**
    -   `Ruff`를 사용하여 코드 스타일을 일관되게 유지하고 잠재적인 오류를 사전에 발견합니다.
    ```bash
    # 린트 검사
    ruff check .
    
    # 자동 코드 포맷팅
    ruff format .
    ```

## 6. PR (Pull Request) 작성 가이드 (PR Creation Guide)

-   **제목 형식:** `[<타입>] <내용>`
    -   `feat`: 새로운 기능 추가
    -   `fix`: 버그 수정
    -   `docs`: 문서 수정
    -   `refactor`: 코드 리팩토링
    -   `test`: 테스트 코드 추가/수정
    -   **예시:** `[feat] 컨텍스트 인지형 디버깅 에이전트 추가`

-   **PR 제출 전 체크리스트:**
    -   [ ] 모든 테스트가 통과했는가? (`pytest`)
    -   [ ] 린트 검사를 통과했는가? (`ruff check .`)
    -   [ ] 코드 자동 포맷팅을 적용했는가? (`ruff format .`)
    -   [ ] 변경 사항에 대한 문서(Docstring 등)를 업데이트했는가?