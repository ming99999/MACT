# 테이블 상태 관리 개선 계획

**날짜**: 2025-10-05
**목표**: 원본 테이블과 중간 결과 테이블을 분리하여 다단계 추론 안정성 및 정확도 향상
**현재 상태**: LangGraph MACT는 모든 테이블(원본, 중간 결과)을 단일 리스트(`state['tables']`)로 관리하여 LLM에게 혼란을 야기하고, 원본 MACT의 '최신 테이블 사용' 로직을 제대로 구현하지 못함.

---

## 🎯 핵심 아이디어

**"원본 테이블과 작업 테이블(중간 결과)을 명시적으로 분리하여 상태를 관리한다."**

- **`original_tables`**: 최초에 로드된 원본 테이블들. 이 상태는 전체 프로세스 동안 변경되지 않음 (Immutable).
- **`intermediate_tables`**: 각 도구 실행 단계에서 생성되는 중간 결과 테이블들. 단계가 진행됨에 따라 이 리스트에 결과가 누적됨.

---

## 🔧 구체적인 구현 계획

### 1. `MACTState` 스키마 수정 (`src/mact_langgraph/state.py`)

기존의 `tables` 필드를 두 개의 명확한 필드로 분리합니다.

```python
# Before
class MACTState(TypedDict):
    # ...
    tables: List[Dict[str, Any]]
    # ...

# After
class MACTState(TypedDict):
    # ...
    original_tables: List[Dict[str, Any]]      # ✅ 원본 테이블 (불변)
    intermediate_tables: List[Dict[str, Any]]  # ✅ 중간 결과 테이블 (가변)
    # ...
```

`create_initial_state` 함수도 이에 맞게 수정하여, 초기에는 `original_tables`만 채우고 `intermediate_tables`는 빈 리스트로 시작합니다.

### 2. 도구 노드(`tool_nodes.py`) 수정

`retriever_tool_node`와 `operator_tool_node`의 로직을 다음과 같이 변경합니다.

#### **입력 테이블 선택 로직 개선**

도구가 코드 생성을 위해 LLM을 호출하기 전에, 어떤 테이블을 컨텍스트로 제공할지 결정하는 로직을 명확하게 합니다.

```python
# tool_nodes.py 내부

# 1. 상태에서 테이블 분리
original_tables = get_original_tables_from_state(state)
intermediate_tables = get_intermediate_tables_from_state(state)

# 2. 작업 대상 테이블 결정 (원본 MACT 방식 모방)
if intermediate_tables:
    # 중간 결과가 있으면, 가장 최근의 것을 'df'로 사용
    working_df_code = intermediate_tables[-1].df_code
else:
    # 없으면, 원본 테이블 중 첫 번째를 'df'로 사용
    working_df_code = original_tables[0].df_code if original_tables else ""

# 3. Coder LLM을 위한 실행 환경 구성
# 원본 테이블들은 df_orig_1, df_orig_2 등으로, 작업 테이블은 df로 명확히 구분
exec_env_code = build_execution_environment(original_tables, working_df_code)
```

#### **출력 테이블 저장 로직 수정**

도구가 성공적으로 새로운 테이블을 생성했을 때, `intermediate_tables` 리스트에만 추가합니다.

```python
# tool_nodes.py 내부

# 도구 실행 후...
if new_table_info:
    # ✅ intermediate_tables에만 새로운 중간 결과를 추가
    updated_state["intermediate_tables"] = state.get("intermediate_tables", []) + [new_table_info.to_dict()]
```

### 3. 프롬프트 개선 (`prompt_utils.py`)

Coder LLM에게 제공되는 프롬프트가 훨씬 명확해집니다.

```
# 개선된 프롬프트 예시

# 사용 가능한 DataFrame:
# - df_orig_1: 원본 'department' 테이블
# - df_orig_2: 원본 'management' 테이블
# - df: 이전 단계에서 생성된 JOIN 결과 테이블

# 지시사항: "df"에서 'budget'이 100 이상인 부서를 필터링하세요.

# 생성될 코드:
new_table = df[df['budget'] > 100]
```
LLM은 이제 `df`가 무엇을 의미하는지 명확하게 인지하고 코드를 생성할 수 있습니다.

---

## 📈 예상되는 성능 향상

1.  **정확도 향상**: LLM이 참조할 테이블의 모호성이 사라져, 올바른 DataFrame에 대한 연산을 수행할 확률이 크게 증가합니다. 특히 다단계 추론 문제에서 연쇄적인 오류가 발생할 가능성이 줄어듭니다.
2.  **안정성 증가**: 상태 전파가 명확해져 에이전트의 동작을 예측하고 디버깅하기 쉬워집니다.
3.  **원본 MACT와의 패리티(Parity) 확보**: 원본 MACT의 핵심적인 다단계 처리 로직(`self.table_dfs`)을 LangGraph 환경에 맞게 성공적으로 이식하게 됩니다.

---

## 🧪 검증 계획

1.  **신규 브랜치 생성**: `feature/separate-table-state`
2.  **코드 수정**: 위에 계획된 대로 `state.py`, `tool_nodes.py`, `prompt_utils.py` 등 관련 파일 수정
3.  **단위 테스트**: 수정된 각 노드가 올바른 상태를 반환하는지 확인
4.  **통합 테스트**: `mmqa_samples.json` 데이터셋으로 전체 워크플로우를 실행하여 기존 버전(Phase 1 Revised)과 성능 비교
5.  **결과 분석**: 정확도, 평균 단계 수, 실패 유형 등을 비교하여 개선 효과 정량화

**성공 기준**: 현재 28.6%인 정확도를 40% 이상으로 끌어올리는 것을 목표로 합니다.
