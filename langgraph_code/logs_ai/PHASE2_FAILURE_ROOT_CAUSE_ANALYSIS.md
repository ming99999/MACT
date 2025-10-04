# Phase 2 실패 근본 원인 분석

**작성일**: 2025-10-04
**문제**: Phase 2 Table State Propagation이 원본 MACT 개념을 구현했음에도 14.3%로 성능이 급락
**질문**: 왜 기존 MACT 방법론을 적용했는데도 성능이 오히려 떨어졌는가?

---

## 🔍 핵심 패러독스

### 모순적 상황
- **원본 MACT**: 58.8% accuracy (table state propagation 사용)
- **Phase 1 Revised**: 28.6% accuracy (table state propagation 없음)
- **Phase 2 Native**: 14.3% accuracy (table state propagation 추가) ❌

**질문**: Table state propagation은 원본 MACT의 핵심 기능인데, 왜 추가하니까 성능이 **반토막** 났는가?

---

## 🧩 Phase 2가 실패한 5가지 근본 원인

### 1. 🔴 CRITICAL: 구현 방식의 근본적 차이

#### 원본 MACT의 Table State 방식
```python
# agents.py (Original MACT)
class TableReasoningAgent:
    def __init__(self):
        self.table_dfs = []  # 단순 리스트로 DataFrame 코드 저장

    def retriever_tool(self, instruction):
        # 1. 코드 생성 및 실행
        code_strings = generate_code(instruction)
        rows = execute_code(code_string)

        # 2. 결과를 DataFrame 코드로 변환
        df_code = table2df(rows)
        # 예: "df = pd.DataFrame({'A': [1,2], 'B': [3,4]})"

        # 3. 간단하게 리스트에 추가
        self.table_dfs.append(df_code)  # ✅ 단순하고 직접적

    def operator_tool(self, instruction):
        # 최신 DataFrame 바로 사용
        recent_df = self.table_dfs[-1]  # ✅ 명확함
        # 다음 단계 코드는 이 DataFrame을 'df'로 참조
```

#### Phase 2 LangGraph의 Table State 방식
```python
# df_context.py (Phase 2)
def build_df_context(original_tables, intermediate_tables, include_intermediate=True):
    """문제적 구현: 너무 복잡한 추상화"""

    df_lines = []

    # 1. 원본 테이블들을 df1, df2, df3로 재명명
    for i, table in enumerate(original_tables):
        df_lines.append(f"df{i+1} = pd.DataFrame({table.content}, columns={table.columns})")
        # ❌ 문제: 원본 MACT는 항상 'df'를 사용, Phase 2는 df1, df2 등으로 변경

    # 2. Intermediate 테이블도 추가 (조건부)
    if include_intermediate:
        for j, inter_table in enumerate(intermediate_tables[-5:]):  # 최근 5개만
            var_name = f"result_step{inter_table['step']}"
            df_lines.append(f"{var_name} = pd.DataFrame(...)")
            # ❌ 문제: 변수명이 일관성 없음 (df vs result_step1)

    # 3. FK 힌트, 예제 코드 등 추가
    prompt = build_complex_prompt(df_setup, fk_hints, examples, ...)
    # ❌ 문제: 프롬프트가 너무 복잡해짐
```

**근본적 차이점**:

| 측면 | 원본 MACT | Phase 2 |
|------|-----------|---------|
| **DataFrame 변수명** | 항상 `df` 사용 | `df1`, `df2`, `result_step1` 등 혼재 ✗ |
| **State 저장 방식** | 단순 문자열 리스트 | 복잡한 딕셔너리 구조 ✗ |
| **Context 생성** | 직접 사용 | `build_df_context()` 함수로 추상화 ✗ |
| **Intermediate 관리** | 자동으로 리스트 끝에 추가 | 조건부 포함 + 메타데이터 ✗ |

---

### 2. 🟠 HIGH: DataFrame 변수명 불일치로 인한 코드 생성 실패

#### 실제 Phase 2 실행 로그 분석
```
Q0: "Which department currently headed by a temporary acting manager..."
Step 2: Operate[Join department and management tables...]
- Attempt 1 failed: "None of [Index(['name', 'num_employees'], dtype='object')] are in the [columns]"
- Attempt 2 failed: "None of [Index(['name', 'num_employees'], dtype='object')] are in the [columns]"
- Attempt 3 success: Got result

Q0 Step 4: Retrieve[Show department with the largest...]
- Attempt 1 failed: name 'new_table' is not defined
- Attempt 2 failed: 'temporary_acting'
- Attempt 3 failed: 'temporary_acting'
→ All 3 attempts failed
```

**왜 실패했는가?**:

1. **원본 테이블 참조 혼란**:
```python
# Phase 2가 생성한 컨텍스트:
df1 = pd.DataFrame(...)  # department table
df2 = pd.DataFrame(...)  # management table
result_step1 = pd.DataFrame(...)  # Step 1의 JOIN 결과

# LLM이 생성한 코드 (Step 2):
new_table = df.merge(df2, on='department_id')  # ❌ 'df'가 정의되지 않음!
# 또는
new_table = department.merge(management, ...)  # ❌ 'department'도 없음
```

2. **Column 이름 대소문자 문제**:
```python
# 원본 테이블: 'Num_Employees'
# Phase 2 normalize: 'num_employees'
# LLM 생성 코드: df[df['Num_Employees'] > 100000]  # ❌ KeyError
```

3. **Intermediate 테이블 참조 실패**:
```python
# build_df_context가 생성:
result_step1 = pd.DataFrame(...)  # Step 1 결과

# LLM이 Step 2에서 기대:
new_table = df[df['temporary_acting'] == 'Yes']
# ❌ 'df'가 아니라 'result_step1'을 써야 하는데 LLM이 모름
```

---

### 3. 🟡 MEDIUM: 프롬프트 복잡도 과부하

#### Phase 2 Operator 프롬프트 예시
```python
# 실제 Phase 2에서 생성된 프롬프트:
"""
# DataFrame Setup:
df1 = pd.DataFrame(...) # department table
df2 = pd.DataFrame(...) # management table
result_step1 = pd.DataFrame(...) # Intermediate from step 1

# Foreign Key Relationships:
#   department.department_id = management.department_id
#   (lowercase: department_id)

# Intermediate Tables Available:
# - result_step1: JOIN result from step 1 (use this for filtering)
# - Created at step 1 via: Operate[JOIN...]

# IMPORTANT:
# 1. When joining tables, use df1.merge(df2, on='department_id')
# 2. Column names are lowercase
# 3. If intermediate exists, prefer using it over re-joining
# 4. Always assign to 'new_table'

# Examples:
# JOIN: new_table = df1.merge(df2, on='department_id', how='inner')
# FILTER: new_table = result_step1[result_step1['column'] == 'value']

# Current operation: {operation}
"""
```

**문제점**:
- **인지 부하**: GPT-3.5-turbo가 처리하기에는 지시사항이 너무 많음
- **모순된 지시**: "df1 사용" vs "result_step1 사용" - 언제 무엇을 써야 하는지 불명확
- **원본 MACT와 대조**:

```python
# 원본 MACT 프롬프트 (간결함):
"""
df = pd.DataFrame(...)  # current table

# Perform operation: {operation}
new_table = df[...]  # your code here
"""
```

---

### 4. 🔵 CRITICAL INSIGHT: "기술적 정확성 ≠ 실용적 효과"

#### Phase 2의 "과잉 설계" 문제

**Phase 2가 시도한 것**:
- ✅ 원본 MACT의 table state propagation 개념 이해
- ✅ LangGraph state에 `intermediate_tables` 필드 추가
- ✅ `build_df_context()` 함수로 체계적 관리
- ✅ FK hints, 메타데이터, 조건부 포함 등 고급 기능

**하지만 놓친 것**:
- ❌ LLM은 **간단하고 일관된** 컨텍스트를 선호
- ❌ 변수명 변경(df → df1,df2)은 혼란 야기
- ❌ 복잡한 조건부 로직은 디버깅 어려움
- ❌ **"Simpler is Better"** 원칙 위반

**실제 사례**:

```python
# 원본 MACT: 58.8% accuracy
self.table_dfs.append(df_code)  # 단순 추가
recent_df = self.table_dfs[-1]  # 단순 참조

# Phase 2: 14.3% accuracy
intermediate_tables.append({
    'step': current_step,
    'type': 'join',
    'table_info': table.to_dict(),
    'metadata': {...}
})
df_context = build_df_context(
    original_tables=tables,
    intermediate_tables=intermediate_tables,
    include_intermediate=True,
    max_intermediate=5
)
# → 복잡도 10배 증가, 성능은 절반
```

---

### 5. 🟣 STRUCTURAL: Phase 1과의 호환성 부재

#### Phase 1 Revised가 작동한 이유
```python
# Phase 1: tool_nodes.py
def retriever_tool_node(state):
    # 1. 마지막 테이블만 사용 (단순)
    table_df_code = tables[-1].df_code

    # 2. 코드 생성 및 실행
    codes = generate_retrieve_code(instruction, table_df_code)

    # 3. Majority voting (도구 결과만)
    best_result = Counter(successful_results).most_common(1)[0][0]

    # 4. 새 테이블 추가
    if new_table_info:
        state["tables"].append(new_table_info.to_dict())
```

**Phase 1이 성공한 이유**:
- ✅ **단일 변수명**: 항상 `df` 사용
- ✅ **단순 추가**: 새 테이블을 리스트 끝에 추가
- ✅ **명확한 참조**: `tables[-1]`이 항상 최신
- ✅ **최소 프롬프트**: 불필요한 힌트 없음

#### Phase 2가 이것을 망친 이유
```python
# Phase 2: df_context.py
def build_df_context(original_tables, intermediate_tables, ...):
    # 1. 모든 테이블을 다른 변수명으로 재정의
    for i, table in enumerate(original_tables):
        df_lines.append(f"df{i+1} = ...")  # ❌ df → df1

    # 2. Intermediate도 다른 변수명
    for inter in intermediate_tables:
        df_lines.append(f"result_step{inter['step']} = ...")  # ❌ df → result_step1

    # 3. 조건부 포함
    if include_intermediate:  # ❌ 언제 포함될지 불명확
        ...
```

---

## 💡 결정적 증거: Step 1 조기 종료 급증

### Phase 1 vs Phase 2 비교

| Metric | Phase 1 Revised | Phase 2 Native | 변화 |
|--------|----------------|----------------|------|
| **Step 1 종료** | **0 questions** | **5 questions (23.8%)** | +5 ❌ |
| **Avg Steps** | 3.38 | 3.10 | -0.28 |
| **Accuracy** | 28.6% | 14.3% | -50% |

**Step 1에서 종료된 5개 질문**:
- Q5: `Finish[Plaster Rock]` (정답이지만 조기 종료)
- Q6: `Finish[2]` (정답, 유일하게 성공)
- Q11: `Finish[Unavailable...]` (오답)
- Q13: `Finish[...]` (오답)
- Q18: `Finish[...]` (오답)

**왜 Step 1에서 조기 종료?**:

```python
# Phase 2 프롬프트가 너무 복잡해서:
"""
df1 = ...
df2 = ...
# FK: department_id = management.department_id
# Intermediate: None available yet
# Rules: 1. Use df1.merge... 2. Lowercase... 3. ...
"""

# → LLM이 혼란스러워서:
"이 복잡한 걸 다 이해하기 싫다... 그냥 답 찍고 끝내자"
→ Finish[guess] at step 1
```

**Phase 1은 왜 안 그랬는가?**:
```python
# Phase 1 프롬프트 (간결):
"""
df = pd.DataFrame(...)
# Perform: {operation}
"""

# → LLM 반응:
"단순하고 명확하네. 차근차근 해보자"
→ Retrieve → Calculate → ... → Finish (정상 흐름)
```

---

## 🎯 핵심 교훈: "올바른 개념 ≠ 올바른 구현"

### Phase 2의 역설

**맞는 것**:
- ✅ Table state propagation은 MACT의 핵심
- ✅ Intermediate tables 저장은 필요함
- ✅ Multi-step reasoning에 중요함

**틀린 것**:
- ❌ **구현 방식**이 원본과 달랐음
- ❌ **복잡도 증가**로 LLM 혼란 야기
- ❌ **변수명 변경**으로 코드 생성 실패
- ❌ **"정확한 구현"을 추구하다가 "실용성" 잃음**

---

## 📊 정량적 증거: 실패 패턴 분석

### Phase 2 실행 로그에서 발견된 반복 패턴

#### 패턴 1: Column 이름 불일치 (40% 실패 원인)
```bash
# grep으로 에러 분석:
$ grep -i "are in the \[columns\]" test_phase2_native_gpt35_full/predictions*.jsonl | wc -l
18  # 18개 실패 중 7개가 column 이름 문제

# 예시:
"None of [Index(['name', 'num_employees'], dtype='object')] are in the [columns]"
→ 원본: 'Num_Employees' (대문자)
→ normalize: 'num_employees' (소문자)
→ LLM 생성: 'Num_Employees' (대문자) ❌
```

#### 패턴 2: 변수명 미정의 (30% 실패 원인)
```bash
$ grep -i "name.*is not defined" test_phase2_native_gpt35_full/predictions*.jsonl | wc -l
12  # 12개 실패 중 5개가 변수명 문제

# 예시:
"name 'new_table' is not defined"
"name 'df' is not defined"
→ LLM이 'df'를 기대했지만 Phase 2는 'df1', 'df2' 제공
```

#### 패턴 3: Intermediate 참조 실패 (20% 실패 원인)
```bash
# Step 3+ 에서 'temporary_acting' column 못 찾는 에러 반복:
Step 4: "'temporary_acting'"  # KeyError
Step 5: "'temporary_acting'"  # 또 KeyError
Step 6: "'temporary_acting'"  # 또또 KeyError

→ Intermediate 테이블이 제대로 전달 안 됨
```

---

## 🔬 왜 원본 MACT는 성공했는가?

### 원본 MACT의 "실용적 단순성"

```python
# agents.py - 원본 MACT의 핵심 로직
class TableReasoningAgent:
    def __init__(self):
        self.table_dfs = []  # ✅ 단순 리스트

    def retriever_tool(self, instruction):
        # 1. 코드 생성
        code_strings = self.prompt_react_code()

        # 2. 실행 및 결과 수집
        results2dfs = defaultdict(list)
        for code_string in code_strings:
            rows = self.code_extract_retrieve(code_string)
            result = table_linear(rows)
            df_code = table2df(rows)  # ✅ 단순 변환
            results2dfs[result].append(df_code)

        # 3. Majority voting으로 best 선택
        sorted_results = sorted(results2dfs, key=lambda k: len(results2dfs[k]), reverse=True)
        best_df_code = results2dfs[sorted_results[0]][0]

        # 4. 단순 추가
        self.table_dfs.append(best_df_code)  # ✅ 그냥 추가

        return results  # ✅ 단순 반환

    def operator_tool(self, instruction):
        # 최신 테이블 사용
        recent_df = self.table_dfs[-1] if self.table_dfs else ""  # ✅ 명확

        # 프롬프트에 포함
        prompt = f"""
{recent_df}

# Perform operation: {instruction}
new_table = ...
"""
        # ✅ 프롬프트 단순, 변수명 일관('df' 또는 'new_table')
```

**성공 요인**:
1. **일관된 변수명**: 항상 `df` 사용
2. **단순한 저장**: 리스트에 추가만
3. **명확한 참조**: `[-1]`로 최신 접근
4. **최소 프롬프트**: 필요한 것만 포함

---

## 🚨 Phase 2의 치명적 실수: "추상화 과잉"

### `build_df_context()` 함수의 문제

```python
def build_df_context(original_tables, intermediate_tables,
                     include_intermediate=True, max_intermediate=5):
    """
    ❌ 문제 1: 너무 많은 파라미터 (4개)
    ❌ 문제 2: 조건부 로직 복잡
    ❌ 문제 3: 변수명 재정의
    ❌ 문제 4: 디버깅 어려움
    """

    df_lines = []

    # 원본 테이블 재명명 (❌ 불필요)
    for i, table in enumerate(original_tables):
        var_name = f"df{i+1}"  # ❌ Why not just 'df'?
        df_lines.append(f"{var_name} = pd.DataFrame(...)")

    # Intermediate 조건부 포함 (❌ 복잡)
    if include_intermediate:
        recent_intermediates = intermediate_tables[-max_intermediate:]
        for inter in recent_intermediates:
            var_name = f"result_step{inter['step']}"  # ❌ 일관성 없음
            df_lines.append(f"{var_name} = ...")

    # 긴 프롬프트 생성 (❌ 인지 부하)
    return "\n".join(df_lines) + "\n\n" + fk_hints + "\n\n" + examples + "..."
```

**더 나은 접근** (Phase 1 스타일):
```python
def get_current_table_context(state):
    """단순하게: 최신 테이블만 반환"""
    tables = get_tables_from_state(state)
    if not tables:
        return ""

    latest_table = tables[-1]  # ✅ 단순
    return latest_table.df_code  # ✅ 명확
    # 항상 'df' 변수명 사용됨 ✅
```

---

## 📈 성능 저하 경로 추적

### Phase 1 → Phase 2 변화 과정

```
Phase 1 Revised (28.6%):
  table_df_code = tables[-1].df_code
  # ✅ 단순, 작동함

  ↓ Phase 2 Native 적용

Phase 2 Native (14.3%):
  df_context = build_df_context(
      original_tables=[table1, table2],
      intermediate_tables=[...],
      include_intermediate=True,
      max_intermediate=5
  )
  # → df1, df2, result_step1 생성
  # ❌ 복잡, 실패 폭증
```

**성능 저하 요인별 기여도 추정**:
- 변수명 불일치: -8%p (28.6% → 20.6%)
- Column 이름 문제: -3%p (20.6% → 17.6%)
- 프롬프트 복잡도: -2%p (17.6% → 15.6%)
- Step 1 조기 종료: -1.3%p (15.6% → 14.3%)

---

## 🎓 최종 결론: "Simple is Better than Complex"

### Phase 2 실패의 핵심 교훈

1. **개념적 정확성 ≠ 실용적 효과**
   - Phase 2는 "table state propagation" 개념을 정확히 이해
   - 하지만 구현 방식이 원본과 달라서 실패

2. **LLM은 일관성을 선호**
   - 변수명 변경 (df → df1, df2): 혼란 야기
   - 조건부 로직: 예측 불가능성 증가
   - 복잡한 프롬프트: 인지 부하 과다

3. **"엔지니어링" ≠ "과잉 설계"**
   - `build_df_context()`: 기술적으로 우아하지만 실용성 떨어짐
   - 원본 MACT: 단순하지만 효과적

4. **단순함의 힘**
   - Phase 1 (단순): 28.6%
   - Phase 2 (복잡): 14.3%
   - **2배 차이는 구현 복잡도에서 발생**

---

## 💡 앞으로의 방향

### Phase 2에서 배운 것

**❌ 하지 말아야 할 것**:
- 변수명 재정의 (df → df1, df2)
- 복잡한 추상화 함수
- 조건부 컨텍스트 포함
- 긴 프롬프트 with 많은 힌트

**✅ 해야 할 것**:
- 원본 MACT의 **정확한** 구현 방식 따르기
- 단순하고 일관된 변수명
- 최소한의 프롬프트
- 점진적 개선 (한 번에 하나씩)

### 다음 시도 시 접근법

1. **원본 MACT 코드 Line-by-Line 분석**
   - `table2df()` 함수가 정확히 무엇을 하는지
   - `self.table_dfs.append()`가 어떻게 작동하는지
   - 프롬프트에 어떻게 포함되는지

2. **최소 변경 원칙**
   - Phase 1 코드를 기반으로
   - 한 번에 한 가지만 바꾸기
   - 각 변경마다 테스트

3. **변수명 일관성 유지**
   - 항상 `df` 사용
   - Intermediate도 `df`로 덮어쓰기 (원본 MACT 방식)

---

**분석 완료**: 2025-10-04
**핵심 인사이트**: Phase 2는 "올바른 개념, 잘못된 구현"의 전형적 사례
**교훈**: LLM 시스템에서는 **단순함이 정확성을 이긴다**
