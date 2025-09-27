"""
MMQA dataset specific utilities.
"""

from typing import List, Dict, Any, Tuple
from ..state import TableInfo
from .table_utils import table_linear, table2df


def process_mmqa_tables(tables_data: List[Dict[str, Any]]) -> List[TableInfo]:
    """
    Process MMQA tables data into TableInfo objects.

    Args:
        tables_data: List of table dictionaries from MMQA dataset

    Returns:
        List of processed TableInfo objects
    """
    processed_tables = []

    for i, table_data in enumerate(tables_data):
        # Extract table information
        name = table_data.get("table_name", f"table_{i}")
        columns = table_data["table_columns"]
        content = table_data["table_content"]

        # Create table rows (header + content)
        table_rows = [columns] + content

        # Generate DataFrame code
        df_code = table2df(table_rows)

        # Generate linear representation
        linear_rep = table_linear(table_rows, num_row=None)

        table_info = TableInfo(
            name=name,
            columns=columns,
            content=content,
            df_code=df_code,
            linear_representation=linear_rep
        )

        processed_tables.append(table_info)

    return processed_tables


def create_mmqa_context(
    table_names: List[str],
    foreign_keys: List[str] = None,
    primary_keys: List[str] = None
) -> str:
    """
    Create context string from MMQA metadata.

    Args:
        table_names: Names of the tables
        foreign_keys: Foreign key relationships
        primary_keys: Primary key information

    Returns:
        Formatted context string
    """
    context_parts = []

    if table_names:
        context_parts.append(f"Tables: {', '.join(table_names)}")

    if foreign_keys:
        context_parts.append(f"Foreign Keys: {', '.join(foreign_keys)}")

    if primary_keys:
        context_parts.append(f"Primary Keys: {', '.join(primary_keys)}")

    return " | ".join(context_parts)


def combine_tables_for_qa(tables: List[TableInfo]) -> Tuple[str, List[List[Any]]]:
    """
    Combine multiple tables into a single representation for QA.

    Args:
        tables: List of TableInfo objects

    Returns:
        Tuple of (combined_text_representation, combined_table_data)
    """
    if len(tables) == 1:
        return tables[0].linear_representation, [tables[0].columns] + tables[0].content

    # For multi-table cases, create a combined representation
    combined_text = "Multi-table dataset:\n\n"
    all_table_data = []

    for i, table in enumerate(tables):
        combined_text += f"Table {i+1} ({table.name}):\n"
        combined_text += table.linear_representation + "\n\n"

        # Keep table data separate for now
        table_data = [table.columns] + table.content
        all_table_data.extend(table_data)

    return combined_text.strip(), all_table_data


def extract_mmqa_answer(item: Dict[str, Any]) -> str:
    """
    Extract answer from MMQA item in consistent format.

    Args:
        item: MMQA dataset item

    Returns:
        Standardized answer string
    """
    answer = item.get('answer', '')

    if isinstance(answer, list):
        if len(answer) > 0:
            answer = answer[0]
        else:
            answer = ''

    return str(answer).strip()


def format_mmqa_item_for_processing(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format MMQA item for processing by MACT graph.

    Args:
        item: Raw MMQA dataset item

    Returns:
        Formatted item ready for processing
    """
    # Process tables
    tables = process_mmqa_tables(item['tables'])

    # Extract metadata
    table_names = item.get('table_names', [f"table_{i}" for i in range(len(tables))])
    foreign_keys = item.get('foreign_keys', [])
    primary_keys = item.get('primary_keys', [])

    # Create context
    context = create_mmqa_context(table_names, foreign_keys, primary_keys)

    # Get answer
    answer = extract_mmqa_answer(item)

    return {
        'id': item.get('id_', item.get('id', 0)),
        'question': item['Question'],
        'tables': [table.to_dict() for table in tables],
        'table_names': table_names,
        'foreign_keys': foreign_keys,
        'primary_keys': primary_keys,
        'context': context,
        'answer': answer,
        'sql': item.get('SQL', ''),  # Reference SQL (not used in execution)
        'original_item': item
    }


def create_mmqa_config(
    plan_model: str = "gpt-3.5-turbo",
    code_model: str = "gpt-3.5-turbo",
    reward_type: str = "consistency",
    plan_sample: int = 5,
    code_sample: int = 5,
    max_steps: int = 6,
    **kwargs
) -> Dict[str, Any]:
    """
    Create configuration for MMQA processing.

    Args:
        plan_model: Model for planning
        code_model: Model for code generation
        reward_type: Type of reward function
        plan_sample: Number of planning samples
        code_sample: Number of code samples
        max_steps: Maximum reasoning steps
        **kwargs: Additional configuration options

    Returns:
        Configuration dictionary
    """
    config = {
        'plan_model': plan_model,
        'code_model': code_model,
        'reward_type': reward_type,
        'plan_sample': plan_sample,
        'code_sample': code_sample,
        'max_steps': max_steps,
        'max_actual_steps': kwargs.get('max_actual_steps', max_steps),
        'use_pre_answer': kwargs.get('use_pre_answer', True),
        'answer_threshold': kwargs.get('answer_threshold', 1.0),
        'long_table_op': kwargs.get('long_table_op', 'ignore'),
        'code_as_observation': kwargs.get('code_as_observation', False),
        'without_tool': kwargs.get('without_tool', False)
    }

    return config


def validate_mmqa_item(item: Dict[str, Any]) -> bool:
    """
    Validate that an MMQA item has required fields.

    Args:
        item: MMQA dataset item

    Returns:
        True if item is valid, False otherwise
    """
    required_fields = ['Question', 'tables']

    for field in required_fields:
        if field not in item:
            return False

    # Validate tables structure
    if not isinstance(item['tables'], list):
        return False

    for table in item['tables']:
        if not isinstance(table, dict):
            return False
        if 'table_columns' not in table or 'table_content' not in table:
            return False

    return True


def load_mmqa_dataset(file_path: str) -> List[Dict[str, Any]]:
    """
    Load MMQA dataset from file.

    Args:
        file_path: Path to MMQA dataset file

    Returns:
        List of validated MMQA items
    """
    import json

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_path.endswith('.jsonl'):
                # JSONL format
                dataset = [json.loads(line) for line in f]
            else:
                # JSON format
                dataset = json.load(f)

        # Validate items
        valid_items = []
        for item in dataset:
            if validate_mmqa_item(item):
                valid_items.append(item)
            else:
                print(f"Skipping invalid item: {item.get('id_', 'unknown')}")

        return valid_items

    except Exception as e:
        print(f"Error loading MMQA dataset from {file_path}: {e}")
        return []


def calculate_mmqa_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate evaluation metrics for MMQA results.

    Args:
        results: List of result dictionaries

    Returns:
        Dictionary with calculated metrics
    """
    from .table_utils import exact_match

    if not results:
        return {"exact_match": 0.0, "total": 0, "correct": 0}

    correct = 0
    total = len(results)

    for result in results:
        predicted = str(result.get("predicted", "")).strip()
        target = str(result.get("target", "")).strip()

        if exact_match(predicted, target):
            correct += 1

    exact_match_score = correct / total if total > 0 else 0.0

    return {
        "exact_match": exact_match_score,
        "correct": correct,
        "total": total,
        "accuracy": exact_match_score
    }