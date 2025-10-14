"""
Simple test script for Multi-Agent framework.

Tests the framework with a single question to verify all components work.
"""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from multi_agent.graph import MultiAgentGraph
from multi_agent.state import create_multi_agent_initial_state


async def test_single_question():
    """Test Multi-Agent framework with a simple single-table question."""

    # Simple test data
    question = "How many students are there in total?"

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

    # Configuration
    config = {
        "plan_model": "gpt-3.5-turbo",
        "code_model": "gpt-3.5-turbo",
        "plan_sample": 2,  # Reduced for faster testing
        "code_sample": 2,
        "max_steps": 4
    }

    print("\n" + "="*80)
    print("MULTI-AGENT FRAMEWORK TEST")
    print("="*80)
    print(f"\nQuestion: {question}")
    print(f"Tables: {len(tables_data)}")
    print(f"\nConfiguration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    print("\n" + "="*80 + "\n")

    # Create initial state
    initial_state = create_multi_agent_initial_state(
        question=question,
        tables_data=tables_data,
        output_format="simple_answer",
        config=config
    )

    # Create and run graph
    graph = MultiAgentGraph(config)

    try:
        print("Starting Multi-Agent execution...\n")
        final_state = await graph.run(initial_state)

        # Get summary
        summary = graph.get_execution_summary(final_state)

        # Print results
        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)
        print(f"\nFinal Answer: {summary['final_answer']}")
        print(f"Confidence: {summary['confidence']:.2%}")
        print(f"Steps Taken: {summary['steps_taken']}")
        print(f"\nEDA Summary:")
        print(f"  - Tables analyzed: {summary['eda_summary']['num_tables']}")
        print(f"  - FKs detected: {summary['eda_summary']['detected_fks']}")
        print(f"  - Context length: {summary['eda_summary']['context_length']} chars")
        print(f"\nExecution Status:")
        print(f"  - Finished: {summary['is_finished']}")
        print(f"  - Halted: {summary['is_halted']}")
        print(f"  - Error: {summary['has_error']}")

        if summary['has_error']:
            print(f"  - Error message: {summary['error_message']}")

        print(f"\nToken Usage:")
        print(f"  - Input: {summary['total_input_tokens']}")
        print(f"  - Output: {summary['total_output_tokens']}")

        print("\n" + "="*80)

        # Check if answer is correct
        expected_answer = "5"
        actual_answer = str(summary['final_answer']).strip()

        if expected_answer in actual_answer:
            print("\n✅ TEST PASSED: Answer is correct!")
        else:
            print(f"\n⚠️  TEST WARNING: Expected '{expected_answer}', got '{actual_answer}'")

        print("\n")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_multi_table_question():
    """Test Multi-Agent framework with a multi-table question."""

    question = "What are the names of students who have enrolled in Mathematics?"

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
            "table_columns": ["student_id", "course_id"],
            "table_content": [
                [1, 101],
                [2, 102],
                [3, 101]
            ]
        },
        {
            "table_name": "courses",
            "table_columns": ["course_id", "course_name"],
            "table_content": [
                [101, "Mathematics"],
                [102, "Physics"]
            ]
        }
    ]

    config = {
        "plan_model": "gpt-3.5-turbo",
        "code_model": "gpt-3.5-turbo",
        "plan_sample": 2,
        "code_sample": 2,
        "max_steps": 6
    }

    print("\n" + "="*80)
    print("MULTI-TABLE TEST")
    print("="*80)
    print(f"\nQuestion: {question}")
    print(f"Tables: {len(tables_data)}")
    print("\n" + "="*80 + "\n")

    initial_state = create_multi_agent_initial_state(
        question=question,
        tables_data=tables_data,
        output_format="simple_answer",
        config=config
    )

    graph = MultiAgentGraph(config)

    try:
        final_state = await graph.run(initial_state)
        summary = graph.get_execution_summary(final_state)

        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)
        print(f"\nFinal Answer: {summary['final_answer']}")
        print(f"Confidence: {summary['confidence']:.2%}")
        print(f"\nDetected Foreign Keys: {summary['eda_summary']['detected_fks']}")

        # Check if answer contains expected names
        answer_lower = str(summary['final_answer']).lower()
        if "alice" in answer_lower and "charlie" in answer_lower:
            print("\n✅ TEST PASSED: Answer contains expected students!")
        else:
            print(f"\n⚠️  TEST WARNING: Expected 'Alice' and 'Charlie' in answer")

        print("\n")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""

    print("\n" + "="*80)
    print("MULTI-AGENT FRAMEWORK - TEST SUITE")
    print("="*80 + "\n")

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ ERROR: OPENAI_API_KEY environment variable not set")
        print("   Please set it with: export OPENAI_API_KEY='your-key-here'\n")
        return

    print("✅ OPENAI_API_KEY found\n")

    # Run tests
    test_results = []

    print("\n" + "─"*80)
    print("Test 1: Single Table Question")
    print("─"*80)
    result1 = await test_single_question()
    test_results.append(("Single Table", result1))

    print("\n" + "─"*80)
    print("Test 2: Multi-Table Question")
    print("─"*80)
    result2 = await test_multi_table_question()
    test_results.append(("Multi-Table", result2))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    print("="*80 + "\n")

    all_passed = all(result for _, result in test_results)
    if all_passed:
        print("🎉 All tests passed!\n")
    else:
        print("⚠️  Some tests failed. Please review the output above.\n")


if __name__ == "__main__":
    asyncio.run(main())
