# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository contains two implementations of MACT (Multi-Agent Collaboration with Tool use), a NAACL 2025 framework for complex table question answering:

1. **Original MACT** (`code/`) - The baseline implementation
2. **LangGraph MACT** (`langgraph_code/`) - A LangGraph-based reimplementation with performance optimizations

Both implementations are actively developed and maintained on separate branches.

## Project Structure

```
MACT/
├── code/                           # Original MACT implementation
│   ├── tqa.py                      # Main entry point for original MACT
│   ├── agents.py                   # Agent classes (ReactAgent)
│   ├── llm.py                      # LLM interface (OpenAI + RunPod vLLM)
│   ├── tot.py                      # Tree-of-thought action selection
│   └── utils.py                    # Helper functions
│
├── langgraph_code/                 # LangGraph reimplementation
│   ├── main.py                     # Entry point for LangGraph version
│   ├── src/mact_langgraph/
│   │   ├── graph.py                # LangGraph workflow definition
│   │   ├── state.py                # State schema (MACTState TypedDict)
│   │   ├── nodes/
│   │   │   ├── core_nodes.py       # Planner, selector, finish nodes
│   │   │   ├── tool_nodes.py       # Retriever, operator, calculator
│   │   │   └── subtask_nodes.py    # MMQA subtask extraction (Phase 3A)
│   │   └── utils/
│   │       ├── mmqa_utils.py       # MMQA dataset handling
│   │       ├── prompt_utils.py     # Prompt templates (REACT format)
│   │       ├── table_utils.py      # Pandas code execution & JOIN logic
│   │       ├── result_utils.py     # Results saving & metrics
│   │       └── subtask_extraction.py # LLM-based FK extraction
│   └── logs_ai/                    # Development logs & analysis
│
└── datasets_examples/              # Sample datasets
    ├── mmqa_samples.json           # 21-question MMQA test set
    └── mmqa_two_table_0.1_filtered.json  # Multi-table subset
```

## Common Commands

### Environment Setup

```bash
# Create conda environment
conda create --name mact python=3.10 -y
conda activate mact

# Install dependencies (choose one)
pip install -r requirements.txt                    # Original MACT
pip install -r langgraph_code/requirements.txt     # LangGraph version
```

### Running Tests

#### Original MACT
```bash
cd code/
export OPENAI_API_KEY="your_key"
export OPENAI_API_BASE="https://api.openai.com/v1"  # or RunPod URL

# WTQ dataset example
python tqa.py --plan_model_name gpt-3.5-turbo \
              --code_model_name gpt-3.5-turbo \
              --dataset_path ../datasets_examples/wtq.jsonl \
              --task wtq \
              --plan_sample 5 \
              --code_sample 5 \
              --as_reward consistency
```

#### LangGraph MACT
```bash
cd langgraph_code/
export OPENAI_API_KEY="your_key"

# Basic run with GPT-3.5-turbo
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
               --plan_model "gpt-3.5-turbo" \
               --code_model "gpt-3.5-turbo" \
               --plan_sample 3 \
               --code_sample 3 \
               --output_dir test_results

# Debug mode (limit to 3 questions)
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
               --plan_model "gpt-3.5-turbo" \
               --code_model "gpt-3.5-turbo" \
               --debug --debug_limit 3 \
               --output_dir debug_test

# With Qwen via RunPod vLLM
export OPENAI_API_BASE="https://api.runpod.ai/v2/your_endpoint/openai/v1"
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
               --plan_model "Qwen/Qwen3-8B" \
               --code_model "Qwen/Qwen3-8B" \
               --plan_sample 3 \
               --code_sample 3 \
               --output_dir test_qwen
```

### Running Evaluation Tools

```bash
cd langgraph_code/

# Compare two test runs
python compare_results.py

# Evaluate MMQA subtask predictions (FK, PK, SQL)
python evaluate_mmqa.py \
  --predictions test_results/predictions_*.jsonl \
  --ground_truth ../datasets_examples/mmqa_samples.json
```

## Architecture & Design Principles

### Original MACT Architecture

The original implementation uses a class-based agent design:

- **ReactAgent** (agents.py:40-800): Main agent class with:
  - `run()`: Execute reasoning loop until answer or max steps
  - `numerical_tool()`: Execute code with **majority voting** across `code_sample` attempts
  - `as_reward_fn()`: Select best action using 5 reward strategies:
    - `consistency`: Action type majority voting
    - `llm`: LLM-based evaluation
    - `logp`: Log probability scoring
    - `rollout`: Full look-ahead simulation
    - `combined`: Ensemble of all strategies

**Critical Pattern**: All tool executions use **majority voting** to handle unreliable code generation (agents.py:430-485).

### LangGraph MACT Architecture

The LangGraph version uses a graph-based workflow with state passing:

**State Flow**:
```
Input → Planner → Selector → Tool Execution → Observation → Check → (loop or finish)
```

**Key Nodes** (src/mact_langgraph/nodes/):
1. **planner_node**: Generate `plan_sample` action candidates
2. **action_selector_node**: Select best action using reward function
3. **Tool nodes** (retriever, operator, calculator): Execute actions with **majority voting**
4. **check_finished_node**: Decide next action (loop, finish, or halt)

**State Schema** (state.py:97-175):
- `MACTState`: TypedDict with 40+ fields for reasoning state
- All data serialized as dicts/lists for LangGraph compatibility
- Key fields: `candidate_actions`, `tool_results`, `scratchpad`, `final_answer`

### Critical Implementation Details

#### 1. Majority Voting in Tool Execution

Both implementations must generate multiple code samples and use majority voting:

```python
# Tool nodes in langgraph_code/src/mact_langgraph/nodes/tool_nodes.py
# Lines 163-196 (retriever), 376-408 (operator)

successful_results = []
for code in codes:
    result, rows, error, _ = execute_table_code(code, table_df_code)
    if result and rows and not error:
        successful_results.append(result)

# Majority voting
if successful_results:
    result_counts = Counter(successful_results)
    best_result = result_counts.most_common(1)[0][0]
```

**Important**: Never use `break` after first success - always execute all samples and vote.

#### 2. Batch API Calls for Performance

To match original MACT speed, use OpenAI's `n` parameter for batch generation:

```python
# In core_nodes.py:115-140
response = await llm.async_client.chat.completions.create(
    model=state["plan_model"],
    messages=[{"role": "user", "content": prompt}],
    max_tokens=2048,
    temperature=0.3,
    n=plan_sample,  # Generate multiple candidates in one call
    logprobs=True,  # For logp reward strategy
    top_logprobs=5
)
```

#### 3. Table JOIN Logic

Multi-table operations require careful variable scoping:

```python
# In table_utils.py:execute_table_code()
# Lines 430-505

# Create exec namespace with all dataframes
exec_namespace = {"pd": pd}
for table in tables:
    exec_namespace[table.name] = table_df  # Add each table as variable

# Execute combined code (df definitions + user code)
combined_code = table_df_code + "\n" + code
exec(combined_code, exec_namespace)

# Extract result from 'new_table' variable
new_table = exec_namespace.get("new_table")
```

#### 4. MMQA-Specific Features (Phase 3A)

The LangGraph version includes optional MMQA subtask extraction:

- **Foreign Key Extraction**: LLM-based FK discovery from table schemas (subtask_extraction.py)
- **Primary Key Extraction**: Similar LLM-based approach
- **SQL Generation**: Optional SQL output for compatibility

These features are **dataset-specific** and can be disabled with `--no_examples` flag for dataset-agnostic operation.

## Performance Benchmarks

### Baseline Performance (GPT-3.5-turbo, MMQA 21 questions)

| Metric | Original MACT | LangGraph (Current) | Notes |
|--------|---------------|---------------------|-------|
| **Accuracy** | ~58.8% | 42.9% | Target: match original |
| **Speed** | ~5-10s/question | 13.5s/question | 30-50x faster than initial version |
| **Error Rate** | ~5% | 0% | Better error handling |

### Optimization History

- **Initial LangGraph**: 10-20 min/question (10-20x slower than original)
- **Phase 1**: Reduced sampling (plan=3, code=3) → 42s/question (15-30x speedup)
- **Phase 2**: Batch API + majority voting → 13.5s/question
- **Phase 3**: Ongoing accuracy improvements (42.9% → target 50%+)

See `langgraph_code/logs_ai/PERFORMANCE_OPTIMIZATION_PLAN.md` for detailed optimization history.

## Development Workflow

### Branch Strategy

- **main**: Stable releases
- **langgraph_mmqa**: Active LangGraph development (current branch)
- **cs8903**: Course-specific experiments

### Testing Protocol

When making changes that affect accuracy:

1. **Run baseline test** (if not recent):
   ```bash
   python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
                  --plan_model "gpt-3.5-turbo" \
                  --code_model "gpt-3.5-turbo" \
                  --plan_sample 3 --code_sample 3 \
                  --output_dir test_baseline
   ```

2. **Run modified version** with clear naming:
   ```bash
   python main.py ... --output_dir test_<feature_name>
   ```

3. **Compare results**:
   ```bash
   python compare_results.py
   # Check: accuracy, avg steps, execution time, error rate
   ```

4. **Document in logs_ai/** if significant:
   - Create `logs_ai/<PHASE_NAME>_<DATE>.md`
   - Include: baseline metrics, changes made, results, decision

### Key Files for Common Tasks

| Task | Primary Files | Notes |
|------|---------------|-------|
| Add new agent action | `nodes/core_nodes.py`, `nodes/tool_nodes.py` | Follow ActionType enum pattern |
| Modify prompts | `utils/prompt_utils.py` | Lines 161-230 for REACT prompt |
| Change reward strategy | `nodes/core_nodes.py` | Lines 487-550 for selector logic |
| Fix table JOIN bugs | `utils/table_utils.py` | execute_table_code() function |
| Add dataset support | `utils/mmqa_utils.py` | load_dataset_universal() |
| Modify result format | `utils/result_utils.py` | save_prediction_item() |

## Common Issues & Solutions

### Issue: "department_ID" KeyError in Table Operations

**Cause**: Column name case mismatch between tables
**Solution**: Use `utils/table_utils.py:normalize_column_name()` consistently
**Example**: See Phase 2C analysis in `logs_ai/PHASE2C_IMPROVEMENT_PLAN.md`

### Issue: Agent Finishes Immediately (0 steps)

**Cause**: First-step Finish action not prevented
**Solution**: Validate action in `core_nodes.py:action_selector_node()`
```python
if state["current_step"] == 1 and selected_action.action_type == ActionType.FINISH:
    # Force alternative action or reject
```

### Issue: Low Accuracy with Qwen Models

**Cause**: Verbose code generation with syntax errors
**Solution**: Use aggressive code cleaning in `table_utils.py:clean_qwen_code()`
**Note**: Majority voting helps recover from occasional failures

### Issue: Slow Execution Speed

**Causes & Solutions**:
1. **Sequential API calls**: Use batch `n` parameter
2. **Large scratchpad**: Implement observation summarization
3. **Too many samples**: Reduce plan_sample/code_sample (3 is optimal)
4. **No early termination**: Add confidence-based stopping (optional)

## Important Notes

### Model Compatibility

The unified LLM interface (llm.py, llm_utils.py) automatically routes models:
- **OpenAI models** (gpt-3.5-turbo, gpt-4): Direct OpenAI API
- **Open-source models** (Qwen/*, meta-llama/*): RunPod vLLM endpoint

Set `OPENAI_API_BASE` to control routing:
- OpenAI: `https://api.openai.com/v1`
- RunPod: `https://api.runpod.ai/v2/<endpoint_id>/openai/v1`

### Dataset Format Requirements

All datasets must include:
```json
{
  "statement": "question text",           // or "Question"
  "table_text": [[col1, col2], ...],      // or "tables" for MMQA
  "answer": ["answer1", "answer2"]        // list format
}
```

MMQA-specific fields (optional):
```json
{
  "foreign_keys": ["table1.col = table2.col"],
  "primary_keys": ["table1.id"],
  "sql": "SELECT ... FROM ..."  // reference SQL (not executed)
}
```

### Logging & Debugging

Enable detailed logging:
```bash
# LangGraph version
python main.py --debug --debug_limit 1 ...

# Check execution log in results
cat test_results/predictions_*.jsonl | jq '.execution_log'
```

Key debug info locations:
- **API calls**: Look for "DEBUG: Generated X candidates" in stdout
- **Code execution**: Check "DEBUG: Executing combined code" messages
- **Majority voting**: "Majority voting: ... appeared X/Y times"
- **State transitions**: See step_history in result JSON

### Performance Optimization Guidelines

When optimizing, maintain this priority order:
1. **Correctness** (accuracy) > Speed > Memory
2. **Majority voting** is non-negotiable (prevents unreliable code issues)
3. **Batch API calls** for speed (2-3x speedup)
4. **Avoid dataset-specific hacks** (maintain generalizability)

See `logs_ai/PHASE3A_PLAN.md` for dataset-agnostic improvement strategies.

## Git Commit Guidelines

When committing significant changes:

1. **Include metrics in commit message**:
   ```
   Phase X: Description of change

   - Accuracy: X% → Y% (±Z%p)
   - Speed: Xs/q → Ys/q
   - Modified: file1.py (lines X-Y), file2.py

   🤖 Generated with Claude Code
   Co-Authored-By: Claude <noreply@anthropic.com>
   ```

2. **Document in logs_ai/** for experimental phases

3. **Test results directory naming**: `test_<phase>_<description>`
   - Example: `test_phase3a_dataset_agnostic`
   - Git-ignored, but keep for comparison

## Reference Documentation

- **Original Paper**: arXiv:2412.20145 (NAACL 2025)
- **Dev Logs**: `langgraph_code/logs_ai/` (30+ analysis documents)
- **Performance Plans**: See `PERFORMANCE_OPTIMIZATION_PLAN.md`, `PHASE3A_PLAN.md`
- **Comparison Reports**: `COMPARISON_REPORT_GPT35.md`, `QWEN3_VS_GPT35_FINAL_COMPARISON.md`
