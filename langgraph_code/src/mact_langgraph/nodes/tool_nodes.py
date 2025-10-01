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

from ..state import MACTState, TableInfo, ActionType, get_tables_from_state
from .core_nodes import create_llm
from ..utils.table_utils import (
    table_linear, table2df, execute_table_code, extract_code_from_response
)
from ..utils.prompt_utils import build_code_generation_prompt


async def retriever_tool_node(state: MACTState) -> MACTState:
    """
    Retrieve data from tables based on specified conditions.
    🎯 Bug Fix #2: Enhanced with multi-table detection to delegate to operator when needed.
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

    # 🎯 Bug Fix #2: Detect if instruction mentions multiple tables
    instruction_lower = instruction.lower()
    table_keywords = {
        'department': ['department', 'dept'],
        'management': ['management', 'manager', 'head', 'acting'],
        'city': ['city', 'cities'],
        'farm_competition': ['competition', 'farm', 'host'],
        'student': ['student'],
        'course': ['course', 'class'],
        'people': ['people', 'person'],
        'candidate': ['candidate'],
        'head': ['head'],
    }

    mentioned_table_types = []
    for table_type, keywords in table_keywords.items():
        if any(kw in instruction_lower for kw in keywords):
            mentioned_table_types.append(table_type)

    # Check if multi-table operation (JOIN likely needed)
    multi_table_indicators = [
        ' and ', ' with ', ' from ', ' join',
        'both', 'together', 'combine', 'merge'
    ]
    likely_multi_table = (
        len(mentioned_table_types) >= 2 or
        any(indicator in instruction_lower for indicator in multi_table_indicators)
    )

    if likely_multi_table and len(tables) >= 2:
        # Delegate to operator for multi-table operations
        log_msg = f"🔄 Multi-table retrieval detected - delegating to Operator: {instruction[:80]}..."
        print(log_msg)

        # Update state to call operator instead
        state_for_operator = {
            **state,
            "current_action_type": ActionType.OPERATE.value,
            "current_argument": f"Retrieve data for: {instruction}",
            "execution_log": state["execution_log"] + [log_msg]
        }
        return await operator_tool_node(state_for_operator)

    # Single-table retrieval (original logic)
    # Use the latest table in the list for operations
    table_df_code = tables[-1].df_code if tables else ""
    debug_log = f"Retriever debug: Single-table mode, using table {len(tables)-1}, df_code length: {len(table_df_code)}"
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

        # 🎯 Phase 1 Fix: Hybrid voting like original MACT
        # Combine tool execution results with LLM observations
        all_observations = successful_results.copy()

        # Add LLM observations if not using code-as-observation mode
        long_table = state.get("long_table_op") not in [None, "ignore"]
        code_as_observation = state.get("code_as_observation", False)

        if not long_table and not code_as_observation and successful_results:
            # Generate LLM observations from successful results
            for i, result in enumerate(successful_results):
                llm_obs = f"Observation {state['current_step']}: {result[:100]}"
                all_observations.append(llm_obs)

        # 🎯 핵심: 하이브리드 다수결 (도구 결과 + LLM 관찰)
        if all_observations:
            # 가장 많이 나온 결과를 선택 (original MACT 방식)
            result_counts = Counter(all_observations)
            best_result = result_counts.most_common(1)[0][0]
            best_count = result_counts.most_common(1)[0][1]

            # 선택된 결과에 해당하는 TableInfo 찾기
            for item in successful_table_infos:
                if item['result'] in best_result:  # Contains check for observation format
                    new_table_info = item['table_info']
                    break

            # 다수결 정보 로깅
            success_rate = len(successful_results) / len(codes) * 100 if codes else 0
            debug_msg = f"Hybrid voting: {best_result[:50]}... (appeared {best_count}/{len(all_observations)} times, tool success: {success_rate:.1f}%)"
            state = {**state, "execution_log": state["execution_log"] + [debug_msg]}

            # Store LLM observations for future use
            state = {**state, "llm_observations": state["llm_observations"] + all_observations}

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

        # 🎯 Bug Fix #1: Extract FK information to guide JOIN operations
        fk_hints = ""
        foreign_keys = state.get("foreign_keys", [])
        if foreign_keys:
            fk_hints = "\n# Foreign Key Relationships (use these for JOINs):\n"
            for fk in foreign_keys:
                # Normalize FK names
                from ..utils.table_utils import normalize_column_name
                normalized_fk = normalize_column_name(fk)
                fk_hints += f"#   - {normalized_fk}\n"
            fk_hints += "# All column names are normalized to lowercase (e.g., 'department_id', 'host_city_id')\n"

        # 🎯 Bug Fix #1: Enhanced prompt with FK hints and normalized column guidance
        prompt = build_code_generation_prompt(
            f"Perform table operation: {operation}",
            df_setup_code,
            model_name=state.get("code_model"),
            examples=f"""
# IMPORTANT: Always assign final result to 'new_table' variable
# Available tables: df1, df2, df3, etc. and primary df
{fk_hints}
# Common operations:
# JOIN: new_table = df1.merge(df2, on='department_id', how='inner')  # Use normalized column names
# JOIN (different names): new_table = df1.merge(df2, left_on='col1', right_on='col2', how='inner')
# FILTER: new_table = df[df['column'] == 'value']
# GROUP BY: new_table = df.groupby('column').agg({{'target_col': 'sum'}}).reset_index()
# SELECT: new_table = df[['col1', 'col2', 'col3']]

# ⚠️ CRITICAL: All column names are LOWERCASE (e.g., 'department_id', not 'Department_ID')
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

        # 🎯 Phase 1 Fix: Hybrid voting for operator tool
        all_observations = successful_results.copy()

        # Add LLM observations if not using code-as-observation mode
        long_table = state.get("long_table_op") not in [None, "ignore"]
        code_as_observation = state.get("code_as_observation", False)

        if not long_table and not code_as_observation and successful_results:
            # Generate LLM observations from successful results
            for i, result in enumerate(successful_results):
                llm_obs = f"Observation {state['current_step']}: {result[:100]}"
                all_observations.append(llm_obs)

        # 🎯 핵심: 하이브리드 다수결 (도구 결과 + LLM 관찰)
        if all_observations:
            # 가장 많이 나온 결과를 선택 (original MACT 방식)
            result_counts = Counter(all_observations)
            best_result = result_counts.most_common(1)[0][0]
            best_count = result_counts.most_common(1)[0][1]

            # 선택된 결과에 해당하는 TableInfo 찾기
            for item in successful_table_infos:
                if item['result'] in best_result:  # Contains check for observation format
                    new_table_info = item['table_info']
                    break

            # 다수결 정보 로깅
            success_rate = len(successful_results) / len(codes) * 100 if codes else 0
            debug_msg = f"Operation hybrid voting: {best_result[:50]}... (appeared {best_count}/{len(all_observations)} times, tool success: {success_rate:.1f}%)"
            state = {**state, "execution_log": state["execution_log"] + [debug_msg]}

            # Store LLM observations for future use
            state = {**state, "llm_observations": state["llm_observations"] + all_observations}

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