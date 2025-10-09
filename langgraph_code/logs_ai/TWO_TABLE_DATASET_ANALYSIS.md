# Two-Table Dataset Performance Analysis

**Date**: 2025-10-08
**Model**: GPT-3.5-turbo
**Dataset**: mmqa_two_table_0.1_filtered.json (218 questions)
**Version**: MACT LangGraph Phase 2C

---

## 📊 Executive Summary

The two-table dataset reveals **significantly lower performance** compared to the smaller MMQA samples dataset, highlighting critical challenges in multi-table reasoning and complex JOIN operations.

### Key Findings
- **Accuracy: 19.7%** (43/218) - 23.2%p lower than MMQA samples (42.9%)
- **Early Termination: 22.0%** - High rate of premature Finish actions
- **Complex Queries: 35.3%** require 5+ steps, indicating dataset difficulty
- **Zero System Errors** - Framework stability confirmed

---

## 1. Performance Metrics

### 1.1 Overall Results

| Metric | Two-Table Dataset | MMQA Samples | Difference |
|--------|------------------|--------------|------------|
| **Questions** | 218 | 21 | - |
| **Accuracy** | 19.7% (43/218) | 42.9% (9/21) | **-23.2%p** |
| **Error Rate** | 0.0% | 0.0% | Same |
| **Avg Steps** | 3.18 | 3.43 | -0.25 |
| **Avg Confidence** | 0.558 | 0.610 | -0.052 |
| **Total Time** | 3776.9s (63 min) | 282.7s (5 min) | 13.4x |
| **Time per Question** | 17.3s | 13.5s | **+28%** |

### 1.2 Step Distribution Analysis

```
Two-Table Dataset:
  Step 1: 48 (22.0%) ← Early termination problem
  Step 2: 37 (17.0%)
  Step 3: 38 (17.4%)
  Step 4: 18 (8.3%)
  Step 5: 77 (35.3%) ← Most complex queries

MMQA Samples (for comparison):
  Step 1: 1 (4.8%)   ← Much lower early termination
  Step 2: 6 (28.6%)
  Step 3: 4 (19.0%)
  Step 4: 3 (14.3%)
  Step 5: 7 (33.3%)
```

**Key Insight**: Two-table dataset shows **4.6x higher early termination rate** (22.0% vs 4.8%), indicating the model struggles with initial planning for complex multi-table queries.

### 1.3 Confidence Distribution

| Confidence Range | Count | Percentage |
|-----------------|-------|------------|
| Low (<0.5) | 66 | 30.3% |
| Medium (0.5-0.7) | 0 | 0.0% |
| High (>0.7) | 152 | 69.7% |

**Note**: Binary confidence distribution suggests the model is either very confident or not confident at all, with no middle ground.

---

## 2. Failure Pattern Analysis

### 2.1 Step Distribution by Correctness

| Metric | Correct Answers | Incorrect Answers |
|--------|----------------|-------------------|
| **Count** | 43 | 175 |
| **Avg Steps** | 2.51 | 3.33 |
| **Step 1 Terminations** | 7/43 (16.3%) | 41/175 (23.4%) |

**Key Insight**: Incorrect answers require **32% more steps** on average, suggesting the model gets lost in complex reasoning chains.

### 2.2 Failure Type Taxonomy

#### **Type 1: Incomplete Results (Partial JOIN)**
```
Question: Which companies are founded by entrepreneurs taller than 1.85m?
Predicted: Umbrolly, Elizabeth Galton Ltd
Target: Umbrolly, Grails Ltd, Elizabeth Galton Ltd
Steps: 4, Confidence: 0.800
```
**Root Cause**: Missing entries in JOIN or incorrect filtering conditions

#### **Type 2: Format Extraction Failure**
```
Question: What is the average rating of items titled 'orange' and 'apple'?
Predicted: Final answer: Average rating of items titled 'orange' and 'apple'
Target: 6.6667
Steps: 1, Confidence: 0.800
```
**Root Cause**: Failed to extract numerical result from reasoning chain

#### **Type 3: Unable to Determine**
```
Question: What are the states or counties of the stores...?
Predicted: Unable to determine answer
Target: {'columns': ['State_County'], 'index': [0, 1, 2], 'data': [...]}
Steps: 5, Confidence: 0.000
```
**Root Cause**: Complex table structure or nested JSON output format not handled

#### **Type 4: Incorrect Data Selection**
```
Question: Who won the match held in New York City?
Predicted: Hannes Arch
Target: Della Lindgren
Steps: 2, Confidence: 0.800
```
**Root Cause**: Wrong condition matching or data retrieval error

### 2.3 Failure Distribution Summary

| Failure Type | Estimated % | Primary Issue |
|-------------|------------|---------------|
| Incomplete Results | ~30% | JOIN/Filter bugs |
| Format Extraction | ~25% | Answer extraction |
| Unable to Determine | ~20% | Complex structures |
| Wrong Data Selection | ~25% | Condition matching |

---

## 3. Comparative Analysis

### 3.1 Dataset Difficulty Assessment

The two-table dataset is **2.2x harder** than MMQA samples:
- **Accuracy drop**: 42.9% → 19.7% (-23.2%p)
- **Early termination increase**: 4.8% → 22.0% (+17.2%p)
- **Processing time increase**: 13.5s → 17.3s (+28%)

This suggests the two-table dataset is **closer to real-world production difficulty**.

### 3.2 Speed Analysis

**Per-question processing time breakdown**:
- MMQA Samples: 13.5s/question
- Two-Table: 17.3s/question (+28% slower)

**Factors**:
1. More complex queries require more API calls
2. Multi-table operations are slower
3. Higher step count (3.18 avg) increases latency

---

## 4. Sample Cases

### ✅ Successful Cases

**Case 1: Complex Aggregation**
```
Question: What is the average savings balance of customers whose names start with 'M'?
Answer: 500000029.5
Steps: 4, Confidence: 0.800
```

**Case 2: Multi-Table JOIN**
```
Question: What are the first and last names of students who have a nut allergy
          and live in the city with the code 'PIT'?
Answer: Michael Leighton
Steps: 3, Confidence: 0.800
```

**Case 3: Simple Retrieval**
```
Question: Who is the head of the Surgery department?
Answer: John Wen
Steps: 3, Confidence: 0.800
```

### ❌ Failed Cases

**Case 1: Incomplete JOIN**
```
Question: Which companies are founded by entrepreneurs taller than 1.85m?
Predicted: Umbrolly, Elizabeth Galton Ltd (MISSING: Grails Ltd)
```

**Case 2: Early Termination**
```
Question: How many distinct staff members have had the role of 'leader'...?
Predicted: Number of distinct staff members who were leaders... (Description only)
Target: 2
```

---

## 5. Future Improvement Plan

### Phase 3: Enhanced Multi-Table Reasoning

#### 5.1 Tool Enhancement Strategy

**Goal**: Improve accuracy from 19.7% to 40%+ by adding specialized tools and better table handling

##### **A. Table Manipulation Tools**

1. **TableInspect Tool**
   ```python
   def inspect_table(table_name: str) -> dict:
       """Return schema, sample rows, statistics"""
       return {
           'columns': [...],
           'dtypes': {...},
           'sample_rows': [...],
           'row_count': int,
           'null_counts': {...}
       }
   ```
   **Use Case**: Understanding table structure before JOIN

2. **TableJoin Tool** (Explicit JOIN operation)
   ```python
   def join_tables(
       left_table: str,
       right_table: str,
       on: str | list[str],
       how: str = 'inner'
   ) -> str:
       """Perform explicit JOIN with validation"""
   ```
   **Use Case**: Reduce JOIN errors by explicit tool call

3. **TableFilter Tool**
   ```python
   def filter_table(
       table_name: str,
       conditions: list[dict]
   ) -> str:
       """Apply multiple filter conditions"""
       # conditions = [
       #   {'column': 'height', 'op': '>', 'value': 1.85},
       #   {'column': 'city', 'op': '==', 'value': 'NYC'}
       # ]
   ```
   **Use Case**: Complex filtering without code generation

4. **TableAggregate Tool**
   ```python
   def aggregate_table(
       table_name: str,
       group_by: list[str],
       agg_functions: dict
   ) -> str:
       """Perform groupby and aggregation"""
   ```
   **Use Case**: Common aggregation patterns (AVG, COUNT, SUM)

5. **TableValidate Tool**
   ```python
   def validate_result(
       result: Any,
       expected_type: str
   ) -> dict:
       """Validate if result matches expected format"""
       return {
           'is_valid': bool,
           'actual_type': str,
           'suggestions': list[str]
       }
   ```
   **Use Case**: Catch format errors before Finish

##### **B. DataFrame Control Enhancements**

6. **DataFrameSnapshot Tool**
   ```python
   def save_checkpoint(df_name: str, step: int):
       """Save intermediate DataFrame state"""
   ```
   **Use Case**: Rollback to previous state if operation fails

7. **DataFrameDebug Tool**
   ```python
   def debug_dataframe(df_name: str) -> dict:
       """Return detailed DataFrame debugging info"""
       return {
           'shape': tuple,
           'head': str,
           'tail': str,
           'dtypes': dict,
           'memory_usage': str,
           'duplicates': int
       }
   ```
   **Use Case**: Troubleshoot incorrect results

8. **DataFrameMerge Tool** (Smart JOIN with FK hints)
   ```python
   def smart_merge(
       left: str,
       right: str,
       foreign_keys: list[dict]
   ) -> str:
       """Use FK relationships to auto-determine JOIN keys"""
   ```
   **Use Case**: Leverage existing FK metadata

##### **C. Answer Extraction Improvements**

9. **ExtractAnswer Tool**
   ```python
   def extract_final_answer(
       dataframe: str,
       question_type: str  # 'scalar', 'list', 'table'
   ) -> Any:
       """Smart extraction based on expected answer type"""
   ```
   **Use Case**: Fix "Final answer: ..." format errors

10. **FormatAnswer Tool**
    ```python
    def format_answer(
        raw_result: Any,
        target_format: str
    ) -> str:
        """Convert result to expected output format"""
    ```
    **Use Case**: Handle JSON, list, scalar conversions

#### 5.2 Agent Strategy Improvements

##### **Strategy 1: Progressive JOIN Planning**
- **Step 1**: Inspect all tables involved
- **Step 2**: Identify JOIN keys from FK relationships
- **Step 3**: Plan JOIN sequence (left → right order)
- **Step 4**: Execute JOINs with validation
- **Step 5**: Apply filters and aggregations

##### **Strategy 2: Fallback Mechanisms**
- If Operator fails → Try TableJoin/TableFilter tools
- If format error → Use ExtractAnswer tool
- If "Unable to determine" → Use TableInspect for hints

##### **Strategy 3: Early Termination Prevention**
- **Minimum action requirement**:
  - Block Finish at Step 1-2 unless question is trivial
  - Require at least one Retrieve/Operator before Finish
- **Data validation gate**:
  - Validate result format matches question type
  - Reject Finish if result is description/explanation

##### **Strategy 4: Multi-Step Verification**
- Add "Verify" action type to check intermediate results
- Run sample queries to validate JOIN correctness
- Cross-check result count against expected range

#### 5.3 Implementation Priorities

**Phase 3A: Critical Fixes (Target: +10%p accuracy)**
1. ✅ Fix early termination (implement minimum action requirement)
2. ✅ Add ExtractAnswer tool (fix format errors)
3. ✅ Implement TableValidate (catch bad results)

**Phase 3B: Table Tools (Target: +15%p accuracy)**
4. ✅ Add TableInspect tool
5. ✅ Add TableJoin tool with FK awareness
6. ✅ Add TableFilter tool

**Phase 3C: Advanced Features (Target: +10%p accuracy)**
7. ✅ Implement progressive JOIN planning
8. ✅ Add DataFrameDebug tool
9. ✅ Implement fallback mechanisms
10. ✅ Add multi-step verification

**Expected Final Accuracy**: 19.7% + 35%p = **~55% target**

#### 5.4 Evaluation Metrics

Track improvements on:
- **Primary**: Accuracy on two-table dataset (218 questions)
- **Secondary**: Step distribution (reduce Step 1 from 22% → <10%)
- **Tertiary**: Failure type breakdown (reduce each category)

**Success Criteria**:
- Accuracy: 19.7% → 55%+ (2.8x improvement)
- Early termination: 22% → <10% (2.2x reduction)
- "Unable to determine": <5% of total failures

---

## 6. Conclusions

### Current State
- ✅ **Framework is stable** (0% error rate)
- ✅ **MMQA samples performance is acceptable** (42.9%)
- ❌ **Two-table performance needs significant improvement** (19.7%)
- ❌ **Early termination is a major issue** (22%)

### Root Causes Identified
1. **Insufficient table manipulation tools** → Add specialized JOIN/Filter tools
2. **Poor multi-table reasoning** → Implement progressive planning
3. **Format extraction failures** → Add ExtractAnswer tool
4. **Early termination problem** → Strengthen minimum action requirements

### Next Steps
1. **Implement Phase 3A fixes** (critical issues)
2. **Add specialized table tools** (Phase 3B)
3. **Validate on two-table dataset** (target 40%+ accuracy)
4. **Iterate on failures** until 55%+ target reached

---

## Appendix: Test Configuration

```json
{
  "plan_model": "gpt-3.5-turbo",
  "code_model": "gpt-3.5-turbo",
  "reward_type": "consistency",
  "plan_sample": 3,
  "code_sample": 3,
  "max_steps": 6,
  "use_examples": true,
  "dataset": "mmqa_two_table_0.1_filtered.json",
  "dataset_size": 218,
  "total_execution_time": "3776.9s (62.9 min)"
}
```

**Files**:
- Metrics: `test_gpt35_two_table_full/metrics_gpt-3.5-turbo_mmqa_two_table_0.1_filtered_20251008_214601.json`
- Predictions: `test_gpt35_two_table_full/predictions_gpt-3.5-turbo_mmqa_two_table_0.1_filtered_20251008_214601.jsonl`
- Full log: `gpt35_two_table_test.log`
