"""
Prompt building utilities for MACT LangGraph.
"""

from typing import List, Dict, Any
from ..state import MACTState, get_tables_from_state


# ReAct prompt templates
# QWEN-optimized short prompt
REACT_SYSTEM_PROMPT_QWEN = """You are an expert at answering questions about tables using a step-by-step reasoning approach.

Your task is to use tools to find the answer. You MUST follow these rules:
1.  **Examine Data First**: ALWAYS start by using the `Retrieve` or `Operate` tool to look at the data.
2.  **No Direct Answers**: NEVER use the `Finish` action as your first step. You must use at least one data tool before finishing.
3.  **Reason Step-by-Step**: Provide a `Thought` explaining your plan for the next action.
4.  **Base on Facts**: Your final answer must be based on observations from the tools.

Available actions:
- Retrieve[condition]: Get specific data from tables.
- Calculate[expression]: Perform math calculations.
- Operate[operation]: Perform complex table operations like JOIN.
- Search[query]: Search for external information.
- Finish[answer]: Provide the final answer ONLY after using other tools.

Begin!
"""

# Standard prompt for other models
REACT_SYSTEM_PROMPT = """You are an expert at answering questions about tables using a step-by-step reasoning approach.

IMPORTANT: You MUST use the provided tools to access table data. Do NOT guess or assume answers without examining the actual data.

Available actions:
- Retrieve[condition]: Get specific data from tables based on conditions
- Calculate[expression]: Perform mathematical calculations
- Operate[operation]: Perform complex table operations like JOIN, GROUP BY, etc.
- Search[query]: Search for external information when needed
- Finish[answer]: Provide the final answer ONLY after using tools to examine the data

REQUIRED FORMAT:
Thought: [your reasoning about what to do next]
Action: [one of the actions above with appropriate argument]

RULES:
1. ALWAYS start by examining the table data using Retrieve or Operate
2. NEVER use Finish as your first action
3. You must use at least one data access tool (Retrieve/Operate) before Finish
4. Base your answer on actual data, not assumptions

Continue this step-by-step process until you have verified your answer with actual data."""


MMQA_REACT_EXAMPLES = """
Example 1:
Question: Which department currently headed by a temporary acting manager has the largest number of employees?
Tables: department (Department_ID, Name, Creation, Ranking, Budget_in_Billions, Num_Employees)
         management (department_ID, head_ID, temporary_acting)

Thought: I need to find departments with temporary acting managers and their employee counts. I should examine the tables first.
Action: Retrieve[Show departments and management data]

Observation: Found department table with employee numbers and management table with temporary_acting status.

Thought: Now I need to find which departments have temporary acting managers.
Action: Operate[Join department and management tables where temporary_acting = 'Yes']

Observation: Found departments with temporary acting managers: Treasury (115897 employees), Homeland Security (208000 employees).

Thought: I need to identify which has the largest number of employees among these.
Action: Calculate[Compare 115897 vs 208000]

Observation: 208000 > 115897, but let me verify the data more carefully.

Thought: Wait, I should double-check which department actually has temporary acting management and the correct employee count.
Action: Retrieve[Verify temporary acting departments and their employee counts]

Observation: After careful verification: Treasury has temporary acting management with 115897 employees.

Thought: Based on the verified data, Treasury is the department with temporary acting management.
Action: Finish[Treasury, 115897]

Example 2:
Question: What is the average age of department heads who are serving as temporary acting heads?
Tables: head (head_ID, name, born_state, age)
         management (department_ID, head_ID, temporary_acting)

Thought: I need to find heads who are temporary acting and calculate their average age.
Action: Operate[JOIN head h AND management m ON h.head_ID = m.head_ID WHERE m.temporary_acting = 'Yes']

Observation: Found temporary acting heads: ages 52, 53, 69

Thought: Now I calculate the average of these ages.
Action: Calculate[(52 + 53 + 69) / 3]

Observation: 58.0

Thought: The average age is 58.0 years.
Action: Finish[58.0]
"""


def build_react_prompt(state: MACTState) -> str:
    """
    Build ReAct prompt for the current state.

    Args:
        state: Current MACT state

    Returns:
        Formatted prompt string
    """
    tables = get_tables_from_state(state)

    # Build table information
    table_info = []
    for table in tables:
        columns_str = ", ".join(table.columns)
        table_info.append(f"Table: {table.name}\nColumns: {columns_str}")

    table_description = "\n\n".join(table_info)

    # Add context if available
    context_section = ""
    if state["context"]:
        context_section = f"\nContext: {state['context']}\n"

    # Check if examples should be included (defaults to True for backward compatibility)
    use_examples = state.get("config", {}).get("use_examples", True)

    # Use QWEN-optimized prompt for QWEN models
    if "qwen" in state.get("config", {}).get("plan_model", "").lower():
        # QWEN can now optionally include examples
        if use_examples:
            prompt = f"""{REACT_SYSTEM_PROMPT_QWEN}

{MMQA_REACT_EXAMPLES}

Now solve this question:

Question: {state['question']}
{table_description}
{context_section}
Current: {state['scratchpad']}

Next action:"""
        else:
            # Zero-shot QWEN prompt (original behavior)
            prompt = f"""{REACT_SYSTEM_PROMPT_QWEN}

Question: {state['question']}
{table_description}
{context_section}
Current: {state['scratchpad']}

Next action:"""
    else:
        # Standard prompt for other models (GPT, etc.)
        if use_examples:
            # Few-shot with examples (original behavior)
            prompt = f"""{REACT_SYSTEM_PROMPT}

{MMQA_REACT_EXAMPLES}

Now solve this question:

Question: {state['question']}

{table_description}
{context_section}
Current reasoning:
{state['scratchpad']}

Think step by step and choose your next action:"""
        else:
            # Zero-shot without examples
            prompt = f"""{REACT_SYSTEM_PROMPT}

Now solve this question:

Question: {state['question']}

{table_description}
{context_section}
Current reasoning:
{state['scratchpad']}

Think step by step and choose your next action:"""

    return prompt


def build_multi_table_prompt(state: MACTState) -> str:
    """
    Build prompt specifically for multi-table scenarios.

    Args:
        state: Current MACT state

    Returns:
        Formatted prompt string for multi-table processing
    """
    tables = get_tables_from_state(state)

    prompt_parts = [
        "You are an expert at answering questions about multiple related tables.",
        f"Question: {state['question']}",
    ]

    if state["context"]:
        prompt_parts.append(f"Context: {state['context']}")

    prompt_parts.append("\nAvailable Tables:")

    # Add detailed table information
    for i, table in enumerate(tables):
        prompt_parts.append(f"\nTable {i+1}: {table.name}")
        prompt_parts.append(f"Columns: {', '.join(table.columns)}")

        # Show first few rows as example
        if table.content:
            prompt_parts.append("Sample data:")
            if table.linear_representation:
                # Show first few lines of linear representation
                lines = table.linear_representation.split('\n')[:4]
                prompt_parts.append('\n'.join(lines))
            else:
                # Show first row of content
                if len(table.content) > 0:
                    sample_row = table.content[0]
                    prompt_parts.append(f"  {sample_row}")

    # Add relationship information
    if state["foreign_keys"] or state["primary_keys"]:
        prompt_parts.append("\nTable Relationships:")
        if state["foreign_keys"]:
            prompt_parts.append(f"Foreign Keys: {', '.join(state['foreign_keys'])}")
        if state["primary_keys"]:
            prompt_parts.append(f"Primary Keys: {', '.join(state['primary_keys'])}")

    prompt_parts.extend([
        "\nYou can use the following actions:",
        "- Retrieve[table_name, condition]: Get data from a specific table",
        "- Calculate[expression]: Perform calculations",
        "- Operate[sql_like_operation]: Perform JOIN or complex operations",
        "- Search[query]: Search external knowledge",
        "- Finish[answer]: Provide final answer",
        "",
        f"Current reasoning:\n{state['scratchpad']}",
        "",
        "Think step by step and choose your next action:"
    ])

    return "\n".join(prompt_parts)


def build_tool_prompt(action_type: str, argument: str, table_info: str) -> str:
    """
    Build prompt for tool execution.

    Args:
        action_type: Type of action to perform
        argument: Action argument
        table_info: Information about available tables

    Returns:
        Formatted prompt for tool execution
    """
    if action_type == "Retrieve":
        return f"""Extract data from the table based on this condition: {argument}

Available tables:
{table_info}

Provide the extracted data in a clear format."""

    elif action_type == "Calculate":
        return f"""Perform this calculation: {argument}

Show your work and provide the final result."""

    elif action_type == "Operate":
        return f"""Perform this table operation: {argument}

Available tables:
{table_info}

Provide the result in table format."""

    elif action_type == "Search":
        return f"""Search for information about: {argument}

Provide relevant information that might help answer the question."""

    else:
        return f"Perform action: {action_type}[{argument}]"


def build_evaluation_prompt(candidates: List[Dict[str, Any]], context: str) -> str:
    """
    Build prompt for evaluating action candidates.

    Args:
        candidates: List of action candidates
        context: Current reasoning context

    Returns:
        Evaluation prompt
    """
    prompt_parts = [
        "Given the current reasoning context and several candidate actions, "
        "decide which action is most promising for solving the question.",
        "",
        f"Context: {context}",
        "",
        "Candidate Actions:"
    ]

    for i, candidate in enumerate(candidates):
        prompt_parts.append(f"\nCandidate {i+1}:")
        prompt_parts.append(f"Thought: {candidate.get('thought', '')}")
        prompt_parts.append(f"Action: {candidate.get('action', '')}")

    prompt_parts.extend([
        "",
        "Analyze each candidate and conclude with:",
        '"The best path is X" where X is the number of the best candidate.'
    ])

    return "\n".join(prompt_parts)


def build_direct_reasoning_prompt(question: str, tables: List[Dict], context: str = "") -> str:
    """
    Build prompt for direct reasoning without step-by-step actions.

    Args:
        question: Question to answer
        tables: Table information
        context: Additional context

    Returns:
        Direct reasoning prompt
    """
    table_descriptions = []
    for table in tables:
        cols = ", ".join(table.get("columns", []))
        table_descriptions.append(f"{table.get('name', 'Table')}: {cols}")

    context_section = f"\nContext: {context}" if context else ""

    return f"""Answer the following question based on the provided tables.

Question: {question}

Tables:
{chr(10).join(table_descriptions)}
{context_section}

Provide a clear, direct answer with your reasoning:"""


def build_code_generation_prompt(instruction: str, table_df_code: str, examples: str = "", model_name: str = None) -> str:
    """
    Build prompt for code generation tasks with model-specific optimization.

    Args:
        instruction: Instruction for what code to generate
        table_df_code: DataFrame setup code
        examples: Example code snippets
        model_name: Model name for specific optimization

    Returns:
        Code generation prompt
    """
    # QWEN3-8B specific prompt (ultra concise)
    if model_name and 'qwen' in model_name.lower():
        return f"""Task: {instruction}

{table_df_code}

Write clean pandas code. End with: new_table = result

```python"""

    # Standard prompt for other models
    return f"""Generate Python code to: {instruction}

Table setup:
{table_df_code}

{examples}

Requirements:
- Use pandas operations
- Store the final result in a variable called 'result' or 'final_result'
- Include only the necessary code

Code:
```python"""