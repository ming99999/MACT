"""
Core nodes for MACT LangGraph implementation.

These nodes handle the main reasoning workflow:
- Input processing
- Planning
- Action selection
- Observation
- Termination checking
- Answer aggregation
"""

import asyncio
from typing import List, Dict, Any
from collections import Counter
from langchain_openai import ChatOpenAI

from ..state import (
    MACTState, ActionType, ActionCandidate, RewardType,
    get_tables_from_state, get_candidates_from_state,
    update_state_with_candidates, update_state_with_selected_action
)
from ..utils.prompt_utils import build_react_prompt, build_evaluation_prompt
from ..utils.action_utils import parse_thought_action, parse_action, extract_from_outputs
from ..utils.table_utils import normalize_answer, exact_match


async def input_processor_node(state: MACTState) -> MACTState:
    """
    Process input data and initialize state for graph execution.

    Args:
        state: Current MACT state

    Returns:
        Updated state with processed input data
    """
    # Convert tables to TableInfo objects if needed
    tables = get_tables_from_state(state)

    # Generate linear representations and DataFrame code for each table
    from ..utils.table_utils import table_linear, table2df

    updated_tables = []
    for table in tables:
        if not table.linear_representation:
            table_rows = [table.columns] + table.content
            table.linear_representation = table_linear(table_rows)

        if not table.df_code:
            table_rows = [table.columns] + table.content
            table.df_code = table2df(table_rows)

        updated_tables.append(table.to_dict())

    # Log initialization
    log_entry = f"Initialized with question: {state['question'][:100]}..."
    execution_log = state["execution_log"] + [log_entry]

    return {
        **state,
        "tables": updated_tables,
        "execution_log": execution_log,
        "current_step": 1,
        "actual_step": 1,
        "is_finished": False,
        "is_halted": False,
        "scratchpad": "",
        "step_history": []
    }


async def planner_node(state: MACTState) -> MACTState:
    """
    Generate candidate actions using the planning model.

    Args:
        state: Current MACT state

    Returns:
        Updated state with candidate actions
    """
    # Build prompt for current state
    prompt = build_react_prompt(state)

    # Initialize LLM
    llm = ChatOpenAI(
        model=state["plan_model"],
        temperature=0.6,
        max_tokens=1000
    )

    # Generate multiple candidate actions
    candidates = []
    plan_sample = state["plan_sample"]

    for i in range(plan_sample):
        try:
            response = await llm.ainvoke(prompt)
            content = response.content

            # Parse thought and action
            thought, action = parse_thought_action(content)

            if action:
                # Parse action type and argument
                action_type, argument = parse_action(action)

                if action_type and argument:
                    candidate = ActionCandidate(
                        thought=thought,
                        action=action,
                        action_type=ActionType(action_type),
                        argument=argument,
                        score=0.0,
                        raw_response=content
                    )
                    candidates.append(candidate)

        except Exception as e:
            # Log error but continue with other candidates
            error_log = f"Error generating candidate {i}: {str(e)}"
            state = {
                **state,
                "execution_log": state["execution_log"] + [error_log]
            }

    # Update state with candidates
    updated_state = update_state_with_candidates(state, candidates)

    # Log planning step
    log_entry = f"Generated {len(candidates)} candidate actions for step {state['current_step']}"
    updated_state["execution_log"] = updated_state["execution_log"] + [log_entry]

    return updated_state


async def action_selector_node(state: MACTState) -> MACTState:
    """
    Select the best action from candidates using the specified reward function.

    Args:
        state: Current MACT state

    Returns:
        Updated state with selected action
    """
    candidates = get_candidates_from_state(state)

    if not candidates:
        # No candidates available, mark as error
        return {
            **state,
            "has_error": True,
            "error_message": "No valid action candidates generated",
            "is_halted": True
        }

    reward_type = RewardType(state["reward_type"])
    selected_action = None

    if reward_type == RewardType.CONSISTENCY:
        # Select most frequent action
        selected_action = _select_by_consistency(candidates)

    elif reward_type == RewardType.LLM:
        # Use LLM to evaluate candidates
        selected_action = await _select_by_llm_evaluation(candidates, state)

    elif reward_type == RewardType.LOGP:
        # Use log probabilities (simplified implementation)
        selected_action = _select_by_random(candidates)  # Placeholder

    elif reward_type == RewardType.ROLLOUT:
        # Use rollout evaluation (simplified implementation)
        selected_action = _select_by_consistency(candidates)  # Placeholder

    elif reward_type == RewardType.COMBINED:
        # Combine multiple methods
        selected_action = await _select_by_combined(candidates, state)

    else:
        # Default to consistency
        selected_action = _select_by_consistency(candidates)

    if selected_action is None:
        selected_action = candidates[0]  # Fallback to first candidate

    # Update state with selected action
    updated_state = update_state_with_selected_action(state, selected_action)

    # Log selection
    log_entry = f"Selected action: {selected_action.action_type.value}[{selected_action.argument[:50]}...]"
    updated_state["execution_log"] = updated_state["execution_log"] + [log_entry]

    return updated_state


async def observer_node(state: MACTState) -> MACTState:
    """
    Process tool execution results and update the scratchpad.

    Args:
        state: Current MACT state

    Returns:
        Updated state with observation
    """
    # Get the latest tool result
    tool_results = state["tool_results"]
    observation = ""

    if tool_results:
        observation = tool_results[-1]
    else:
        observation = "No observation available"

    # Format observation
    formatted_observation = f"Observation {state['current_step']}: {observation}"

    # Update scratchpad
    scratchpad_update = (
        f"Thought {state['current_step']}: {state['current_thought']}\n"
        f"Action {state['current_step']}: {state['current_action']}\n"
        f"{formatted_observation}\n"
    )

    updated_scratchpad = state["scratchpad"] + scratchpad_update

    # Record step in history
    step_record = {
        "step": state["current_step"],
        "thought": state["current_thought"],
        "action": state["current_action"],
        "observation": formatted_observation
    }

    step_history = state["step_history"] + [step_record]

    # Log observation
    log_entry = f"Step {state['current_step']} completed: {observation[:100]}..."
    execution_log = state["execution_log"] + [log_entry]

    return {
        **state,
        "scratchpad": updated_scratchpad,
        "current_observation": formatted_observation,
        "step_history": step_history,
        "execution_log": execution_log
    }


async def termination_checker_node(state: MACTState) -> MACTState:
    """
    Check if the reasoning process should terminate.

    Args:
        state: Current MACT state

    Returns:
        Updated state with termination status
    """
    is_finished = False
    is_halted = False
    reason = ""

    # Check if action was "Finish"
    if state["current_action_type"] == ActionType.FINISH.value:
        is_finished = True
        reason = "Finish action executed"
        # Extract answer from argument
        final_answer = state["current_argument"]
    else:
        final_answer = state["final_answer"]

    # Check step limits
    if state["current_step"] >= state["max_steps"]:
        is_halted = True
        reason = "Maximum steps reached"

    if state["actual_step"] >= state["max_actual_steps"]:
        is_halted = True
        reason = "Maximum actual steps reached"

    # Check for errors
    if state["has_error"]:
        is_halted = True
        reason = f"Error occurred: {state['error_message']}"

    # Increment step counters if continuing
    next_step = state["current_step"]
    next_actual_step = state["actual_step"]

    if not is_finished and not is_halted:
        next_step += 1
        next_actual_step += 1

    # Log termination check
    log_entry = f"Termination check: finished={is_finished}, halted={is_halted}, reason='{reason}'"
    execution_log = state["execution_log"] + [log_entry]

    return {
        **state,
        "is_finished": is_finished,
        "is_halted": is_halted,
        "final_answer": final_answer,
        "current_step": next_step,
        "actual_step": next_actual_step,
        "execution_log": execution_log
    }


async def answer_aggregator_node(state: MACTState) -> MACTState:
    """
    Aggregate answers and produce final result.

    Args:
        state: Current MACT state

    Returns:
        Updated state with final answer and confidence
    """
    final_answer = state["final_answer"]
    confidence_score = 0.0

    # If no answer yet, try to aggregate from preliminary answers
    if not final_answer and state["preliminary_answers"]:
        # Use most frequent answer
        answer_counts = Counter(state["preliminary_answers"])
        if answer_counts:
            most_common = answer_counts.most_common(1)[0]
            final_answer = most_common[0]
            confidence_score = most_common[1] / len(state["preliminary_answers"])

    # If still no answer, try to extract from scratchpad
    if not final_answer and state["scratchpad"]:
        # Look for "Finish[" pattern in scratchpad
        import re
        finish_pattern = r'Finish\[([^\]]+)\]'
        matches = re.findall(finish_pattern, state["scratchpad"])
        if matches:
            final_answer = matches[-1]  # Take the last match
            confidence_score = 0.7

    # If still no answer, provide default
    if not final_answer:
        final_answer = "Unable to determine answer"
        confidence_score = 0.0

    # Calculate answer frequencies
    answer_frequencies = dict(Counter(state["preliminary_answers"]))

    # Log final result
    log_entry = f"Final answer: '{final_answer}' (confidence: {confidence_score:.2f})"
    execution_log = state["execution_log"] + [log_entry]

    return {
        **state,
        "final_answer": final_answer,
        "confidence_score": confidence_score,
        "answer_frequencies": answer_frequencies,
        "execution_log": execution_log,
        "is_finished": True
    }


# Helper functions for action selection

def _select_by_consistency(candidates: List[ActionCandidate]) -> ActionCandidate:
    """Select action by consistency (most frequent action type)."""
    if not candidates:
        return None

    # Count action types
    action_counts = Counter(candidate.action_type for candidate in candidates)
    most_common_type = action_counts.most_common(1)[0][0]

    # Find first candidate with most common action type
    for candidate in candidates:
        if candidate.action_type == most_common_type:
            return candidate

    return candidates[0]


async def _select_by_llm_evaluation(candidates: List[ActionCandidate], state: MACTState) -> ActionCandidate:
    """Select action using LLM evaluation."""
    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    try:
        # Build evaluation prompt
        context = f"Question: {state['question']}\nReasoning: {state['scratchpad']}"
        prompt = build_evaluation_prompt([c.to_dict() for c in candidates], context)

        # Use planning model for evaluation
        llm = ChatOpenAI(model=state["plan_model"], temperature=0.0)
        response = await llm.ainvoke(prompt)

        # Extract choice
        choice_idx = extract_from_outputs(response.content, len(candidates))
        return candidates[choice_idx]

    except Exception:
        # Fallback to consistency
        return _select_by_consistency(candidates)


def _select_by_random(candidates: List[ActionCandidate]) -> ActionCandidate:
    """Select action randomly (placeholder for logp)."""
    import random
    return random.choice(candidates) if candidates else None


async def _select_by_combined(candidates: List[ActionCandidate], state: MACTState) -> ActionCandidate:
    """Select action using combined methods."""
    if not candidates:
        return None

    # Combine consistency and LLM evaluation
    consistency_choice = _select_by_consistency(candidates)
    llm_choice = await _select_by_llm_evaluation(candidates, state)

    # If both agree, use that choice
    if consistency_choice == llm_choice:
        return consistency_choice

    # Otherwise, prefer LLM choice
    return llm_choice if llm_choice else consistency_choice