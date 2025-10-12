"""
MMQA Subtask Generation Nodes

This module provides LangGraph nodes for generating MMQA subtask outputs
(SQL, FK, PK) after answer generation is complete.

Author: MACT LangGraph Team
Date: 2025-10-11
"""

from typing import Dict, Any
import logging
from openai import AsyncOpenAI

from ..state import MACTState
from ..utils.subtask_extraction import (
    extract_sql_from_history,
    extract_foreign_keys_from_history,
    extract_primary_keys_from_tables
)

logger = logging.getLogger(__name__)


async def subtask_generation_node(state: MACTState) -> Dict[str, Any]:
    """
    Generate SQL, FK, and PK predictions after answer is determined.

    This node runs AFTER the answer has been finalized and leverages the rich
    reasoning history accumulated during answer generation to extract the other
    MMQA subtask outputs.

    Args:
        state: Current MACT state with completed answer generation

    Returns:
        Updated state with predicted_sql, predicted_foreign_keys, predicted_primary_keys
    """
    print("\n" + "="*80)
    print("SUBTASK GENERATION NODE - ENTRY POINT")
    print("="*80)
    logger.info("=== Subtask Generation Node ===")

    # Get configuration
    config = state.get('config', {})
    code_model = config.get('code_model', 'gpt-3.5-turbo')

    # Create OpenAI client
    openai_client = AsyncOpenAI()

    try:
        # Extract question and tables
        question = state['question']
        tables = state['tables']
        step_history = state.get('step_history', [])

        print(f"DEBUG - Question: {question[:100]}...")
        print(f"DEBUG - Number of tables: {len(tables)}")
        print(f"DEBUG - Step history length: {len(step_history)}")
        print(f"DEBUG - Using model: {code_model}")

        logger.info(f"Extracting subtasks for question: {question[:80]}...")

        # Generate SQL query
        print("\n--- Starting SQL Extraction ---")
        logger.info("Extracting SQL from history...")
        predicted_sql = await extract_sql_from_history(
            question=question,
            history=step_history,
            tables_info=tables,
            llm_model=code_model,
            openai_client=openai_client
        )
        print(f"DEBUG - Extracted SQL ({len(predicted_sql)} chars): {predicted_sql[:150]}...")

        # Generate foreign keys
        print("\n--- Starting FK Extraction ---")
        logger.info("Extracting foreign keys from history...")
        predicted_fks = await extract_foreign_keys_from_history(
            history=step_history,
            tables_info=tables,
            llm_model=code_model,
            openai_client=openai_client
        )
        print(f"DEBUG - Extracted FKs ({len(predicted_fks)} total): {predicted_fks}")

        # Generate primary keys
        print("\n--- Starting PK Extraction ---")
        logger.info("Extracting primary keys from tables...")
        predicted_pks = await extract_primary_keys_from_tables(
            tables_info=tables,
            history=step_history,
            llm_model=code_model,
            openai_client=openai_client
        )
        print(f"DEBUG - Extracted PKs ({len(predicted_pks)} total): {predicted_pks}")

        logger.info(f"Subtask extraction complete: SQL={len(predicted_sql)} chars, "
                   f"FKs={len(predicted_fks)}, PKs={len(predicted_pks)}")

        result = {
            'predicted_sql': predicted_sql,
            'predicted_foreign_keys': predicted_fks,
            'predicted_primary_keys': predicted_pks
        }

        print("\n--- Subtask Generation Results ---")
        print(f"Returning: {result}")
        print("="*80 + "\n")

        # Return updated state
        return result

    except Exception as e:
        print(f"\nERROR in subtask_generation_node: {e}")
        print(f"Exception type: {type(e)}")
        import traceback
        traceback.print_exc()
        logger.error(f"Error in subtask generation: {e}", exc_info=True)

        # Return empty predictions on error
        error_result = {
            'predicted_sql': '',
            'predicted_foreign_keys': [],
            'predicted_primary_keys': []
        }
        print(f"Returning error result: {error_result}")
        print("="*80 + "\n")
        return error_result


async def validate_subtask_outputs(state: MACTState) -> Dict[str, Any]:
    """
    Validate and post-process subtask outputs for quality.

    This optional node can be used to validate SQL syntax, check FK/PK formats,
    and ensure outputs meet MMQA requirements.

    Args:
        state: Current MACT state with subtask predictions

    Returns:
        Updated state with validated subtask outputs
    """
    logger.info("=== Validating Subtask Outputs ===")

    predicted_sql = state.get('predicted_sql', '')
    predicted_fks = state.get('predicted_foreign_keys', [])
    predicted_pks = state.get('predicted_primary_keys', [])

    # Validate SQL (basic checks)
    if predicted_sql:
        # Check for SQL keywords
        sql_keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'GROUP', 'ORDER']
        has_keywords = any(kw in predicted_sql.upper() for kw in sql_keywords)

        if not has_keywords:
            logger.warning("SQL validation failed: Missing key SQL keywords")
            predicted_sql = ''

    # Validate FK format (should be "table1.col1 = table2.col2")
    validated_fks = []
    for fk in predicted_fks:
        if '=' in fk and '.' in fk:
            parts = fk.split('=')
            if len(parts) == 2 and all('.' in p for p in parts):
                validated_fks.append(fk.strip())
            else:
                logger.warning(f"Invalid FK format: {fk}")
        else:
            logger.warning(f"Invalid FK format: {fk}")

    # Validate PK format (should be "table.column")
    validated_pks = []
    for pk in predicted_pks:
        if '.' in pk:
            parts = pk.split('.')
            if len(parts) == 2:
                validated_pks.append(pk.strip())
            else:
                logger.warning(f"Invalid PK format: {pk}")
        else:
            logger.warning(f"Invalid PK format: {pk}")

    logger.info(f"Validation complete: SQL valid={bool(predicted_sql)}, "
               f"FKs={len(validated_fks)}/{len(predicted_fks)}, "
               f"PKs={len(validated_pks)}/{len(predicted_pks)}")

    return {
        'predicted_sql': predicted_sql,
        'predicted_foreign_keys': validated_fks,
        'predicted_primary_keys': validated_pks
    }
