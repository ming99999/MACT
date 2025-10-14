"""
Planning Agent

Wraps the existing MACT planner_node with EDA context injection.
This agent generates multiple action candidates considering table analysis results.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from mact_langgraph.nodes.core_nodes import planner_node
from ..state import MultiAgentState, get_eda_context_summary


async def planning_agent_node(state: MultiAgentState) -> MultiAgentState:
    """
    Planning Agent: Generate action candidates with EDA context.

    This is a thin wrapper around the original planner_node that:
    1. Injects EDA context into the state's context field
    2. Calls the original planner
    3. Returns updated state

    Args:
        state: Current multi-agent state

    Returns:
        Updated state with candidate_actions populated
    """
    print("\n" + "="*60)
    print("PLANNING AGENT: Generating action candidates...")
    print("="*60)

    # Inject EDA context into the reasoning context
    eda_summary = get_eda_context_summary(state)

    if eda_summary:
        # Combine original context with EDA context
        enhanced_context = state.get("context", "")
        if enhanced_context:
            enhanced_context += "\n\n" + eda_summary
        else:
            enhanced_context = eda_summary

        # Create enhanced state for planning
        enhanced_state = {**state, "context": enhanced_context}

        print(f"📊 Enhanced context with EDA analysis ({len(eda_summary)} chars)")
    else:
        enhanced_state = state
        print("⚠️  No EDA context available, using original state")

    # Call original planner with enhanced context
    result_state = await planner_node(enhanced_state)

    print(f"✅ Planning Agent completed: {len(result_state.get('candidate_actions', []))} candidates generated")
    print("="*60 + "\n")

    return result_state
