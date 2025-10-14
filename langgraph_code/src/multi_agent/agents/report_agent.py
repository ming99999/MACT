"""
Report Generator Agent

Generates flexible output formats based on user requirements:
- MMQA JSON: {answer, foreign_keys, primary_keys, sql}
- Business Report: Natural language with reasoning
- Research Detailed: Full execution details
- Simple Answer: Just the answer string
"""

import sys
import os
from typing import Dict, Any
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from mact_langgraph.nodes.core_nodes import answer_aggregator_node
from mact_langgraph.nodes.subtask_nodes import subtask_generation_node
from ..state import MultiAgentState


async def report_agent_node(state: MultiAgentState) -> MultiAgentState:
    """
    Report Generator Agent: Format output according to user requirements.

    This agent:
    1. Aggregates final answer (using existing answer_aggregator)
    2. Generates subtask outputs if needed (for MMQA)
    3. Formats output according to output_format specification
    4. Generates reasoning report
    5. Calculates confidence breakdown

    Args:
        state: Current multi-agent state with reasoning complete

    Returns:
        Updated state with formatted_output populated
    """
    print("\n" + "="*60)
    print("REPORT GENERATOR AGENT: Formatting output...")
    print("="*60)

    # Step 1: Aggregate final answer
    print("📊 Step 1: Aggregating final answer...")
    state = await answer_aggregator_node(state)

    # Step 2: Generate subtask outputs if needed (MMQA format)
    output_format = state.get("output_format", "simple_answer")

    if output_format == "mmqa_json":
        print("📝 Step 2: Generating MMQA subtask outputs...")
        state = await subtask_generation_node(state)

    # Step 3: Calculate confidence breakdown
    print("🎯 Step 3: Calculating confidence scores...")
    state = calculate_confidence_breakdown(state)

    # Step 4: Generate reasoning report
    print("📄 Step 4: Generating reasoning report...")
    state = generate_reasoning_report(state)

    # Step 5: Format output according to specification
    print(f"🎨 Step 5: Formatting output as '{output_format}'...")
    state = format_output(state, output_format)

    print("✅ Report Generator Agent completed")
    print("="*60 + "\n")

    return state


def calculate_confidence_breakdown(state: MultiAgentState) -> MultiAgentState:
    """
    Calculate confidence scores for different aspects of the answer.

    Args:
        state: Current state

    Returns:
        Updated state with confidence_breakdown populated
    """
    # 1. Answer consensus score
    answer_frequencies = state.get("answer_frequencies", {})
    if answer_frequencies:
        total_votes = sum(answer_frequencies.values())
        max_votes = max(answer_frequencies.values()) if answer_frequencies else 0
        answer_consensus = max_votes / total_votes if total_votes > 0 else 0.0
    else:
        answer_consensus = 0.0

    # 2. Code execution success rate
    step_history = state.get("step_history", [])
    if step_history:
        successful_steps = sum(
            1 for step in step_history
            if "observation" in step and not step.get("observation", "").lower().startswith("error")
        )
        code_execution = successful_steps / len(step_history) if step_history else 0.0
    else:
        code_execution = 0.0

    # 3. Reasoning coherence (did we finish vs. halt?)
    reasoning_coherence = 1.0 if state.get("is_finished") else 0.5 if state.get("is_halted") else 0.0

    # 4. Overall confidence (weighted average)
    overall = (
        0.5 * answer_consensus +
        0.3 * code_execution +
        0.2 * reasoning_coherence
    )

    confidence_breakdown = {
        "overall": overall,
        "answer_consensus": answer_consensus,
        "code_execution": code_execution,
        "reasoning_coherence": reasoning_coherence
    }

    print(f"   Overall confidence: {overall:.2%}")
    print(f"   - Answer consensus: {answer_consensus:.2%}")
    print(f"   - Code execution: {code_execution:.2%}")
    print(f"   - Reasoning coherence: {reasoning_coherence:.2%}")

    return {
        **state,
        "confidence_breakdown": confidence_breakdown,
        "confidence_score": overall
    }


def generate_reasoning_report(state: MultiAgentState) -> MultiAgentState:
    """
    Generate a natural language summary of the reasoning process.

    Args:
        state: Current state

    Returns:
        Updated state with reasoning_report populated
    """
    report_parts = []

    # Header
    report_parts.append("=== REASONING REPORT ===\n")

    # Question
    report_parts.append(f"Question: {state.get('question', 'N/A')}\n")

    # EDA Summary
    if state.get("eda_context"):
        report_parts.append("--- Table Analysis ---")
        # Extract key info from EDA context
        num_tables = len(state.get("tables", []))
        num_fks = len(state.get("detected_foreign_keys", []))
        report_parts.append(f"Analyzed {num_tables} table(s), detected {num_fks} relationship(s)\n")

    # Reasoning Steps
    step_history = state.get("step_history", [])
    if step_history:
        report_parts.append(f"--- Reasoning Process ({len(step_history)} steps) ---")
        for i, step in enumerate(step_history, 1):
            action = step.get("action", "Unknown")
            observation = step.get("observation", "")
            # Truncate long observations
            obs_preview = observation[:100] + "..." if len(observation) > 100 else observation
            report_parts.append(f"Step {i}: {action}")
            report_parts.append(f"  Result: {obs_preview}")

    # Final Answer
    report_parts.append("\n--- Final Answer ---")
    report_parts.append(f"Answer: {state.get('final_answer', 'No answer')}")

    # Confidence
    confidence = state.get("confidence_breakdown", {})
    if confidence:
        report_parts.append(f"Confidence: {confidence.get('overall', 0):.2%}\n")

    reasoning_report = "\n".join(report_parts)

    return {
        **state,
        "reasoning_report": reasoning_report
    }


def format_output(state: MultiAgentState, output_format: str) -> MultiAgentState:
    """
    Format output according to the specified format.

    Args:
        state: Current state
        output_format: Desired output format

    Returns:
        Updated state with formatted_output populated
    """
    if output_format == "mmqa_json":
        formatted_output = format_mmqa_json(state)

    elif output_format == "business_report":
        formatted_output = format_business_report(state)

    elif output_format == "research_detailed":
        formatted_output = format_research_detailed(state)

    else:  # simple_answer
        formatted_output = format_simple_answer(state)

    return {
        **state,
        "formatted_output": formatted_output
    }


def format_mmqa_json(state: MultiAgentState) -> Dict[str, Any]:
    """
    Format output for MMQA dataset evaluation.

    Returns JSON with: answer, foreign_keys, primary_keys, sql
    """
    # Use predicted subtasks if available, otherwise use detected/provided ones
    foreign_keys = state.get("predicted_foreign_keys") or state.get("detected_foreign_keys") or state.get("foreign_keys", [])
    primary_keys = state.get("predicted_primary_keys") or state.get("primary_keys", [])
    sql = state.get("predicted_sql", "")

    output = {
        "answer": state.get("final_answer", ""),
        "foreign_keys": foreign_keys,
        "primary_keys": primary_keys,
        "sql": sql,
        "confidence": state.get("confidence_score", 0.0),
        "execution_log": state.get("execution_log", [])
    }

    print(f"   MMQA JSON output: {len(foreign_keys)} FKs, {len(primary_keys)} PKs, SQL: {len(sql)} chars")

    return output


def format_business_report(state: MultiAgentState) -> Dict[str, Any]:
    """
    Format output as a business-style report.

    Returns natural language report with key findings.
    """
    # Build natural language report
    report_sections = []

    # Executive Summary
    report_sections.append("## Executive Summary")
    report_sections.append(f"**Question:** {state.get('question', 'N/A')}")
    report_sections.append(f"**Answer:** {state.get('final_answer', 'No answer available')}")
    report_sections.append(f"**Confidence Level:** {state.get('confidence_score', 0):.1%}\n")

    # Data Analysis
    if state.get("eda_context"):
        report_sections.append("## Data Analysis")
        num_tables = len(state.get("tables", []))
        num_fks = len(state.get("detected_foreign_keys", []))
        report_sections.append(f"- Analyzed {num_tables} data table(s)")
        report_sections.append(f"- Identified {num_fks} relationship(s) between tables")

        # Key table info
        table_stats = state.get("table_statistics", {})
        for table_name, stats in table_stats.items():
            report_sections.append(f"- {table_name}: {stats.get('num_rows', 0)} records")

        report_sections.append("")

    # Methodology
    step_history = state.get("step_history", [])
    if step_history:
        report_sections.append("## Methodology")
        report_sections.append(f"Analysis completed in {len(step_history)} steps:")
        for i, step in enumerate(step_history, 1):
            action = step.get("action", "Unknown")
            report_sections.append(f"{i}. {action}")
        report_sections.append("")

    # Confidence Breakdown
    confidence = state.get("confidence_breakdown", {})
    if confidence:
        report_sections.append("## Confidence Assessment")
        report_sections.append(f"- Overall Confidence: {confidence.get('overall', 0):.1%}")
        report_sections.append(f"- Data Quality: {confidence.get('code_execution', 0):.1%}")
        report_sections.append(f"- Answer Consistency: {confidence.get('answer_consensus', 0):.1%}")

    report_text = "\n".join(report_sections)

    output = {
        "report": report_text,
        "answer": state.get("final_answer", ""),
        "confidence": state.get("confidence_score", 0.0)
    }

    return output


def format_research_detailed(state: MultiAgentState) -> Dict[str, Any]:
    """
    Format output with full execution details for research purposes.
    """
    output = {
        # Basic info
        "question": state.get("question", ""),
        "answer": state.get("final_answer", ""),
        "confidence": state.get("confidence_score", 0.0),

        # Execution details
        "num_steps": state.get("current_step", 0) - 1,
        "is_finished": state.get("is_finished", False),
        "is_halted": state.get("is_halted", False),
        "has_error": state.get("has_error", False),

        # EDA Analysis
        "eda_context": state.get("eda_context", ""),
        "detected_foreign_keys": state.get("detected_foreign_keys", []),
        "table_statistics": state.get("table_statistics", {}),

        # Reasoning process
        "step_history": state.get("step_history", []),
        "execution_log": state.get("execution_log", []),

        # Answer tracking
        "preliminary_answers": state.get("preliminary_answers", []),
        "answer_frequencies": state.get("answer_frequencies", {}),

        # Confidence breakdown
        "confidence_breakdown": state.get("confidence_breakdown", {}),

        # Token usage
        "total_input_tokens": state.get("total_input_tokens", 0),
        "total_output_tokens": state.get("total_output_tokens", 0),

        # MMQA subtasks (if available)
        "predicted_foreign_keys": state.get("predicted_foreign_keys", []),
        "predicted_primary_keys": state.get("predicted_primary_keys", []),
        "predicted_sql": state.get("predicted_sql", ""),

        # Full reasoning report
        "reasoning_report": state.get("reasoning_report", "")
    }

    return output


def format_simple_answer(state: MultiAgentState) -> Dict[str, Any]:
    """
    Format output as simple answer string.
    """
    output = {
        "answer": state.get("final_answer", "")
    }

    return output


# Future enhancement: LLM-based report generation
# async def generate_report_with_llm(
#     state: MultiAgentState,
#     report_style: str
# ) -> str:
#     """
#     Use LLM to generate more sophisticated reports.
#     Could generate executive summaries, detailed analysis, etc.
#     """
#     pass
