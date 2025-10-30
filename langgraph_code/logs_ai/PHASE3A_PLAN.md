# Phase 3A: Dataset-Agnostic Improvements Plan

**Date**: 2025-10-10
**Goal**: Improve accuracy from 42.9% → 50%+ without dataset-specific overfitting
**Baseline**: 42.9% on MMQA samples (GPT-3.5-turbo)

---

## 🎯 Core Philosophy

**AVOID**: Dataset-specific tricks (FK hints, lowercase column enforcement, multi-table detection keywords)
**FOCUS**: Generic reasoning improvements that work on ANY table-based QA dataset

---

## 📋 Proposed Improvements

### 1️⃣ **Enhanced Chain-of-Thought Prompting**

**Current Problem**: Planning prompt doesn't track progress
**Solution**: Add structured reasoning template

```python
# In prompt_utils.py - build_react_prompt()
prompt_additions = f"""
Before choosing your next action, reflect on:
1. What information have I collected so far?
2. What do I still need to know to answer: "{state['question']}"?
3. Which action will get me closer to the answer?

Your response:
Thought: [answer the 3 questions above]
Action: [your chosen action]
"""
```

**Why dataset-agnostic**: This reasoning structure helps with ANY complex task, not just MMQA.

---

### 2️⃣ **Generic Error-Based Self-Correction**

**Current Problem**: When SQL/code fails, agent doesn't get helpful feedback
**Solution**: On error, provide available schema information

```python
# In tool_nodes.py - operator_tool_node()
# After code execution fails:
if error:
    # Extract available column names from ALL tables
    available_columns = {}
    for table in tables:
        available_columns[table.name] = table.columns

    error_context = f"""
Operation failed with error: {error}

Available table schemas:
{json.dumps(available_columns, indent=2)}

Hint: Check if column names match exactly (case-sensitive).
Retry the operation with correct column names.
"""

    # Add to observation for next step
    results.append(error_context)
```

**Why dataset-agnostic**: Schema inspection is a standard DB debugging practice, not MMQA-specific.

---

### 3️⃣ **Answer Format Validation**

**Current Problem**: Agent sometimes outputs descriptions instead of answers
**Solution**: Validate answer format before Finish

```python
# In core_nodes.py - finish_node()
def validate_answer_format(answer: str, question: str) -> tuple[bool, str]:
    """
    Check if answer is properly formatted (not a description).

    Returns:
        (is_valid, error_message)
    """
    # Check for common invalid patterns
    invalid_patterns = [
        r"^(The |A |An )?answer is",  # "The answer is..."
        r"^(I need to|First|Let me|To answer)",  # Process descriptions
        r"^Unable to determine",  # Failure acknowledgment
    ]

    for pattern in invalid_patterns:
        if re.match(pattern, answer, re.IGNORECASE):
            return False, f"Answer looks like a description, not a direct answer. Provide the actual data/value."

    return True, ""

# In finish_node():
is_valid, error_msg = validate_answer_format(state["current_argument"], state["question"])
if not is_valid:
    return {
        **state,
        "scratchpad": state["scratchpad"] + f"\n\nValidation Error: {error_msg}\n",
        "execution_log": state["execution_log"] + [f"Finish validation failed: {error_msg}"]
    }
```

**Why dataset-agnostic**: Answer format validation is universal QA best practice.

---

### 4️⃣ **Observation History Summarization**

**Current Problem**: Long scratchpad loses context
**Solution**: Summarize previous observations

```python
# In build_react_prompt():
if len(state["tool_results"]) > 3:
    # Summarize older observations
    recent_obs = state["tool_results"][-2:]
    older_count = len(state["tool_results"]) - 2

    summary = f"[Previous {older_count} observations summarized - data was collected but answer not yet determined]\n"
    summary += "\n".join(recent_obs)

    observation_context = summary
else:
    observation_context = "\n".join(state["tool_results"])
```

**Why dataset-agnostic**: Context window management is a general LLM best practice.

---

## 🚫 Removed Dataset-Specific Features

### ❌ **FK Hints Removal**

**Current code (lines 399-409 in tool_nodes.py)**:
```python
fk_hints = ""
foreign_keys = state.get("foreign_keys", [])
if foreign_keys:
    fk_hints = "\n# Foreign Key Relationships (use these for JOINs):\n"
    for fk in foreign_keys:
        normalized_fk = normalize_column_name(fk)
        fk_hints += f"#   - {normalized_fk}\n"
```

**Why problematic**: Real-world databases rarely provide explicit FK metadata in query contexts.

**Replacement**: Only show FK info **on error**, as part of generic schema inspection.

---

### ❌ **Lowercase Column Enforcement**

**Current code (line 427 in tool_nodes.py)**:
```python
# ⚠️ CRITICAL: All column names are LOWERCASE (e.g., 'department_id', not 'Department_ID')
```

**Why problematic**: This is specific to MMQA's preprocessing, not a general pattern.

**Replacement**: Show actual case-sensitive column names on error.

---

### ❌ **Multi-Table Detection Keywords**

**Current code**: (if exists) Keyword-based detection of "JOIN", multiple table names, etc.

**Why problematic**: Databases have various ways to express multi-table operations.

**Replacement**: Let the agent decide tool usage based on data, not keywords.

---

## 📊 Expected Impact

### Conservative Estimates

| Improvement | Accuracy Gain | Speed Impact |
|------------|---------------|--------------|
| Enhanced CoT | +3-5%p | +5% (extra tokens) |
| Error-based correction | +2-4%p | +10% (retry overhead) |
| Answer validation | +1-2%p | <1% (quick check) |
| Observation summary | +1-2%p | -2% (shorter prompts) |
| **Total** | **+7-13%p** | **+13% slower** |

### Projected Performance

- **Baseline**: 42.9% (282.7s for 21 questions = 13.5s/q)
- **Phase 3A Target**: 50-55% (15.3s/q = +13% time)
- **Acceptable trade-off**: +7-12%p accuracy for +13% time

---

## 🔬 Testing Protocol

### Baseline Test (Already Completed)
- **Dataset**: mmqa_samples.json (21 questions)
- **Model**: gpt-3.5-turbo
- **Config**: plan_sample=3, code_sample=3
- **Result**: 42.9% accuracy, 13.5s/question

### Phase 3A Test (To Run)
```bash
cd langgraph_code
export OPENAI_API_KEY="sk-proj-..."
export OPENAI_API_BASE="https://api.openai.com/v1"

python main.py \
  --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_model "gpt-3.5-turbo" \
  --code_model "gpt-3.5-turbo" \
  --plan_sample 3 \
  --code_sample 3 \
  --output_dir test_phase3a_dataset_agnostic
```

### Success Criteria
✅ **Accuracy**: 50%+ (≥ +7%p improvement)
✅ **Speed**: <18s/question (<+33% slowdown)
✅ **Generalizability**: No MMQA-specific hacks
✅ **Error rate**: Maintain 0%

---

## 🛠️ Implementation Order

1. ✅ **Remove FK hints** from operator_tool_node (lines 399-427)
2. ✅ **Add error-based schema hints** (only when code fails)
3. ✅ **Enhance CoT prompt** with 3-question reflection
4. ✅ **Add answer format validation** in finish_node
5. ✅ **Implement observation summarization** in build_react_prompt
6. 🧪 **Run baseline test** (if not already)
7. 🧪 **Run Phase 3A test**
8. 📊 **Compare results**

---

## 📝 Code Changes Summary

### Files to Modify
1. `src/mact_langgraph/nodes/tool_nodes.py`
   - Remove FK hints (lines 399-427)
   - Add error-based schema hints

2. `src/mact_langgraph/utils/prompt_utils.py`
   - Enhance CoT prompt (lines 161-174)
   - Add observation summarization

3. `src/mact_langgraph/nodes/core_nodes.py`
   - Add answer format validation in finish_node

### Estimated LOC Changes
- **Additions**: ~50 lines
- **Deletions**: ~30 lines (FK hints removal)
- **Modifications**: ~20 lines
- **Total**: ~100 LOC

---

## 🎓 Lessons Learned

### What NOT to Do
- ❌ Don't add dataset-specific metadata (FK, PK) to prompts
- ❌ Don't enforce preprocessing rules (lowercase) in prompts
- ❌ Don't use keyword detection for tool selection

### What WORKS Universally
- ✅ Structured reasoning prompts (CoT with questions)
- ✅ Error-driven schema inspection (only when needed)
- ✅ Answer format validation (detect descriptions vs answers)
- ✅ Observation summarization (manage context)

---

## 🔮 Future Work (Phase 3B+)

If Phase 3A succeeds, consider:
- **Phase 3B**: Multi-step verification (cross-check results)
- **Phase 3C**: Dynamic tool parameter tuning (adaptive sampling)
- **Phase 3D**: Confidence-based early stopping

But ONLY if Phase 3A proves the dataset-agnostic approach works!
