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
import os
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


async def generate_plan_batch(llm, prompt: str, n: int, model_name: str = None) -> List[str]:
    """
    🎯 Fix #3: Generate multiple action plans in ONE API call (Original MACT style)

    Uses OpenAI's n parameter to generate correlated samples for consistency reward.

    Args:
        llm: LangChain LLM instance
        prompt: Planning prompt
        n: Number of samples to generate
        model_name: Model name

    Returns:
        List of raw LLM response strings
    """
    try:
        if hasattr(llm, 'client'):
            print(f"🔍 DEBUG Planning: Attempting batch API with n={n}")
            from openai import AsyncOpenAI

            api_key = llm.openai_api_key.get_secret_value() if hasattr(llm, 'openai_api_key') and llm.openai_api_key else None
            base_url = llm.openai_api_base if hasattr(llm, 'openai_api_base') else None

            print(f"🔍 DEBUG Planning: API base_url={base_url}")

            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=600.0  # 10 minutes for cold start
            )

            print(f"🔍 DEBUG Planning: Calling batch API with model={model_name or llm.model_name}")
            response = await client.chat.completions.create(
                model=model_name or llm.model_name,
                messages=[{"role": "user", "content": prompt}],
                n=n,
                temperature=0.6,
                max_tokens=1500
            )

            print(f"🔍 DEBUG Planning: Response received, type={type(response)}")
            print(f"🔍 DEBUG Planning: Response={response}")
            print(f"🔍 DEBUG Planning: Response dict={response.model_dump() if hasattr(response, 'model_dump') else 'N/A'}")
            print(f"🔍 DEBUG Planning: Has choices={hasattr(response, 'choices')}")
            if hasattr(response, 'choices'):
                print(f"🔍 DEBUG Planning: Choices={response.choices}")
                print(f"🔍 DEBUG Planning: Choices length={len(response.choices) if response.choices else 'None'}")

            if response and response.choices:
                responses = [choice.message.content for choice in response.choices if choice.message.content]
                if responses:
                    print(f"🎯 Planning Batch API: Generated {len(responses)} plans in 1 call")
                    return responses

            # If batch API didn't work, fall through to fallback
            print(f"⚠️ DEBUG Planning: Batch API returned empty, falling through")
            raise ValueError("Batch API returned no valid responses")

        else:
            print(f"⚠️ Fallback: Using sequential calls ({n} calls)")
            responses = []
            for _ in range(n):
                response = await llm.ainvoke(prompt)
                responses.append(response.content)
            return responses

    except Exception as e:
        print(f"⚠️ Batch planning failed: {e}, using fallback")
        responses = []
        for _ in range(n):
            response = await llm.ainvoke(prompt)
            responses.append(response.content)
        return responses


def create_llm(model_name: str) -> ChatOpenAI:
    """
    Create LLM instance with support for OpenAI and RunPod vLLM.

    Args:
        model_name: Name of the model to use

    Returns:
        Configured ChatOpenAI instance
    """
    # Check if RunPod should be used
    runpod_api_key = os.getenv("RUNPOD_API_KEY")
    runpod_base_url = os.getenv("RUNPOD_BASE_URL")

    if runpod_api_key and runpod_base_url and model_name.startswith("runpod"):
        # Use RunPod vLLM endpoint - support cold start with longer timeout
        actual_model = model_name.replace("runpod:", "") if ":" in model_name else "Qwen/Qwen3-8B"

        print(f"🚀 Connecting to RunPod vLLM with model: {actual_model}")
        print(f"   Base URL: {runpod_base_url}")
        print(f"   Cold start timeout: 300 seconds")

        try:
            llm = ChatOpenAI(
                model=actual_model,
                api_key=runpod_api_key,
                base_url=runpod_base_url,
                temperature=0.1,
                max_tokens=2048,
                timeout=300,  # 5 minutes for cold start
                max_retries=1
            )

            print("🔍 Testing RunPod vLLM connectivity...")
            test_response = llm.invoke("Hello, respond with 'OK'")
            if test_response and test_response.content:
                print(f"✅ RunPod vLLM connected successfully!")
                print(f"   Model: {actual_model}")
                print(f"   Test response: {test_response.content[:50]}...")
                return llm
            else:
                print("❌ RunPod vLLM test failed: Empty response")
                exit(1)

        except Exception as e:
            print(f"❌ RunPod vLLM connection failed: {e}")
            print("🛑 Experiment terminated. Please check RunPod endpoint and try again.")
            exit(1)
    else:
        # Use OpenAI API
        print(f"🌐 Using OpenAI API with model: {model_name}")
        return ChatOpenAI(
            model=model_name,
            temperature=0.1,
            max_tokens=2048,
            timeout=60
        )


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
        table_rows = [table.columns] + table.content

        # Force regenerate linear representation (기존 MACT 방식)
        linear_rep = table_linear(table_rows)

        # Force regenerate DataFrame code (기존 MACT 방식)
        df_code = table2df(table_rows)

        # Create updated table dictionary with forced values
        updated_table = table.to_dict()
        updated_table["linear_representation"] = linear_rep
        updated_table["df_code"] = df_code

        updated_tables.append(updated_table)

    # Log initialization with table info
    init_log = f"Initialized with question: {state['question'][:100]}..."
    table_logs = [f"Table {i}: Generated df_code ({len(updated_tables[i]['df_code'])} chars)"
                  for i in range(len(updated_tables))]
    execution_log = state["execution_log"] + [init_log] + table_logs

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
    llm = create_llm(state["plan_model"])

    # Generate multiple candidate actions using batch API call
    candidates = []
    plan_sample = state["plan_sample"]

    # 🎯 Fix #2: Extract LLM observations for hybrid voting (Original MACT style)
    llm_observations = []
    current_step = state["current_step"]

    # 🎯 Phase 2-B: 기존 MACT처럼 배치 API 호출로 성능 개선
    # LOGP reward를 위해 logprobs도 수집
    reward_type = state.get("reward_type", "consistency")
    logprobs_enabled = reward_type == "logp"

    try:
        # 🎯 Fix #3: Use batch API for correlated samples (Original MACT style)
        raw_responses = await generate_plan_batch(llm, prompt, plan_sample, state["plan_model"])

        import re
        for i, content in enumerate(raw_responses):
            try:
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

                        # 🎯 Fix #2: Extract LLM-predicted observations from raw response
                        obs_pattern = rf"Observation {current_step}:\s*(.+?)(?=\n(?:Thought|Action|$))"
                        obs_matches = re.findall(obs_pattern, content, re.DOTALL | re.IGNORECASE)
                        for obs_text in obs_matches:
                            obs_text = obs_text.strip()
                            if obs_text and len(obs_text) > 0:
                                formatted_obs = f"Observation {current_step}: {obs_text}"
                                llm_observations.append(formatted_obs)

            except Exception as e:
                # Log error but continue with other candidates
                error_log = f"Error parsing candidate {i}: {str(e)}"
                state = {
                    **state,
                    "execution_log": state["execution_log"] + [error_log]
                }

    except Exception as e:
        # Fallback to sequential if batch fails
        error_log = f"Batch planning failed, using fallback: {str(e)}"
        state = {
            **state,
            "execution_log": state["execution_log"] + [error_log]
        }

        # Fallback: use original sequential approach
        for i in range(min(plan_sample, 2)):  # Limit fallback to 2 attempts
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
                error_log = f"Error in fallback candidate {i}: {str(e)}"
                state = {
                    **state,
                    "execution_log": state["execution_log"] + [error_log]
                }

    # Update state with candidates
    updated_state = update_state_with_candidates(state, candidates)

    # 🎯 Fix #2: Store LLM observations for hybrid voting
    updated_state["llm_observations"] = llm_observations

    # Log planning step
    log_entry = f"Generated {len(candidates)} candidate actions for step {state['current_step']}"
    if llm_observations:
        log_entry += f" (extracted {len(llm_observations)} LLM observations)"
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

    # 🎯 Bug Fix #3: STRICTLY prevent first-step Finish actions
    current_step = state.get("current_step", 1)
    original_candidate_count = len(candidates)

    if current_step == 1:
        # STRICTLY filter out all Finish actions on first step
        candidates = [c for c in candidates if c.action_type != ActionType.FINISH]

        filtered_count = original_candidate_count - len(candidates)
        if filtered_count > 0:
            log_msg = f"🚫 BLOCKED {filtered_count} first-step Finish action(s) - Step 1 requires data gathering"
            print(log_msg)
            state = {**state, "execution_log": state["execution_log"] + [log_msg]}

        # If ALL candidates were Finish, force a Retrieve action
        if len(candidates) == 0:
            fallback_msg = "⚠️ All actions were Finish at step 1. Forcing Retrieve action."
            print(fallback_msg)

            from ..state import ActionCandidate
            forced_candidate = ActionCandidate(
                action="Retrieve[examine available table data]",
                action_type=ActionType.RETRIEVE,
                thought="I need to first examine the available data to answer this question.",
                argument="examine available table data",
                score=1.0
            )
            candidates = [forced_candidate]
            state = {**state, "execution_log": state["execution_log"] + [fallback_msg]}

    # 🎯 Bug Fix #3 Extended: Also block Finish at step 2 if no tools used
    elif current_step == 2 and len(state.get("tool_results", [])) == 0:
        original_count = len(candidates)
        candidates = [c for c in candidates if c.action_type != ActionType.FINISH]

        if original_count != len(candidates):
            log_msg = f"🚫 BLOCKED Finish at step 2 - No tools used yet (must use at least 1 tool)"
            print(log_msg)
            state = {**state, "execution_log": state["execution_log"] + [log_msg]}

    # Early termination: if we have successful candidates and high confidence, use the first good one
    config = state.get("config", {})
    if "qwen" in config.get("plan_model", "").lower() and len(candidates) >= 1:
        # For QWEN models, be more aggressive about early termination
        for candidate in candidates:
            if hasattr(candidate, 'confidence') and candidate.confidence > 0.7:
                # Use this candidate immediately
                candidates = [candidate]
                break

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
        # Use log probabilities to select best candidate
        selected_action = _select_by_logp(candidates)

    elif reward_type == RewardType.ROLLOUT:
        # Use rollout evaluation (look-ahead simulation)
        selected_action = await _select_by_rollout(candidates, state)

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

    # Verify action type is properly set
    if "current_action_type" not in updated_state or not updated_state["current_action_type"]:
        error_msg = f"Action type not properly set for action: {selected_action.action}"
        updated_state = {
            **updated_state,
            "has_error": True,
            "error_message": error_msg,
            "execution_log": updated_state["execution_log"] + [f"ERROR: {error_msg}"]
        }
        return updated_state

    # Enhanced logging with action type verification
    action_type = updated_state["current_action_type"]
    log_entry = f"Selected action: {action_type}[{selected_action.argument[:50]}...] (confidence: {getattr(selected_action, 'score', 0.0):.2f})"
    debug_log = f"Debug - Action candidates: {len(candidates)}, Selected: {selected_action.action_type.value}, Raw: {selected_action.action[:50]}..."

    updated_state["execution_log"] = updated_state["execution_log"] + [log_entry, debug_log]

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
    final_answer = state["final_answer"]

    # Priority 1: Check if action was "Finish" (highest priority)
    if state["current_action_type"] == ActionType.FINISH.value:
        is_finished = True
        reason = "Finish action executed"
        # Extract answer from argument
        final_answer = state["current_argument"]

        # Log termination check for Finish action
        log_entry = f"Termination check: finished=True, reason='Finish action executed'"
        execution_log = state["execution_log"] + [log_entry]

        # Finish action: return immediately without incrementing steps
        return {
            **state,
            "is_finished": True,
            "is_halted": False,  # Explicitly set to False
            "final_answer": final_answer,
            "execution_log": execution_log
            # Keep current_step and actual_step unchanged
        }

    # Priority 2: Check for errors
    if state["has_error"]:
        is_halted = True
        reason = f"Error occurred: {state['error_message']}"

    # Priority 3: Check step limits (only if not finished and no error)
    elif state["current_step"] >= state["max_steps"]:
        is_halted = True
        reason = "Maximum steps reached"

    elif state["actual_step"] >= state["max_actual_steps"]:
        is_halted = True
        reason = "Maximum actual steps reached"

    # Increment step counters only if continuing (not finished, not halted)
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

    # First, check if current selected action is a Finish action
    if state.get("current_action") and state["current_action"].startswith("Finish["):
        import re
        finish_pattern = r'Finish\[([^\]]+)\]'
        matches = re.findall(finish_pattern, state["current_action"])
        if matches:
            final_answer = matches[0]  # Take the first match
            confidence_score = 0.8

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
        llm = create_llm(state["plan_model"])
        response = await llm.ainvoke(prompt)

        # Extract choice
        choice_idx = extract_from_outputs(response.content, len(candidates))
        return candidates[choice_idx]

    except Exception:
        # Fallback to consistency
        return _select_by_consistency(candidates)


def _select_by_logp(candidates: List[ActionCandidate]) -> ActionCandidate:
    """Select action based on highest log probability."""
    if not candidates:
        return None

    # Select candidate with highest log probability (stored in score field)
    # Higher logprob (less negative) means more confident generation
    best_candidate = max(candidates, key=lambda c: c.score if c.score else -float('inf'))
    return best_candidate


async def _select_by_rollout(candidates: List[ActionCandidate], state: MACTState) -> ActionCandidate:
    """Select action using rollout evaluation (look-ahead)."""
    if not candidates:
        return None

    # 🎯 ROLLOUT: 기존 MACT의 rollout 전략 - 각 후보를 끝까지 시뮬레이션
    # 복잡한 구현이므로 현재는 간소화된 버전
    # TODO: 향후 완전한 rollout 구현 필요

    # 현재는 LLM 평가와 consistency를 결합한 방식으로 구현
    try:
        # 각 후보의 potential quality를 평가
        scored_candidates = []
        for candidate in candidates:
            # 간단한 휴리스틱: action_type과 argument의 관련성 평가
            score = 0.0

            # 더 구체적인 argument를 가진 action에 높은 점수
            if candidate.argument and len(candidate.argument.strip()) > 5:
                score += 1.0

            # Finish 액션은 마지막에만 선택되도록 낮은 점수
            if candidate.action_type == ActionType.FINISH:
                score -= 0.5

            # Retrieve와 Operate는 중간 단계에서 유용
            if candidate.action_type in [ActionType.RETRIEVE, ActionType.OPERATE]:
                score += 0.5

            scored_candidates.append((candidate, score))

        # 가장 높은 점수의 후보 선택
        best_candidate = max(scored_candidates, key=lambda x: x[1])[0]
        return best_candidate

    except Exception:
        # Fallback to consistency
        return _select_by_consistency(candidates)


def _select_by_random(candidates: List[ActionCandidate]) -> ActionCandidate:
    """Select action randomly (fallback)."""
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