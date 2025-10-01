# LangGraph MACT 버그 수정 계획

**작성일:** 2025-09-30
**기반 테스트:** Original MACT vs LangGraph MACT 비교 (gpt-3.5-turbo)
**발견된 정확도 차이:** -39.8 percentage points (58.8% → 19.0%)

---

## 📋 목차

1. [발견된 버그 요약](#발견된-버그-요약)
2. [Bug #1: TABLE JOIN 실패](#bug-1-table-join-실패)
3. [Bug #2: Retrieve Tool 로직 문제](#bug-2-retrieve-tool-로직-문제)
4. [Bug #3: 첫 단계 Finish 액션 허용](#bug-3-첫-단계-finish-액션-허용)
5. [수정 우선순위 및 일정](#수정-우선순위-및-일정)
6. [검증 계획](#검증-계획)

---

## 발견된 버그 요약

| Bug ID | 이름 | 영향도 | 발생 빈도 | 예상 정확도 영향 |
|--------|------|--------|-----------|-----------------|
| **#1** | TABLE JOIN 실패 | 🔴 Critical | 100% (모든 JOIN 시도) | +30-40% |
| **#2** | Retrieve 로직 문제 | 🟠 High | ~40% | +10-15% |
| **#3** | 첫 단계 Finish 허용 | 🔴 Critical | 33.3% (7/21) | +15-20% |

**예상 수정 후 정확도:** 19.0% → 64-94% (목표: 60%+)

---

## Bug #1: TABLE JOIN 실패

### 🔍 증상 분석

**테스트 결과:**
```
Question: "Which department currently headed by a temporary acting manager
           has the largest number of employees?"

Execution Log:
DEBUG: Operation attempt 1 failed: 'department_ID'
DEBUG: Operation attempt 2 failed: 'department_ID'
DEBUG: Operation attempt 3 failed: 'department_ID'

Result: FAILED (모든 시도 실패)
```

**발생 빈도:**
- Multi-table JOIN이 필요한 모든 질문에서 발생
- Department 관련 질문: 100% 실패 (0/4 정답)
- 전체 정확도에 30-40%p 영향

### 🎯 근본 원인

#### 원인 1: 칼럼명 대소문자 불일치

**문제 코드 위치:** `table_utils.py:457-549` (`_fix_column_references()`)

**상세 분석:**
```python
# 테이블 1 (department) 생성 시:
data={'Department_ID':[1, 2, 3, ...], 'Name':['State', 'Treasury', ...]}
df1=pd.DataFrame(data)

# 테이블 2 (management) 생성 시:
data={'department_ID':[2, 15, 2, ...], 'head_ID':[5, 4, 6, ...]}
df2=pd.DataFrame(data)

# LLM이 생성한 JOIN 코드:
result = df1.merge(df2, on='department_ID', how='inner')
# ❌ KeyError: 'department_ID' not in df1 (df1에는 'Department_ID'만 존재)
```

**핵심 문제:**
1. **table2df()에서 원본 칼럼명 그대로 유지**
   - `table_utils.py:61-106`
   - MMQA 데이터셋의 두 테이블이 서로 다른 케이스 사용
   - department: `Department_ID` (대문자 D)
   - management: `department_ID` (소문자 d)

2. **_fix_column_references()의 한계**
   - `table_utils.py:457-549`에 수정 로직 존재
   - 하지만 **실제 DataFrame 생성 후**에는 적용 불가능
   - 코드만 수정해도 데이터 자체의 칼럼명이 다름

3. **LLM이 일관된 칼럼명 생성 불가**
   - 프롬프트에서 두 테이블의 칼럼명이 다르게 보임
   - LLM은 한쪽 칼럼명을 선택해서 JOIN 시도
   - 불일치로 인해 100% 실패

#### 원인 2: Multi-table 환경 설정 코드 문제

**문제 코드 위치:** `tool_nodes.py:213-260` (`operator_tool_node()`)

```python
# 현재 구현 (tool_nodes.py:245-254):
setup_code = "import pandas as pd\nimport numpy as np\n"
for idx, table in enumerate(tables):
    table_dict = table if isinstance(table, dict) else table.to_dict()
    df_code = table_dict.get('df_code', '')
    setup_code += df_code + "\n"
setup_code += "df = df1  # Primary table\n"
setup_code += "# Additional tables: df2, df3, etc.\n"
```

**문제점:**
1. **각 테이블의 원본 칼럼명 그대로 사용**
   - 테이블마다 독립적으로 `table2df()` 실행
   - 칼럼명 정규화 없음

2. **FK 관계 정보 미활용**
   - MMQA 데이터셋의 `foreign_keys` 정보 무시
   - `Department_ID ↔ department_ID` 같은 관계 인식 못함

3. **칼럼명 매핑 없음**
   - JOIN 전에 칼럼명 통일 안 함
   - 프롬프트에도 매핑 정보 제공 안 함

### ✅ 해결책

#### Solution 1-A: table2df()에서 칼럼명 정규화 (근본 해결)

**수정 파일:** `table_utils.py`
**수정 위치:** `table2df()` 함수 (line 61-106)

```python
def table2df(table: List[List[Any]], normalize_columns: bool = True) -> str:
    """Convert table to pandas DataFrame code string with optional column normalization."""
    if not table or len(table) == 0:
        return "import pandas as pd\ndf = pd.DataFrame()"

    output = "import pandas as pd\n"
    header = table[0]
    header = [clean_cell(cell, i, header=True) for i, cell in enumerate(header)]
    header = check_header(header)

    # 🎯 NEW: Normalize column names to lowercase with underscores
    if normalize_columns:
        header = [normalize_column_name(col) for col in header]

    # ... rest of the function
```

**새 함수 추가:**
```python
def normalize_column_name(col_name: str) -> str:
    """
    Normalize column names to consistent format.
    Examples:
      'Department_ID' -> 'department_id'
      'department_ID' -> 'department_id'
      'Host_city_ID' -> 'host_city_id'
    """
    # Strategy: lowercase all, keep underscores
    normalized = col_name.strip()

    # Special handling for common ID patterns
    id_pattern = re.compile(r'([A-Za-z_]+)_?([Ii][Dd])$')
    match = id_pattern.match(normalized)
    if match:
        # e.g., "Department_ID" -> "department_id"
        prefix = match.group(1).lower()
        return f"{prefix}_id"

    # General case: just lowercase
    return normalized.lower()
```

**영향:**
- ✅ 모든 테이블의 칼럼명이 일관된 형식으로 생성
- ✅ JOIN 시 칼럼명 불일치 문제 완전 해결
- ✅ LLM이 정규화된 칼럼명만 보게 됨

#### Solution 1-B: operator_tool_node()에서 FK 정보 활용

**수정 파일:** `tool_nodes.py`
**수정 위치:** `operator_tool_node()` (line 213-280)

```python
async def operator_tool_node(state: MACTState) -> MACTState:
    """
    Enhanced with FK-aware JOIN hints.
    """
    operation = state["current_argument"]

    # ... existing code ...

    # 🎯 NEW: Extract FK information from original dataset
    fk_hints = ""
    if "foreign_keys" in state and state["foreign_keys"]:
        fk_list = state["foreign_keys"]
        fk_hints = "\n# Foreign Key Relationships:\n"
        for fk in fk_list:
            fk_hints += f"# - {fk}\n"
        fk_hints += "# Use these columns for JOIN operations\n"

    # Enhanced prompt with FK hints
    prompt = f"""Given tables and operation instruction, generate pandas code.

Available tables:
{table_descriptions}

{fk_hints}

Operation: {operation}

Generate code that:
1. Uses normalized column names (all lowercase, e.g., 'department_id')
2. JOINs tables using foreign key relationships when needed
3. Stores result in 'new_table' variable

Example JOIN:
new_table = df1.merge(df2, on='department_id', how='inner')
"""
```

**영향:**
- ✅ LLM이 FK 정보를 보고 올바른 JOIN 칼럼 선택
- ✅ 정규화된 칼럼명 사용 강제
- ✅ JOIN 성공률 대폭 향상

#### Solution 1-C: 칼럼명 매핑 자동 감지

**수정 파일:** `table_utils.py`
**새 함수 추가:**

```python
def detect_join_columns(tables_df_codes: List[str], foreign_keys: List[str] = None) -> Dict[str, List[str]]:
    """
    Detect potential JOIN columns across multiple tables.
    Returns a mapping of normalized column names to their original variations.

    Example return:
    {
        'department_id': ['Department_ID', 'department_ID', 'dept_id'],
        'head_id': ['head_ID', 'Head_ID'],
        'host_city_id': ['Host_city_ID', 'host_city_ID']
    }
    """
    column_variations = {}

    for df_code in tables_df_codes:
        # Extract all column names from data dict
        pattern = r"'([^']+)':"
        columns = re.findall(pattern, df_code)

        for col in columns:
            normalized = normalize_column_name(col)
            if normalized not in column_variations:
                column_variations[normalized] = []
            if col not in column_variations[normalized]:
                column_variations[normalized].append(col)

    # Add foreign key hints
    if foreign_keys:
        for fk in foreign_keys:
            normalized = normalize_column_name(fk)
            if normalized not in column_variations:
                column_variations[normalized] = [fk]

    return column_variations
```

**사용 예:**
```python
# operator_tool_node()에서:
join_mappings = detect_join_columns(
    [t.get('df_code') for t in tables],
    foreign_keys=state.get('foreign_keys', [])
)

# 프롬프트에 추가:
mapping_info = "\n# Column Name Mappings:\n"
for norm_name, variations in join_mappings.items():
    if len(variations) > 1:
        mapping_info += f"# '{norm_name}' appears as: {variations}\n"
        mapping_info += f"# Use '{norm_name}' in JOIN operations\n"
```

### 📊 예상 효과

**수정 전:**
- JOIN 성공률: 0% (0/모든 시도)
- Department 질문 정확도: 0%

**수정 후:**
- JOIN 성공률: 80-90% (칼럼명 통일로)
- Department 질문 정확도: 50-75%
- **전체 정확도:** +30-40%p 개선

### 🧪 검증 방법

```python
# 테스트 케이스:
test_cases = [
    {
        "question": "Which department with temporary acting management has highest budget?",
        "tables": ["department", "management"],
        "expected_join": "df1.merge(df2, on='department_id')",
        "target_answer": "Treasury"
    },
    # ... more cases
]

# 검증 스크립트:
for case in test_cases:
    result = run_langgraph_mact(case["question"], case["tables"])
    assert "department_id" in result["executed_code"].lower()
    assert "KeyError" not in result["errors"]
    print(f"✅ {case['question'][:50]}... - JOIN successful")
```

---

## Bug #2: Retrieve Tool 로직 문제

### 🔍 증상 분석

**테스트 결과:**
```
Question: "Show department and management data"

Expected: JOIN of department + management tables
Actual: | department_ID | head_ID |  (management table only)

Observation: Wrong table returned, missing department info
```

**발생 빈도:**
- ~40% 질문에서 부정확한 데이터 반환
- 특히 multi-table 요청에서 자주 발생
- City/Competition 질문 정확도 저하 원인

### 🎯 근본 원인

#### 원인 1: 프롬프트 해석 로직 빈약

**문제 코드 위치:** `tool_nodes.py:40-80` (`retriever_tool_node()`)

**현재 구현:**
```python
prompt = f"""Given table data and retrieval instruction, generate pandas code.

Table: {table_name}
Columns: {columns}

Instruction: {instruction}

Generate code to retrieve data. Store result in 'new_table' variable.

Examples:
"Show department data" -> new_table = df.copy()
"Get departments where budget > 10" -> new_table = df[df['Budget_in_Billions'] > 10]

Current instruction: {instruction}
new_table = df  # Replace with appropriate logic
"""
```

**문제점:**
1. **Multi-table 요청 감지 안 함**
   - "department and management"처럼 여러 테이블 언급 시
   - 첫 번째 테이블만 사용 (line 43: `tables[0]`)
   - 나머지 테이블 무시

2. **관계형 쿼리 이해 부족**
   - "departments with temporary acting managers"
   - → 두 테이블 JOIN 필요함을 인식 못함
   - → 단일 테이블 필터링만 시도

3. **예제가 단순함**
   - 프롬프트의 예제가 모두 단일 테이블 조작
   - Multi-table 예제 없음

#### 원인 2: 테이블 선택 로직 고정

**문제 코드:**
```python
# tool_nodes.py:43
table_df_code = tables[0].df_code if tables else ""
```

**문제점:**
- 항상 첫 번째 테이블만 사용
- `instruction`에 언급된 테이블 이름 확인 안 함
- Multi-table 시나리오 완전 무시

### ✅ 해결책

#### Solution 2-A: Instruction 파싱 개선

**수정 파일:** `tool_nodes.py`
**수정 위치:** `retriever_tool_node()` (line 40-156)

```python
async def retriever_tool_node(state: MACTState) -> MACTState:
    """
    Enhanced retrieval with multi-table awareness.
    """
    instruction = state["current_argument"]
    tables = [TableInfo.from_dict(t) for t in state["tables"]]

    # 🎯 NEW: Detect if instruction mentions multiple tables
    mentioned_tables = []
    table_keywords = {
        'department': ['department', 'dept'],
        'management': ['management', 'manager', 'head'],
        'city': ['city', 'cities'],
        'farm_competition': ['competition', 'farm'],
        'student': ['student'],
        'course': ['course', 'class'],
        'people': ['people', 'person'],
        'candidate': ['candidate']
    }

    instruction_lower = instruction.lower()
    for table_name, keywords in table_keywords.items():
        if any(kw in instruction_lower for kw in keywords):
            # Check if this table exists in state
            matching_table = None
            for t in tables:
                if table_name in t.name.lower():
                    matching_table = t
                    break
            if matching_table:
                mentioned_tables.append(matching_table)

    # Decide retrieval strategy
    if len(mentioned_tables) >= 2:
        # Multi-table retrieval -> delegate to operator
        return await _multi_table_retrieve(state, mentioned_tables, instruction)
    elif len(mentioned_tables) == 1:
        # Single table retrieval
        return await _single_table_retrieve(state, mentioned_tables[0], instruction)
    else:
        # Fallback: use first table
        return await _single_table_retrieve(state, tables[0], instruction)
```

**새 함수 추가:**
```python
async def _multi_table_retrieve(
    state: MACTState,
    tables: List[TableInfo],
    instruction: str
) -> MACTState:
    """
    Handle retrieval that requires multiple tables (likely needs JOIN).
    """
    # Create a simple JOIN instruction
    table_names = [t.name for t in tables]
    join_instruction = f"Retrieve data from {' and '.join(table_names)} for: {instruction}"

    # Update state to trigger operator tool instead
    state["current_action_type"] = ActionType.OPERATOR.value
    state["current_argument"] = join_instruction

    # Call operator tool
    return await operator_tool_node(state)


async def _single_table_retrieve(
    state: MACTState,
    table: TableInfo,
    instruction: str
) -> MACTState:
    """
    Handle single-table retrieval with enhanced filtering.
    """
    # ... existing single-table logic ...
    # (current code from line 40-156)
```

#### Solution 2-B: 프롬프트 개선

**수정 내용:**
```python
prompt = f"""Given table data and retrieval instruction, generate pandas code.

Table: {table_name}
Columns: {columns}

Instruction: {instruction}

Generate code to retrieve/filter data. Store result in 'new_table' variable.

Examples:
# Basic retrieval
"Show department data" -> new_table = df.copy()

# Filtering
"Get departments where budget > 10" -> new_table = df[df['budget_in_billions'] > 10]

# Complex filtering
"Departments ranked in top 10 with temporary acting" ->
    new_table = df[(df['ranking'] < 10) & (df['temporary_acting'] == 'Yes')]

# Column selection
"Get department names and budgets" -> new_table = df[['name', 'budget_in_billions']]

IMPORTANT:
- Use lowercase column names (e.g., 'department_id', not 'Department_ID')
- For conditions, check actual column values in data
- If filtering by 'Yes'/'No', use exact string match

Current instruction: {instruction}
new_table = df  # Replace with appropriate logic
"""
```

#### Solution 2-C: 반환 데이터 검증

**새 함수 추가:** `tool_nodes.py`

```python
def validate_retrieval_result(
    instruction: str,
    result_table: pd.DataFrame,
    original_tables: List[TableInfo]
) -> Tuple[bool, str]:
    """
    Validate if retrieved data matches instruction intent.

    Returns:
        (is_valid, reason)
    """
    if result_table is None or result_table.empty:
        return False, "Empty result"

    # Check 1: If instruction mentions specific columns, verify they exist
    mentioned_columns = []
    instruction_lower = instruction.lower()
    for table in original_tables:
        for col in table.columns:
            if col.lower() in instruction_lower:
                mentioned_columns.append(col.lower())

    if mentioned_columns:
        result_columns_lower = [c.lower() for c in result_table.columns]
        missing = [c for c in mentioned_columns if c not in result_columns_lower]
        if missing:
            return False, f"Missing expected columns: {missing}"

    # Check 2: Reasonable row count
    if len(result_table) == 0:
        return False, "No rows in result"

    # Check 3: Not just returning entire original table unchanged
    # (unless instruction explicitly asks for all data)
    if "all" not in instruction_lower and "show" in instruction_lower:
        original_sizes = [len(t.content) if hasattr(t, 'content') else 0 for t in original_tables]
        if any(len(result_table) == size for size in original_sizes):
            # Might be returning original table without filtering
            # Only flag if instruction had filtering keywords
            filter_keywords = ['where', 'with', 'that', 'which', 'greater', 'less', 'between']
            if any(kw in instruction_lower for kw in filter_keywords):
                return False, "Result appears to be unfiltered original table"

    return True, "Valid"
```

**사용:**
```python
# retriever_tool_node()에서:
if new_table_info:
    # Validate result
    result_df = pd.DataFrame(new_table_info.content, columns=new_table_info.columns)
    is_valid, reason = validate_retrieval_result(instruction, result_df, tables)

    if not is_valid:
        # Log warning
        state["execution_log"].append(f"⚠️ Retrieval validation failed: {reason}")
        # Could retry with different code or escalate to operator
```

### 📊 예상 효과

**수정 전:**
- Multi-table 요청 성공률: ~30%
- 부정확한 데이터 반환: ~40%

**수정 후:**
- Multi-table 요청 자동 감지 및 operator로 위임: 90%+
- 데이터 검증으로 부정확한 반환 감소: <10%
- **전체 정확도:** +10-15%p 개선

### 🧪 검증 방법

```python
test_cases = [
    {
        "instruction": "Show department and management data",
        "expected_behavior": "delegate_to_operator",
        "expected_tables": ["department", "management"]
    },
    {
        "instruction": "Get departments where budget > 10",
        "expected_behavior": "single_table_filter",
        "expected_columns": ["name", "budget_in_billions"]
    }
]

for case in test_cases:
    result = test_retriever_node(case["instruction"])
    if case["expected_behavior"] == "delegate_to_operator":
        assert result["action_type"] == "OPERATOR"
    elif case["expected_behavior"] == "single_table_filter":
        assert len(result["result_columns"]) >= len(case["expected_columns"])
    print(f"✅ {case['instruction'][:40]}...")
```

---

## Bug #3: 첫 단계 Finish 액션 허용

### 🔍 증상 분석

**테스트 결과:**
```
7 questions (33.3%) terminated with 0 steps:

Question 1: "Which department...?"
  Steps: 0
  Answer: "Department A ($8B), Department B ($6B)"  ← Placeholder

Question 5: "Which city with population > 1000...?"
  Steps: 0
  Answer: "City X"  ← Generic placeholder

Question 9: "What is the official name of city...?"
  Steps: 0
  Answer: "Official Name of the city..."  ← Template answer
```

**영향:**
- 33.3% 질문이 즉시 종료 (추론 없음)
- Placeholder/template 답변만 생성
- 완전한 추론 프로세스 우회

### 🎯 근본 원인

#### 원인 1: 첫 단계 Finish 액션 검증 부재

**문제 코드 위치:** `core_nodes.py:248-330` (`action_selector_node()`)

**현재 구현:**
```python
async def action_selector_node(state: MACTState) -> MACTState:
    """Select best action from candidates using reward function."""

    candidates = [ActionCandidate.from_dict(c) for c in state["action_candidates"]]

    # 🎯 Phase 3-C: Filter out first-step Finish actions
    if state["current_step"] == 1:
        finish_candidates = [c for c in candidates if c.action_type == ActionType.FINISH]
        if finish_candidates:
            # Log but DON'T filter yet (BUG!)
            print(f"DEBUG: Filtered out {len(finish_candidates)} first-step Finish actions")
        # ❌ BUG: 필터링을 로그만 하고 실제로는 안 함

    # Select best action using reward function
    selected = await select_action_by_reward(candidates, state)
    # ❌ selected가 Finish일 수 있음 (step 1에서도)
```

**문제점:**
1. **조건문만 있고 실제 필터링 없음**
   - `if state["current_step"] == 1:` 체크는 함
   - 하지만 `candidates`에서 Finish 제거 안 함
   - 로그만 출력하고 통과

2. **Reward 함수가 Finish 선호**
   - Consistency reward: Finish가 가장 많이 생성되면 선택됨
   - LLM이 3번 중 2번 이상 Finish 생성 시 선택

3. **모델이 쉽게 Finish 생성**
   - GPT-3.5-turbo가 충분히 생각하지 않고 빠른 답변 선호
   - 프롬프트에 "Think step by step" 강조 부족

#### 원인 2: Planner 프롬프트 문제

**문제 코드 위치:** `prompt_utils.py` (planner prompt)

**현재 프롬프트:** (추정)
```python
prompt = f"""
Question: {question}
Tables: {tables}

You can use actions: Retrieve, Calculate, Search, Operator, Finish

Thought: [your reasoning]
Action: [action name][argument]

{scratchpad}
"""
```

**문제점:**
1. **Finish 사용 시기 명시 안 함**
   - "Use Finish only when you have the final answer"
   - 이런 제약 없음

2. **최소 단계 강제 안 함**
   - "You must use at least 2 tools before Finish"
   - 이런 가이드라인 없음

3. **단계적 사고 독려 부족**
   - "Break down complex questions into steps"
   - 이런 instruction 부족

### ✅ 해결책

#### Solution 3-A: 첫 단계 Finish 강제 차단

**수정 파일:** `core_nodes.py`
**수정 위치:** `action_selector_node()` (line 248-330)

```python
async def action_selector_node(state: MACTState) -> MACTState:
    """
    Select best action from candidates using reward function.
    Enhanced with first-step Finish validation.
    """
    candidates = [ActionCandidate.from_dict(c) for c in state["action_candidates"]]

    # 🎯 NEW: STRICTLY filter out first-step Finish actions
    if state["current_step"] == 1:
        original_count = len(candidates)
        candidates = [c for c in candidates if c.action_type != ActionType.FINISH]
        filtered_count = original_count - len(candidates)

        if filtered_count > 0:
            log_msg = f"🚫 Blocked {filtered_count} first-step Finish actions (step 1 requires actual reasoning)"
            print(log_msg)
            state = {
                **state,
                "execution_log": state["execution_log"] + [log_msg]
            }

        # If all candidates were Finish, force a default Retrieve action
        if len(candidates) == 0:
            fallback_log = "⚠️ All actions were Finish at step 1. Forcing Retrieve action."
            print(fallback_log)

            # Create fallback Retrieve action
            fallback_candidate = ActionCandidate(
                thought="I need to first examine the available data to answer this question.",
                action="Retrieve[examine all available table data]",
                action_type=ActionType.RETRIEVE,
                argument="examine all available table data",
                score=1.0,
                raw_response=""
            )
            candidates = [fallback_candidate]

            state = {
                **state,
                "execution_log": state["execution_log"] + [fallback_log]
            }

    # 🎯 NEW: Also block Finish at step 2 if no tools used yet
    if state["current_step"] == 2 and len(state["tool_results"]) == 0:
        original_count = len(candidates)
        candidates = [c for c in candidates if c.action_type != ActionType.FINISH]
        if original_count != len(candidates):
            log_msg = f"🚫 Blocked Finish at step 2 (no tools used yet)"
            state = {
                **state,
                "execution_log": state["execution_log"] + [log_msg]
            }

    # Now select from valid candidates
    if not candidates:
        # Extreme fallback (should not happen)
        raise ValueError("No valid action candidates after filtering")

    selected = await select_action_by_reward(candidates, state)

    # ... rest of function
```

#### Solution 3-B: Planner 프롬프트 강화

**수정 파일:** `prompt_utils.py`
**수정 위치:** `build_react_prompt()` 또는 관련 함수

```python
def build_react_prompt(state: MACTState) -> str:
    """Build ReAct-style prompt with enhanced Finish guidelines."""

    question = state["question"]
    context = state.get("context", "")
    scratchpad = state.get("scratchpad", "")
    current_step = state["current_step"]

    # 🎯 NEW: Add step-specific instructions
    step_instruction = ""
    if current_step == 1:
        step_instruction = """
⚠️ IMPORTANT: This is step 1. You MUST use a tool to gather information first.
DO NOT use Finish action at step 1. Start with Retrieve, Calculate, Search, or Operator.
"""
    elif current_step == 2:
        if len(state.get("tool_results", [])) == 0:
            step_instruction = """
⚠️ You have not used any tools yet. Please retrieve or analyze data before answering.
"""

    prompt = f"""You are solving a complex question that requires multi-step reasoning and table operations.

Question: {question}

{context}

Available Actions:
- Retrieve[instruction]: Get data from tables based on instruction
- Calculate[expression]: Perform mathematical calculations
- Search[query]: Search external information (Wikipedia)
- Operator[operation]: Perform complex table operations (JOIN, GROUP BY, etc.)
- Finish[answer]: Provide final answer (ONLY when you have verified the answer)

⚠️ CRITICAL RULES:
1. You MUST use at least ONE tool action before Finish
2. For complex questions, use 2-3 tool actions to gather and analyze data
3. DO NOT guess or use placeholder answers
4. Verify your answer by examining actual data from tables

{step_instruction}

Reasoning Format:
Thought: [Your step-by-step reasoning about what to do next]
Action: [ActionName][argument]

Previous Steps:
{scratchpad}

Now, what is your next Thought and Action?
"""

    return prompt
```

#### Solution 3-C: 최소 단계 강제

**수정 파일:** `core_nodes.py`
**새 validation 함수 추가:**

```python
def validate_finish_action(state: MACTState) -> Tuple[bool, str]:
    """
    Validate if Finish action is appropriate at current state.

    Returns:
        (is_allowed, reason)
    """
    current_step = state["current_step"]
    tool_results = state.get("tool_results", [])

    # Rule 1: Never allow Finish at step 1
    if current_step == 1:
        return False, "Step 1 requires gathering information first"

    # Rule 2: Must have used at least one tool
    if len(tool_results) == 0:
        return False, "Must use at least one tool before Finish"

    # Rule 3: For multi-table questions, require 2+ tool uses
    tables = state.get("tables", [])
    if len(tables) >= 2 and len(tool_results) < 2:
        return False, "Multi-table questions require at least 2 tool operations"

    # Rule 4: Check if tool results contain actual data
    valid_results = [r for r in tool_results if r and "error" not in r.lower() and len(r) > 10]
    if len(valid_results) == 0:
        return False, "No valid tool results obtained yet"

    # All checks passed
    return True, "Finish action is appropriate"


# 사용 in action_selector_node():
if selected.action_type == ActionType.FINISH:
    is_allowed, reason = validate_finish_action(state)
    if not is_allowed:
        # Block and force a different action
        log_msg = f"🚫 Finish action blocked: {reason}"
        print(log_msg)

        # Select next best non-Finish action
        non_finish_candidates = [c for c in candidates if c.action_type != ActionType.FINISH]
        if non_finish_candidates:
            selected = non_finish_candidates[0]
        else:
            # Force Retrieve
            selected = create_fallback_retrieve_action()
```

### 📊 예상 효과

**수정 전:**
- 즉시 종료 비율: 33.3% (7/21)
- 평균 steps: 2.14
- Placeholder 답변: 7개

**수정 후:**
- 즉시 종료 비율: 0% (완전 차단)
- 평균 steps: 2.5-3.5 (최소 1회 tool 사용 강제)
- 실제 데이터 기반 답변: 100%
- **전체 정확도:** +15-20%p 개선

### 🧪 검증 방법

```python
# Test 1: Step 1 Finish 차단
def test_first_step_finish_blocked():
    state = create_test_state(current_step=1)
    candidates = [
        ActionCandidate(action_type=ActionType.FINISH, ...),
        ActionCandidate(action_type=ActionType.RETRIEVE, ...)
    ]

    result = action_selector_node(state, candidates)

    assert result["current_action_type"] != ActionType.FINISH
    assert "Blocked" in result["execution_log"][-1]
    print("✅ First-step Finish successfully blocked")


# Test 2: 최소 tool 사용 강제
def test_minimum_tool_usage():
    state = create_test_state(current_step=2, tool_results=[])
    candidates = [ActionCandidate(action_type=ActionType.FINISH, ...)]

    result = action_selector_node(state, candidates)

    assert result["current_action_type"] != ActionType.FINISH
    assert len(result["tool_results"]) > 0  # Should force tool usage
    print("✅ Minimum tool usage enforced")


# Test 3: 유효한 Finish는 허용
def test_valid_finish_allowed():
    state = create_test_state(
        current_step=3,
        tool_results=["Table data retrieved", "Calculation completed"]
    )
    candidates = [ActionCandidate(action_type=ActionType.FINISH, argument="42")]

    result = action_selector_node(state, candidates)

    assert result["current_action_type"] == ActionType.FINISH
    assert result["final_answer"] == "42"
    print("✅ Valid Finish action allowed")
```

---

## 수정 우선순위 및 일정

### Phase 1: Critical Bugs (2-3일)

**우선순위 1: Bug #3 - 첫 단계 Finish 차단** (가장 쉬운 수정)
- **작업 시간:** 2-3시간
- **수정 파일:**
  - `core_nodes.py`: `action_selector_node()` validation 추가
  - `prompt_utils.py`: 프롬프트 강화
- **테스트:** 즉시 종료 케이스 재실행
- **예상 효과:** +15-20%p 정확도

**우선순위 2: Bug #1 - TABLE JOIN 수정** (가장 큰 impact)
- **작업 시간:** 1-2일
- **수정 파일:**
  - `table_utils.py`: `table2df()`, `normalize_column_name()` 추가
  - `tool_nodes.py`: `operator_tool_node()` FK hints 추가
- **테스트:** Multi-table JOIN 케이스 집중 테스트
- **예상 효과:** +30-40%p 정확도

### Phase 2: Important Bugs (1-2일)

**우선순위 3: Bug #2 - Retrieve 로직 개선**
- **작업 시간:** 1일
- **수정 파일:**
  - `tool_nodes.py`: Multi-table 감지, validation 추가
- **테스트:** Retrieve 정확도 검증
- **예상 효과:** +10-15%p 정확도

### 전체 일정

```
Day 1: Bug #3 수정 + 테스트
Day 2-3: Bug #1 수정 + 집중 테스트
Day 4: Bug #2 수정 + 통합 테스트
Day 5: 전체 MMQA 데이터셋 재테스트 + 결과 분석
```

---

## 검증 계획

### Step 1: Unit Tests

각 버그별로 독립적인 unit test 작성 및 실행

```python
# tests/test_bug_fixes.py

def test_bug1_join_column_normalization():
    """Test that JOIN operations work with normalized column names."""
    pass

def test_bug2_multi_table_detection():
    """Test that multi-table requests are correctly detected."""
    pass

def test_bug3_first_step_finish_blocked():
    """Test that first-step Finish actions are blocked."""
    pass
```

### Step 2: Integration Tests

전체 workflow에서 버그 수정 효과 검증

```python
# tests/test_integration.py

def test_department_questions():
    """Test all department-related questions (Bug #1 focus)."""
    questions = load_department_questions()
    for q in questions:
        result = run_langgraph_mact(q)
        assert "KeyError" not in result["errors"]
        # Check accuracy
```

### Step 3: Comparison Test

Original MACT와 다시 비교

```bash
# 수정 후 재실행
python code/tqa_mmqa.py --plan_model gpt-3.5-turbo --code_model gpt-3.5-turbo \
  --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_sample 3 --code_sample 3 --output_dir comparison_original_v2

python langgraph_code/main.py --plan_model gpt-3.5-turbo --code_model gpt-3.5-turbo \
  --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_sample 3 --code_sample 3 --output_dir comparison_fixed_langgraph

# 비교 분석
python analyze_comparison.py comparison_original_v2 comparison_fixed_langgraph
```

### Step 4: Success Criteria

| Metric | 수정 전 | 목표 | Stretch Goal |
|--------|---------|------|--------------|
| **전체 정확도** | 19.0% | 60%+ | 70%+ |
| **Department 질문** | 0% | 50%+ | 75%+ |
| **City 질문** | 25% | 60%+ | 75%+ |
| **Student 질문** | 28.6% | 50%+ | 65%+ |
| **즉시 종료 비율** | 33.3% | 0% | 0% |
| **JOIN 성공률** | 0% | 80%+ | 90%+ |
| **평균 Steps** | 2.14 | 2.5-3.5 | 3.0+ |

---

## 추가 개선 사항 (Optional)

### 1. 에러 복구 메커니즘
- JOIN 실패 시 자동으로 칼럼명 변형 시도
- Retrieve 실패 시 operator로 자동 escalation

### 2. 프롬프트 최적화
- Few-shot examples 추가 (특히 JOIN 예제)
- 모델별 프롬프트 튜닝 (GPT-3.5 vs GPT-4 vs Qwen)

### 3. 디버깅 개선
- 더 상세한 실행 로그
- 중간 단계 결과 시각화
- 실패 케이스 자동 분석

---

**문서 버전:** 1.0
**최종 업데이트:** 2025-09-30
**작성자:** Claude Code Assistant
**상태:** ✅ Ready for Implementation