# MMQA Benchmark Compliance Fix (2025-10-11)

## 🚨 Critical Issue Identified

**Problem**: Both original MACT and LangGraph versions incorrectly used `foreign_keys` and `primary_keys` fields as **input hints** instead of **output targets**.

According to the MMQA paper, these fields are **evaluation targets** (subtasks), not input features.

## MMQA Benchmark Structure

### INPUT (Allowed)
- `Question` (natural language query)
- `table_names` (list of table names)
- `tables` (table schemas and content)

### OUTPUT (Model should generate - Evaluation targets)
1. `answer` → Evaluated with **EM** (Exact Match) and **PM** (Partial Match)
2. `SQL` → Evaluated with **Rouge-1, Rouge-L, BLEU**
3. `primary_keys` → Evaluated with **PKS** (Primary Key Selection accuracy)
4. `foreign_keys` → Evaluated with **FKS** (Foreign Key Selection accuracy)

---

## Fixes Applied

### LangGraph Version Fixes

#### 1. State Definition (`src/mact_langgraph/state.py`)
**Changed**: Removed `foreign_keys` and `primary_keys` from MACTState TypedDict

```python
# OLD (lines 108-109):
foreign_keys: List[str]
primary_keys: List[str]

# NEW (line 108):
context: str  # Context contains ONLY table names, NO FK/PK (MMQA compliance)
```

**Changed**: Updated `create_initial_state()` signature to remove FK/PK parameters

```python
# OLD signature:
def create_initial_state(
    question: str,
    tables_data: List[Dict[str, Any]],
    table_names: List[str] = None,
    foreign_keys: List[str] = None,  # REMOVED
    primary_keys: List[str] = None,  # REMOVED
    context: str = "",
    config: Dict[str, Any] = None
) -> MACTState:

# NEW signature:
def create_initial_state(
    question: str,
    tables_data: List[Dict[str, Any]],
    table_names: List[str] = None,
    config: Dict[str, Any] = None
) -> MACTState:
    """
    MMQA Compliance: FK/PK are NOT input fields - they are evaluation targets.
    Only question, tables, and table_names are valid inputs.
    """
```

**Changed**: Context generation now uses ONLY table names (lines 213-222)

```python
# Create context with ONLY table names (MMQA compliance)
table_name_list = table_names or [f"table_{i}" for i in range(len(tables))]
context = f"Tables: {', '.join(table_name_list)}" if table_name_list else ""
```

#### 2. MMQA Utilities (`src/mact_langgraph/utils/mmqa_utils.py`)
**Changed**: Simplified `create_mmqa_context()` to only use table_names (lines 50-67)

```python
# OLD (lines 50-77):
def create_mmqa_context(
    table_names: List[str],
    foreign_keys: List[str] = None,  # REMOVED
    primary_keys: List[str] = None   # REMOVED
) -> str:
    context_parts = []
    if table_names:
        context_parts.append(f"Tables: {', '.join(table_names)}")
    if foreign_keys:  # REMOVED
        context_parts.append(f"Foreign Keys: {', '.join(foreign_keys)}")
    if primary_keys:  # REMOVED
        context_parts.append(f"Primary Keys: {', '.join(primary_keys)}")
    return " | ".join(context_parts)

# NEW (lines 50-67):
def create_mmqa_context(
    table_names: List[str]
) -> str:
    """
    MMQA Compliance: FK/PK are NOT input - they are evaluation targets.
    Context should ONLY contain table names.
    """
    if table_names:
        return f"Tables: {', '.join(table_names)}"
    return ""
```

**Changed**: Updated `format_mmqa_item_for_processing()` to separate inputs from evaluation targets (lines 119-155)

```python
def format_mmqa_item_for_processing(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    MMQA Compliance: FK/PK are NOT input - they are evaluation targets stored separately.
    """
    # Process tables
    tables = process_mmqa_tables(item['tables'])

    # Extract table names (INPUT - allowed)
    table_names = item.get('table_names', [f"table_{i}" for i in range(len(tables))])

    # Get answer (EVALUATION TARGET)
    answer = extract_mmqa_answer(item)

    return {
        'id': item.get('id_', item.get('id', 0)),
        'question': item['Question'],  # INPUT
        'tables': [table.to_dict() for table in tables],  # INPUT
        'table_names': table_names,  # INPUT

        # EVALUATION TARGETS (not used as input, stored for comparison only)
        'answer': answer,
        'sql': item.get('SQL', ''),
        'foreign_keys': item.get('foreign_keys', []),
        'primary_keys': item.get('primary_keys', []),

        'original_item': item
    }
```

#### 3. Main Entry Point (`main.py`)
**Changed**: Removed FK/PK from `create_initial_state()` call (lines 62-68)

```python
# OLD (lines 63-71):
initial_state = create_initial_state(
    question=item['question'],
    tables_data=item['tables'],
    table_names=item['table_names'],
    foreign_keys=item['foreign_keys'],  # REMOVED
    primary_keys=item['primary_keys'],  # REMOVED
    context=item['context'],
    config=config
)

# NEW (lines 62-68):
# Create initial state (MMQA compliance: NO FK/PK as input)
initial_state = create_initial_state(
    question=item['question'],
    tables_data=item['tables'],
    table_names=item['table_names'],
    config=config
)
```

### Original MACT Fixes

#### 1. Context Creation (`code/tqa_mmqa.py`)
**Changed**: Updated `create_mmqa_context()` to remove FK/PK (lines 51-60)

```python
# OLD (lines 51-64):
def create_mmqa_context(item):
    """Create context string from MMQA item metadata."""
    context_parts = []
    if 'table_names' in item:
        context_parts.append(f"Tables: {', '.join(item['table_names'])}")
    if 'foreign_keys' in item and item['foreign_keys']:  # REMOVED
        context_parts.append(f"Foreign Keys: {', '.join(item['foreign_keys'])}")
    if 'primary_keys' in item and item['primary_keys']:  # REMOVED
        context_parts.append(f"Primary Keys: {', '.join(item['primary_keys'])}")
    return " | ".join(context_parts)

# NEW (lines 51-60):
def create_mmqa_context(item):
    """
    MMQA Compliance: FK/PK are NOT input - they are evaluation targets.
    Context should ONLY contain table names.
    """
    if 'table_names' in item:
        return f"Tables: {', '.join(item['table_names'])}"
    return ""
```

---

## Test Results

### Corrected LangGraph Version (MMQA Compliant)
**Test Date**: October 11, 2025
**Model**: gpt-3.5-turbo
**Dataset**: mmqa_samples.json (21 questions)
**Configuration**: plan_sample=3, code_sample=3

**Results**:
- **Accuracy**: 28.6% (6/21 correct)
- **Error rate**: 0.0%
- **Avg steps**: 2.76
- **Avg confidence**: 0.65

### Comparison with Previous Versions

| Version | FK/PK as Input? | Accuracy | Note |
|---------|----------------|----------|------|
| Phase 2C | ✅ Yes (cheating) | 42.9% | Used FK hints for table JOIN guidance |
| Phase 3A | ❌ No (honest) | 38.1% | Removed FK hints from prompts only |
| **Compliant** | ❌ No (fully compliant) | **28.6%** | Removed FK/PK from state entirely |

### Performance Drop Analysis

- **Phase 2C → Phase 3A**: -4.8%p (42.9% → 38.1%)
  - Removed FK hints from code generation prompts

- **Phase 3A → Compliant**: -9.5%p (38.1% → 28.6%)
  - Removed FK/PK from state and context entirely

- **Total "Cheating Penalty"**: -14.3%p (42.9% → 28.6%)
  - This represents the full cost of honest MMQA compliance

---

## Key Findings

### 1. Magnitude of Cheating Effect
The total performance drop of **-14.3 percentage points** (from 42.9% to 28.6%) reveals that FK/PK information was providing substantial "cheating" benefit across two mechanisms:

**Mechanism 1**: FK hints in code generation prompts (-4.8%p)
- Explicit guidance like "Use foreign key 'department_id' to join tables"
- Helped model generate correct JOIN operations

**Mechanism 2**: FK/PK in state and context (-9.5%p)
- Even without explicit hints, having FK/PK in state affected:
  - Planning decisions (action selection)
  - Tool execution strategies
  - Implicit bias in LLM reasoning

### 2. Original MACT Was Also Non-Compliant
The original MACT codebase (`code/tqa_mmqa.py`) suffered from the same fundamental issue:
- Used FK/PK as input fields
- Included them in context string generation
- Likely inflated reported performance metrics

### 3. MMQA Compliance Is More Strict Than Expected
The MMQA benchmark requires models to:
- Infer table relationships from data alone
- Predict primary keys from table structure
- Predict foreign keys from multi-table queries
- Generate SQL queries without schema hints

All published MMQA results must use **only** question + tables + table_names as input.

---

## Remaining Work (Phase 2: Subtask Generation)

### 1. Output Generation for All 4 Subtasks ⚠️ IN PROGRESS
**Current State**: Only Answer is generated (28.6% EM - validated ✅)
**Required**: Generate all 4 evaluation targets

**Status**:
- ✅ Answer (already generated) - **WORKING**
- ⚠️ SQL query (rudimentary extraction implemented)
- ⚠️ Primary keys (basic heuristics implemented)
- ⚠️ Foreign keys (basic extraction from code implemented)

**Phase 2 Plan** (see `todo_20251011.md` for detailed plan):

#### Option 1: Post-Processing with LLM (RECOMMENDED ⭐)
**Approach**: After answer generation, use LLM to extract SQL/FK/PK from reasoning history

**Implementation Steps**:
1. **Create Subtask Extraction Utilities** (`src/mact_langgraph/utils/subtask_extraction.py`)
   - `extract_sql_from_history()`: Convert pandas operations to SQL using LLM
   - `extract_foreign_keys_from_history()`: Extract FK from JOIN/merge operations
   - `extract_primary_keys_from_tables()`: Predict PK from structure + usage patterns

2. **Add Post-Processing Node** (`src/mact_langgraph/nodes/subtask_nodes.py`)
   - `subtask_generation_node()`: Runs AFTER answer finalized
   - Calls all 3 extraction functions
   - Updates state with predicted_sql, predicted_fks, predicted_pks

3. **Update State Schema** (`src/mact_langgraph/state.py`)
   - Add `predicted_sql: Optional[str]`
   - Add `predicted_primary_keys: List[str]`
   - Add `predicted_foreign_keys: List[str]`

4. **Integrate into Graph** (`src/mact_langgraph/graph.py`)
   - Add subtask node after finish_node
   - Connect: finish → generate_subtasks → END

5. **Update Output Format** (`main.py`)
   - Include all 4 subtask predictions in result dictionary

**Advantages**:
- ✅ Minimal changes to core MACT framework
- ✅ Leverages existing reasoning history
- ✅ Maintains MACT's strength (answer generation)
- ✅ Can iterate on subtask extraction independently

**Estimated Timeline**: 6-9 hours
- Extraction utilities: 2-3 hours
- Graph integration: 1-2 hours
- Testing & refinement: 2-3 hours

#### Why This Approach?
**Root Cause Analysis**: MACT was designed for Question → Answer, NOT for SQL/FK/PK generation
- Original framework focuses on answer extraction
- Code generation produces pandas operations, not SQL
- FK/PK relationships inferred during execution but not explicitly output

**Opportunity**: Rich reasoning history can be leveraged
- `step_history`: Records all actions and observations
- `scratchpad`: Contains reasoning chain
- `execution_log`: Records tool executions
- Generated code: Contains JOIN/merge operations indicating FK relationships

### 2. Comprehensive Evaluation Metrics ✅ PARTIALLY COMPLETED
**Implemented**:
- ✅ EM (Exact Match) for answers - working
- ✅ PM (Partial Match) for answers - working
- ✅ PKS (Primary Key Selection) accuracy - implemented
- ✅ FKS (Foreign Key Selection) accuracy - implemented

**Still Needed**:
- ⚠️ Rouge-1, Rouge-L for SQL - need to add after SQL generation improves
- ⚠️ BLEU for SQL - need to add after SQL generation improves

### 3. Evaluation Script ✅ COMPLETED
**Created**: `code/evaluate_mmqa.py`
- ✅ Load predictions and ground truth from JSONL
- ✅ Calculate EM, PM for answers
- ✅ Calculate PKS, FKS accuracy
- ✅ Generate detailed JSON reports
- ✅ Support both LangGraph and original MACT output formats

**Ready to enhance** with SQL metrics once SQL generation is improved

---

## Files Modified

### LangGraph Version
- ✅ `src/mact_langgraph/state.py` (lines 104-108, 170-190, 213-222)
- ✅ `src/mact_langgraph/utils/mmqa_utils.py` (lines 50-67, 119-155)
- ✅ `main.py` (lines 62-68)

### Original MACT Version
- ✅ `code/tqa_mmqa.py` (lines 51-60)
- ⏳ Output format update (pending)

### Documentation
- ✅ `todo_20251011.md` (comprehensive fix plan)
- ✅ `logs_ai/MMQA_COMPLIANCE_FIX.md` (this file)

---

## Lessons Learned

1. **Dataset Compliance Is Critical**: Using evaluation target fields as inputs fundamentally invalidates benchmark results

2. **Incremental Fixes Reveal Hidden Dependencies**: Phase 3A removed explicit FK hints but kept FK/PK in state, revealing a second layer of cheating

3. **Performance Trade-offs**: Honest benchmark compliance often means lower raw performance, but this is the correct baseline for fair comparison

4. **Documentation Matters**: Clear separation of INPUT vs OUTPUT fields in dataset documentation prevents such mistakes

---

## Next Steps

1. ✅ Complete LangGraph compliance fixes
2. ✅ Test corrected LangGraph version
3. ⏳ Complete original MACT fixes
4. ⏳ Implement 4-subtask output generation
5. ⏳ Create comprehensive evaluation script
6. ⏳ Run full evaluation on both versions
7. ⏳ Document final results and comparison

---

## References

- MMQA Paper: Multi-table QA evaluation with EM, PM, Rouge, BLEU, PKS, FKS metrics
- Original MACT: `code/tqa_mmqa.py`
- LangGraph MACT: `src/mact_langgraph/`
- Test Dataset: `datasets_examples/mmqa_samples.json` (21 questions)

---

**Date**: October 11, 2025
**Status**: LangGraph version compliance fixes completed and tested ✅
**Next**: Complete original MACT fixes and add 4-subtask output generation
