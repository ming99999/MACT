# MACT 프레임워크 분석 보고서

## 1. MACT 프레임워크 동작 원리

MACT 프레임워크는 **ReAct(Reason-Act)** 패러다임을 기반으로 하는 에이전트 시스템입니다. 주요 동작 원리는 다음과 같습니다.

1.  **Planner-Coder 아키텍처**:
    *   **Planner (계획자)**: 상위 레벨의 LLM(e.g., GPT-4)이 사용자의 질문과 테이블을 보고, 문제를 해결하기 위한 생각(Thought)과 행동(Action)을 생성합니다.
    *   **Coder (코드 생성자)**: `Action`이 코드 생성을 요구할 경우(e.g., `Retrieve`, `Calculate`), 하위 레벨의 LLM(e.g., GPT-3.5)이 해당 작업을 수행하는 Python(pandas) 코드를 생성합니다.

2.  **ReAct (Reason-Act) 루프**:
    *   **Thought (생각)**: 에이전트가 현재 상황을 분석하고 다음 행동 계획을 세웁니다.
    *   **Action (행동)**: 계획에 따라 사전에 정의된 도구(Tool)를 실행합니다. 주요 도구는 다음과 같습니다.
        *   `Retrieve[instruction]`: 테이블에서 특정 데이터를 검색합니다. 내부적으로 Coder LLM을 호출하여 pandas 코드를 생성하고 실행합니다.
        *   `Calculate[instruction]`: 계산을 수행합니다. 이 또한 Coder LLM을 호출하여 코드를 생성하고 실행합니다.
        *   `Search[entity]`: Wikipedia에서 정보를 검색합니다.
        *   `Finish[answer]`: 최종 답변을 내리고 작업을 종료합니다.
    *   **Observation (관찰)**: `Action`의 실행 결과를 받아옵니다. 이 결과는 다음 `Thought`를 위한 입력으로 사용됩니다.
    *   이 `Thought` -> `Action` -> `Observation` 과정을 `Finish` 액션이 호출될 때까지 반복합니다.

3.  **Self-Consistency (자가 일관성) 및 투표**:
    *   `agents.py`의 `as_reward_fn` 함수를 통해 구현됩니다.
    *   하나의 `Thought` 단계에서 여러 개의 후보 `Action`을 생성(`plan_sample` 개수만큼)하고, 그중 가장 일관성 있거나 다수가 선택한 `Action`을 투표(majority voting) 방식으로 선택하여 안정성을 높입니다.

4.  **유연한 LLM 사용**:
    *   `llm.py`의 `UnifiedLLM` 클래스와 `config.py`를 통해 OpenAI 모델(GPT)과 오픈소스 모델(Qwen, Llama 등)을 동일한 인터페이스로 사용할 수 있도록 추상화되어 있습니다.

요약하자면, MACT는 **"계획 LLM이 ReAct 방식으로 추론하고, 실행 LLM이 동적으로 코드를 생성하여 테이블을 조작하는"** 이중 LLM 구조의 에이전트 프레임워크입니다.

## 2. MACT의 Multi-Table Question Answering 접근 방식

결론부터 말하자면, **MACT의 핵심 `ReactAgent`는 본질적으로 Multi-Table을 직접적으로 인식하고 처리하도록 설계되지 않았습니다.** 에이전트는 단일 테이블 컨텍스트 내에서 동작합니다.

대신, 프레임워크는 Multi-Table 문제를 다음과 같은 **"전처리(Pre-processing)"** 전략을 통해 해결합니다.

1.  **테이블 직렬화 및 병합 (Serialization and Concatenation)**:
    *   `tqa_mmqa.py`에서 볼 수 있듯이, 여러 개의 테이블(`tables` 리스트)이 주어지면 각 테이블을 텍스트 형식(Markdown 스타일)으로 변환합니다.
    *   그 후, 이 텍스트들을 **하나의 거대한 텍스트 블록으로 이어 붙입니다.** 예를 들어, "Table 1 (department): ...", "Table 2 (management): ..." 와 같은 형태로 하나의 문자열로 만듭니다.

2.  **단일 컨텍스트로 제공**:
    *   이렇게 병합된 거대한 텍스트 덩어리를 `ReactAgent`에게 마치 **하나의 큰 테이블인 것처럼** 전달합니다.
    *   마찬가지로, 모든 테이블의 데이터를 합쳐서 하나의 거대한 pandas DataFrame을 생성하고, Coder LLM이 이 DataFrame을 조작하는 코드를 생성하게 합니다.

3.  **LLM의 문맥 이해 능력에 의존**:
    *   결국 이 방식은 `ReactAgent`가 "Table 1", "Table 2"와 같은 구분자를 보고 **LLM 자체가 문맥을 파악하여** 여러 테이블 간의 관계를 이해하고 올바른 코드를 생성할 것이라는 가정에 기반합니다.
    *   즉, 프레임워크 레벨에서 `JOIN`과 같은 Multi-Table 전용 도구를 제공하는 것이 아니라, 모든 정보를 하나의 프롬프트에 넣어 LLM의 능력에 의존하는 방식입니다.

이 방식은 테이블 구조가 복잡하지 않고 LLM의 문맥 이해 능력이 충분히 높을 때 효과적일 수 있지만, 복잡한 `JOIN`이나 여러 테이블에 걸친 집계(aggregation)가 필요할 경우 성능이 저하될 수 있습니다.

## 3. `tqa_mmqa.py`에 추가된 내용 분석

`tqa_mmqa.py`는 기존의 단일 테이블 처리 방식(`tqa.py`)을 MMQA 데이터셋에 맞게 확장하기 위해 다음과 같은 핵심 함수들을 추가했습니다. **`ReactAgent` 자체에 새로운 도구가 추가된 것은 없습니다.** 모든 변경점은 에이전트에 데이터를 전달하기 전의 **데이터 준비 단계**에 집중되어 있습니다.

1.  **`process_mmqa_tables(tables_data)`**:
    *   MMQA 데이터셋의 `tables` 필드(테이블 리스트)를 순회합니다.
    *   각 테이블의 이름, 컬럼, 데이터를 추출하여 `table_linear` 함수로 텍스트 형식으로 변환하고, 이를 리스트에 저장합니다.

2.  **`create_mmqa_context(item)`**:
    *   테이블 이름, 외래 키(Foreign Keys), 기본 키(Primary Keys) 같은 메타데이터를 하나의 문자열 컨텍스트로 만듭니다.
    *   이 컨텍스트는 LLM이 테이블 간의 관계를 더 잘 이해하도록 돕는 추가 정보 역할을 합니다.

3.  **`combine_tables_for_qa(combined_tables)`**:
    *   이것이 Multi-Table을 처리하는 가장 핵심적인 함수입니다.
    *   `process_mmqa_tables`에서 생성된 각 테이블의 텍스트 표현을 **하나의 큰 문자열로 합칩니다.** 각 테이블은 "Table 1 (테이블명):"과 같은 헤더로 구분됩니다.
    *   이 함수는 두 가지를 반환합니다:
        1.  `table_string`: LLM의 프롬프트에 들어갈, 모든 테이블이 합쳐진 텍스트
        2.  `table_data`: 모든 테이블의 데이터를 합친 리스트. 이 리스트는 `table2df` 함수를 통해 **하나의 pandas DataFrame 생성 코드로 변환**됩니다.

4.  **`main` 함수 내 로직**:
    *   위 함수들을 순서대로 호출하여 MMQA 데이터를 처리합니다.
    *   `ReactAgent`를 생성할 때, `table` 인자에는 모든 테이블의 원본 데이터를 합친 리스트를, `table_df` 인자에는 모든 테이블을 합쳐 만든 DataFrame 코드를, `context` 인자에는 테이블 관계 메타데이터를 전달합니다.
    *   `task="mmqa"`로 지정하여, 에이전트가 `react_agent_prompt_wtq` 프롬프트를 사용하도록 설정합니다. (MMQA 전용 프롬프트는 따로 없습니다.)

요약하면, `tqa_mmqa.py`는 Multi-Table 데이터를 **"하나의 테이블인 척"** 보이도록 가공하여 기존 `ReactAgent`에 주입하는 역할을 합니다. 에이전트의 내부 로직이나 도구는 변경되지 않았습니다.
