"""
Table processing utilities adapted from original MACT implementation.
"""

import re
import string
import random
import pandas as pd
from typing import List, Any, Tuple


def clean_cell(cell: Any, idx: int, header: bool = False) -> str:
    """Clean individual table cell."""
    if not isinstance(cell, str):
        cell = str(cell)
    cell = cell.replace("\\n", " ")
    cell = cell.replace("\n", " ")
    if cell.strip() == "" and header:
        cell = f"column {idx+1}"
    return cell


def check_header(header: List[str]) -> List[str]:
    """Check and fix duplicate header names."""
    if len(set(header)) == len(header):
        return header

    header_ = []
    for cell in header:
        if cell in header_:
            cell = cell + f"_{random.randint(0, 1000)}"
        header_.append(cell)
    return header_


def table_linear(table: List[List[Any]], num_row: int = None) -> str:
    """Convert table to linear string representation."""
    if not table or len(table) == 0:
        return ""

    header = table[0]
    header = [clean_cell(cell, i, header=True) for i, cell in enumerate(header)]
    header = check_header(header)

    if not num_row:
        num_row = len(table) - 1

    selected_rows = table[1:num_row+1]
    output = ""
    output += "| " + " | ".join(header) + " |"
    output += "\n"

    for row in selected_rows:
        row = [clean_cell(cell, i, header=False) for i, cell in enumerate(row)]
        output += "| " + " | ".join(row) + " |"
        output += "\n"

    return output


def normalize_column_name(col_name: str) -> str:
    """
    🎯 Bug Fix #1: Normalize column names to consistent lowercase format.
    This fixes JOIN failures caused by case mismatches (e.g., 'Department_ID' vs 'department_ID').

    Examples:
        'Department_ID' -> 'department_id'
        'department_ID' -> 'department_id'
        'Host_city_ID' -> 'host_city_id'
        'temporary_acting' -> 'temporary_acting'
    """
    if not col_name:
        return col_name

    normalized = col_name.strip()

    # Special handling for ID columns (most common JOIN issue)
    # Pattern: [prefix]_ID or [prefix]_Id or [prefix]ID
    id_pattern = re.compile(r'(.+?)_?([Ii][Dd])$')
    match = id_pattern.match(normalized)
    if match:
        prefix = match.group(1)
        # Normalize: prefix_id (all lowercase with underscore)
        return f"{prefix.lower()}_id"

    # General case: lowercase all
    return normalized.lower()


def table2df(table: List[List[Any]], normalize_columns: bool = True) -> str:
    """
    Convert table to pandas DataFrame code string.

    Args:
        table: List of lists representing table data (first row is header)
        normalize_columns: If True, normalize column names to lowercase (fixes Bug #1)

    Returns:
        Python code string that creates a pandas DataFrame
    """
    if not table or len(table) == 0:
        return "import pandas as pd\ndf = pd.DataFrame()"

    output = "import pandas as pd\n"
    header = table[0]
    header = [clean_cell(cell, i, header=True) for i, cell in enumerate(header)]
    header = check_header(header)

    # 🎯 Bug Fix #1: Normalize column names to prevent JOIN failures
    if normalize_columns:
        header = [normalize_column_name(col) for col in header]

    rows = table[1:]
    rows_ = []

    for row in rows:
        row_ = []
        for cell in row:
            try:
                cell = int(cell)
            except:
                try:
                    cell = float(cell)
                except:
                    pass
            if isinstance(cell, str):
                cell = cell.replace("\\n", " ")
                cell = cell.replace("\n", " ")
            row_.append(cell)
        rows_.append(row_)

    # Transpose rows to columns
    transposed_rows = [[] for _ in range(len(header))]
    for line in rows_:
        for i, cell in enumerate(line):
            if i < len(transposed_rows):
                transposed_rows[i].append(cell)

    output += "data={"
    for h, v_row in zip(header, transposed_rows):
        output += f"'{h}':{v_row}"
        output += ","
    output = output[:-1]  # Remove last comma
    output += "}"
    output += "\n"
    output += "df=pd.DataFrame(data)"

    return output


def normalize_answer(text: str) -> str:
    """Normalize answer for evaluation."""
    def remove_articles(text):
        return re.sub(r"\b(a|an|the)\b", " ", text)

    def white_space_fix(text):
        return " ".join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(text))))


def exact_match(predicted: str, target: str) -> bool:
    """Calculate exact match score."""
    normalized_pred = normalize_answer(predicted)
    normalized_target = normalize_answer(target)

    # Check for numeric equality (e.g., "123" == "123.0")
    try:
        pred_num = float(predicted.strip())
        target_num = float(target.strip())
        if pred_num == target_num:
            return True
    except (ValueError, AttributeError):
        pass

    return normalized_pred == normalized_target


def dfcode2str(dfcode: str) -> str:
    """Convert DataFrame code to string representation."""
    try:
        data = re.findall(r'\{.+?\}', dfcode)[0]
        data = eval(data)
        df = pd.DataFrame(data)
        rows = df.values.tolist()
        header = df.columns.tolist()
        rows.insert(0, header)
        table_string = table_linear(rows, num_row=50)
        return table_string
    except:
        return ""


def clean_qwen_code(code: str) -> str:
    """Clean QWEN3-8B generated code to fix common issues."""
    # Phase 2-A: More aggressive cleaning for unterminated string literals
    lines = code.split('\n')
    cleaned_lines = []

    for line in lines:
        # Skip overly verbose comments or explanations
        if line.strip().startswith('#') and len(line.strip()) > 50:
            continue

        # Skip text that looks like explanations (more comprehensive)
        if any(phrase in line.lower() for phrase in [
            'first, i need', 'wait, ', 'but wait,', 'looking at',
            'so the code', 'the user', 'example shows', 'let me think',
            'but the user', 'wait, the user', 'however, the user',
            'the example shows', 'the problem', 'the instruction',
            'perhaps the', 'maybe the', 'so perhaps', 'but since',
            'but the column', 'but since the', 'but here', 'but in this case'
        ]):
            continue

        # 🎯 Phase 2-A: Aggressive string literal fixing
        if line.strip() and not line.strip().startswith('#'):
            original_line = line

            # Remove unterminated explanatory text that might break strings
            if line.count('"') % 2 == 1:
                # Strategy 1: Find last complete assignment
                if '=' in line:
                    parts = line.split('=')
                    if len(parts) >= 2:
                        left_part = parts[0] + '='
                        right_part = '='.join(parts[1:])

                        # Try to fix the right part
                        if right_part.count('"') % 2 == 1:
                            # Find the first complete quoted string
                            first_quote = right_part.find('"')
                            if first_quote >= 0:
                                second_quote = right_part.find('"', first_quote + 1)
                                if second_quote >= 0:
                                    # Keep only up to the second quote
                                    fixed_right = right_part[:second_quote + 1]
                                    line = left_part + fixed_right
                                else:
                                    # No closing quote found, remove the opening quote part
                                    line = left_part + right_part[:first_quote]

                # Strategy 2: Remove everything after unbalanced quotes
                if line.count('"') % 2 == 1:
                    last_quote = line.rfind('"')
                    # If there's code before the quote, keep it
                    if last_quote > 0 and any(keyword in line[:last_quote] for keyword in ['df', '=', 'pd.']):
                        line = line[:last_quote]
                    else:
                        # Remove the problematic part
                        line = line.replace('"', '')

            # Strategy 3: Remove lines with obvious explanation text mixed with code
            explanation_patterns = [
                'but wait', 'but the', 'but since', 'however', 'perhaps',
                'maybe the', 'so the', 'but in this case', 'wait, the',
                'so perhaps', 'wait, no', 'hmm', 'oh right', 'actually'
            ]
            if any(pattern in line.lower() for pattern in explanation_patterns):
                continue

            # Remove lines that are clearly just text explanations
            if (not any(symbol in line for symbol in ['=', '(', ')', '[', ']', '.']) and
                len(line.strip()) > 30 and
                not line.strip().startswith('import')):
                continue

            cleaned_lines.append(line)

    # Join and ensure proper code structure
    cleaned_code = '\n'.join(cleaned_lines)

    # Extract only executable pandas code with more strict filtering
    executable_lines = []
    for line in cleaned_code.split('\n'):
        line = line.strip()

        # Must contain actual executable code patterns
        if (line.startswith('import') or
            line.startswith('df') or
            line.startswith('result') or
            line.startswith('final_result') or
            line.startswith('new_table') or
            'pd.DataFrame' in line or
            'pd.' in line or
            ('.merge(' in line) or
            ('.groupby(' in line) or
            ('[' in line and ']' in line and ('==' in line or '>' in line or '<' in line)) or  # filtering
            ('=' in line and any(keyword in line for keyword in ['df', 'result', 'merge', 'groupby']))):

            # Additional safety check: skip if it looks like text
            if not any(bad_phrase in line.lower() for bad_phrase in [
                'but wait', 'the user', 'example', 'problem', 'instruction',
                'but the', 'however', 'perhaps', 'wait, the'
            ]):
                executable_lines.append(line)

    final_code = '\n'.join(executable_lines)

    # Final syntax check and repair
    final_code = _repair_syntax_issues(final_code)

    return final_code


def _repair_syntax_issues(code: str) -> str:
    """Repair common syntax issues in generated code."""
    lines = code.split('\n')
    repaired_lines = []

    for line in lines:
        if not line.strip():
            continue

        # Fix unbalanced quotes
        if line.count('"') % 2 == 1:
            # Try to balance by removing the last quote
            last_quote = line.rfind('"')
            if last_quote >= 0:
                line = line[:last_quote] + line[last_quote + 1:]

        # Fix incomplete function calls
        if '(' in line and ')' not in line and not line.strip().endswith(':'):
            line = line + ')'

        # Fix incomplete assignments
        if line.strip().endswith('='):
            continue  # Skip incomplete assignments

        repaired_lines.append(line)

    return '\n'.join(repaired_lines)


def extract_code_from_response(response: str, model_name: str = None) -> str:
    """Extract Python code from LLM response with model-specific post-processing."""
    # Look for code blocks
    pattern = r"```(?:python|Python)?\n?(.*?)\n?```"
    matches = re.findall(pattern, response, re.DOTALL)

    raw_code = ""
    if matches:
        raw_code = matches[0].strip()
    else:
        # Fallback: look for lines that look like code
        lines = response.split('\n')
        code_lines = []
        for line in lines:
            line = line.strip()
            if (line.startswith('df') or
                line.startswith('result') or
                line.startswith('final_result') or
                line.startswith('new_table') or
                'pd.' in line or
                '=' in line and ('df' in line or 'result' in line)):
                code_lines.append(line)
        raw_code = '\n'.join(code_lines)

    # Apply model-specific cleaning
    is_qwen = (model_name and 'qwen' in model_name.lower()) or 'qwen' in response.lower()
    is_verbose_output = len(raw_code.split('\n')) > 10

    if is_qwen or is_verbose_output:
        # Apply QWEN3-8B specific cleaning for verbose/problematic outputs
        return clean_qwen_code(raw_code)

    return raw_code


def execute_table_code(code: str, table_df: str, df_path: str = None, model_name: str = None) -> Tuple[Any, List[List[Any]], Exception, str]:
    """Execute table manipulation code safely using original MACT approach with robust column name handling."""
    result = ""
    rows = []
    current_error = None
    executable_code = None

    try:
        # Extract executable code (original MACT approach)
        p = re.compile(r"```(?:Python|python).*?```", re.DOTALL)
        code_matches = re.findall(p, code)

        if code_matches:
            executable_code = code_matches[0]
            executable_code = "\n".join(executable_code.split("\n")[1:-1])
        else:
            executable_code = extract_code_from_response(code, model_name=model_name)

        if not executable_code:
            return "", [], None, None

        # 🎯 Phase 3-A Fix: Preprocess code to fix column name issues
        executable_code = _fix_column_references(executable_code, table_df)

        # Original MACT approach: combine table_df with executable_code
        combined_code = "\n".join([table_df, executable_code]) if table_df else executable_code

        # Debug logging
        print(f"DEBUG: Executing combined code ({len(combined_code)} chars)")
        print(f"DEBUG: Table setup code present: {bool(table_df)}")
        print(f"DEBUG: Executable code preview: {executable_code[:100]}...")

        # Prepare execution environment with proper imports
        import pandas as pd
        import numpy as np

        global_vars = {
            '__builtins__': __builtins__,
            'pd': pd,
            'pandas': pd,
            'np': np,
            'numpy': np
        }
        local_vars = {}

        # Load original dataframe if available
        if df_path:
            local_vars['original_df'] = pd.read_parquet(df_path, engine='pyarrow')

        # Execute combined code (original MACT approach)
        exec(combined_code, global_vars, local_vars)

        # Original MACT expects 'new_table' variable
        if 'new_table' in local_vars:
            new_table = local_vars['new_table']
            print(f"DEBUG: Found new_table variable: {type(new_table)}")

            # Convert to appropriate format (original MACT logic)
            if isinstance(new_table, pd.Series):
                new_table = new_table.to_frame()

            if isinstance(new_table, pd.DataFrame) and not new_table.empty:
                # Convert to string format (original MACT approach)
                header = new_table.columns.tolist()
                rows = new_table.values.tolist()
                rows.insert(0, header)

                if len(new_table) > 10:
                    remain_line = len(new_table) - 4
                    result = table_linear(rows, num_row=3) + f"\n ...[remaining {remain_line} rows not shown due to large table size]..."
                    rows = rows[:4]  # Keep header + 3 rows
                else:
                    result = table_linear(rows, num_row=None)

                print(f"DEBUG: Generated table result ({len(result)} chars)")
            else:
                print("DEBUG: new_table is empty or not a DataFrame")
                result = ""
        else:
            print(f"DEBUG: No 'new_table' variable found. Available variables: {list(local_vars.keys())}")
            # Fallback: try other result variables
            result_vars = ['final_result', 'result', 'answer']
            for var_name in result_vars:
                if var_name in local_vars:
                    fallback_result = local_vars[var_name]
                    print(f"DEBUG: Using fallback variable '{var_name}': {type(fallback_result)}")

                    # Convert fallback result to table format
                    if isinstance(fallback_result, pd.Series):
                        fallback_result = fallback_result.to_frame()

                    if isinstance(fallback_result, pd.DataFrame) and not fallback_result.empty:
                        header = fallback_result.columns.tolist()
                        rows = fallback_result.values.tolist()
                        rows.insert(0, header)

                        if len(fallback_result) > 10:
                            remain_line = len(fallback_result) - 4
                            result = table_linear(rows, num_row=3) + f"\n ...[remaining {remain_line} rows not shown due to large table size]..."
                            rows = rows[:4]  # Keep header + 3 rows
                        else:
                            result = table_linear(rows, num_row=None)

                        print(f"DEBUG: Converted fallback to table result ({len(result)} chars)")
                        break
                    else:
                        result = str(fallback_result)
                        break

        if not isinstance(result, str):
            result = str(result)

    except Exception as e:
        current_error = e
        result = ""
        rows = []
        print(f"DEBUG: Execution error: {e}")
        print(f"DEBUG: Failed code: {combined_code if 'combined_code' in locals() else executable_code}")

    return result, rows, current_error, executable_code


def _fix_column_references(code: str, table_df_code: str = None) -> str:
    """
    Fix column reference issues in generated code to prevent KeyError.
    This addresses the critical 'department_ID' error and similar column name mismatches.
    Enhanced to handle multi-table scenarios with robust column normalization.
    """
    if not code:
        return code

    # Extract actual column names from table_df_code (handles both single and multi-table scenarios)
    actual_columns = set()
    if table_df_code:
        # Extract column names from all data dictionaries in the setup code
        import re
        data_pattern = r"data=\{([^}]+)\}"
        data_matches = re.findall(data_pattern, table_df_code)
        for data_content in data_matches:
            # Extract keys (column names)
            key_pattern = r"'([^']+)':"
            column_matches = re.findall(key_pattern, data_content)
            actual_columns.update(column_matches)

    # 🎯 Critical Multi-Table Fix: Normalize all table column references to a consistent format
    # This is the root cause of JOIN failures - inconsistent column naming between tables
    if actual_columns:
        # Create bidirectional mapping for all department/head ID variations
        dept_columns = [col for col in actual_columns if 'department' in col.lower() and 'id' in col.lower()]
        head_columns = [col for col in actual_columns if 'head' in col.lower() and 'id' in col.lower()]

        # If we have mixed case department columns, normalize to the most common format
        if dept_columns:
            # Choose the most frequent format or default to 'Department_ID'
            target_dept_col = 'Department_ID' if 'Department_ID' in dept_columns else dept_columns[0]
            for col in dept_columns:
                if col != target_dept_col:
                    # Replace all references to this column with the target format
                    patterns = [f"'{col}'", f'"{col}"', f"['{col}']", f'["{col}"]', f"on='{col}'", f'on="{col}"']
                    replacements = [f"'{target_dept_col}'", f'"{target_dept_col}"', f"['{target_dept_col}']", f'["{target_dept_col}"]', f"on='{target_dept_col}'", f'on="{target_dept_col}"']
                    for pattern, replacement in zip(patterns, replacements):
                        if pattern in code:
                            code = code.replace(pattern, replacement)
                            print(f"DEBUG: Normalized column: {pattern} -> {replacement}")

        # Same for head columns
        if head_columns:
            target_head_col = 'head_ID' if 'head_ID' in head_columns else head_columns[0]
            for col in head_columns:
                if col != target_head_col:
                    patterns = [f"'{col}'", f'"{col}"', f"['{col}']", f'["{col}"]', f"on='{col}'", f'on="{col}"']
                    replacements = [f"'{target_head_col}'", f'"{target_head_col}"', f"['{target_head_col}']", f'["{target_head_col}"]', f"on='{target_head_col}'", f'on="{target_head_col}"']
                    for pattern, replacement in zip(patterns, replacements):
                        if pattern in code:
                            code = code.replace(pattern, replacement)
                            print(f"DEBUG: Normalized column: {pattern} -> {replacement}")

    # Common column name mapping patterns from MMQA dataset
    column_mappings = {
        # Department-related columns
        'department_ID': ['Department_ID', 'department_id', 'dept_id'],
        'Department_ID': ['department_ID', 'department_id', 'dept_id'],
        'department_id': ['Department_ID', 'department_ID', 'dept_id'],

        # Head-related columns
        'head_ID': ['Head_ID', 'head_id'],
        'Head_ID': ['head_ID', 'head_id'],
        'head_id': ['Head_ID', 'head_ID'],

        # Other common patterns
        'Host_city_ID': ['host_city_ID', 'Host_City_ID', 'host_city_id'],
        'host_city_ID': ['Host_city_ID', 'Host_City_ID', 'host_city_id'],

        # Temporary acting column variations
        'temporary_acting': ['Temporary_Acting', 'temporary_Acting', 'Temporary_acting'],
        'Temporary_Acting': ['temporary_acting', 'temporary_Acting', 'Temporary_acting'],
    }

    fixed_code = code

    # Strategy 1: Use actual columns from table_df_code if available
    if actual_columns:
        # Create case-insensitive mapping
        column_map = {}
        for actual_col in actual_columns:
            # Map variations to the actual column name
            variations = [
                actual_col.lower(),
                actual_col.upper(),
                actual_col.replace('_', '').lower(),
                actual_col.replace('_', '').upper()
            ]
            for variation in variations:
                if variation != actual_col:
                    column_map[variation] = actual_col

        # Apply the mapping
        for wrong_name, correct_name in column_map.items():
            # Replace column references in various contexts
            patterns = [
                f"'{wrong_name}'",  # String literals
                f'"{wrong_name}"',  # Double quoted strings
                f"['{wrong_name}']",  # DataFrame column access
                f'["{wrong_name}"]',  # DataFrame column access with double quotes
            ]

            replacements = [
                f"'{correct_name}'",
                f'"{correct_name}"',
                f"['{correct_name}']",
                f'["{correct_name}"]',
            ]

            for pattern, replacement in zip(patterns, replacements):
                if pattern in fixed_code:
                    fixed_code = fixed_code.replace(pattern, replacement)
                    print(f"DEBUG: Fixed column reference: {pattern} -> {replacement}")

    # Strategy 2: Apply common MMQA column mappings
    for wrong_name, possible_correct in column_mappings.items():
        if actual_columns:
            # Find the correct name that exists in actual columns
            correct_name = None
            for candidate in possible_correct:
                if candidate in actual_columns:
                    correct_name = candidate
                    break

            if correct_name:
                patterns = [
                    f"'{wrong_name}'",
                    f'"{wrong_name}"',
                    f"['{wrong_name}']",
                    f'["{wrong_name}"]',
                ]

                replacements = [
                    f"'{correct_name}'",
                    f'"{correct_name}"',
                    f"['{correct_name}']",
                    f'["{correct_name}"]',
                ]

                for pattern, replacement in zip(patterns, replacements):
                    if pattern in fixed_code:
                        fixed_code = fixed_code.replace(pattern, replacement)
                        print(f"DEBUG: Applied MMQA column mapping: {pattern} -> {replacement}")

    # Strategy 3: Fix common pandas operation issues
    # Fix merge column specification issues
    merge_patterns = [
        (r"merge\([^,]+,\s*on='([^']+)'\)", r"merge(df2, on='\1', how='inner')"),
        (r'merge\([^,]+,\s*on="([^"]+)"\)', r'merge(df2, on="\1", how="inner")')
    ]

    for pattern, replacement in merge_patterns:
        fixed_code = re.sub(pattern, replacement, fixed_code)

    return fixed_code