# Original MACT vs LangGraph MACT 비교 분석

## 최종 결론: 두 구현은 동일하지 않음

`langgraph_code`는 원본 MACT 알고리즘을 LangGraph 프레임워크 위에서 **재해석하고 구조화한 버전**이지, **알고리즘적으로 100% 동일한 복제품은 아닙니다.**

-   **잘 구현된 부분**: ReAct 루프, Planner-Coder 구조, 액션 선택을 위한 투표 메커니즘, Hybrid Voting 등 핵심 아이디어는 성공적으로 이식되었습니다.
-   **개선된 부분**: 여러 테이블을 별개의 DataFrame으로 올바르게 처리하는 방식은 원본의 구조적 결함보다 뛰어납니다.
-   **누락된 핵심 부분**: **중간 테이블 결과를 다음 단계로 넘겨주는 'Table State Propagation' 메커니즘이 누락**되어 있습니다. 이것이 두 구현 간의 가장 큰 알고리즘적 차이이며, LangGraph 버전의 성능 저하에 결정적인 영향을 미치고 있을 가능성이 매우 높습니다.

따라서, 현재 `langgraph_code`는 원본 알고리즘의 "흐름"을 완전히 동일하게 구현하고 있다고 말하기 어렵습니다. 특히 다단계 추론이 필요한 문제에서 데이터 처리 방식이 근본적으로 다르게 동작합니다.

---

## 상세 비교 분석

### 🟢 유사점: 핵심 아키텍처와 철학

두 구현은 다음과 같은 핵심 철학을 공유합니다.

1.  **ReAct (Reason-Act) 패러다임**: 두 버전 모두 `Thought -> Action -> Observation` 사이클을 기반으로 동작합니다. LangGraph에서는 이 사이클이 노드(Node)와 엣지(Edge)로 명시적으로 표현됩니다.
    *   `planner_node` -> `action_selector_node` -> `tool_nodes` -> `observer_node` -> `termination_checker_node` -> (루프) `planner_node`

2.  **Planner-Coder 아키텍처**: 상위 레벨의 'Planner' LLM이 행동을 계획하고(`planner_node`), 하위 레벨의 'Coder' LLM이 도구 내에서 실제 코드를 생성하는(`retriever_tool_node`, `operator_tool_node`) 구조가 동일합니다.

3.  **Self-Consistency (자가 일관성) 및 투표**:
    *   **Action 선택**: `plan_sample` 수만큼 여러 후보 액션을 생성하고, 그중 가장 일관된 액션을 투표로 선택하는 로직(`action_selector_node`)이 동일하게 구현되어 있습니다.
    *   **Tool 실행**: `code_sample` 수만큼 여러 코드를 생성하고, 실행 결과를 투표로 결정하는 방식도 동일합니다.

### 🔴 차이점: 데이터 흐름 및 상태 관리

알고리즘의 실제 동작에 큰 영향을 미치는 중요한 차이점들이 존재합니다.

**1. 상태 관리 방식 (State Management)**

*   **Original MACT**: `ReactAgent`라는 **클래스(Class)**가 모든 상태(`self.scratchpad`, `self.table_dfs` 등)를 인스턴스 변수로 직접 관리합니다. 이는 상태가 가변적(mutable)이며 클래스 내에서 자유롭게 수정됨을 의미합니다.
*   **LangGraph MACT**: `MACTState`라는 **TypedDict**를 사용합니다. 각 노드는 상태를 입력으로 받아 새로운 상태를 반환하며, 상태 자체가 불변(immutable) 객체처럼 다루어집니다. 이는 더 명시적이고 예측 가능한 흐름을 만들지만, 원본의 유연한 상태 수정을 그대로 옮기기 어렵게 만듭니다.

**2. 테이블 상태 전파 (Table State Propagation) - ⚠️ 가장 결정적인 차이**

*   **Original MACT**:
    *   `self.table_dfs`라는 리스트를 유지하며, `Retrieve`나 `Operate` 도구가 성공적으로 실행될 때마다 **결과로 나온 새로운 DataFrame을 이 리스트에 추가(`append`)**합니다.
    *   다음 단계의 `Calculate`나 `Operate` 도구는 `recent_table_df = self.table_dfs[-1]` 코드를 통해 **가장 최근에 생성된 중간 결과 테이블**을 입력으로 사용합니다.
    *   이를 통해 "1단계에서 테이블을 JOIN하고, 2단계에서 그 JOIN된 결과를 필터링"하는 식의 **연쇄적인 작업(Chained Operations)이 가능**합니다.

*   **LangGraph MACT**:
    *   `Phase 2a`에서 이 로직을 구현하려 했으나, **잘못된 중간 결과가 저장되면서 전체 추론을 망치는 문제(Error Cascading)가 발생**하여 현재는 비활성화된 것으로 보입니다. (`PHASE2A_FAILURE_ANALYSIS.md` 참고)
    *   현재 구현은 각 도구 노드가 상태에 있는 **초기 테이블 목록(`state['tables']`)을 주로 참조**합니다. 중간 결과가 다음 단계의 입력으로 직접적으로, 그리고 안정적으로 전달되는 메커니즘이 **누락되어 있습니다.**
    *   **영향**: 이 차이점 때문에 LangGraph 버전은 복잡한 다단계 추론에서 이전 단계의 결과를 활용하지 못하고, 매번 원본 테이블을 다시 처리하게 되어 성능 저하의 가장 큰 원인이 됩니다.

**3. Multi-Table 처리 전략**

*   **Original MACT**: `tqa_mmqa.py`에서 여러 테이블을 **단순히 텍스트로 이어 붙여(concatenation)** 하나의 거대한 테이블처럼 만듭니다. 이 과정에서 스키마 정보가 손실되고 두 번째 테이블의 헤더가 데이터로 취급되는 등 **구조적으로 잘못된 DataFrame**이 생성됩니다. (`ORIGINAL_MACT_CONCAT_ANALYSIS.md` 참고)

*   **LangGraph MACT**:
    *   `main.py`에서 각 테이블을 별도의 `TableInfo` 객체로 관리합니다.
    *   `tool_nodes.py`의 `_build_multi_table_df_code` 함수는 각 테이블을 `df1`, `df2` 등 별개의 DataFrame 변수로 만들어주는 코드를 생성합니다.
    *   **결론**: LangGraph의 방식이 **구조적으로 훨씬 올바르며**, 실제 `JOIN` 연산을 가능하게 합니다. 이 부분은 원본을 그대로 재현한 것이 아니라 **개선한 것**입니다.

### 요약 비교표

| 기능 | Original MACT (`code`) | LangGraph MACT (`langgraph_code`) | 동일성 및 평가 |
| :--- | :--- | :--- | :--- |
| **전체 흐름** | `while` 루프 기반의 ReAct | `StateGraph` 기반의 ReAct | 🟢 **유사 (철학 공유)** |
| **상태 관리** | 클래스 인스턴스 변수 (Mutable) | `TypedDict` 상태 객체 (Immutable-like) | 🟡 **다름 (구현 방식 차이)** |
| **Action 선택** | `as_reward_fn` (다수결 투표) | `action_selector_node` (다수결 투표) | 🟢 **유사 (로직 재현)** |
| **Tool 실행** | `retriever_tool` 등 함수 | `retriever_tool_node` 등 노드 | 🟢 **유사 (Planner-Coder 구조)** |
| **Hybrid Voting** | Tool 결과 + LLM 예측 결합 | Tool 결과 + LLM 예측 결합 | 🟢 **유사 (Phase 1 Revised에서 재현)** |
| **Table State 전파** | `self.table_dfs`에 중간 결과 누적 | **누락됨 (가장 큰 차이)** | 🔴 **다름 (핵심 로직 누락)** |
| **Multi-Table 처리** | Naive Concatenation (구조적 오류) | 개별 DataFrames (`df1`, `df2`) | 🔵 **다름 (LangGraph가 더 우수)** |
