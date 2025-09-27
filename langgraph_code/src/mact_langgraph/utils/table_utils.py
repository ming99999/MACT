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


def table2df(table: List[List[Any]]) -> str:
    """Convert table to pandas DataFrame code string."""
    if not table or len(table) == 0:
        return "import pandas as pd\ndf = pd.DataFrame()"

    output = "import pandas as pd\n"
    header = table[0]
    header = [clean_cell(cell, i, header=True) for i, cell in enumerate(header)]
    header = check_header(header)

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
    return normalize_answer(predicted) == normalize_answer(target)


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


def extract_code_from_response(response: str) -> str:
    """Extract Python code from LLM response."""
    # Look for code blocks
    pattern = r"```(?:python|Python)?\n?(.*?)\n?```"
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        return matches[0].strip()

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

    return '\n'.join(code_lines)


def execute_table_code(code: str, table_df: str, df_path: str = None) -> Tuple[Any, List[List[Any]], Exception, str]:
    """Execute table manipulation code safely."""
    result = ""
    rows = []
    current_error = None
    executable_code = None

    try:
        # Extract executable code
        p = re.compile(r"```(?:Python|python).*?```", re.DOTALL)
        code_matches = re.findall(p, code)

        if code_matches:
            executable_code = code_matches[0]
            executable_code = "\n".join(executable_code.split("\n")[1:-1])
        else:
            executable_code = extract_code_from_response(code)

        if not executable_code:
            return "", [], None, None

        # Prepare execution environment
        local_vars = {}

        # Load original dataframe if available
        if df_path:
            import pandas as pd
            local_vars['original_df'] = pd.read_parquet(df_path, engine='pyarrow')

        # Execute table setup code
        if table_df:
            exec(table_df, globals(), local_vars)

        # Execute the main code
        exec(executable_code, globals(), local_vars)

        # Try to get result
        result_vars = ['final_result', 'result', 'new_table', 'answer']
        for var_name in result_vars:
            if var_name in local_vars:
                result = local_vars[var_name]
                break

        # Convert result to appropriate format
        if isinstance(result, pd.Series):
            result = result.to_frame()

        if isinstance(result, pd.DataFrame) and not result.empty:
            header = result.columns.tolist()
            rows = result.values.tolist()
            rows.insert(0, header)

            if len(result) > 10:
                remain_line = len(result) - 4
                result = table_linear(rows, num_row=3) + f"\n ...[remaining {remain_line} rows not shown due to large table size]..."
                rows = rows[:4]  # Keep header + 3 rows
            else:
                result = table_linear(rows, num_row=None)

        if not isinstance(result, str):
            result = str(result)

    except Exception as e:
        current_error = e
        result = ""
        rows = []

    return result, rows, current_error, executable_code