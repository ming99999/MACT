"""
Coding Agent

Wraps the existing MACT tool nodes (retriever, calculator, operator, search).
Routes to appropriate tool based on selected action type.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from mact_langgraph.state import ActionType
from mact_langgraph.nodes.tool_nodes import (
    retriever_tool_node,
    calculator_tool_node,
    operator_tool_node,
    search_tool_node
)
from mact_langgraph.nodes.core_nodes import action_selector_node
from ..state import MultiAgentState


async def coding_agent_node(state: MultiAgentState) -> MultiAgentState:
    """
    Coding Agent: Generate and execute code based on selected action.

    This agent:
    1. Selects the best action from candidates (using existing selector)
    2. Routes to appropriate tool node for execution
    3. Returns state with execution results

    Args:
        state: Current multi-agent state with candidate_actions

    Returns:
        Updated state with tool execution results
    """
    print("\n" + "="*60)
    print("CODING AGENT: Selecting and executing action...")
    print("="*60)

    # Step 1: Select best action
    print("🎯 Step 1: Selecting best action from candidates...")
    state = await action_selector_node(state)

    selected_action_type = state.get("current_action_type", "")
    print(f"   Selected action: {selected_action_type}")

    # Step 2: Route to appropriate tool
    print(f"⚙️  Step 2: Executing {selected_action_type} tool...")

    if selected_action_type == ActionType.RETRIEVE.value:
        state = await retriever_tool_node(state)
    elif selected_action_type == ActionType.CALCULATE.value:
        state = await calculator_tool_node(state)
    elif selected_action_type == ActionType.OPERATE.value:
        state = await operator_tool_node(state)
    elif selected_action_type == ActionType.SEARCH.value:
        state = await search_tool_node(state)
    elif selected_action_type == ActionType.FINISH.value:
        print("   🏁 Finish action selected - skipping tool execution")
    else:
        print(f"   ⚠️  Unknown action type: {selected_action_type}")

    print("✅ Coding Agent completed")
    print("="*60 + "\n")

    return state


# Note: We keep the original tool nodes as-is since they already implement
# majority voting and robust error handling. The Coding Agent simply orchestrates them.
