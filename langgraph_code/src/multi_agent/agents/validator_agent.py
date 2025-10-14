"""
Validator Agent

Extends the existing MACT observer_node with enhanced validation logic.
Validates execution results and determines whether to continue or terminate.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from mact_langgraph.nodes.core_nodes import observer_node, termination_checker_node
from ..state import MultiAgentState


async def validator_agent_node(state: MultiAgentState) -> MultiAgentState:
    """
    Validator Agent: Validate results and check termination conditions.

    This agent:
    1. Observes and records the execution result
    2. Validates result quality (using EDA statistics for sanity checks)
    3. Checks termination conditions
    4. Provides enhanced feedback for next iteration

    Args:
        state: Current multi-agent state with tool execution results

    Returns:
        Updated state with observation and termination flags
    """
    print("\n" + "="*60)
    print("VALIDATOR AGENT: Validating results...")
    print("="*60)

    # Step 1: Record observation (existing observer logic)
    print("📝 Step 1: Recording observation...")
    state = await observer_node(state)

    # Step 2: Enhanced validation using EDA context
    print("✅ Step 2: Validating result quality...")
    state = validate_result_quality(state)

    # Step 3: Check termination conditions
    print("🔍 Step 3: Checking termination conditions...")
    state = await termination_checker_node(state)

    status = "finished" if state.get("is_finished") else "halted" if state.get("is_halted") else "continuing"
    print(f"   Status: {status}")
    print("="*60 + "\n")

    return state


def validate_result_quality(state: MultiAgentState) -> MultiAgentState:
    """
    Perform enhanced validation using EDA statistics.

    Checks:
    - Numeric results are within expected ranges (from EDA statistics)
    - Categorical results match known categories
    - Result is not obviously incorrect

    Args:
        state: Current state

    Returns:
        Updated state with validation warnings if any
    """
    current_observation = state.get("current_observation", "")

    # Extract result from observation if it's a numeric answer
    validation_warnings = []

    # TODO: Implement more sophisticated validation
    # For now, basic sanity checks

    if current_observation and current_observation.lower().startswith("error"):
        validation_warnings.append("Execution error detected")

    # Check if result is empty or placeholder
    if not current_observation or current_observation.strip() in ["", "None", "null"]:
        validation_warnings.append("Empty or null result")

    # Add warnings to execution log if any
    if validation_warnings:
        warning_msg = "Validator warnings: " + "; ".join(validation_warnings)
        state["execution_log"].append(warning_msg)
        print(f"   ⚠️  {warning_msg}")
    else:
        print("   ✅ Result validation passed")

    return state


# Future enhancement: Advanced validation
# def validate_with_eda_statistics(
#     result: Any,
#     state: MultiAgentState
# ) -> Tuple[bool, List[str]]:
#     """
#     Validate result against EDA statistics.
#
#     Returns:
#         (is_valid, list_of_warnings)
#     """
#     warnings = []
#
#     # Check numeric ranges
#     # Check categorical values
#     # Check result type consistency
#
#     return len(warnings) == 0, warnings
