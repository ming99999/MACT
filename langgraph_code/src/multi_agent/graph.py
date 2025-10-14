"""
Multi-Agent Graph Definition

Orchestrates the multi-agent workflow:
1. EDA Agent: Analyze tables
2. Planning Agent: Generate action candidates
3. Coding Agent: Select and execute action
4. Validator Agent: Validate and check termination
5. Report Generator: Format output

Flow:
Input → EDA → Planning → Coding → Validator → (loop or finish) → Report → Output
"""

from typing import Literal, Dict, Any
from langgraph.graph import StateGraph, END
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from .state import MultiAgentState
from .agents.eda_agent import eda_agent_node
from .agents.planning_agent import planning_agent_node
from .agents.coding_agent import coding_agent_node
from .agents.validator_agent import validator_agent_node
from .agents.report_agent import report_agent_node

from mact_langgraph.state import ActionType


def route_after_coding(state: MultiAgentState) -> Literal["validator", "report"]:
    """
    Route after Coding Agent execution.

    If Finish action was selected, skip to report.
    Otherwise, validate the result.
    """
    if state.get("current_action_type") == ActionType.FINISH.value:
        return "report"
    else:
        return "validator"


def check_termination(state: MultiAgentState) -> Literal["planning", "report"]:
    """
    Check if the reasoning process should continue or terminate.

    Priority: finished > halted > continue
    """
    if state.get("is_finished", False):
        return "report"
    elif state.get("is_halted", False):
        return "report"
    else:
        return "planning"


def create_multi_agent_graph() -> StateGraph:
    """
    Create the Multi-Agent state graph.

    Graph Structure:
    ```
    [START] → EDA → Planning → Coding → Validator → (loop or finish)
                      ↑            ↓                       ↓
                      └────────────┴───────────────────> Report → [END]
    ```

    Returns:
        Compiled state graph ready for execution
    """
    # Initialize the graph
    workflow = StateGraph(MultiAgentState)

    # Add all agent nodes
    workflow.add_node("eda", eda_agent_node)
    workflow.add_node("planning", planning_agent_node)
    workflow.add_node("coding", coding_agent_node)
    workflow.add_node("validator", validator_agent_node)
    workflow.add_node("report", report_agent_node)

    # Set entry point
    workflow.set_entry_point("eda")

    # Define the main flow
    workflow.add_edge("eda", "planning")
    workflow.add_edge("planning", "coding")

    # Conditional routing from coding agent
    workflow.add_conditional_edges(
        "coding",
        route_after_coding,
        {
            "validator": "validator",
            "report": "report"
        }
    )

    # Conditional routing from validator (loop or finish)
    workflow.add_conditional_edges(
        "validator",
        check_termination,
        {
            "planning": "planning",
            "report": "report"
        }
    )

    # Report is the final node
    workflow.add_edge("report", END)

    # Compile the graph
    return workflow.compile()


class MultiAgentGraph:
    """
    Main interface for Multi-Agent graph execution.

    Provides high-level methods for running multi-agent table QA
    and managing the execution process.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Multi-Agent graph.

        Args:
            config: Configuration dictionary for the graph
        """
        self.config = config or {}
        self.graph = create_multi_agent_graph()

    async def run(self, initial_state: MultiAgentState) -> MultiAgentState:
        """
        Run the Multi-Agent graph on the given initial state.

        Args:
            initial_state: Initial state for graph execution

        Returns:
            Final state after graph execution
        """
        try:
            # Set recursion limit for this execution
            result = await self.graph.ainvoke(
                initial_state,
                config={"recursion_limit": 50}
            )
            return result
        except Exception as e:
            # Handle execution errors
            import traceback
            print(f"\n❌ Multi-Agent Graph Error: {str(e)}")
            traceback.print_exc()

            error_state = {
                **initial_state,
                "has_error": True,
                "error_message": str(e),
                "is_halted": True,
                "final_answer": "Error occurred during execution",
                "formatted_output": {
                    "answer": "Error occurred during execution",
                    "error": str(e)
                }
            }
            return error_state

    def run_sync(self, initial_state: MultiAgentState) -> MultiAgentState:
        """
        Run the Multi-Agent graph synchronously.

        Args:
            initial_state: Initial state for graph execution

        Returns:
            Final state after graph execution
        """
        try:
            result = self.graph.invoke(
                initial_state,
                config={"recursion_limit": 50}
            )
            return result
        except Exception as e:
            # Handle execution errors
            import traceback
            print(f"\n❌ Multi-Agent Graph Error: {str(e)}")
            traceback.print_exc()

            error_state = {
                **initial_state,
                "has_error": True,
                "error_message": str(e),
                "is_halted": True,
                "final_answer": "Error occurred during execution",
                "formatted_output": {
                    "answer": "Error occurred during execution",
                    "error": str(e)
                }
            }
            return error_state

    def stream(self, initial_state: MultiAgentState):
        """
        Stream the graph execution for monitoring.

        Args:
            initial_state: Initial state for graph execution

        Yields:
            Intermediate states during execution
        """
        try:
            for state in self.graph.stream(
                initial_state,
                config={"recursion_limit": 50}
            ):
                yield state
        except Exception as e:
            error_state = {
                **initial_state,
                "has_error": True,
                "error_message": str(e),
                "is_halted": True
            }
            yield error_state

    async def stream_async(self, initial_state: MultiAgentState):
        """
        Asynchronously stream the graph execution.

        Args:
            initial_state: Initial state for graph execution

        Yields:
            Intermediate states during execution
        """
        try:
            async for state in self.graph.astream(
                initial_state,
                config={"recursion_limit": 50}
            ):
                yield state
        except Exception as e:
            error_state = {
                **initial_state,
                "has_error": True,
                "error_message": str(e),
                "is_halted": True
            }
            yield error_state

    def get_graph_visualization(self) -> str:
        """
        Get a text representation of the graph structure.

        Returns:
            String representation of the graph
        """
        return """
Multi-Agent Graph Structure:

[START]
   ↓
EDA Agent (Analyze tables and generate context)
   ↓
Planning Agent (Generate action candidates with EDA context)
   ↓
Coding Agent (Select and execute best action)
   ↓
   ├─ If FINISH → Report Generator
   └─ Otherwise → Validator Agent
                     ↓
                     ├─ If finished/halted → Report Generator
                     └─ Otherwise → Planning Agent (loop)
                                       ↓
                              Report Generator (Format output)
                                       ↓
                                     [END]

Agents:
1. EDA Agent: Table analysis, FK detection, context generation
2. Planning Agent: Action planning with enhanced context
3. Coding Agent: Code generation and execution
4. Validator Agent: Result validation and termination check
5. Report Generator: Flexible output formatting

Output Formats:
- mmqa_json: {answer, foreign_keys, primary_keys, sql}
- business_report: Natural language report
- research_detailed: Full execution details
- simple_answer: Just the answer
"""

    def get_execution_summary(self, final_state: MultiAgentState) -> Dict[str, Any]:
        """
        Get a summary of the execution.

        Args:
            final_state: Final state after execution

        Returns:
            Dictionary with execution summary
        """
        return {
            "question": final_state.get("question", ""),
            "final_answer": final_state.get("final_answer", ""),
            "formatted_output": final_state.get("formatted_output", {}),
            "confidence": final_state.get("confidence_score", 0.0),
            "confidence_breakdown": final_state.get("confidence_breakdown", {}),
            "steps_taken": final_state.get("current_step", 0) - 1,
            "is_finished": final_state.get("is_finished", False),
            "is_halted": final_state.get("is_halted", False),
            "has_error": final_state.get("has_error", False),
            "error_message": final_state.get("error_message", ""),
            "eda_summary": {
                "num_tables": len(final_state.get("tables", [])),
                "detected_fks": len(final_state.get("detected_foreign_keys", [])),
                "context_length": len(final_state.get("eda_context", ""))
            },
            "execution_log": final_state.get("execution_log", []),
            "total_input_tokens": final_state.get("total_input_tokens", 0),
            "total_output_tokens": final_state.get("total_output_tokens", 0)
        }


# Convenience function for quick usage
def run_multi_agent_on_question(
    question: str,
    tables_data: list,
    output_format: str = "simple_answer",
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Convenience function to run Multi-Agent framework on a single question.

    Args:
        question: Question to answer
        tables_data: List of table data
        output_format: Desired output format
        config: Configuration options

    Returns:
        Execution summary dictionary with formatted_output
    """
    from .state import create_multi_agent_initial_state

    # Create initial state
    initial_state = create_multi_agent_initial_state(
        question=question,
        tables_data=tables_data,
        output_format=output_format,
        config=config
    )

    # Create and run graph
    graph = MultiAgentGraph(config)
    final_state = graph.run_sync(initial_state)

    # Return summary
    return graph.get_execution_summary(final_state)


# Async version
async def run_multi_agent_on_question_async(
    question: str,
    tables_data: list,
    output_format: str = "simple_answer",
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Async version of run_multi_agent_on_question.

    Args:
        question: Question to answer
        tables_data: List of table data
        output_format: Desired output format
        config: Configuration options

    Returns:
        Execution summary dictionary with formatted_output
    """
    from .state import create_multi_agent_initial_state

    # Create initial state
    initial_state = create_multi_agent_initial_state(
        question=question,
        tables_data=tables_data,
        output_format=output_format,
        config=config
    )

    # Create and run graph
    graph = MultiAgentGraph(config)
    final_state = await graph.run(initial_state)

    # Return summary
    return graph.get_execution_summary(final_state)
