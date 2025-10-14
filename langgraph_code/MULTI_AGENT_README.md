# Multi-Agent Framework for Table QA

A sophisticated multi-agent architecture extending the LangGraph-based MACT implementation with specialized agents for exploratory data analysis, planning, coding, validation, and report generation.

## Overview

This framework introduces a **5-agent architecture** that enhances table question answering through:

1. **EDA Agent**: Analyzes tables and generates contextual information
2. **Planning Agent**: Creates action plans leveraging EDA insights
3. **Coding Agent**: Generates and executes code with majority voting
4. **Validator Agent**: Validates results and manages reasoning loops
5. **Report Generator**: Formats outputs for different use cases

### Key Improvements Over Base MACT

- 🔍 **Automatic Table Analysis**: EDA Agent pre-analyzes tables and detects relationships
- 🎯 **Enhanced Context**: Planning Agent uses table insights for better reasoning
- 📊 **Flexible Output**: Report Generator supports multiple output formats
- 🔄 **Modular Design**: Easy to extend with new agents (e.g., R-Zero)

## Architecture

```
Input (Question + Tables)
    ↓
┌───────────────────────────────────────────────┐
│  EDA Agent                                    │
│  - Analyze table schemas                     │
│  - Detect foreign key relationships          │
│  - Extract statistical patterns              │
│  - Generate natural language context         │
└───────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────┐
│  Planning Agent (with EDA context)           │
│  - Generate action candidates                │
│  - Leverage table insights                   │
└───────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────┐
│  Coding Agent                                 │
│  - Select best action                        │
│  - Execute code with majority voting         │
└───────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────┐
│  Validator Agent                              │
│  - Validate execution results                │
│  - Check termination conditions              │
│  - Loop back to Planning or finish           │
└───────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────┐
│  Report Generator                             │
│  - Aggregate final answer                    │
│  - Calculate confidence scores               │
│  - Format output (MMQA JSON, Business, etc.) │
└───────────────────────────────────────────────┘
    ↓
Output (Formatted Results)
```

## Installation

```bash
# Navigate to langgraph_code directory
cd MACT/langgraph_code

# Install dependencies (if not already installed)
pip install -r requirements.txt

# Set up environment
export OPENAI_API_KEY="your_key_here"
```

## Quick Start

### 1. Test the Framework

Run the test script to verify everything works:

```bash
python test_multi_agent.py
```

This will run two test cases:
- Single-table question (simple aggregation)
- Multi-table question (with JOIN operations)

### 2. Run on MMQA Dataset

```bash
# Basic run with MMQA JSON output
python multi_agent_main.py \
    --dataset_path ../datasets_examples/mmqa_samples.json \
    --plan_model gpt-3.5-turbo \
    --code_model gpt-3.5-turbo \
    --output_format mmqa_json \
    --output_dir multi_agent_results

# Debug mode (process only 3 questions)
python multi_agent_main.py \
    --dataset_path ../datasets_examples/mmqa_samples.json \
    --plan_model gpt-3.5-turbo \
    --code_model gpt-3.5-turbo \
    --output_format mmqa_json \
    --debug --debug_limit 3 \
    --output_dir debug_results
```

### 3. Try Different Output Formats

```bash
# Business report format (natural language)
python multi_agent_main.py ... --output_format business_report

# Detailed research format (full execution details)
python multi_agent_main.py ... --output_format research_detailed

# Simple answer only
python multi_agent_main.py ... --output_format simple_answer
```

## Output Formats

### 1. MMQA JSON (`mmqa_json`)
For MMQA dataset evaluation. Includes answer and subtasks:
```json
{
  "answer": "42",
  "foreign_keys": ["table1.id = table2.student_id"],
  "primary_keys": ["table1.id"],
  "sql": "SELECT COUNT(*) FROM table1 JOIN table2 ON ...",
  "confidence": 0.85
}
```

### 2. Business Report (`business_report`)
Natural language report for business stakeholders:
```json
{
  "report": "## Executive Summary\n**Question:** ...\n**Answer:** ...",
  "answer": "42",
  "confidence": 0.85
}
```

### 3. Research Detailed (`research_detailed`)
Complete execution details for research analysis:
```json
{
  "question": "...",
  "answer": "42",
  "eda_context": "...",
  "step_history": [...],
  "confidence_breakdown": {...},
  "total_input_tokens": 1234,
  "total_output_tokens": 567
}
```

### 4. Simple Answer (`simple_answer`)
Just the answer string:
```json
{
  "answer": "42"
}
```

## Configuration Options

### Model Selection
```bash
--plan_model gpt-3.5-turbo    # Model for Planning Agent
--code_model gpt-3.5-turbo    # Model for Coding Agent
```

### Agent Parameters
```bash
--plan_sample 3        # Number of action candidates to generate
--code_sample 3        # Number of code samples for majority voting
--max_steps 6          # Maximum reasoning steps
--reward_type consistency  # Action selection strategy
```

### Reward Types
- `consistency`: Majority voting on action types (default, fastest)
- `llm`: LLM-based evaluation
- `logp`: Log probability scoring
- `rollout`: Full look-ahead simulation
- `combined`: Ensemble of all strategies

## Directory Structure

```
MACT/langgraph_code/
├── multi_agent_main.py          # Main entry point
├── test_multi_agent.py          # Test script
├── MULTI_AGENT_README.md        # This file
│
├── src/multi_agent/             # Multi-Agent framework
│   ├── __init__.py
│   ├── state.py                 # Extended state schema
│   ├── graph.py                 # Multi-agent graph definition
│   │
│   ├── agents/                  # Agent implementations
│   │   ├── eda_agent.py         # Table analysis & context
│   │   ├── planning_agent.py   # Action planning
│   │   ├── coding_agent.py     # Code execution
│   │   ├── validator_agent.py  # Result validation
│   │   └── report_agent.py     # Output formatting
│   │
│   └── utils/                   # Utilities
│       ├── context_utils.py    # Context management
│       └── ...                 # Reuses mact_langgraph.utils
│
├── claude_logs/                 # Development documentation
│   ├── PROJECT_CONTEXT.md      # Project overview
│   ├── CURRENT_TASK.md         # Current work status
│   └── DECISIONS.md            # Design decisions log
│
└── src/mact_langgraph/         # Original MACT (reused)
    ├── nodes/                  # Core MACT nodes
    └── utils/                  # MACT utilities
```

## Agent Details

### EDA Agent
**Purpose**: Pre-analyze tables to provide context for reasoning

**Capabilities**:
- Schema analysis (column types, null ratios, unique counts)
- Foreign key detection (name matching + value overlap)
- Statistical profiling (ranges, distributions, patterns)
- Natural language context generation

**Output**: Enriched context injected into Planning Agent prompts

### Planning Agent
**Purpose**: Generate action candidates with enhanced context

**How it works**: Wraps the original MACT planner with EDA context injection

**Benefits**: Better action plans informed by table structure and relationships

### Coding Agent
**Purpose**: Select and execute the best action

**How it works**:
1. Selects best action using reward function
2. Routes to appropriate tool (Retrieve, Operate, Calculate, Search)
3. Executes code with majority voting (reuses MACT tools)

**Safety**: Majority voting ensures robustness against unreliable code generation

### Validator Agent
**Purpose**: Validate results and manage reasoning loop

**Capabilities**:
- Record execution observations
- Validate result quality (using EDA statistics)
- Check termination conditions (finished, halted, continue)
- Provide enhanced feedback for next iteration

### Report Generator
**Purpose**: Format output according to user requirements

**Capabilities**:
- Answer aggregation with confidence scoring
- Flexible output formatting (4 formats supported)
- Reasoning report generation
- MMQA subtask extraction (FK, PK, SQL)

## Comparison with Base MACT

| Feature | Base MACT | Multi-Agent |
|---------|-----------|-------------|
| Table Analysis | Manual FK specification | ✅ Automatic EDA |
| Context | Basic table representation | ✅ Rich analysis context |
| Output Format | Fixed MMQA format | ✅ 4 flexible formats |
| Agent Architecture | Node-based workflow | ✅ Specialized agents |
| Extensibility | Moderate | ✅ High (agent paradigm) |
| Reasoning Quality | Good | ✅ Enhanced (EDA insights) |

## Performance Expectations

Based on base MACT performance (MMQA 21 questions):
- **Accuracy**: Target ≥42.9% (baseline)
- **Speed**: ~16-20s/question (includes EDA overhead)
- **Error Rate**: Target 0%
- **EDA Overhead**: ~1-2s per question (one-time cost)

## Future Enhancements (Step 2: R-Zero)

The modular agent design enables easy extension with:

1. **Challenger Agent**: Generate difficult table QA problems
2. **Solver Agent**: Solve problems and record solutions
3. **Memory System**: Store and retrieve solution patterns
4. **Approach Library**: Build knowledge base of table QA strategies

See `claude_logs/PROJECT_CONTEXT.md` for roadmap details.

## Troubleshooting

### Import Errors
```bash
# Make sure you're in the langgraph_code directory
cd MACT/langgraph_code

# Python path issues - the scripts handle this automatically
```

### API Key Not Set
```bash
export OPENAI_API_KEY="your_key_here"

# For RunPod vLLM endpoints
export OPENAI_API_BASE="https://api.runpod.ai/v2/your_endpoint/openai/v1"
```

### Low Accuracy
- Try increasing `--plan_sample` and `--code_sample` (e.g., 5 each)
- Try more sophisticated reward type: `--reward_type combined`
- Check execution logs in output files for specific failure patterns

### Slow Execution
- Reduce `--plan_sample` and `--code_sample` (e.g., 2 each)
- Use `--reward_type consistency` (fastest)
- Use debug mode for quick testing: `--debug --debug_limit 3`

## Development Logs

For detailed development context, design decisions, and progress:
- [PROJECT_CONTEXT.md](claude_logs/PROJECT_CONTEXT.md) - Project overview
- [CURRENT_TASK.md](claude_logs/CURRENT_TASK.md) - Current status
- [DECISIONS.md](claude_logs/DECISIONS.md) - Design rationale

## License

Same as parent MACT project.

## Citation

If you use this multi-agent framework, please cite the original MACT paper:
```
@inproceedings{mact2025,
  title={MACT: Multi-Agent Collaboration with Tool use for Table Question Answering},
  booktitle={NAACL 2025},
  year={2025}
}
```
