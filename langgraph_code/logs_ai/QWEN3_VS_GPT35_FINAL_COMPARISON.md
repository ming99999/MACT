# Qwen3-8B vs GPT-3.5-Turbo Final Comparison

**Date**: 2025-10-05
**Dataset**: mmqa_samples.json (21 questions)
**Implementation**: MACT LangGraph with `<think>` tag post-processing

---

## 📊 Executive Summary

**GPT-3.5-turbo는 Qwen3-8B보다 2.3배 더 정확하고 3.9배 더 빠릅니다.**

| Metric | Qwen3-8B | GPT-3.5-turbo | Winner |
|--------|----------|---------------|--------|
| **Accuracy** | 19.0% | **42.9%** | **GPT-3.5** (2.3x) |
| **Speed** | 1107s | **283s** | **GPT-3.5** (3.9x) |
| **Avg Steps** | 1.62 | **3.43** | **GPT-3.5** |
| **Correct** | 4/21 | **9/21** | **GPT-3.5** |

---

## 🔬 Detailed Results

### Qwen3-8B (with `<think>` tag stripping)

**Performance**:
- ✅ **Accuracy**: 19.0% (4/21 correct)
- ⚠️ **Avg steps**: 1.62 (too low - early termination)
- ❌ **Execution time**: 1106.9s (~18.5 minutes)
- ✅ **Error rate**: 0.0% (stable)

**Step Distribution**:
```
Step 1: 12 questions (57.1%) - 조기 종료 경향
Step 2: 7 questions (33.3%)
Step 3: 1 question (4.8%)
Step 5: 1 question (4.8%)
```

**Confidence**:
- High confidence: 21/21 (100%)
- Despite high confidence, only 19% accuracy → **overconfident**

### GPT-3.5-turbo (Phase 2C Step 1)

**Performance**:
- ✅ **Accuracy**: 42.9% (9/21 correct)
- ✅ **Avg steps**: 3.43 (proper exploration)
- ✅ **Execution time**: 282.7s (~4.7 minutes)
- ✅ **Error rate**: 0.0% (stable)

**Step Distribution**:
```
Step 1: 1 question (4.8%) - 조기 종료 최소화
Step 2: 6 questions (28.6%)
Step 3: 4 questions (19.0%)
Step 4: 3 questions (14.3%)
Step 5: 7 questions (33.3%) - 충분한 탐색
```

**Confidence**:
- High confidence: 16/21 (76.2%)
- Medium: 0/21
- Low: 5/21 (23.8%)
- **Appropriately calibrated confidence**

---

## 📈 Comparison Analysis

### 1. **Accuracy Gap: 23.8pp** (GPT-3.5 wins)

| Aspect | Qwen3-8B | GPT-3.5 | Difference |
|--------|----------|---------|------------|
| Accuracy | 19.0% | 42.9% | **+23.8pp** |
| Relative | 44.4% of GPT-3.5 | 100% | **GPT-3.5 is 2.3x better** |
| Correct | 4/21 | 9/21 | **+5 questions** |

**Root Cause**:
- Qwen3-8B suffers from **조기 종료** (57% at step 1)
- GPT-3.5 explores properly (only 5% at step 1)

### 2. **Speed Gap: 3.9x slower** (GPT-3.5 wins)

| Metric | Qwen3-8B | GPT-3.5 | Ratio |
|--------|----------|---------|-------|
| Total time | 1107s | 283s | **3.9x** |
| Per question | ~53s | ~13s | **4.0x** |
| Per step | ~33s | ~4s | **8.3x** |

**Root Cause**:
- Qwen3-8B generates verbose `<think>` tags (stripped in post-processing)
- Even with stripping, generation is slow
- GPT-3.5 is concise and fast

### 3. **Reasoning Quality Gap**

**Qwen3-8B Issues**:
1. ❌ **Early Termination**: 57.1% at step 1 (vs 4.8% for GPT-3.5)
2. ❌ **Insufficient Exploration**: Avg 1.62 steps (vs 3.43 for GPT-3.5)
3. ❌ **Overconfidence**: 100% high confidence despite 19% accuracy

**GPT-3.5 Strengths**:
1. ✅ **Proper Exploration**: 33.3% reach step 5
2. ✅ **Balanced Steps**: Good distribution across steps
3. ✅ **Calibrated Confidence**: 23.8% low confidence on uncertain answers

---

## 💡 Key Findings

### What Worked: `<think>` Tag Post-Processing ✅

**Implementation**:
```python
# Strip <think>...</think> tags after LLM response
if is_qwen and responses:
    import re
    cleaned = re.sub(r'<think>.*?</think>', '', resp, flags=re.DOTALL)
    cleaned = re.sub(r'</?think>', '', cleaned).strip()
```

**Impact**:
- ✅ Prevents timeout (previous tests hung indefinitely)
- ✅ Enables completion of full dataset
- ✅ Reduces token waste (e.g., 6857 → 305 chars)
- ❌ **Does NOT improve accuracy** (still 19%)

### What Failed: Qwen3-8B's Core Reasoning ❌

Despite fixing the `<think>` tag issue:

1. **Still produces low accuracy**: 19% vs 42.9% for GPT-3.5
2. **Still terminates early**: 57% at step 1
3. **Still slower**: 3.9x slower than GPT-3.5
4. **Overconfident**: 100% high confidence despite poor accuracy

---

## 🎯 Conclusions

### Qwen3-8B is NOT Suitable for MACT

**Reasons**:

1. ❌ **Poor Accuracy**: 19.0% (less than half of GPT-3.5's 42.9%)
2. ❌ **Slow Speed**: 3.9x slower (1107s vs 283s)
3. ❌ **Early Termination**: 57% terminate at step 1
4. ❌ **Insufficient Reasoning**: Avg 1.62 steps vs 3.43 for GPT-3.5
5. ❌ **Overconfidence**: 100% high confidence despite 19% accuracy

Even with `<think>` tag post-processing:
- ✅ Speed improved (from timeout to 1107s)
- ❌ Accuracy still poor (19%)
- ❌ Reasoning quality still inadequate

### GPT-3.5-turbo is Optimal for MACT

**Reasons**:

1. ✅ **Good Accuracy**: 42.9% (2.3x better than Qwen3)
2. ✅ **Fast Speed**: 283s (3.9x faster)
3. ✅ **Proper Exploration**: Only 5% early termination
4. ✅ **Balanced Reasoning**: Avg 3.43 steps
5. ✅ **Calibrated Confidence**: 24% low confidence when uncertain

---

## 📊 Full Comparison Table

| Metric | Qwen3-8B | GPT-3.5 Phase 2C Step 1 | Difference | Winner |
|--------|----------|------------------------|------------|--------|
| **Accuracy** | 19.0% | 42.9% | +23.8pp | **GPT-3.5** |
| **Correct** | 4/21 | 9/21 | +5 | **GPT-3.5** |
| **Error Rate** | 0.0% | 0.0% | - | Tie |
| **Avg Steps** | 1.62 | 3.43 | +1.81 | **GPT-3.5** |
| **Step 1 %** | 57.1% | 4.8% | -52.3pp | **GPT-3.5** |
| **Step 5 %** | 4.8% | 33.3% | +28.5pp | **GPT-3.5** |
| **High Conf %** | 100% | 76.2% | -23.8pp | **GPT-3.5** (better calibrated) |
| **Low Conf %** | 0% | 23.8% | +23.8pp | **GPT-3.5** (acknowledges uncertainty) |
| **Execution Time** | 1107s | 283s | -824s | **GPT-3.5** |
| **Time/Question** | 53s | 13s | -40s | **GPT-3.5** |
| **Time/Step** | 33s | 4s | -29s | **GPT-3.5** |

**Overall Winner**: **GPT-3.5-turbo** (wins 9/10 metrics)

---

## 🔍 Historical Context

### Evolution of Results

| Version | Model | Accuracy | Status |
|---------|-------|----------|--------|
| Original MACT (paper) | GPT-3.5 | 58.8% | ✅ Baseline |
| LG Phase 1 Revised | GPT-3.5 | 28.6% | ✅ |
| **LG Phase 2C Step 1** | **GPT-3.5** | **42.9%** | ✅ **Current Best** |
| Original MACT (old) | Qwen3-8B | 0.0% | ❌ |
| Original MACT (RunPod) | Qwen3-8B | 0.0% | ❌ Timeout |
| LG (no fix) | Qwen3-8B | 0.0% | ❌ Timeout |
| LG (stop tokens) | Qwen3-8B | 0.0% | ❌ Empty responses |
| **LG (think stripping)** | **Qwen3-8B** | **19.0%** | ❌ **Poor accuracy** |

**Gap to Original MACT**:
- GPT-3.5 LG Phase 2C: -15.9pp (58.8% → 42.9%)
- Qwen3-8B LG: -39.8pp (58.8% → 19.0%)

---

## 🚀 Recommendations

### For Production

**Use GPT-3.5-turbo (Phase 2C Step 1)**:
- ✅ 42.9% accuracy (proven)
- ✅ 283s execution time (fast)
- ✅ Stable and reliable
- ✅ No special handling needed

### For Qwen3-8B

**NOT Recommended for MACT**:
- ❌ Poor accuracy (19%) despite fixes
- ❌ Slow speed (3.9x slower)
- ❌ Fundamental reasoning issues

**If must use Qwen3**:
1. Apply `<think>` tag post-processing (required)
2. Expect 19% accuracy (less than half of GPT-3.5)
3. Expect 3.9x slower execution
4. Consider alternative prompting strategies

### Future Research

To close gap to original MACT (58.8%):

1. **Test on full MMQA dataset** (not just samples)
2. **Align prompts with original MACT** exactly
3. **Try GPT-4** for better reasoning
4. **Simplify to single-table approach** (like original)

---

## 📁 Test Files

### Qwen3-8B
- `test_qwen3_full_dataset_fixed/metrics_Qwen_Qwen3-8B_mmqa_samples_*.json`
- `test_qwen3_full_dataset_fixed/predictions_Qwen_Qwen3-8B_mmqa_samples_*.jsonl`
- `qwen3_full_test.log`

### GPT-3.5-turbo
- `test_phase2c_step1_variable_consistency/metrics_gpt-3.5-turbo_mmqa_samples_*.json`
- `test_phase2c_step1_variable_consistency/predictions_gpt-3.5-turbo_mmqa_samples_*.jsonl`

### Code Changes
- `src/mact_langgraph/nodes/core_nodes.py` (lines 62-103): Planning `<think>` stripping
- `src/mact_langgraph/nodes/tool_nodes.py` (lines 65-104): Code gen `<think>` stripping

---

## 🎓 Lessons Learned

### 1. "Post-Processing Can Fix Format Issues"
- `<think>` tag stripping enabled Qwen3 to complete
- Prevented timeouts and empty responses
- **BUT** did not fix accuracy issues

### 2. "Model Quality Matters More Than Fixes"
- Qwen3-8B: 19% despite all fixes
- GPT-3.5: 42.9% with simple implementation
- **Core reasoning ability > technical fixes**

### 3. "Speed and Accuracy Are Correlated"
- Qwen3: Verbose + slow + inaccurate
- GPT-3.5: Concise + fast + accurate
- **Better models are better in all dimensions**

### 4. "Early Termination Indicates Poor Reasoning"
- Qwen3: 57% step 1 termination → 19% accuracy
- GPT-3.5: 5% step 1 termination → 42.9% accuracy
- **Proper exploration essential for accuracy**

### 5. "Confidence Calibration Matters"
- Qwen3: 100% high conf + 19% accuracy = overconfident
- GPT-3.5: 76% high conf + 42.9% accuracy = calibrated
- **Well-calibrated models are more reliable**

---

## 📊 Summary

### Best Configuration

**Model**: GPT-3.5-turbo
**Version**: Phase 2C Step 1
**Accuracy**: 42.9%
**Speed**: 283s
**Status**: ✅ Production-ready

### Qwen3-8B Status

**With `<think>` stripping**:
- ✅ No timeout (improved)
- ✅ Full dataset completion (improved)
- ❌ Poor accuracy: 19% (still bad)
- ❌ Slow speed: 3.9x vs GPT-3.5 (still bad)
- ❌ Early termination: 57% (still bad)

**Conclusion**: **Not suitable for MACT**, even with fixes.

---

**Analysis Complete**: 2025-10-05 06:48 KST
**Final Recommendation**: Use GPT-3.5-turbo Phase 2C Step 1 (42.9%)
**Qwen3-8B Status**: Not recommended (19.0%, 3.9x slower)
