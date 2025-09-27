"""
Tool nodes for MACT LangGraph implementation.

These nodes handle specific tool operations:
- Table retrieval and filtering
- Mathematical calculations
- External search
- Complex table operations
"""

import re
import asyncio
from typing import List, Dict, Any, Union
from collections import defaultdict
from langchain_openai import ChatOpenAI
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

from ..state import MACTState, get_tables_from_state
from ..utils.table_utils import (
    table_linear, table2df, execute_table_code, extract_code_from_response
)
from ..utils.prompt_utils import build_code_generation_prompt


async def retriever_tool_node(state: MACTState) -> MACTState:
    """
    Retrieve data from tables based on specified conditions.

    Args:
        state: Current MACT state

    Returns:
        Updated state with retrieval results
    """
    instruction = state["current_argument"]
    tables = get_tables_from_state(state)

    results = []
    code_sample = state["code_sample"]

    try:
        # Use code model to generate table retrieval code
        llm = ChatOpenAI(model=state["code_model"], temperature=0.6)

        # Get the first table's DataFrame code for context
        table_df_code = tables[0].df_code if tables else ""

        for attempt in range(code_sample):
            try:
                # Build prompt for code generation
                prompt = build_code_generation_prompt(
                    f"Filter and retrieve data from table: {instruction}",
                    table_df_code,
                    examples="""
# Example: Get rows where column > value
filtered_df = df[df['column_name'] > value]
new_table = filtered_df

# Example: Select specific columns
result = df[['col1', 'col2']]
new_table = result
"""
                )

                response = await llm.ainvoke(prompt)
                code = response.content

                # Execute the generated code
                result, rows, error, _ = execute_table_code(code, table_df_code)

                if result and rows:
                    results.append(result)

            except Exception as e:
                # Log error but continue with other attempts
                error_msg = f"Retrieval attempt {attempt + 1} failed: {str(e)}"
                state = {
                    **state,
                    "execution_log": state["execution_log"] + [error_msg]
                }

        # Select best result (most frequent)
        if results:
            from collections import Counter
            result_counts = Counter(results)
            best_result = result_counts.most_common(1)[0][0]
        else:
            best_result = f"Unable to retrieve data for: {instruction}"

    except Exception as e:
        best_result = f"Error in retrieval: {str(e)}"

    # Update state with result
    tool_results = state["tool_results"] + [best_result]
    log_entry = f"Retrieval completed: {best_result[:100]}..."

    return {
        **state,
        "tool_results": tool_results,
        "execution_log": state["execution_log"] + [log_entry]
    }


async def calculator_tool_node(state: MACTState) -> MACTState:
    """
    Perform mathematical calculations.

    Args:
        state: Current MACT state

    Returns:
        Updated state with calculation results
    """
    expression = state["current_argument"]

    try:
        # Clean the expression
        expression = expression.replace(",", "").replace("$", "")

        # Try direct evaluation first
        try:
            # Simple expression evaluation
            result = eval(expression, {"__builtins__": {}})
            result_str = str(result)
        except:
            # If direct evaluation fails, try with mathematical operations
            import math
            safe_dict = {
                "abs": abs, "round": round, "min": min, "max": max,
                "sum": sum, "len": len, "int": int, "float": float,
                "math": math, "sqrt": math.sqrt, "pow": pow
            }

            try:
                result = eval(expression, {"__builtins__": {}}, safe_dict)
                result_str = str(result)
            except:
                # If still fails, try with code generation
                result_str = await _calculate_with_code_generation(expression, state)

    except Exception as e:
        result_str = f"Calculation error: {str(e)}"

    # Update state with result
    tool_results = state["tool_results"] + [result_str]
    calculation_results = state["calculation_results"] + [result_str]
    log_entry = f"Calculation completed: {expression} = {result_str}"

    return {
        **state,
        "tool_results": tool_results,
        "calculation_results": calculation_results,
        "execution_log": state["execution_log"] + [log_entry]
    }


async def search_tool_node(state: MACTState) -> MACTState:
    """
    Search for external information using Wikipedia.

    Args:
        state: Current MACT state

    Returns:
        Updated state with search results
    """
    query = state["current_argument"]

    try:
        # Use Wikipedia search
        wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
        search_result = wikipedia.run(query)

        # Truncate result if too long
        if len(search_result) > 500:
            search_result = search_result[:500] + "..."

    except Exception as e:
        search_result = f"Search failed: {str(e)}"

    # Update state with result
    tool_results = state["tool_results"] + [search_result]
    search_results = state["search_results"] + [search_result]
    log_entry = f"Search completed for: {query}"

    return {
        **state,
        "tool_results": tool_results,
        "search_results": search_results,
        "execution_log": state["execution_log"] + [log_entry]
    }


async def operator_tool_node(state: MACTState) -> MACTState:
    """
    Perform complex table operations like JOIN, GROUP BY, etc.

    Args:
        state: Current MACT state

    Returns:
        Updated state with operation results
    """
    operation = state["current_argument"]
    tables = get_tables_from_state(state)

    results = []
    code_sample = state["code_sample"]

    try:
        # Use code model to generate operation code
        llm = ChatOpenAI(model=state["code_model"], temperature=0.6)

        # Prepare DataFrame setup code for multiple tables
        df_setup_code = _build_multi_table_df_code(tables)

        for attempt in range(code_sample):
            try:
                # Build prompt for complex operation
                prompt = build_code_generation_prompt(
                    f"Perform table operation: {operation}",
                    df_setup_code,
                    examples="""
# Example: JOIN tables
result = df1.merge(df2, on='common_column', how='inner')
final_result = result

# Example: GROUP BY operation
grouped = df.groupby('column').sum()
final_result = grouped

# Example: Filter and aggregate
filtered = df[df['condition'] == value]
final_result = filtered.groupby('group_col').agg({'num_col': 'sum'})
"""
                )

                response = await llm.ainvoke(prompt)
                code = response.content

                # Execute the generated code
                result, rows, error, _ = execute_table_code(code, df_setup_code)

                if result and rows:
                    results.append(result)

            except Exception as e:
                # Log error but continue with other attempts
                error_msg = f"Operation attempt {attempt + 1} failed: {str(e)}"
                state = {
                    **state,
                    "execution_log": state["execution_log"] + [error_msg]
                }

        # Select best result
        if results:
            from collections import Counter
            result_counts = Counter(results)
            best_result = result_counts.most_common(1)[0][0]
        else:
            best_result = f"Unable to perform operation: {operation}"

    except Exception as e:
        best_result = f"Error in operation: {str(e)}"

    # Update state with result
    tool_results = state["tool_results"] + [best_result]
    table_operations = state["table_operations"] + [best_result]
    log_entry = f"Operation completed: {operation[:50]}..."

    return {
        **state,
        "tool_results": tool_results,
        "table_operations": table_operations,
        "execution_log": state["execution_log"] + [log_entry]
    }


# Helper functions

async def _calculate_with_code_generation(expression: str, state: MACTState) -> str:
    """Generate code to perform calculation."""
    try:
        llm = ChatOpenAI(model=state["code_model"], temperature=0.0)

        prompt = f"""Calculate the following expression and return only the result:
{expression}

Provide Python code to calculate this:
```python
result = {expression}
print(result)
```"""

        response = await llm.ainvoke(prompt)
        code = extract_code_from_response(response.content)

        if code:
            # Execute the code safely
            local_vars = {}
            exec(code, {"__builtins__": {}}, local_vars)

            if "result" in local_vars:
                return str(local_vars["result"])

        return f"Unable to calculate: {expression}"

    except Exception as e:
        return f"Calculation error: {str(e)}"


def _build_multi_table_df_code(tables: List) -> str:
    """Build DataFrame setup code for multiple tables."""
    setup_lines = ["import pandas as pd", "import numpy as np"]

    for i, table in enumerate(tables):
        # Create individual DataFrame code
        table_rows = [table.columns] + table.content
        df_code = table2df(table_rows)

        # Modify variable name for multi-table setup
        modified_code = df_code.replace("df=pd.DataFrame(data)", f"df{i+1}=pd.DataFrame(data)")
        setup_lines.append(modified_code)

    # Add convenience variables
    if len(tables) >= 1:
        setup_lines.append("df = df1  # Primary table")
    if len(tables) >= 2:
        setup_lines.append("# Additional tables: df2, df3, etc.")

    return "\n".join(setup_lines)


def _clean_equation(equation: str) -> str:
    """Clean equation for calculation."""
    equation = equation.replace(",", "")
    equation = equation.replace("$", "")
    equation = equation.replace("%", "/100")
    return equation.strip()


def _extract_numerical_result(text: str) -> Union[float, str]:
    """Extract numerical result from text."""
    # Look for numbers in the text
    import re

    # Try to find numbers
    number_patterns = [
        r'\d+\.?\d*',  # Basic decimal numbers
        r'\$[\d,]+\.?\d*',  # Currency
        r'[\d,]+\.?\d*%',  # Percentages
    ]

    for pattern in number_patterns:
        matches = re.findall(pattern, text)
        if matches:
            # Take the last match (often the result)
            last_match = matches[-1]
            # Clean and convert
            cleaned = last_match.replace('$', '').replace(',', '').replace('%', '')
            try:
                return float(cleaned)
            except:
                continue

    return text  # Return original if no number found