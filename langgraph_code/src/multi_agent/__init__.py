"""
Multi-Agent Framework for Table QA

This module implements a sophisticated multi-agent architecture for table question answering,
extending the original MACT framework with:
- EDA Agent: Exploratory data analysis and context generation
- Planning Agent: Action planning with enhanced context
- Coding Agent: Code generation and execution
- Validator Agent: Result validation and error handling
- Report Generator: Flexible output formatting

See ../claude_logs/PROJECT_CONTEXT.md for detailed documentation.
"""

from .state import MultiAgentState, create_multi_agent_initial_state
from .graph import MultiAgentGraph, create_multi_agent_graph

__all__ = [
    "MultiAgentState",
    "create_multi_agent_initial_state",
    "MultiAgentGraph",
    "create_multi_agent_graph"
]
