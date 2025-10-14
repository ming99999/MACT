"""
MMQA Subtask Extraction Utilities

This module provides functions to extract MMQA subtask outputs (SQL, FK, PK) from
the reasoning history generated during answer generation.

Author: MACT LangGraph Team
Date: 2025-10-11
"""

from typing import List, Dict, Any, Optional
import re
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


async def extract_sql_from_history(
    question: str,
    history: List[Dict],
    tables_info: List[Dict],
    llm_model: str,
    openai_client: Optional[AsyncOpenAI] = None
) -> str:
    """
    Extract SQL query from reasoning history using LLM.

    This function analyzes the step history and generated pandas code to reconstruct
    the equivalent SQL query that would answer the question.

    Args:
        question: The original question
        history: List of step history dictionaries with actions and observations
        tables_info: List of table information dictionaries
        llm_model: Model name to use for extraction
        openai_client: OpenAI client instance (optional, will create if not provided)

    Returns:
        Predicted SQL query string
    """
    if openai_client is None:
        openai_client = AsyncOpenAI()

    # Extract pandas operations from history
    pandas_operations = []
    for step in history:
        if 'action' in step and step.get('action_type') == 'Operator':
            code = step.get('code', '')
            if code and any(op in code for op in ['merge', 'join', 'groupby', 'filter', 'sort_values']):
                pandas_operations.append(code)

    # Build table schema summary
    table_schemas = []
    for table in tables_info:
        cols = table.get('columns', [])
        table_name = table.get('name', 'table')
        table_schemas.append(f"{table_name}: {', '.join(cols)}")

    # Create prompt for SQL extraction
    prompt = f"""Given a question and the pandas operations used to answer it, generate the equivalent SQL query.

Question: {question}

Table Schemas:
{chr(10).join(table_schemas)}

Pandas Operations:
{chr(10).join(pandas_operations[:5])}  # Limit to first 5 operations

Generate a single SQL query that answers the question. The SQL should:
1. Use proper JOIN syntax for multi-table queries
2. Include WHERE clauses for filtering
3. Use GROUP BY for aggregations
4. Use ORDER BY and LIMIT as needed
5. Be syntactically correct and executable

Return ONLY the SQL query, no explanation.
"""

    try:
        response = await openai_client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": "You are an expert at converting pandas operations to SQL queries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=500
        )

        sql = response.choices[0].message.content.strip()

        # Clean up SQL - remove markdown code blocks if present
        sql = re.sub(r'^```sql\s*', '', sql)
        sql = re.sub(r'^```\s*', '', sql)
        sql = re.sub(r'\s*```$', '', sql)
        sql = sql.strip()

        logger.info(f"Extracted SQL: {sql[:100]}...")
        return sql

    except Exception as e:
        logger.error(f"Error extracting SQL: {e}")
        return "SELECT * FROM table;"  # Fallback


async def extract_foreign_keys_from_history(
    history: List[Dict],
    tables_info: List[Dict],
    llm_model: str,
    openai_client: Optional[AsyncOpenAI] = None
) -> List[str]:
    """
    Extract predicted foreign keys from reasoning history.

    This function combines rule-based extraction of JOIN/merge operations with
    LLM validation to predict foreign key relationships.

    Args:
        history: List of step history dictionaries
        tables_info: List of table information dictionaries
        llm_model: Model name to use for validation
        openai_client: OpenAI client instance (optional)

    Returns:
        List of predicted foreign key relationships in format "table1.col1 = table2.col2"
    """
    if openai_client is None:
        openai_client = AsyncOpenAI()

    # Step 1: Extract FK candidates from JOIN/merge operations (rule-based)
    fk_candidates = []

    for step in history:
        if 'action' in step and step.get('action_type') == 'Operator':
            code = step.get('code', '')

            # Look for merge operations
            merge_patterns = [
                r"merge\([^,]+,\s*[^,]+,\s*(?:left_on|right_on|on)=['\"]([^'\"]+)['\"]",
                r"join\([^,]+,\s*(?:on|lsuffix|rsuffix)=['\"]([^'\"]+)['\"]"
            ]

            for pattern in merge_patterns:
                matches = re.findall(pattern, code)
                fk_candidates.extend(matches)

    # Remove duplicates
    fk_candidates = list(set(fk_candidates))

    if not fk_candidates:
        logger.info("No FK candidates found in history")
        return []

    # Step 2: Use LLM to validate and format FK relationships
    table_schemas = []
    for table in tables_info:
        cols = table.get('columns', [])
        table_name = table.get('name', 'table')
        table_schemas.append(f"{table_name}: {', '.join(cols)}")

    prompt = f"""Given table schemas and candidate join columns, identify the foreign key column names.

Table Schemas:
{chr(10).join(table_schemas)}

Candidate Join Columns:
{chr(10).join(fk_candidates)}

IMPORTANT: Return ONLY the column names that are foreign keys, one per line.
Format: Use lowercase with spaces instead of underscores (e.g., "department id" not "department_id").
Do NOT include table names or equals signs. Just the column names.
Examples: "head id", "department id", "employee id"
"""

    try:
        response = await openai_client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": "You are a database schema expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=300
        )

        fks_text = response.choices[0].message.content.strip()
        # Extract column names, convert underscores to spaces, make lowercase
        fks = []
        for line in fks_text.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                # Remove any table prefixes (table.column -> column)
                if '.' in line:
                    line = line.split('.')[-1]
                # Remove any = signs and take first part
                if '=' in line:
                    line = line.split('=')[0].strip()
                # Convert underscore to space and lowercase
                line = line.replace('_', ' ').lower().strip()
                if line:
                    fks.append(line)

        # Remove duplicates while preserving order
        seen = set()
        fks = [x for x in fks if not (x in seen or seen.add(x))]

        logger.info(f"Extracted {len(fks)} foreign keys: {fks}")
        return fks

    except Exception as e:
        logger.error(f"Error extracting foreign keys: {e}")
        return []


async def extract_primary_keys_from_tables(
    tables_info: List[Dict],
    history: List[Dict],
    llm_model: str,
    openai_client: Optional[AsyncOpenAI] = None
) -> List[str]:
    """
    Predict primary keys from table structure and usage patterns.

    This function uses both heuristics (column names ending in '_id', 'id', etc.)
    and LLM analysis of table structure to predict primary keys.

    Args:
        tables_info: List of table information dictionaries
        history: List of step history for context
        llm_model: Model name to use for prediction
        openai_client: OpenAI client instance (optional)

    Returns:
        List of predicted primary keys in format "table.column"
    """
    if openai_client is None:
        openai_client = AsyncOpenAI()

    # Step 1: Rule-based heuristics for PK candidates
    pk_candidates = []

    for table in tables_info:
        table_name = table.get('name', 'table')
        columns = table.get('columns', [])

        # Look for common PK patterns
        for col in columns:
            col_lower = col.lower()
            if (col_lower == 'id' or
                col_lower.endswith('_id') or
                col_lower == f"{table_name.lower()}_id" or
                col_lower == 'pk'):
                pk_candidates.append(f"{table_name}.{col}")

    if not pk_candidates:
        logger.info("No PK candidates found via heuristics")
        # Fall back to first column of each table
        for table in tables_info:
            table_name = table.get('name', 'table')
            columns = table.get('columns', [])
            if columns:
                pk_candidates.append(f"{table_name}.{columns[0]}")

    # Step 2: Use LLM to validate PK candidates
    table_schemas = []
    for table in tables_info:
        cols = table.get('columns', [])
        table_name = table.get('name', 'table')
        table_schemas.append(f"{table_name}: {', '.join(cols)}")

    prompt = f"""Given table schemas and primary key candidates, identify which column names are actually primary keys.

Table Schemas:
{chr(10).join(table_schemas)}

Primary Key Candidates:
{chr(10).join(pk_candidates)}

IMPORTANT: Return ONLY the column names that are primary keys, one per line.
Format: Use lowercase with spaces instead of underscores (e.g., "department id" not "department_id").
Do NOT include table names or dots. Just the column names.
Examples: "department id", "head id", "employee id"
"""

    try:
        response = await openai_client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": "You are a database schema expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=200
        )

        pks_text = response.choices[0].message.content.strip()
        # Extract column names, convert underscores to spaces, make lowercase
        pks = []
        for line in pks_text.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                # Remove any table prefixes (table.column -> column)
                if '.' in line:
                    line = line.split('.')[-1]
                # Convert underscore to space and lowercase
                line = line.replace('_', ' ').lower().strip()
                if line:
                    pks.append(line)

        # Remove duplicates while preserving order
        seen = set()
        pks = [x for x in pks if not (x in seen or seen.add(x))]

        logger.info(f"Extracted {len(pks)} primary keys: {pks}")
        return pks

    except Exception as e:
        logger.error(f"Error extracting primary keys: {e}")
        # Fall back to candidates, but convert format
        fallback_pks = []
        for pk in pk_candidates:
            if '.' in pk:
                col = pk.split('.')[-1]
            else:
                col = pk
            col = col.replace('_', ' ').lower()
            fallback_pks.append(col)
        return fallback_pks


def extract_pandas_to_sql_hints(code: str) -> Dict[str, Any]:
    """
    Helper function to extract SQL operation hints from pandas code.

    Args:
        code: Pandas code string

    Returns:
        Dictionary with SQL operation hints (joins, filters, aggregations)
    """
    hints = {
        'joins': [],
        'filters': [],
        'aggregations': [],
        'sort': None,
        'limit': None
    }

    # Extract merge/join operations
    merge_pattern = r"merge\(([^)]+)\)"
    merges = re.findall(merge_pattern, code)
    hints['joins'].extend(merges)

    # Extract filtering operations
    filter_pattern = r"\[([^\]]+[<>=!]+[^\]]+)\]"
    filters = re.findall(filter_pattern, code)
    hints['filters'].extend(filters)

    # Extract groupby operations
    groupby_pattern = r"groupby\(['\"]([^'\"]+)['\"]\)"
    groupbys = re.findall(groupby_pattern, code)
    if groupbys:
        hints['aggregations'].append(f"GROUP BY {', '.join(groupbys)}")

    # Extract sort operations
    sort_pattern = r"sort_values\(['\"]([^'\"]+)['\"]\)"
    sorts = re.findall(sort_pattern, code)
    if sorts:
        hints['sort'] = sorts[0]

    # Extract head/limit operations
    head_pattern = r"\.head\((\d+)\)"
    heads = re.findall(head_pattern, code)
    if heads:
        hints['limit'] = int(heads[0])

    return hints
