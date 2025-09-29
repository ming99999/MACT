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
from collections import Counter
from langchain_openai import ChatOpenAI
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

from ..state import MACTState, TableInfo, get_tables_from_state
from .core_nodes import create_llm
from ..utils.table_utils import (
    table_linear, table2df, execute_table_code, extract_code_from_response
)
from ..utils.prompt_utils import build_code_generation_prompt


async def retriever_tool_node(state: MACTState) -> MACTState:
    """
    Retrieve data from tables based on specified conditions.
    Phase 3-B: Fixed logic to properly interpret 'Show X' vs 'Filter X' instructions.
    Now persists the resulting table back into the state.
    """
    instruction = state["current_argument"]
    tables = get_tables_from_state(state)
    results = []
    code_sample = state["code_sample"]
    new_table_info = None

    if not tables:
        return {
            **state,
            "tool_results": state["tool_results"] + ["No tables available"],
            "execution_log": state["execution_log"] + ["ERROR: No tables in state"]
        }

    # Use the latest table in the list for operations
    table_df_code = tables[-1].df_code if tables else ""
    debug_log = f"Retriever debug: Using table {len(tables)-1}, df_code length: {len(table_df_code)}"
    print(f"DEBUG: {debug_log}")

    if not table_df_code:
        error_msg = "No DataFrame code available for table retrieval"
        return {
            **state,
            "tool_results": state["tool_results"] + [f"ERROR: {error_msg}"],
            "execution_log": state["execution_log"] + [f"ERROR: {error_msg}"]
        }

    try:
        llm = create_llm(state["code_model"])
        # 🎯 Phase 3-B Fix: Improved Retrieve prompt with better instructions
        prompt = build_code_generation_prompt(
            f"Retrieve and show data from table: {instruction}",
            table_df_code,
            model_name=state.get("code_model"),
            examples=f"""
# IMPORTANT: Always assign final result to 'new_table' variable
# For "Show X data" or "Display X" - show the full relevant data
# For "Get X where Y" - filter the data based on condition Y

# Examples:
# "Show department data" -> new_table = df.copy()
# "Show management data" -> new_table = df.copy()
# "Get departments where budget > 10" -> new_table = df[df['Budget_in_Billions'] > 10]
# "Filter by temporary acting" -> new_table = df[df['temporary_acting'] == 'Yes']

# Current instruction: {instruction}
new_table = df  # Replace with appropriate logic
"""
        )

        responses = await llm.abatch([prompt] * code_sample)
        codes = [response.content for response in responses if response.content]

        # 🎯 Phase 2-A: 기존 MACT처럼 모든 코드를 실행하고 다수결로 선택
        successful_results = []
        successful_table_infos = []

        for i, code in enumerate(codes):
            try:
                result, rows, error, _ = execute_table_code(
                    code,
                    table_df_code,
                    model_name=state.get("code_model")
                )
                if result and rows and not error:
                    # 성공한 결과만 수집
                    successful_results.append(result)
                    successful_table_infos.append({
                        'result': result,
                        'rows': rows,
                        'table_info': TableInfo(
                            name=f"retrieved_step_{state['current_step']}_attempt_{i}",
                            columns=rows[0],
                            content=rows[1:],
                            df_code=table2df(rows),
                            linear_representation=table_linear(rows, num_row=None)
                        )
                    })
                    results.append(result)  # 전체 결과에도 추가
                else:
                    # 실패한 경우도 로깅
                    error_msg = f"Attempt {i+1} failed: {error or 'Empty result'}"
                    state = {**state, "execution_log": state["execution_log"] + [error_msg]}

            except Exception as e:
                error_msg = f"Attempt {i+1} exception: {str(e)}"
                state = {**state, "execution_log": state["execution_log"] + [error_msg]}

        # 🎯 핵심: 성공한 결과들 중에서 다수결로 최적 선택
        if successful_results:
            # 가장 많이 나온 결과를 선택
            result_counts = Counter(successful_results)
            best_result = result_counts.most_common(1)[0][0]
            best_count = result_counts.most_common(1)[0][1]

            # 선택된 결과에 해당하는 TableInfo 찾기
            for item in successful_table_infos:
                if item['result'] == best_result:
                    new_table_info = item['table_info']
                    break

            # 다수결 정보 로깅
            success_rate = len(successful_results) / len(codes) * 100
            debug_msg = f"Majority voting: {best_result[:50]}... (appeared {best_count}/{len(successful_results)} times, success rate: {success_rate:.1f}%)"
            state = {**state, "execution_log": state["execution_log"] + [debug_msg]}

        elif results:
            # 성공한 것이 없다면 기존 방식 폴백
            best_result = Counter(results).most_common(1)[0][0]
        else:
            best_result = f"Unable to retrieve data for: {instruction} (all {len(codes)} attempts failed)"

    except Exception as e:
        best_result = f"Error in retrieval: {str(e)}"

    # Prepare state update
    updated_state = {**state}
    updated_state["tool_results"] = state["tool_results"] + [best_result]
    updated_state["execution_log"] = state["execution_log"] + [f"Retrieval completed: {best_result[:100]}..."]

    # THE FIX: If a new table was created, add it to the state for the next step
    if new_table_info:
        updated_state["tables"] = state["tables"] + [new_table_info.to_dict()]

    return updated_state


async def calculator_tool_node(state: MACTState) -> MACTState:
    """
    Perform mathematical calculations.
    """
    expression = state["current_argument"]
    try:
        expression = expression.replace(",", "").replace("$", "")
        try:
            result = eval(expression, {"__builtins__": {}})
            result_str = str(result)
        except:
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
                result_str = await _calculate_with_code_generation(expression, state)
    except Exception as e:
        result_str = f"Calculation error: {str(e)}"

    return {
        **state,
        "tool_results": state["tool_results"] + [result_str],
        "calculation_results": state["calculation_results"] + [result_str],
        "execution_log": state["execution_log"] + [f"Calculation completed: {expression} = {result_str}"]
    }


async def search_tool_node(state: MACTState) -> MACTState:
    """
    Search for external information using Wikipedia.
    """
    query = state["current_argument"]
    try:
        wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
        search_result = wikipedia.run(query)
        if len(search_result) > 500:
            search_result = search_result[:500] + "..."
    except Exception as e:
        search_result = f"Search failed: {str(e)}"

    return {
        **state,
        "tool_results": state["tool_results"] + [search_result],
        "search_results": state["search_results"] + [search_result],
        "execution_log": state["execution_log"] + [f"Search completed for: {query}"]
    }


async def operator_tool_node(state: MACTState) -> MACTState:
    """
    Perform complex table operations like JOIN, GROUP BY, etc.
    Phase 3-B: Enhanced with robust column name handling and better JOIN logic.
    Now persists the resulting table back into the state.
    """
    operation = state["current_argument"]
    tables = get_tables_from_state(state)
    results = []
    code_sample = state["code_sample"]
    new_table_info = None

    if not tables:
        return {
            **state,
            "tool_results": state["tool_results"] + ["No tables available for operation"],
            "execution_log": state["execution_log"] + ["ERROR: No tables in state for operation"]
        }

    table_codes = [len(table.df_code) for table in tables]
    debug_log = f"Operator debug: Found {len(tables)} tables, df_code lengths: {table_codes}"
    print(f"DEBUG: {debug_log}")

    try:
        llm = create_llm(state["code_model"])
        df_setup_code = _build_multi_table_df_code(tables)

        if not df_setup_code.strip():
            raise ValueError("No DataFrame setup code available for operation")

        # 🎯 Phase 3-B Fix: Improved Operate prompt with robust JOIN examples
        prompt = build_code_generation_prompt(
            f"Perform table operation: {operation}",
            df_setup_code,
            model_name=state.get("code_model"),
            examples=f"""
# IMPORTANT: Always assign final result to 'new_table' variable
# Available tables: df1, df2, df3, etc. and primary df

# Common operations:
# JOIN: new_table = df1.merge(df2, left_on='col1', right_on='col2', how='inner')
# FILTER: new_table = df[df['column'] == 'value']
# GROUP BY: new_table = df.groupby('column').agg({{'target_col': 'sum'}}).reset_index()
# SELECT: new_table = df[['col1', 'col2', 'col3']]

# For multi-table operations, use df1, df2, etc.
# Current operation: {operation}
new_table = df  # Replace with appropriate operation
"""
        )

        responses = await llm.abatch([prompt] * code_sample)
        codes = [response.content for response in responses if response.content]

        # 🎯 Phase 2-A: 기존 MACT처럼 모든 코드를 실행하고 다수결로 선택
        successful_results = []
        successful_table_infos = []

        for i, code in enumerate(codes):
            try:
                result, rows, error, _ = execute_table_code(
                    code,
                    df_setup_code,
                    model_name=state.get("code_model")
                )
                if result and rows and not error:
                    # 성공한 결과만 수집
                    successful_results.append(result)
                    successful_table_infos.append({
                        'result': result,
                        'rows': rows,
                        'table_info': TableInfo(
                            name=f"operated_step_{state['current_step']}_attempt_{i}",
                            columns=rows[0],
                            content=rows[1:],
                            df_code=table2df(rows),
                            linear_representation=table_linear(rows, num_row=None)
                        )
                    })
                    results.append(result)  # 전체 결과에도 추가
                else:
                    # 실패한 경우도 로깅
                    error_msg = f"Operation attempt {i+1} failed: {error or 'Empty result'}"
                    state = {**state, "execution_log": state["execution_log"] + [error_msg]}

            except Exception as e:
                error_msg = f"Operation attempt {i+1} exception: {str(e)}"
                state = {**state, "execution_log": state["execution_log"] + [error_msg]}

        # 🎯 핵심: 성공한 결과들 중에서 다수결로 최적 선택
        if successful_results:
            # 가장 많이 나온 결과를 선택
            result_counts = Counter(successful_results)
            best_result = result_counts.most_common(1)[0][0]
            best_count = result_counts.most_common(1)[0][1]

            # 선택된 결과에 해당하는 TableInfo 찾기
            for item in successful_table_infos:
                if item['result'] == best_result:
                    new_table_info = item['table_info']
                    break

            # 다수결 정보 로깅
            success_rate = len(successful_results) / len(codes) * 100
            debug_msg = f"Operation majority voting: {best_result[:50]}... (appeared {best_count}/{len(successful_results)} times, success rate: {success_rate:.1f}%)"
            state = {**state, "execution_log": state["execution_log"] + [debug_msg]}

        elif results:
            # 성공한 것이 없다면 기존 방식 폴백
            best_result = Counter(results).most_common(1)[0][0]
        else:
            best_result = f"Unable to perform operation: {operation} (all {len(codes)} attempts failed)"

    except Exception as e:
        best_result = f"Error in operation: {str(e)}"

    # Prepare state update
    updated_state = {**state}
    updated_state["tool_results"] = state["tool_results"] + [best_result]
    updated_state["table_operations"] = state["table_operations"] + [best_result]
    updated_state["execution_log"] = state["execution_log"] + [f"Operation completed: {operation[:50]}..."]

    # THE FIX: If a new table was created, add it to the state for the next step
    if new_table_info:
        updated_state["tables"] = state["tables"] + [new_table_info.to_dict()]

    return updated_state


async def _calculate_with_code_generation(expression: str, state: MACTState) -> str:
    """Generate code to perform calculation."""
    try:
        llm = create_llm(state["code_model"])
        prompt = f"""Calculate the following expression and return only the result:
{expression}

Provide Python code to calculate this:
```python
result = {expression}
print(result)
```"""
        response = await llm.ainvoke(prompt)
        code = extract_code_from_response(response.content, state.get("code_model"))
        if code:
            local_vars = {}
            exec(code, {"__builtins__": {}}, local_vars)
            if "result" in local_vars:
                return str(local_vars["result"])
        return f"Unable to calculate: {expression}"
    except Exception as e:
        return f"Calculation error: {str(e)}"


def _build_multi_table_df_code(tables: List[TableInfo]) -> str:
    """Build DataFrame setup code for multiple tables (기존 MACT 방식)."""
    if not tables:
        return ""
    setup_lines = ["import pandas as pd", "import numpy as np"]
    for i, table in enumerate(tables):
        # Use the latest df_code for each table
        df_code = table.df_code
        # Modify variable name for multi-table setup
        modified_code = df_code.replace("df=pd.DataFrame(data)", f"df{i+1}=pd.DataFrame(data)")
        setup_lines.append(modified_code)
    if len(tables) >= 1:
        setup_lines.append("df = df1  # Primary table")
    if len(tables) >= 2:
        setup_lines.append("# Additional tables: df2, df3, etc.")
    result = "\n".join(setup_lines)
    print(f"DEBUG: Generated multi-table setup code ({len(result)} chars)")
    return result


def _clean_equation(equation: str) -> str:
    """Clean equation for calculation."""
    equation = equation.replace(",", "")
    equation = equation.replace("$", "")
    equation = equation.replace("%", "/100")
    return equation.strip()


def _extract_numerical_result(text: str) -> Union[float, str]:
    """Extract numerical result from text."""
    import re
    number_patterns = [
        r'\d+\.?\d*', 
        r'\$[\,\d]+\.?\d*', 
        r'[\,\d]+\.?\d*%', 
    ]
    for pattern in number_patterns:
        matches = re.findall(pattern, text)
        if matches:
            last_match = matches[-1]
            cleaned = last_match.replace('$', '').replace(',', '').replace('%', '')
            try:
                return float(cleaned)
            except:
                continue
    return text