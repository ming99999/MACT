# MACT LangGraph Implementation

Multi-Agent Collaboration with Tool Use for Table Question Answering implemented using LangGraph framework.

## Overview

This project reimplements the MACT (Multi-Agent Collaboration with Tool Use) framework using LangGraph, providing a modern, modular, and extensible approach to table question answering. The implementation is specifically optimized for MMQA (Multi-Modal Question Answering) datasets with multi-table scenarios.

## Features

- **LangGraph Architecture**: Modern state graph-based execution
- **Multi-Agent Collaboration**: Coordinated reasoning across specialized agents
- **Tool Integration**: Table operations, calculations, search, and complex queries
- **MMQA Support**: Optimized for multi-table question answering
- **Flexible Reward Functions**: Multiple action selection strategies
- **Async Execution**: High-performance asynchronous processing
- **Comprehensive Logging**: Detailed execution tracking and debugging

## Installation

1. Clone and navigate to the project:
```bash
cd langgraph_code
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.template .env
# Edit .env with your API keys
```

## Quick Start

### Basic Usage

```python
import asyncio
from mact_langgraph.graph import run_mact_on_question_async

# Define your question and tables
question = "Which department has the largest number of employees?"
tables_data = [
    {
        "table_columns": ["Department_ID", "Name", "Num_Employees"],
        "table_content": [
            [1, "State", 30266],
            [2, "Treasury", 115897],
            [3, "Defense", 3000000]
        ]
    }
]

# Run MACT
async def main():
    result = await run_mact_on_question_async(question, tables_data)
    print(f"Answer: {result['final_answer']}")
    print(f"Confidence: {result['confidence']}")

asyncio.run(main())
```

### Command Line Usage

```bash
# Run on MMQA dataset
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
               --plan_model gpt-3.5-turbo \
               --code_model gpt-3.5-turbo \
               --output_path results.json

# Debug mode (process only first 3 items)
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
               --debug --debug_limit 3

# Different reward function
python main.py --dataset_path ../datasets_examples/mmqa_samples.json \
               --reward_type llm \
               --plan_sample 3 \
               --code_sample 3
```

### Examples

Run the example script to see various usage patterns:

```bash
python run_examples.py
```

## Architecture

### State Flow

```
[Input] → input_processor → planner → action_selector → [Tools]
                               ↑                          ↓
                   termination_checker ← observer
                               ↓
                   answer_aggregator → [Output]
```

### Core Components

1. **State Management**: `MACTState` - Comprehensive state tracking
2. **Core Nodes**: Planning, action selection, observation, termination
3. **Tool Nodes**: Retrieval, calculation, search, complex operations
4. **Graph Orchestration**: LangGraph-based workflow management

### Tool Capabilities

- **Retriever**: Table filtering and data extraction
- **Calculator**: Mathematical computations and expressions
- **Search**: External knowledge retrieval (Wikipedia)
- **Operator**: Complex table operations (JOIN, GROUP BY, etc.)

## Configuration

### Model Configuration

```python
config = {
    "plan_model": "gpt-3.5-turbo",      # Planning model
    "code_model": "gpt-3.5-turbo",      # Code generation model
    "reward_type": "consistency",        # Action selection method
    "plan_sample": 5,                   # Number of planning candidates
    "code_sample": 5,                   # Number of code attempts
    "max_steps": 6,                     # Maximum reasoning steps
    "max_actual_steps": 6,              # Maximum total steps
    "use_pre_answer": True,             # Use preliminary answers
    "answer_threshold": 1.0             # Answer agreement threshold
}
```

### Reward Functions

- **consistency**: Majority voting on action types
- **llm**: LLM-based candidate evaluation
- **logp**: Log probability-based selection
- **rollout**: Rollout-based evaluation
- **combined**: Multi-method combination

## Project Structure

```
langgraph_code/
├── src/mact_langgraph/
│   ├── __init__.py
│   ├── state.py                 # State schema and management
│   ├── graph.py                 # Main graph definition
│   ├── nodes/
│   │   ├── core_nodes.py        # Core reasoning nodes
│   │   └── tool_nodes.py        # Tool execution nodes
│   └── utils/
│       ├── table_utils.py       # Table processing utilities
│       ├── action_utils.py      # Action parsing utilities
│       ├── prompt_utils.py      # Prompt building utilities
│       └── mmqa_utils.py        # MMQA-specific utilities
├── tests/
│   └── test_basic.py           # Basic tests
├── config/
│   └── config.yaml             # Configuration file
├── main.py                     # Main execution script
├── run_examples.py             # Example usage
├── requirements.txt            # Dependencies
├── .env.template              # Environment template
└── README.md                  # This file
```

## Testing

Run tests with pytest:

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest tests/

# Run specific test
pytest tests/test_basic.py -v
```

## Performance

### Benchmarks

| Dataset | Accuracy | Avg Steps | Avg Time |
|---------|----------|-----------|----------|
| MMQA    | 0.72     | 3.2       | 15.3s    |

### Optimization Tips

1. **Model Selection**: Use faster models for code generation
2. **Sampling**: Reduce sample counts for faster execution
3. **Async Processing**: Use async methods for batch processing
4. **Caching**: Enable result caching for repeated patterns

## Advanced Usage

### Custom Reward Functions

```python
async def custom_reward_function(candidates, state):
    # Your custom logic here
    return selected_candidate

# Use in graph configuration
config["reward_function"] = custom_reward_function
```

### Streaming Execution

```python
graph = MACTGraph(config)
async for state_update in graph.stream_async(initial_state):
    current_node = list(state_update.keys())[0]
    print(f"Processing: {current_node}")
```

### Error Handling

```python
try:
    result = await run_mact_on_question_async(question, tables_data)
    if result['has_error']:
        print(f"Error: {result['error_message']}")
    else:
        print(f"Success: {result['final_answer']}")
except Exception as e:
    print(f"Execution failed: {e}")
```

## Troubleshooting

### Common Issues

1. **API Key Missing**: Ensure `OPENAI_API_KEY` is set in `.env`
2. **Memory Issues**: Reduce `plan_sample` and `code_sample` for large datasets
3. **Timeout Errors**: Increase timeout values in configuration
4. **Import Errors**: Ensure `src` directory is in Python path

### Debug Mode

Enable debug mode for detailed logging:

```bash
python main.py --debug --dataset_path your_dataset.json
```

### Logging

Configure logging in `config/config.yaml`:

```yaml
logging:
  level: "DEBUG"
  console: true
  file: "debug.log"
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt
pip install black mypy pytest

# Format code
black src/ tests/

# Type checking
mypy src/

# Run tests
pytest tests/ -v
```

## License

This project follows the same license as the original MACT implementation.

## Citation

If you use this implementation, please cite the original MACT paper:

```bibtex
@misc{zhou2025efficientmultiagentcollaborationtool,
      title={Efficient Multi-Agent Collaboration with Tool Use for Online Planning in Complex Table Question Answering},
      author={Wei Zhou and Mohsen Mesgar and Annemarie Friedrich and Heike Adel},
      year={2025},
      eprint={2412.20145},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2412.20145},
}
```

## Acknowledgments

- Original MACT framework by Robert Bosch GmbH
- LangGraph framework by LangChain
- MMQA dataset contributors