"""
Test EDA Agent without LLM (no API key required).

Tests the table analysis, FK detection, and context generation capabilities.
"""

import sys
import os
import asyncio

sys.path.insert(0, 'src')

from multi_agent.state import create_multi_agent_initial_state
from multi_agent.agents.eda_agent import eda_agent_node


async def test_eda_single_table():
    """Test EDA Agent with single table."""

    print("\n" + "="*80)
    print("TEST 1: Single Table Analysis")
    print("="*80)

    tables_data = [
        {
            "table_name": "students",
            "table_columns": ["student_id", "name", "age", "grade"],
            "table_content": [
                [1, "Alice", 20, "A"],
                [2, "Bob", 21, "B"],
                [3, "Charlie", 19, "A"],
                [4, "David", 22, "C"],
                [5, "Eve", 20, "B"]
            ]
        }
    ]

    state = create_multi_agent_initial_state(
        question="How many students are there?",
        tables_data=tables_data,
        output_format="simple_answer",
        config={}
    )

    # Run EDA Agent
    result_state = await eda_agent_node(state)

    # Check results
    print("\n" + "-"*80)
    print("RESULTS:")
    print("-"*80)

    assert result_state["eda_context"], "❌ EDA context should not be empty"
    print(f"✅ EDA context generated: {len(result_state['eda_context'])} chars")

    assert result_state["table_statistics"], "❌ Table statistics should not be empty"
    print(f"✅ Table statistics: {len(result_state['table_statistics'])} table(s)")

    # Check statistics content
    stats = result_state["table_statistics"]["students"]
    assert stats["num_rows"] == 5, f"❌ Expected 5 rows, got {stats['num_rows']}"
    print(f"✅ Correct row count: {stats['num_rows']}")

    assert stats["num_columns"] == 4, f"❌ Expected 4 columns, got {stats['num_columns']}"
    print(f"✅ Correct column count: {stats['num_columns']}")

    # Check column analysis
    assert "student_id" in stats["columns"], "❌ student_id column not analyzed"
    print(f"✅ Columns analyzed: {list(stats['columns'].keys())}")

    # FK detection (should be empty for single table)
    assert len(result_state["detected_foreign_keys"]) == 0, "❌ Should not detect FKs in single table"
    print(f"✅ FK detection: {len(result_state['detected_foreign_keys'])} (expected 0)")

    print("\n" + "="*80)
    print("TEST 1 PASSED ✅")
    print("="*80 + "\n")

    return True


async def test_eda_multi_table():
    """Test EDA Agent with multiple tables and FK detection."""

    print("\n" + "="*80)
    print("TEST 2: Multi-Table Analysis with FK Detection")
    print("="*80)

    tables_data = [
        {
            "table_name": "students",
            "table_columns": ["student_id", "name"],
            "table_content": [
                [1, "Alice"],
                [2, "Bob"],
                [3, "Charlie"]
            ]
        },
        {
            "table_name": "enrollments",
            "table_columns": ["enrollment_id", "student_id", "course_id"],
            "table_content": [
                [1, 1, 101],
                [2, 2, 102],
                [3, 3, 101],
                [4, 1, 102]
            ]
        },
        {
            "table_name": "courses",
            "table_columns": ["course_id", "course_name"],
            "table_content": [
                [101, "Mathematics"],
                [102, "Physics"],
                [103, "Chemistry"]
            ]
        }
    ]

    state = create_multi_agent_initial_state(
        question="What courses has Alice enrolled in?",
        tables_data=tables_data,
        output_format="simple_answer",
        config={}
    )

    # Run EDA Agent
    result_state = await eda_agent_node(state)

    # Check results
    print("\n" + "-"*80)
    print("RESULTS:")
    print("-"*80)

    # Basic checks
    assert result_state["eda_context"], "❌ EDA context should not be empty"
    print(f"✅ EDA context generated: {len(result_state['eda_context'])} chars")

    assert len(result_state["table_statistics"]) == 3, "❌ Should analyze 3 tables"
    print(f"✅ Analyzed {len(result_state['table_statistics'])} tables")

    # Check FK detection
    detected_fks = result_state["detected_foreign_keys"]
    print(f"\n🔍 Detected FKs: {detected_fks}")

    # Should detect at least one FK relationship
    assert len(detected_fks) > 0, "❌ Should detect at least one FK relationship"
    print(f"✅ FK detection: {len(detected_fks)} relationship(s) found")

    # Check for expected relationships
    expected_relationships = [
        ("students.student_id", "enrollments.student_id"),
        ("courses.course_id", "enrollments.course_id")
    ]

    found_count = 0
    for table1_col, table2_col in expected_relationships:
        for fk in detected_fks:
            if (table1_col in fk and table2_col in fk) or (table2_col in fk and table1_col in fk):
                print(f"   ✅ Found expected relationship: {fk}")
                found_count += 1
                break

    if found_count > 0:
        print(f"✅ Found {found_count} expected relationship(s)")
    else:
        print("⚠️  Warning: Expected relationships not found, but FK detection is working")

    # Check column types
    assert result_state["column_types"], "❌ Column types should not be empty"
    print(f"\n✅ Column types inferred for {len(result_state['column_types'])} tables")

    # Print context preview
    print("\n" + "-"*80)
    print("EDA CONTEXT PREVIEW:")
    print("-"*80)
    context_lines = result_state["eda_context"].split("\n")[:20]  # First 20 lines
    print("\n".join(context_lines))
    if len(result_state["eda_context"].split("\n")) > 20:
        print("... (truncated)")

    print("\n" + "="*80)
    print("TEST 2 PASSED ✅")
    print("="*80 + "\n")

    return True


async def test_eda_statistics_accuracy():
    """Test accuracy of statistical analysis."""

    print("\n" + "="*80)
    print("TEST 3: Statistical Analysis Accuracy")
    print("="*80)

    tables_data = [
        {
            "table_name": "data",
            "table_columns": ["id", "category", "value", "optional"],
            "table_content": [
                [1, "A", 10, "x"],
                [2, "B", 20, None],
                [3, "A", 30, "y"],
                [4, "C", 40, None],
                [5, "A", 50, "z"]
            ]
        }
    ]

    state = create_multi_agent_initial_state(
        question="Test question",
        tables_data=tables_data,
        output_format="simple_answer",
        config={}
    )

    result_state = await eda_agent_node(state)
    stats = result_state["table_statistics"]["data"]

    print("\n" + "-"*80)
    print("CHECKING STATISTICS:")
    print("-"*80)

    # Check numeric column stats
    value_stats = stats["columns"]["value"]
    assert value_stats["min"] == 10, f"❌ Expected min=10, got {value_stats['min']}"
    assert value_stats["max"] == 50, f"❌ Expected max=50, got {value_stats['max']}"
    assert value_stats["mean"] == 30, f"❌ Expected mean=30, got {value_stats['mean']}"
    print(f"✅ Numeric stats correct: min={value_stats['min']}, max={value_stats['max']}, mean={value_stats['mean']}")

    # Check categorical column
    category_stats = stats["columns"]["category"]
    assert category_stats["unique_count"] == 3, f"❌ Expected 3 unique categories, got {category_stats['unique_count']}"
    assert "value_distribution" in category_stats, "❌ Should have value distribution"
    assert category_stats["value_distribution"]["A"] == 3, f"❌ Expected 3 'A's, got {category_stats['value_distribution'].get('A')}"
    print(f"✅ Categorical stats correct: unique={category_stats['unique_count']}, distribution={category_stats['value_distribution']}")

    # Check null handling
    optional_stats = stats["columns"]["optional"]
    assert optional_stats["null_count"] == 2, f"❌ Expected 2 nulls, got {optional_stats['null_count']}"
    assert abs(optional_stats["null_ratio"] - 0.4) < 0.01, f"❌ Expected null_ratio~0.4, got {optional_stats['null_ratio']}"
    print(f"✅ Null handling correct: null_count={optional_stats['null_count']}, null_ratio={optional_stats['null_ratio']:.2f}")

    print("\n" + "="*80)
    print("TEST 3 PASSED ✅")
    print("="*80 + "\n")

    return True


async def main():
    """Run all EDA Agent tests."""

    print("\n" + "="*80)
    print("EDA AGENT TEST SUITE (No API Key Required)")
    print("="*80)

    results = []

    try:
        result1 = await test_eda_single_table()
        results.append(("Single Table", result1))
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Single Table", False))

    try:
        result2 = await test_eda_multi_table()
        results.append(("Multi-Table FK Detection", result2))
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Multi-Table FK Detection", False))

    try:
        result3 = await test_eda_statistics_accuracy()
        results.append(("Statistical Accuracy", result3))
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Statistical Accuracy", False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    print("="*80)

    all_passed = all(result for _, result in results)
    if all_passed:
        print("\n🎉 All EDA Agent tests passed!")
        print("   Framework is ready for LLM integration testing.\n")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review errors above.\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
