"""
EDA (Exploratory Data Analysis) Agent

This agent analyzes input tables and generates contextual information to enhance
the reasoning process of subsequent agents.

Capabilities:
1. Table Schema Analysis: column types, null ratios, unique counts
2. Foreign Key Detection: automatic relationship discovery
3. Statistical Profiling: value distributions, ranges, patterns
4. Natural Language Context Generation: human-readable descriptions
"""

import pandas as pd
from typing import Dict, Any, List, Tuple
from collections import Counter
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from mact_langgraph.state import TableInfo, get_tables_from_state
from ..state import MultiAgentState


async def eda_agent_node(state: MultiAgentState) -> MultiAgentState:
    """
    EDA Agent node: Analyze tables and generate enhanced context.

    Args:
        state: Current multi-agent state

    Returns:
        Updated state with EDA outputs populated
    """
    print("\n" + "="*60)
    print("EDA AGENT: Starting table analysis...")
    print("="*60)

    try:
        # Extract tables from state
        tables = get_tables_from_state(state)

        # 1. Analyze table statistics
        print("📊 Step 1: Analyzing table statistics...")
        table_statistics = analyze_table_statistics(tables)

        # 2. Detect foreign key relationships
        print("🔗 Step 2: Detecting foreign key relationships...")
        detected_fks = detect_foreign_keys(tables, table_statistics)

        # 3. Infer column types
        print("🏷️  Step 3: Inferring column types...")
        column_types = infer_column_types(tables, table_statistics)

        # 4. Detect value patterns
        print("📈 Step 4: Detecting value patterns...")
        value_patterns = detect_value_patterns(tables, table_statistics, column_types)

        # 5. Generate natural language context
        print("📝 Step 5: Generating natural language context...")
        eda_context = generate_eda_context(
            state["question"],
            tables,
            table_statistics,
            detected_fks,
            column_types,
            value_patterns
        )

        print("\n✅ EDA Agent completed successfully")
        print(f"   - Analyzed {len(tables)} table(s)")
        print(f"   - Detected {len(detected_fks)} foreign key relationship(s)")
        print(f"   - Generated context: {len(eda_context)} characters")
        print("="*60 + "\n")

        return {
            **state,
            "eda_context": eda_context,
            "table_statistics": table_statistics,
            "detected_foreign_keys": detected_fks,
            "column_types": column_types,
            "value_patterns": value_patterns,
            "execution_log": state["execution_log"] + [
                f"EDA Agent: Analyzed {len(tables)} tables, detected {len(detected_fks)} FK relationships"
            ]
        }

    except Exception as e:
        print(f"\n❌ EDA Agent error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            **state,
            "eda_context": f"Error during EDA analysis: {str(e)}",
            "table_statistics": {},
            "detected_foreign_keys": [],
            "column_types": {},
            "value_patterns": {},
            "execution_log": state["execution_log"] + [f"EDA Agent: Error - {str(e)}"]
        }


def analyze_table_statistics(tables: List[TableInfo]) -> Dict[str, Any]:
    """
    Analyze statistical properties of tables.

    Args:
        tables: List of TableInfo objects

    Returns:
        Dictionary of statistics per table
    """
    statistics = {}

    for table in tables:
        # Convert to DataFrame for analysis
        df = pd.DataFrame(table.content, columns=table.columns)

        table_stats = {
            "num_rows": len(df),
            "num_columns": len(df.columns),
            "columns": {}
        }

        # Analyze each column
        for col in df.columns:
            col_stats = {
                "type": str(df[col].dtype),
                "null_count": int(df[col].isna().sum()),
                "null_ratio": float(df[col].isna().sum() / len(df)) if len(df) > 0 else 0.0,
                "unique_count": int(df[col].nunique()),
                "sample_values": df[col].dropna().head(3).tolist()
            }

            # For categorical-like columns, get value distribution
            if col_stats["unique_count"] <= 20 and col_stats["unique_count"] > 0:
                value_counts = df[col].value_counts().head(10).to_dict()
                col_stats["value_distribution"] = {str(k): int(v) for k, v in value_counts.items()}

            # For numeric columns, get range
            if pd.api.types.is_numeric_dtype(df[col]):
                col_stats["min"] = float(df[col].min()) if not df[col].isna().all() else None
                col_stats["max"] = float(df[col].max()) if not df[col].isna().all() else None
                col_stats["mean"] = float(df[col].mean()) if not df[col].isna().all() else None

            table_stats["columns"][col] = col_stats

        statistics[table.name] = table_stats

    return statistics


def detect_foreign_keys(
    tables: List[TableInfo],
    statistics: Dict[str, Any]
) -> List[str]:
    """
    Detect potential foreign key relationships between tables.

    Uses heuristics:
    1. Column name similarity (exact match or with _id suffix)
    2. Value overlap analysis
    3. Cardinality checks (FK should have values that exist in PK)

    Args:
        tables: List of TableInfo objects
        statistics: Table statistics from analyze_table_statistics

    Returns:
        List of FK relationships in format "table1.col1 = table2.col2"
    """
    detected_fks = []

    # Only meaningful if we have multiple tables
    if len(tables) < 2:
        return detected_fks

    # Convert tables to DataFrames
    dfs = {}
    for table in tables:
        dfs[table.name] = pd.DataFrame(table.content, columns=table.columns)

    # Compare each pair of tables
    for i, table1 in enumerate(tables):
        for j, table2 in enumerate(tables):
            if i >= j:  # Skip self-comparison and duplicates
                continue

            df1 = dfs[table1.name]
            df2 = dfs[table2.name]

            # Check each column pair
            for col1 in df1.columns:
                for col2 in df2.columns:
                    # Heuristic 1: Column name similarity
                    name_similar = (
                        col1.lower() == col2.lower() or
                        col1.lower() == f"{col2.lower()}_id" or
                        col2.lower() == f"{col1.lower()}_id" or
                        col1.lower().replace("_id", "") == col2.lower().replace("_id", "")
                    )

                    if name_similar:
                        # Heuristic 2: Value overlap
                        values1 = set(df1[col1].dropna().astype(str).values)
                        values2 = set(df2[col2].dropna().astype(str).values)

                        if values1 and values2:
                            overlap = len(values1 & values2)
                            min_size = min(len(values1), len(values2))

                            # If significant overlap (>30%), likely FK
                            if min_size > 0 and overlap / min_size > 0.3:
                                fk_relationship = f"{table1.name}.{col1} = {table2.name}.{col2}"
                                if fk_relationship not in detected_fks:
                                    detected_fks.append(fk_relationship)
                                    print(f"   🔗 Detected FK: {fk_relationship} (overlap: {overlap}/{min_size})")

    return detected_fks


def infer_column_types(
    tables: List[TableInfo],
    statistics: Dict[str, Any]
) -> Dict[str, Dict[str, str]]:
    """
    Infer semantic column types (numeric, categorical, datetime, text).

    Args:
        tables: List of TableInfo objects
        statistics: Table statistics

    Returns:
        Dictionary mapping table.column to semantic type
    """
    column_types = {}

    for table in tables:
        df = pd.DataFrame(table.content, columns=table.columns)
        table_types = {}

        for col in df.columns:
            col_stats = statistics[table.name]["columns"][col]

            # Determine semantic type
            if pd.api.types.is_numeric_dtype(df[col]):
                # Check if it's actually an ID or categorical
                if col_stats["unique_count"] == col_stats["null_count"] + len(df):
                    table_types[col] = "id"  # Unique identifier
                elif col_stats["unique_count"] <= 20:
                    table_types[col] = "categorical_numeric"
                else:
                    table_types[col] = "numeric"

            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                table_types[col] = "datetime"

            else:
                # String type
                if col_stats["unique_count"] <= 20:
                    table_types[col] = "categorical"
                elif col_stats["unique_count"] == len(df):
                    table_types[col] = "id"
                else:
                    table_types[col] = "text"

        column_types[table.name] = table_types

    return column_types


def detect_value_patterns(
    tables: List[TableInfo],
    statistics: Dict[str, Any],
    column_types: Dict[str, Dict[str, str]]
) -> Dict[str, Any]:
    """
    Detect patterns in column values.

    Args:
        tables: List of TableInfo objects
        statistics: Table statistics
        column_types: Column type information

    Returns:
        Dictionary of detected patterns
    """
    patterns = {}

    for table in tables:
        df = pd.DataFrame(table.content, columns=table.columns)
        table_patterns = {}

        for col in df.columns:
            col_type = column_types[table.name][col]
            col_stats = statistics[table.name]["columns"][col]

            if col_type == "numeric" and "min" in col_stats and "max" in col_stats:
                # Numeric range pattern
                table_patterns[col] = {
                    "pattern_type": "numeric_range",
                    "min": col_stats["min"],
                    "max": col_stats["max"],
                    "mean": col_stats.get("mean")
                }

            elif col_type in ["categorical", "categorical_numeric"]:
                # Categorical pattern
                if "value_distribution" in col_stats:
                    table_patterns[col] = {
                        "pattern_type": "categorical",
                        "categories": list(col_stats["value_distribution"].keys()),
                        "num_categories": len(col_stats["value_distribution"])
                    }

        patterns[table.name] = table_patterns

    return patterns


def generate_eda_context(
    question: str,
    tables: List[TableInfo],
    statistics: Dict[str, Any],
    detected_fks: List[str],
    column_types: Dict[str, Dict[str, str]],
    value_patterns: Dict[str, Any]
) -> str:
    """
    Generate natural language context summarizing the EDA analysis.

    This context will be provided to Planning Agent to enhance reasoning.

    Args:
        question: The question being asked
        tables: List of TableInfo objects
        statistics: Table statistics
        detected_fks: Detected foreign key relationships
        column_types: Column types
        value_patterns: Value patterns

    Returns:
        Natural language context string
    """
    context_parts = []

    # 1. Table overview
    context_parts.append("=== Table Overview ===")
    for table_name, stats in statistics.items():
        context_parts.append(
            f"- {table_name}: {stats['num_rows']} rows, {stats['num_columns']} columns"
        )

    # 2. Column descriptions
    context_parts.append("\n=== Column Information ===")
    for table in tables:
        context_parts.append(f"\n{table.name}:")
        stats = statistics[table.name]
        types = column_types[table.name]

        for col in table.columns:
            col_stat = stats["columns"][col]
            col_type = types[col]

            desc_parts = [f"  - {col} ({col_type})"]

            # Add key statistics
            if col_stat["null_ratio"] > 0:
                desc_parts.append(f"{col_stat['null_ratio']*100:.1f}% null")

            if "value_distribution" in col_stat:
                top_values = list(col_stat["value_distribution"].keys())[:3]
                desc_parts.append(f"values: {', '.join(map(str, top_values))}")

            elif "min" in col_stat and "max" in col_stat:
                desc_parts.append(f"range: [{col_stat['min']:.2f}, {col_stat['max']:.2f}]")

            context_parts.append(": ".join(desc_parts) if len(desc_parts) > 1 else desc_parts[0])

    # 3. Relationships
    if detected_fks:
        context_parts.append("\n=== Detected Relationships ===")
        for fk in detected_fks:
            context_parts.append(f"- {fk}")

    # 4. Key insights for the question
    context_parts.append("\n=== Insights for Question ===")
    context_parts.append(f"Question: {question}")

    # Provide guidance based on detected structures
    if len(tables) > 1 and detected_fks:
        context_parts.append("- Multi-table question: JOIN operations likely needed")
        context_parts.append(f"- Use detected relationships: {', '.join(detected_fks)}")
    elif len(tables) == 1:
        context_parts.append("- Single table question: Focus on filtering and aggregation")

    return "\n".join(context_parts)


# TODO: Future enhancement - LLM-based context generation
# async def generate_eda_context_with_llm(
#     question: str,
#     statistics: Dict[str, Any],
#     detected_fks: List[str]
# ) -> str:
#     """
#     Use LLM to generate more sophisticated context.
#     This could provide domain-specific insights and natural language descriptions.
#     """
#     pass
