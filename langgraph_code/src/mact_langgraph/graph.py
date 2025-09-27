"""
Main graph definition for MACT LangGraph implementation.

This module defines the state graph structure, routing logic,
and provides the main interface for creating and running MACT graphs.
"""

from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END

from .state import MACTState, ActionType
from .nodes.core_nodes import (
    input_processor_node,
    planner_node,
    action_selector_node,
    observer_node,
    termination_checker_node,
    answer_aggregator_node
)
from .nodes.tool_nodes import (
    retriever_tool_node,
    calculator_tool_node,
    search_tool_node,
    operator_tool_node
)


def route_action(state: MACTState) -> Literal["retriever_tool", "calculator_tool", "search_tool", "operator_tool", "answer_aggregator"]:
    """
    Route to appropriate tool based on selected action type.

    Args:
        state: Current MACT state

    Returns:
        Name of the next node to execute
    """
    action_type = state.get("current_action_type", "")

    if action_type == ActionType.RETRIEVE.value:
        return "retriever_tool"
    elif action_type == ActionType.CALCULATE.value:
        return "calculator_tool"
    elif action_type == ActionType.SEARCH.value:
        return "search_tool"
    elif action_type == ActionType.OPERATE.value:
        return "operator_tool"
    elif action_type == ActionType.FINISH.value:
        return "answer_aggregator"
    else:
        # Default case - go to answer aggregator
        return "answer_aggregator"


def check_termination(state: MACTState) -> Literal["planner", "answer_aggregator"]:
    """
    Check if the reasoning process should continue or terminate.

    Args:
        state: Current MACT state

    Returns:
        Name of the next node to execute
    """
    if state.get("is_finished", False) or state.get("is_halted", False):
        return "answer_aggregator"
    else:
        return "planner"


def create_mact_graph() -> StateGraph:
    """
    Create the MACT state graph.

    Returns:
        Compiled state graph ready for execution
    """
    # Initialize the graph
    workflow = StateGraph(MACTState)

    # Add all nodes
    workflow.add_node("input_processor", input_processor_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("action_selector", action_selector_node)
    workflow.add_node("retriever_tool", retriever_tool_node)
    workflow.add_node("calculator_tool", calculator_tool_node)
    workflow.add_node("search_tool", search_tool_node)
    workflow.add_node("operator_tool", operator_tool_node)
    workflow.add_node("observer", observer_node)
    workflow.add_node("termination_checker", termination_checker_node)
    workflow.add_node("answer_aggregator", answer_aggregator_node)

    # Set entry point
    workflow.set_entry_point("input_processor")

    # Define the main flow
    workflow.add_edge("input_processor", "planner")
    workflow.add_edge("planner", "action_selector")

    # Conditional routing from action selector to tools
    workflow.add_conditional_edges(
        "action_selector",
        route_action,
        {
            "retriever_tool": "retriever_tool",
            "calculator_tool": "calculator_tool",
            "search_tool": "search_tool",
            "operator_tool": "operator_tool",
            "answer_aggregator": "answer_aggregator"
        }
    )

    # All tools go to observer
    workflow.add_edge("retriever_tool", "observer")
    workflow.add_edge("calculator_tool", "observer")
    workflow.add_edge("search_tool", "observer")
    workflow.add_edge("operator_tool", "observer")

    # Observer goes to termination checker
    workflow.add_edge("observer", "termination_checker")

    # Conditional routing from termination checker
    workflow.add_conditional_edges(
        "termination_checker",
        check_termination,
        {
            "planner": "planner",
            "answer_aggregator": "answer_aggregator"
        }
    )

    # Answer aggregator is the final node
    workflow.add_edge("answer_aggregator", END)

    # Compile the graph
    return workflow.compile()


class MACTGraph:
    """
    Main interface for MACT graph execution.

    This class provides high-level methods for running MACT on questions
    and managing the execution process.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize MACT graph.

        Args:
            config: Configuration dictionary for the graph
        """
        self.config = config or {}
        self.graph = create_mact_graph()

    async def run(self, initial_state: MACTState) -> MACTState:
        """
        Run the MACT graph on the given initial state.

        Args:
            initial_state: Initial state for graph execution

        Returns:
            Final state after graph execution
        """
        try:
            result = await self.graph.ainvoke(initial_state)
            return result
        except Exception as e:
            # Handle execution errors
            error_state = {
                **initial_state,
                "has_error": True,
                "error_message": str(e),
                "is_halted": True,
                "final_answer": "Error occurred during execution"
            }
            return error_state

    def run_sync(self, initial_state: MACTState) -> MACTState:
        """
        Run the MACT graph synchronously.

        Args:
            initial_state: Initial state for graph execution

        Returns:
            Final state after graph execution
        """
        try:
            result = self.graph.invoke(initial_state)
            return result
        except Exception as e:
            # Handle execution errors
            error_state = {
                **initial_state,
                "has_error": True,
                "error_message": str(e),
                "is_halted": True,
                "final_answer": "Error occurred during execution"
            }
            return error_state

    def stream(self, initial_state: MACTState):
        """
        Stream the graph execution for monitoring.

        Args:
            initial_state: Initial state for graph execution

        Yields:
            Intermediate states during execution
        """
        try:
            for state in self.graph.stream(initial_state):
                yield state
        except Exception as e:
            error_state = {
                **initial_state,
                "has_error": True,
                "error_message": str(e),
                "is_halted": True
            }
            yield error_state

    async def stream_async(self, initial_state: MACTState):
        """
        Asynchronously stream the graph execution.

        Args:
            initial_state: Initial state for graph execution

        Yields:
            Intermediate states during execution
        """
        try:
            async for state in self.graph.astream(initial_state):
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
MACT Graph Structure:

[START] → input_processor → planner → action_selector → [Tools]
                                           ↑                ↓
                              termination_checker ← observer
                                           ↓
                              answer_aggregator → [END]

Tools:
- retriever_tool (for Retrieve actions)
- calculator_tool (for Calculate actions)
- search_tool (for Search actions)
- operator_tool (for Operate actions)

Flow:
1. Process input data
2. Generate action candidates (planner)
3. Select best action (action_selector)
4. Execute selected tool
5. Observe results (observer)
6. Check termination conditions
7. Either continue (back to planner) or finish (answer_aggregator)
"""

    def validate_state(self, state: MACTState) -> bool:
        """
        Validate that the state has required fields.

        Args:
            state: State to validate

        Returns:
            True if state is valid, False otherwise
        """
        required_fields = [
            "question", "tables", "plan_model", "code_model",
            "current_step", "is_finished", "is_halted"
        ]

        for field in required_fields:
            if field not in state:
                return False

        return True

    def get_execution_summary(self, final_state: MACTState) -> Dict[str, Any]:
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
            "confidence": final_state.get("confidence_score", 0.0),
            "steps_taken": final_state.get("current_step", 0) - 1,
            "is_finished": final_state.get("is_finished", False),
            "is_halted": final_state.get("is_halted", False),
            "has_error": final_state.get("has_error", False),
            "error_message": final_state.get("error_message", ""),
            "execution_log": final_state.get("execution_log", []),
            "step_history": final_state.get("step_history", []),
            "total_input_tokens": final_state.get("total_input_tokens", 0),
            "total_output_tokens": final_state.get("total_output_tokens", 0)
        }


# Convenience function for quick usage
def run_mact_on_question(
    question: str,
    tables_data: list,
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Convenience function to run MACT on a single question.

    Args:
        question: Question to answer
        tables_data: List of table data
        config: Configuration options

    Returns:
        Execution summary dictionary
    """
    from .state import create_initial_state

    # Create initial state
    initial_state = create_initial_state(
        question=question,
        tables_data=tables_data,
        config=config
    )

    # Create and run graph
    graph = MACTGraph(config)
    final_state = graph.run_sync(initial_state)

    # Return summary
    return graph.get_execution_summary(final_state)


# Async version
async def run_mact_on_question_async(
    question: str,
    tables_data: list,
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Async version of run_mact_on_question.

    Args:
        question: Question to answer
        tables_data: List of table data
        config: Configuration options

    Returns:
        Execution summary dictionary
    """
    from .state import create_initial_state

    # Create initial state
    initial_state = create_initial_state(
        question=question,
        tables_data=tables_data,
        config=config
    )

    # Create and run graph
    graph = MACTGraph(config)
    final_state = await graph.run(initial_state)

    # Return summary
    return graph.get_execution_summary(final_state)