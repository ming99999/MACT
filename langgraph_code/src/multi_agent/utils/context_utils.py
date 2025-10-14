"""
Context management utilities for Multi-Agent framework.

Handles EDA context formatting and compression for inclusion in prompts.
"""

from typing import Dict, Any, List


def format_eda_context_for_prompt(
    eda_context: str,
    detected_fks: List[str],
    table_statistics: Dict[str, Any],
    max_length: int = 2000
) -> str:
    """
    Format EDA context for inclusion in prompts.

    Args:
        eda_context: Raw EDA context
        detected_fks: Detected foreign keys
        table_statistics: Table statistics
        max_length: Maximum length of formatted context

    Returns:
        Formatted context string suitable for prompt inclusion
    """
    parts = []

    # Add EDA context (truncate if needed)
    if eda_context:
        if len(eda_context) > max_length:
            parts.append(eda_context[:max_length] + "\n... (truncated)")
        else:
            parts.append(eda_context)

    # Add FK summary if available
    if detected_fks:
        parts.append(f"\nKey Relationships: {', '.join(detected_fks)}")

    return "\n".join(parts)


def compress_context(context: str, max_length: int = 1500) -> str:
    """
    Compress context to fit within token limits.

    Strategy:
    1. Keep important sections (table names, relationships)
    2. Summarize or truncate detailed statistics
    3. Remove redundant information

    Args:
        context: Original context
        max_length: Maximum length after compression

    Returns:
        Compressed context
    """
    if len(context) <= max_length:
        return context

    # Split into sections
    lines = context.split("\n")

    # Priority sections (keep these)
    priority_lines = []
    optional_lines = []

    for line in lines:
        # Keep section headers and relationship info
        if any(marker in line for marker in ["===", "Relationships", "Overview", "Insights"]):
            priority_lines.append(line)
        else:
            optional_lines.append(line)

    # Reconstruct with priority first
    result = "\n".join(priority_lines)

    # Add optional lines until we hit the limit
    remaining_space = max_length - len(result)
    for line in optional_lines:
        if len(result) + len(line) + 1 <= max_length:
            result += "\n" + line
        else:
            break

    if len(result) > max_length:
        result = result[:max_length] + "\n... (truncated)"

    return result


def extract_key_statistics(table_statistics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract only the most important statistics for prompt inclusion.

    Args:
        table_statistics: Full table statistics

    Returns:
        Simplified statistics dictionary
    """
    key_stats = {}

    for table_name, stats in table_statistics.items():
        key_stats[table_name] = {
            "num_rows": stats.get("num_rows", 0),
            "num_columns": stats.get("num_columns", 0),
            "key_columns": []
        }

        # Find key columns (low cardinality or likely IDs)
        columns = stats.get("columns", {})
        for col_name, col_stats in columns.items():
            unique_ratio = col_stats.get("unique_count", 0) / max(stats.get("num_rows", 1), 1)

            # Likely ID column (high uniqueness)
            if unique_ratio > 0.9:
                key_stats[table_name]["key_columns"].append(f"{col_name} (ID)")

            # Likely categorical column (low uniqueness)
            elif unique_ratio < 0.1 and col_stats.get("unique_count", 0) > 0:
                key_stats[table_name]["key_columns"].append(f"{col_name} (categorical)")

    return key_stats
