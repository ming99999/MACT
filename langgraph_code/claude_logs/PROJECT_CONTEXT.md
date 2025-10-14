# Project Context: Multi-Agent Framework for Table QA

## Project Overview

This project extends the existing LangGraph-based MACT (Multi-Agent Collaboration with Tool use) implementation with a sophisticated multi-agent architecture that includes specialized agents for Exploratory Data Analysis (EDA), planning, coding, validation, and report generation.

## Background

### Original MACT (langgraph_code/)
- **Architecture**: LangGraph state-based workflow
- **Flow**: Input → Planner → Selector → Tool Execution → Observer → Termination Check
- **Performance**: 42.9% accuracy on MMQA (21 questions), 13.5s/question
- **Limitations**:
  - Limited table understanding (no pre-analysis)
  - Fixed output format
  - No domain knowledge extraction

### Research Goals
1. **Step 1 (Current)**: Multi-Agent framework with EDA Agent
   - Add EDA Agent for table analysis and context generation
   - Refactor existing MACT into specialized agents
   - Add Report Generator for flexible output formatting

2. **Step 2 (Future)**: R-Zero integration
   - Challenger agent for generating difficult questions
   - Solver agent with solution memory
   - Memory-based approach improvement

## Project Structure

```
MACT/
├── code/                          # Original MACT implementation
├── langgraph_code/                # Current LangGraph MACT
│   ├── main.py                    # Entry point
│   ├── src/mact_langgraph/        # Existing MACT implementation
│   │   ├── graph.py               # Current graph definition
│   │   ├── state.py               # Current state schema
│   │   ├── nodes/                 # Core + Tool nodes
│   │   └── utils/                 # Utilities
│   └── src/multi_agent/           # NEW: Multi-Agent Framework
│       ├── state.py               # Extended state with EDA context
│       ├── graph.py               # Multi-agent graph
│       ├── agents/
│       │   ├── eda_agent.py       # Table analysis & context generation
│       │   ├── planning_agent.py  # Action planning with EDA context
│       │   ├── coding_agent.py    # Code generation & execution
│       │   ├── validator_agent.py # Result validation
│       │   └── report_agent.py    # Flexible output formatting
│       └── utils/
│           ├── eda_utils.py       # Table analysis utilities
│           ├── context_utils.py   # Context management
│           └── ...                # Reuse existing utilities
└── datasets_examples/
    ├── mmqa_samples.json          # Test dataset (21 questions)
    └── mmqa_two_table_0.1_filtered.json
```

## Key Design Principles

1. **Agent Specialization**: Each agent has a clear, focused responsibility
2. **Context Enhancement**: EDA Agent enriches input with table understanding
3. **Flexibility**: Report Agent adapts output format to user requirements
4. **Reusability**: Leverage existing MACT utilities and LLM infrastructure
5. **Performance**: Maintain or improve accuracy while keeping execution time reasonable

## Technology Stack

- **Framework**: LangGraph (state-based multi-agent orchestration)
- **LLM**: OpenAI GPT-3.5/GPT-4 (with fallback to Qwen via RunPod)
- **Data Processing**: Pandas for table operations
- **Language**: Python 3.10+

## Target Datasets

- **MMQA (Multi-Modal Question Answering)**
  - Multi-table questions requiring JOIN operations
  - Subtasks: FK detection, PK extraction, SQL generation
  - Evaluation metrics: Accuracy, FK F1, PK F1, SQL exact match

## Success Criteria

### Functional
- EDA Agent successfully analyzes tables and generates useful context
- Planning Agent utilizes EDA context for better action planning
- Report Agent produces flexible, user-specified output formats
- System solves MMQA questions end-to-end

### Performance
- **Accuracy**: ≥ 42.9% (maintain baseline) or improve
- **Speed**: < 16.2s/question (+20% tolerance from 13.5s baseline)
- **Robustness**: 0% error rate on valid inputs

### Code Quality
- Clear agent separation and responsibilities
- Well-documented decision rationale
- Easy to extend with new agents (R-Zero preparation)

## Related Documentation

- [CURRENT_TASK.md](./CURRENT_TASK.md) - Current implementation details
- [DECISIONS.md](./DECISIONS.md) - Design decisions log
- [../CLAUDE.md](../CLAUDE.md) - Original MACT documentation
