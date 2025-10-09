# MACT LangGraph Implementation

This is a LangGraph-based implementation of the MACT (Multi-Agent Code generation and Tool use) framework for table reasoning tasks.

## Overview

This project converts the original MACT framework into a LangGraph workflow while maintaining compatibility with the MMQA dataset and original functionality.

## Key Features

- **Multi-Agent Workflow**: Planner, Retriever, Operator, Calculator, and Searcher agents
- **Majority Voting**: Robust code generation with 3-sample majority voting
- **Multiple Reward Strategies**: Consistency, LLM, LogP, Rollout, and Combined rewards
- **Model Support**: OpenAI GPT models and Qwen models via RunPod vLLM
- **Performance Optimizations**: Batch processing and efficient LLM calls

## Directory Structure

```
├── src/mact_langgraph/           # Core implementation
│   ├── graph.py                  # LangGraph workflow definition
│   ├── nodes/                    # Agent node implementations
│   │   ├── core_nodes.py         # Planner and action selector
│   │   └── tool_nodes.py         # Retriever, operator, calculator nodes
│   └── utils/                    # Utility functions
│       ├── mmqa_utils.py         # MMQA dataset handling
│       ├── prompt_utils.py       # Prompt templates
│       ├── table_utils.py        # Table processing and code execution
│       └── result_utils.py       # Results processing
├── config/                       # Configuration files
├── logs_ai/                      # Documentation and analysis logs
└── test_*/                       # Experimental test results (git-ignored)
```

## Recent Development (Phase 3)

### Performance Improvements
- **Speed**: 30-50x improvement from initial implementation
- **Accuracy**: Achieved 14.3% accuracy (up from 0%) on MMQA dataset
- **Robustness**: Fixed critical batch API and column name mapping bugs

### Key Fixes
1. **Batch API Bug**: Fixed AsyncCompletions compatibility issue
2. **First-step Finish Prevention**: Added validation to prevent immediate termination
3. **Column Name Mapping**: Enhanced table JOIN operations with robust column handling
4. **Majority Voting**: Restored original MACT's 3-sample voting mechanism

## Usage

```bash
# Basic usage with GPT-3.5-turbo
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
               --plan_model "gpt-3.5-turbo" \
               --code_model "gpt-3.5-turbo" \
               --output_dir results

# With Qwen model via RunPod
export OPENAI_API_KEY="your_runpod_key"
export OPENAI_API_BASE="https://api.runpod.ai/v2/your_endpoint/openai/v1"
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
               --plan_model "Qwen/Qwen3-8B" \
               --code_model "Qwen/Qwen3-8B" \
               --output_dir results
```

## Configuration

- **Plan/Code Sampling**: Default 3 samples each for robust majority voting
- **Max Steps**: 6 steps maximum per question
- **Reward Types**: consistency (default), llm, logp, rollout, combined
- **Models**: GPT-3.5-turbo, GPT-4, Qwen models via vLLM

## Documentation

All development logs, analysis reports, and optimization plans are stored in the `logs_ai/` directory:

- `PERFORMANCE_OPTIMIZATION_PLAN.md`: Comprehensive optimization tracking
- `gpt35_phase2_analysis_report.md`: Phase 2 analysis results
- `code_revision.md`: Code change documentation

## Known Issues

1. **Column Name Mapping**: Some edge cases in multi-table JOIN operations
2. **ActionCandidate Compatibility**: Interface compatibility issues in some scenarios
3. **MMQA Dataset Specifics**: Need further optimization for complex table structures

## Next Steps

1. Fix remaining ActionCandidate compatibility issues
2. Complete column name mapping logic rewrite
3. Enhance multi-table JOIN operations for MMQA dataset
4. Performance testing with larger datasets

## License

This project is part of academic research for CS8903 at Georgia Tech.