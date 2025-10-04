# Phase 2C 개선 계획: "단순하고 실용적인 MACT"

**작성일**: 2025-10-04
**현재 상태**: Phase 1 Revised (28.6%)
**목표**: 원본 MACT 수준 (58.8%) 달성
**방향**: **복잡도 최소화 + 실용성 극대화**

---

## 🎯 핵심 원칙: "Simple is Better"

Phase 2 실패에서 배운 교훈:
- ❌ 복잡한 추상화는 성능 저하
- ❌ 변수명 변경은 LLM 혼란
- ❌ 긴 프롬프트는 역효과
- ✅ **원본 MACT의 단순함을 따라야 함**

---

## 📋 4단계 개선 계획

### Step 1: 변수명 일관성 개선 (예상 +5-8%p)

#### 문제점
```python
# 현재 Phase 1:
table_df_code = tables[-1].df_code
# → df_code 내용: "df = pd.DataFrame(...)"

# Multi-table 시:
# table 0: "df1 = pd.DataFrame(...)"  ❌
# table 1: "df2 = pd.DataFrame(...)"  ❌
```

#### 개선안: 원본 MACT 방식
```python
# 원본 MACT:
def table2df(rows):
    """항상 'df'로 시작하는 코드 생성"""
    return f"df = pd.DataFrame({content}, columns={columns})"
    # ✅ 일관성

# Phase 2C 개선:
def get_current_df_code(state):
    """최신 테이블을 항상 'df' 변수로 제공"""
    tables = get_tables_from_state(state)
    if not tables:
        return ""

    latest_table = tables[-1]

    # CRITICAL: 항상 'df' 변수명 사용
    df_code = f"df = pd.DataFrame(\n"
    df_code += f"    {latest_table.content},\n"
    df_code += f"    columns={latest_table.columns}\n"
    df_code += f")"

    return df_code  # ✅ 항상 'df = ...' 형태
```

**수정 파일**:
- `src/mact_langgraph/utils/table_utils.py`
  - `table2df()` 함수 단순화
  - 항상 `df` 변수명 사용하도록 강제

**테스트 방법**:
```bash
# Step 1 개선만 적용 후 테스트
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_model gpt-3.5-turbo --code_model gpt-3.5-turbo \
  --plan_sample 3 --code_sample 3 \
  --output_dir test_phase2c_step1_variable_consistency
```

**예상 결과**: 28.6% → 33-36%

---

### Step 2: 프롬프트 단순화 (예상 +3-5%p)

#### 문제점
```python
# 현재 프롬프트 (복잡):
REACT_SYSTEM_PROMPT = """You are an expert at answering questions...

IMPORTANT: You MUST use the provided tools...
REQUIRED FORMAT: ...
RULES:
1. ALWAYS start by examining...
2. NEVER use Finish as your first action...
3. You must use at least one...
...
(총 200+ 라인)
"""
```

#### 개선안: 원본 MACT 스타일
```python
# 원본 MACT (간결):
REACT_INSTRUCTION = """Solve a table question answering task with interleaving Thought, Action, Observation steps.

Action can be four types:
(1) Retrieve[condition], which retrieves data from the table.
(2) Calculate[expression], which performs calculations.
(3) Operate[operation], which performs table operations (JOIN, GROUP BY, etc.).
(4) Finish[answer], which returns the final answer.

Here are some examples:
{examples}
(END OF EXAMPLES)

Table:
{table}

Question: {question}
{scratchpad}"""
```

**핵심 변경**:
1. **간결함**: 50-70 라인으로 축소
2. **명확함**: 각 도구 1줄 설명
3. **예제 중심**: Few-shot 예제 강화
4. **불필요한 규칙 제거**: "MUST", "NEVER" 등 제거

**수정 파일**:
- `src/mact_langgraph/utils/prompt_utils.py`
  - `REACT_SYSTEM_PROMPT` 단순화
  - `build_react_prompt()` 간소화

**테스트 방법**:
```bash
# Step 1 + Step 2 적용 후 테스트
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_model gpt-3.5-turbo --code_model gpt-3.5-turbo \
  --plan_sample 3 --code_sample 3 \
  --output_dir test_phase2c_step2_prompt_simplification
```

**예상 결과**: 33-36% → 36-41%

---

### Step 3: Multi-table 처리 간결화 (예상 +5-8%p)

#### 문제점
```python
# 현재: Multi-table 감지 후 Operator로 delegation
if is_multi_table_query(instruction):
    return operator_tool_node(state)  # ❌ 복잡한 로직
```

#### 개선안: Single-table 기본, Multi-table도 동일 구조
```python
def retriever_tool_node(state):
    """Single/Multi-table 모두 동일하게 처리"""
    tables = get_tables_from_state(state)
    instruction = state["current_argument"]

    # 1. 현재 활성 테이블(들) 코드 생성
    df_setup_code = build_simple_df_setup(tables)
    # ✅ 단순: 최근 1-2개 테이블만 'df' 변수로 제공

    # 2. 프롬프트 생성 (간결)
    prompt = f"""
{df_setup_code}

# Task: {instruction}
# Return: new_table = df[...] or df.merge(...)

new_table = df  # Your code here
"""

    # 3. 코드 생성 및 실행
    codes = await generate_code_batch(prompt, state["code_sample"])

    # 4. Majority voting (단순)
    best_result = majority_vote(results)

    # 5. 결과를 'df'로 덮어쓰기 (원본 MACT 방식)
    new_table_info = create_table_from_result(best_result)
    state["tables"][-1] = new_table_info  # ✅ 덮어쓰기 (append 아님!)

    return state
```

**핵심 변경**:
1. **단일 구조**: Retrieve와 Operate 구분 없음
2. **덮어쓰기**: 새 테이블로 기존 테이블 대체 (원본 MACT 방식)
3. **최소 컨텍스트**: 최근 1-2개 테이블만 제공

**수정 파일**:
- `src/mact_langgraph/nodes/tool_nodes.py`
  - `retriever_tool_node()` 단순화
  - Multi-table delegation 로직 제거
  - `build_simple_df_setup()` 함수 추가

**테스트 방법**:
```bash
# Step 1 + Step 2 + Step 3 적용 후 테스트
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_model gpt-3.5-turbo --code_model gpt-3.5-turbo \
  --plan_sample 3 --code_sample 3 \
  --output_dir test_phase2c_step3_multitable_simplification
```

**예상 결과**: 36-41% → 41-49%

---

### Step 4: Step 1 조기 종료 방지 강화 (예상 +3-5%p)

#### 문제점
```python
# Phase 2에서 발견:
# Step 1에서 5건 조기 종료 (23.8%)
# 원인: 프롬프트 복잡도 + Finish 유혹
```

#### 개선안: 명확한 가이드 + 강제 검증
```python
def action_selector_node(state):
    """Step 1-2에서 Finish 블로킹 강화"""
    candidates = get_candidates_from_state(state)
    current_step = state["current_step"]

    # CRITICAL: Step 1에서 Finish 완전 차단
    if current_step == 1:
        # Finish 액션 모두 제거
        candidates = [c for c in candidates if c.action_type != ActionType.FINISH]

        if not candidates:
            # Fallback: 강제로 Retrieve 추가
            fallback = ActionCandidate(
                thought="I need to examine the table data first.",
                action="Retrieve[Show all data]",
                action_type=ActionType.RETRIEVE,
                argument="Show all data",
                score=0.0
            )
            candidates = [fallback]

        log = f"🚫 Step 1: Blocked ALL Finish actions, forcing data examination"
        state["execution_log"].append(log)

    # Step 2에서도 도구 미사용 시 Finish 차단
    if current_step == 2:
        has_used_tools = len(state["tool_results"]) > 0
        if not has_used_tools:
            candidates = [c for c in candidates if c.action_type != ActionType.FINISH]
            log = f"🚫 Step 2: Blocked Finish (no tools used yet)"
            state["execution_log"].append(log)

    # Consistency reward로 선택
    selected = select_by_consistency(candidates)
    return update_state_with_selected_action(state, selected)
```

**추가 개선**:
1. **Few-shot 예제**: Step 1에서 Retrieve/Operate 사용하는 예제만 제공
2. **시스템 메시지**: "You MUST examine data before answering" (간결하게)

**수정 파일**:
- `src/mact_langgraph/nodes/core_nodes.py`
  - `action_selector_node()` 강화
  - Step 1-2 Finish 차단 로직 추가

**테스트 방법**:
```bash
# 전체 Step 1-4 적용 후 최종 테스트
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_model gpt-3.5-turbo --code_model gpt-3.5-turbo \
  --plan_sample 3 --code_sample 3 \
  --output_dir test_phase2c_step4_early_termination_prevention
```

**예상 결과**: 41-49% → 45-54%

---

## 🔍 단계별 코드 개선 상세

### Step 1: 변수명 일관성 개선

#### 수정 1: `table_utils.py` - `table2df()` 함수
```python
# Before (복잡):
def table2df(rows, table_name="df"):
    # 다양한 변수명 생성 가능
    return f"{table_name} = pd.DataFrame(...)"

# After (단순):
def table2df(rows):
    """항상 'df' 변수명 사용"""
    if not rows or len(rows) == 0:
        return "df = pd.DataFrame()"

    columns = list(rows[0].keys()) if isinstance(rows[0], dict) else []
    content = [[row.get(col, '') for col in columns] for row in rows]

    # CRITICAL: 항상 'df'로 시작
    return f"df = pd.DataFrame({content}, columns={columns})"
```

#### 수정 2: `tool_nodes.py` - DataFrame 코드 생성
```python
def get_current_df_code(state):
    """최신 테이블을 'df' 변수로 제공"""
    tables = get_tables_from_state(state)
    if not tables:
        return "df = pd.DataFrame()"

    latest = tables[-1]

    # 원본 MACT 방식: 항상 'df' 사용
    df_code = f"df = pd.DataFrame(\n"
    df_code += f"    {latest.content},\n"
    df_code += f"    columns={latest.columns}\n"
    df_code += f")"

    return df_code
```

---

### Step 2: 프롬프트 단순화

#### 수정 1: `prompt_utils.py` - REACT 프롬프트
```python
# Before: 200+ 라인의 복잡한 프롬프트

# After: 원본 MACT 스타일 (50-70 라인)
REACT_INSTRUCTION = """Solve a table question answering task with interleaving Thought, Action, Observation steps.

Available actions:
(1) Retrieve[condition] - Get data from the table based on condition
(2) Calculate[expression] - Perform mathematical calculations
(3) Operate[operation] - Perform JOIN, GROUP BY, or other operations
(4) Finish[answer] - Return the final answer

Here are some examples:
{examples}
(END OF EXAMPLES)

Table:
{table}

Question: {question}
{scratchpad}"""

def build_react_prompt(question, table_data, scratchpad="", examples=""):
    """간결한 프롬프트 생성"""
    return REACT_INSTRUCTION.format(
        examples=examples or DEFAULT_EXAMPLES,
        table=table_data,
        question=question,
        scratchpad=scratchpad
    )
```

#### 수정 2: Code generation 프롬프트
```python
# Before: 복잡한 힌트와 예제

# After: 최소한의 정보만
def build_code_generation_prompt(instruction, df_setup_code):
    """단순하고 명확한 코드 생성 프롬프트"""
    return f"""
{df_setup_code}

# Task: {instruction}
# Write Python code to accomplish the task
# Assign the result to 'new_table' variable

new_table = df  # Your code here
"""
```

---

### Step 3: Multi-table 처리 간결화

#### 수정 1: `tool_nodes.py` - Single structure
```python
def retriever_tool_node(state):
    """Retrieve tool - single/multi-table 동일 처리"""
    tables = get_tables_from_state(state)
    instruction = state["current_argument"]

    # 1. 단순한 DataFrame 설정
    if len(tables) == 1:
        # Single table: 기존 방식
        df_code = get_current_df_code(state)
    else:
        # Multi-table: 최근 2개만 제공
        recent_tables = tables[-2:]
        df_code = ""
        for i, table in enumerate(recent_tables):
            df_code += f"df{i} = pd.DataFrame({table.content}, columns={table.columns})\n"
        df_code += "\n# Merge if needed:\n# df = df0.merge(df1, on='key')\n"
        df_code += "df = df0  # or merged result\n"

    # 2. 간결한 프롬프트
    prompt = build_code_generation_prompt(instruction, df_code)

    # 3. 코드 생성 (batch)
    codes = await generate_code_batch(prompt, state["code_sample"])

    # 4. 실행 및 majority voting
    results = [execute_code(code, df_code) for code in codes]
    best_result = majority_vote([r for r in results if r.success])

    # 5. 결과 저장 (덮어쓰기)
    if best_result:
        new_table = create_table_from_result(best_result)
        # CRITICAL: 덮어쓰기 (원본 MACT 방식)
        state["tables"][-1] = new_table.to_dict()

    return state
```

#### 제거할 로직
```python
# ❌ 제거: Multi-table detection and delegation
if is_multi_table_query(instruction):
    return operator_tool_node(state)

# ❌ 제거: 복잡한 df_context.py
# build_df_context(...) 함수 전체
```

---

### Step 4: Step 1 조기 종료 방지

#### 수정: `core_nodes.py` - action_selector_node
```python
async def action_selector_node(state: MACTState) -> MACTState:
    """Select best action with early termination prevention"""
    candidates = get_candidates_from_state(state)
    current_step = state["current_step"]
    logs = []

    # 🚫 Step 1: BLOCK ALL Finish actions
    if current_step == 1:
        finish_count = sum(1 for c in candidates if c.action_type == ActionType.FINISH)
        candidates = [c for c in candidates if c.action_type != ActionType.FINISH]

        if finish_count > 0:
            logs.append(f"🚫 Step 1: Blocked {finish_count} Finish action(s) - Must examine data first")

        # Fallback if all were Finish
        if not candidates:
            fallback = ActionCandidate(
                thought="I need to examine the table data before answering.",
                action="Retrieve[Show all data]",
                action_type=ActionType.RETRIEVE,
                argument="Show all data",
                score=0.0
            )
            candidates = [fallback]
            logs.append("⚠️ Step 1: All actions were Finish - Added fallback Retrieve")

    # 🚫 Step 2: BLOCK Finish if no tools used
    elif current_step == 2:
        has_used_tools = (
            len(state.get("tool_results", [])) > 0 or
            len(state.get("table_operations", [])) > 0
        )

        if not has_used_tools:
            finish_count = sum(1 for c in candidates if c.action_type == ActionType.FINISH)
            candidates = [c for c in candidates if c.action_type != ActionType.FINISH]

            if finish_count > 0:
                logs.append(f"🚫 Step 2: Blocked {finish_count} Finish action(s) - No tools used yet")

    # Consistency reward 기반 선택
    if candidates:
        selected = select_by_consistency_reward(candidates)
    else:
        # Should not happen, but safety fallback
        selected = ActionCandidate(
            thought="Examining data...",
            action="Retrieve[all]",
            action_type=ActionType.RETRIEVE,
            argument="all",
            score=0.0
        )

    updated_state = update_state_with_selected_action(state, selected)
    updated_state["execution_log"] = updated_state["execution_log"] + logs

    return updated_state
```

---

## 📊 예상 성능 개선 경로

| Step | 수정 내용 | 예상 정확도 | 누적 개선 | 테스트 디렉토리 |
|------|-----------|-------------|-----------|-----------------|
| **Baseline** | Phase 1 Revised | 28.6% | - | - |
| **Step 1** | 변수명 일관성 | 33-36% | +5-8%p | test_phase2c_step1 |
| **Step 2** | 프롬프트 단순화 | 36-41% | +8-13%p | test_phase2c_step2 |
| **Step 3** | Multi-table 간결화 | 41-49% | +13-21%p | test_phase2c_step3 |
| **Step 4** | 조기 종료 방지 | 45-54% | +17-26%p | test_phase2c_step4_final |

**목표**: 45-54% (원본 MACT 58.8%에 근접)

---

## 🧪 테스트 계획

### 각 Step별 개별 테스트
```bash
# Step 1: 변수명 일관성
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_model gpt-3.5-turbo --code_model gpt-3.5-turbo \
  --plan_sample 3 --code_sample 3 \
  --output_dir test_phase2c_step1_variable_consistency

# Step 2: 프롬프트 단순화 (Step 1 포함)
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_model gpt-3.5-turbo --code_model gpt-3.5-turbo \
  --plan_sample 3 --code_sample 3 \
  --output_dir test_phase2c_step2_prompt_simplification

# Step 3: Multi-table 간결화 (Step 1-2 포함)
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_model gpt-3.5-turbo --code_model gpt-3.5-turbo \
  --plan_sample 3 --code_sample 3 \
  --output_dir test_phase2c_step3_multitable_simplification

# Step 4: 최종 통합 (Step 1-4 모두 포함)
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_model gpt-3.5-turbo --code_model gpt-3.5-turbo \
  --plan_sample 3 --code_sample 3 \
  --output_dir test_phase2c_step4_final
```

### 비교 분석
```python
# 결과 비교 스크립트
python scripts/compare_phase2c_results.py \
  --baseline test_phase1_gpt35_final \
  --step1 test_phase2c_step1_variable_consistency \
  --step2 test_phase2c_step2_prompt_simplification \
  --step3 test_phase2c_step3_multitable_simplification \
  --step4 test_phase2c_step4_final \
  --output logs_ai/PHASE3_RESULTS_COMPARISON.md
```

---

## ✅ 진행 상황 업데이트 (2025-10-04)

### Step 1: 변수명 일관성 개선 - ✅ 완료

**구현 내용**:
- `tool_nodes.py`: `_build_multi_table_df_code()` 함수 수정 완료
  - Single table: 최신 테이블을 `df`로 제공
  - Multi-table: 이전 테이블들은 `df_{table_name}`, 최신 테이블은 `df`로 제공
  - 테이블 이름 기반 변수명으로 안정성 확보

**테스트 결과** (test_phase2c_step1_variable_consistency):
- **정확도**: 42.9% (9/21 correct) ✅
- **개선폭**: +14.3%p (vs Phase 1 Revised 28.6%)
- **예상치 대비**: +14.3%p (예상 +5-8%p를 **2배 초과 달성**)
- **에러율**: 0.0% (안정성 유지)
- **조기 종료**: Step 1에서 1건만 (vs Phase 2에서 5건)
- **실행 시간**: 282.7초 (37% 단축)

**성공 요인**:
1. 테이블명 기반 변수명 (`df_{table_name}`)으로 안정성 확보
2. 최신 테이블은 항상 `df`로 단순화 (원본 MACT 철학)
3. 프롬프트 복잡도 증가 없이 변수명만 개선

**다음 단계**: Step 2 프롬프트 단순화 진행

---

## 📝 체크리스트

### Step 1: 변수명 일관성
- [x] `tool_nodes.py`: `_build_multi_table_df_code()` 수정 완료
- [x] 테스트 실행 완료
- [x] 결과 분석 완료 (**42.9%** - 예상치 초과 달성 ✅)
- [x] Git 커밋 및 문서 업데이트

### Step 2: 프롬프트 단순화
- [ ] `prompt_utils.py`: `REACT_INSTRUCTION` 단순화
- [ ] `prompt_utils.py`: `build_code_generation_prompt()` 단순화
- [ ] 불필요한 힌트/규칙 제거
- [ ] 테스트 실행
- [ ] 결과 분석 (예상: 33-36% → 36-41%)

### Step 3: Multi-table 간결화
- [ ] `tool_nodes.py`: `retriever_tool_node()` 단순화
- [ ] Multi-table delegation 로직 제거
- [ ] `df_context.py` 삭제 (사용 안 함)
- [ ] 테스트 실행
- [ ] 결과 분석 (예상: 36-41% → 41-49%)

### Step 4: 조기 종료 방지
- [ ] `core_nodes.py`: `action_selector_node()` 강화
- [ ] Step 1-2 Finish 차단 로직 추가
- [ ] Fallback 로직 추가
- [ ] 테스트 실행
- [ ] 결과 분석 (예상: 41-49% → 45-54%)

### 최종 검증
- [ ] 전체 통합 테스트
- [ ] 성능 비교 분석
- [ ] 원본 MACT와 비교
- [ ] 문서화

---

## 🎯 성공 기준

### Step 1 완료 후
- ✅ 변수명 에러 0건 (`name 'df' is not defined` 없음)
- ✅ 정확도 > 33% (+5%p 이상)

### Step 2 완료 후
- ✅ Step 1 조기 종료 < 2건 (현재 5건)
- ✅ 정확도 > 36% (+8%p 이상)

### Step 3 완료 후
- ✅ Multi-table JOIN 성공률 > 60%
- ✅ 정확도 > 41% (+13%p 이상)

### Step 4 완료 후
- ✅ Step 1 조기 종료 = 0건
- ✅ 정확도 > 45% (+17%p 이상)
- ✅ 원본 MACT (58.8%)에 근접

---

## 🚀 실행 순서

1. ✅ **계획 수립** (현재 단계)
2. ⏭️ **Step 1 구현** → 테스트 → 분석
3. ⏭️ **Step 2 구현** → 테스트 → 분석
4. ⏭️ **Step 3 구현** → 테스트 → 분석
5. ⏭️ **Step 4 구현** → 테스트 → 분석
6. ⏭️ **통합 비교** → 최종 문서화

**예상 소요 시간**: 1-2일 (aggressive schedule)

---

**문서 작성 완료**: 2025-10-04
**다음 작업**: Step 1 구현 시작 (변수명 일관성)
**목표**: 단순하고 실용적인 MACT 구현으로 45-54% 달성
