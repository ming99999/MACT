""" Utility classes and functions related to MACT (NAACL 2025). 

Copyright (c) 2025 Robert Bosch GmbH 


This program is free software: you can redistribute it and/or modify 

it under the terms of the GNU Affero General Public License as published 

by the Free Software Foundation, either version 3 of the License, or 

(at your option) any later version. 

This program is distributed in the hope that it will be useful, 

but WITHOUT ANY WARRANTY; without even the implied warranty of 

MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 

GNU Affero General Public License for more details. 

You should have received a copy of the GNU Affero General Public License 

along with this program.  If not, see <https://www.gnu.org/licenses/>. 

"""

import os
import joblib
import json
import pandas as pd
import random
import tiktoken
import re
import string
from typing import List, Dict, Any, Tuple
# random.seed(42)


def clean_cell(cell, idx, header) -> str:
    if not isinstance(cell, str):
        cell = str(cell)
    cell = cell.replace("\\n", " ")
    cell = cell.replace("\n", " ")
    if cell.strip() == "" and header:
        cell = f"column {idx+1}"
    return cell


def check_header(header: list) -> list:
    # check wether header repete
    if not len(set(header)) == len(header):
        header_ = []
        for cell in header:
            if cell in header:
                cell = cell + f"_{random.randint(0,1000)}"
            header_.append(cell)
    return header


def table_linear(table, num_row):

    header = table[0]
    header = [clean_cell(cell, i, header=True)
              for i, cell in enumerate(header)]
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


def table2df(table):
    # transform table in list format into df code
    # currently only relational table
    output = "import pandas as pd\n"
    header = table[0]
    header = [clean_cell(cell, i, header=True)
              for i, cell in enumerate(header)]
    header = check_header(header)
    rows = table[1:]
    rows_ = []
    for row in rows:
        row_ = []
        for cell in row:
            try:
                cell = int(cell)
            except:
                pass
            try:
                cell = float(cell)
            except:
                pass
            if isinstance(cell, str):
                cell = cell.replace("\\n", " ")
                cell = cell.replace("\n", " ")
            row_.append(cell)
        rows_.append(row_)

    transposed_rows = [[] for i in range(len(header))]
    for line in rows_:
        for i, cell in enumerate(line):
            transposed_rows[i].append(cell)
    output += "data={"
    for h, v_row in zip(header, transposed_rows):
        output += f"'{h}':{v_row}"
        output += ","
    output = output[:-1]
    output += "}"
    output += "\n"
    output += "df=pd.DataFrame(data)"
    return output


def summarize_react_trial(agents):
    correct = [a for a in agents if a.is_correct()]
    halted = [a for a in agents if a.is_halted()]
    incorrect = [a for a in agents if a.is_finished() and not a.is_correct()]
    return correct, incorrect, halted


def dfcode2str(dfcode):
    data = re.findall(r'\{.+?\}', dfcode)[0]
    data = eval(data)
    df = pd.DataFrame(data)
    rows = df.values.tolist()
    header = df.columns.tolist()
    rows.insert(0, header)
    table_string = table_linear(rows, num_row=50)
    return table_string


def parse_action(string):
    string = re.findall(r'Retrieve\[.+?\]', string)+re.findall(r'Operate\[.+?\]', string)+re.findall(
        r'Finish\[.+?\]', string)+re.findall(r'Search\[.+?\]', string)+re.findall(r'Calculate\[.+?\]', string)
    if string:
        string = string[0]
        pattern = r'^(\w+)\[(.+)\]$'
        match = re.match(pattern, string)
        if match:
            action_type = match.group(1)
            argument = match.group(2)
            return action_type, argument
        else:
            return None, None
    else:
        return None, None


def extract_from_outputs(outputs, num_choices):
    try:
        extracted = re.findall(r'The best path is \d', outputs) + \
            re.findall(r'The best result is \d', outputs)
        if len(extracted) > 0:
            target_choice = int(re.findall(r'\d', extracted[0])[0])-1
        else:
            target_choice = int(random.sample(num_choices, k=1)[0])
        # make sure target choice is within the num_choices
        if not target_choice < num_choices:
            target_choice = int(random.sample(num_choices, k=1)[0])
    except:
        target_choice = 0
    return target_choice


def get_databench_table(table_dir, dataset, k=2):
    df = pd.read_parquet(
        f"{table_dir}/{dataset}/all.parquet", engine='pyarrow')
    df_path = f"{table_dir}/{dataset}/all.parquet"
    header = df.columns.tolist()
    val_dict = {h: df[h].tolist() for h in header}
    vals = [val_dict[h][:k] for h in header]
    vals = [[col[i] for col in vals] for i in range(k)]
    vals.insert(0, header)
    table = table_linear(vals, num_row=None)
    x = len(df) - 3
    table += f"...[remaining {x} rows unshown due to large table size]..."
    return table, vals,  df_path


def load_dataset(file_path: str) -> List[Dict[str, Any]]:
    """
    Load TQA dataset from JSONL file.
    
    Args:
        file_path: Path to the JSONL dataset file
        
    Returns:
        List of dataset items
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [json.loads(line) for line in f]
    except json.JSONDecodeError:
        # Fallback for JSON array format
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading dataset from {file_path}: {e}")
            return []
    except Exception as e:
        print(f"Error loading dataset from {file_path}: {e}")
        return []


def save_results(results: List[Dict[str, Any]], output_path: str):
    """
    Save results to JSONL file.
    
    Args:
        results: List of result dictionaries
        output_path: Output file path
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for result in results:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
        print(f"Results saved to {output_path}")
    except Exception as e:
        print(f"Error saving results to {output_path}: {e}")


def format_table_for_prompt(table_data) -> str:
    """
    Format table data for LLM prompt.
    
    Args:
        table_data: Table data (can be list of lists, string, or dict)
        
    Returns:
        Formatted table string
    """
    if isinstance(table_data, str):
        return table_data
    
    elif isinstance(table_data, list):
        # List of lists format
        if table_data and isinstance(table_data[0], list):
            # Convert to markdown table
            lines = []
            for i, row in enumerate(table_data):
                line = "| " + " | ".join(str(cell) for cell in row) + " |"
                lines.append(line)
                if i == 0:  # Add header separator
                    separator = "| " + " | ".join("---" for _ in row) + " |"
                    lines.append(separator)
            return "\n".join(lines)
        else:
            return str(table_data)
    
    elif isinstance(table_data, dict):
        # Convert dict to table format
        if "header" in table_data and "rows" in table_data:
            header = table_data["header"]
            rows = table_data["rows"]
            all_rows = [header] + rows
            return format_table_for_prompt(all_rows)
        elif "table_columns" in table_data and "table_content" in table_data:
            header = table_data["table_columns"]
            rows = table_data["table_content"]
            all_rows = [header] + rows
            return format_table_for_prompt(all_rows)
        else:
            return str(table_data)
    
    else:
        return str(table_data)


def create_tqa_prompt(question: str, 
                     table: str, 
                     context: str = "", 
                     task_type: str = "general") -> str:
    """
    Create TQA prompt based on task type.
    
    Args:
        question: The question to answer
        table: Formatted table data
        context: Additional context
        task_type: Type of task (tat, mmqa, wtq, etc.)
        
    Returns:
        Formatted prompt string
    """
    if task_type.lower() == "tat":
        prompt_template = """Given the following table and context, please answer the question accurately.

Context: {context}

Table:
{table}

Question: {question}

Please provide a clear and concise answer based on the information in the table and context."""

    elif task_type.lower() == "mmqa":
        prompt_template = """You are given a table and a question. Please analyze the table carefully and answer the question based on the information provided.

Table:
{table}

Question: {question}

Answer:"""

    elif task_type.lower() in ["wtq", "scitab"]:
        prompt_template = """Given the table below, please answer the question.

Table:
{table}

Question: {question}

Please provide the answer based on the table data:"""

    else:
        # General template
        prompt_template = """Based on the following table, please answer the question.

{context_section}
Table:
{table}

Question: {question}

Answer:"""

    # Handle context section
    context_section = f"Context: {context}\n\n" if context.strip() else ""
    
    return prompt_template.format(
        question=question,
        table=table,
        context=context,
        context_section=context_section
    )


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


def calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate evaluation metrics.
    
    Args:
        results: List of result dictionaries with 'predicted' and 'target' keys
        
    Returns:
        Dictionary containing calculated metrics
    """
    if not results:
        return {"exact_match": 0.0, "total": 0, "correct": 0}
    
    correct = 0
    total = len(results)
    
    for result in results:
        if "predicted" in result and "target" in result:
            if exact_match(str(result["predicted"]), str(result["target"])):
                correct += 1
    
    exact_match_score = correct / total if total > 0 else 0.0
    
    return {
        "exact_match": exact_match_score,
        "correct": correct,
        "total": total
    }


def print_sample_results(results: List[Dict[str, Any]], num_samples: int = 3):
    """Print sample results for inspection."""
    print(f"\n=== Sample Results (showing {min(num_samples, len(results))} out of {len(results)}) ===")
    
    for i, result in enumerate(results[:num_samples]):
        print(f"\nSample {i+1}:")
        print(f"Question: {result.get('question', 'N/A')}")
        print(f"Target: {result.get('target', 'N/A')}")
        print(f"Predicted: {result.get('predicted', 'N/A')}")
        print(f"Correct: {exact_match(str(result.get('predicted', '')), str(result.get('target', '')))}")
        print("-" * 50)
