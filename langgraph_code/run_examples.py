"""
Example usage of MACT LangGraph on MMQA dataset.

This script demonstrates how to use the MACT LangGraph implementation
with different configurations and provides sample usage patterns.
"""

import asyncio
import json
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mact_langgraph.graph import MACTGraph, run_mact_on_question_async
from mact_langgraph.state import create_initial_state
from mact_langgraph.utils.mmqa_utils import load_mmqa_dataset, format_mmqa_item_for_processing


async def example_single_question():
    """Example: Run MACT on a single question."""
    print("Example 1: Single Question Processing")
    print("-" * 40)

    # Sample MMQA-style data
    sample_question = "Which department has the largest number of employees?"

    sample_tables = [
        {
            "table_columns": ["Department_ID", "Name", "Creation", "Ranking", "Budget_in_Billions", "Num_Employees"],
            "table_content": [
                [1, "State", "1789", 1, 9.96, 30266.0],
                [2, "Treasury", "1789", 2, 11.1, 115897.0],
                [3, "Defense", "1947", 3, 439.3, 3000000.0],
                [4, "Justice", "1870", 4, 23.4, 112557.0],
                [5, "Interior", "1849", 5, 10.7, 71436.0]
            ]
        }
    ]

    config = {
        "plan_model": "gpt-3.5-turbo",
        "code_model": "gpt-3.5-turbo",
        "reward_type": "consistency",
        "plan_sample": 3,
        "code_sample": 3,
        "max_steps": 4
    }

    result = await run_mact_on_question_async(
        question=sample_question,
        tables_data=sample_tables,
        config=config
    )

    print(f"Question: {result['question']}")
    print(f"Answer: {result['final_answer']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Steps taken: {result['steps_taken']}")
    print(f"Success: {not result['has_error']}")
    print()


async def example_different_reward_functions():
    """Example: Compare different reward functions."""
    print("Example 2: Different Reward Functions")
    print("-" * 40)

    # Sample data
    question = "What is the total budget of all departments?"
    tables = [
        {
            "table_columns": ["Department_ID", "Name", "Budget_in_Billions"],
            "table_content": [
                [1, "State", 9.96],
                [2, "Treasury", 11.1],
                [3, "Defense", 439.3]
            ]
        }
    ]

    reward_types = ["consistency", "llm"]

    for reward_type in reward_types:
        print(f"Testing reward type: {reward_type}")

        config = {
            "plan_model": "gpt-3.5-turbo",
            "code_model": "gpt-3.5-turbo",
            "reward_type": reward_type,
            "plan_sample": 3,
            "code_sample": 2,
            "max_steps": 3
        }

        result = await run_mact_on_question_async(
            question=question,
            tables_data=tables,
            config=config
        )

        print(f"  Answer: {result['final_answer']}")
        print(f"  Steps: {result['steps_taken']}")
        print(f"  Success: {not result['has_error']}")
        print()


async def example_multi_table_join():
    """Example: Multi-table JOIN operation."""
    print("Example 3: Multi-table JOIN Operation")
    print("-" * 40)

    question = "Which department head is temporary acting and from California?"

    tables = [
        {
            "table_name": "department",
            "table_columns": ["Department_ID", "Name"],
            "table_content": [
                [2, "Treasury"],
                [15, "Homeland Security"]
            ]
        },
        {
            "table_name": "management",
            "table_columns": ["department_ID", "head_ID", "temporary_acting"],
            "table_content": [
                [2, 5, "Yes"],
                [15, 4, "Yes"]
            ]
        },
        {
            "table_name": "head",
            "table_columns": ["head_ID", "name", "born_state", "age"],
            "table_content": [
                [4, "Dudley Hart", "California", 52.0],
                [5, "Jeff Maggert", "Delaware", 53.0]
            ]
        }
    ]

    config = {
        "plan_model": "gpt-3.5-turbo",
        "code_model": "gpt-3.5-turbo",
        "reward_type": "consistency",
        "plan_sample": 3,
        "code_sample": 3,
        "max_steps": 5
    }

    result = await run_mact_on_question_async(
        question=question,
        tables_data=tables,
        config=config
    )

    print(f"Question: {result['question']}")
    print(f"Answer: {result['final_answer']}")
    print(f"Steps taken: {result['steps_taken']}")

    if result['step_history']:
        print("\nReasoning steps:")
        for i, step in enumerate(result['step_history']):
            print(f"  Step {i+1}: {step.get('action', '')}")


async def example_error_handling():
    """Example: Error handling and recovery."""
    print("Example 4: Error Handling")
    print("-" * 40)

    # Intentionally problematic question/data
    question = "What is the impossible calculation?"
    tables = []  # Empty tables to trigger error

    config = {
        "plan_model": "gpt-3.5-turbo",
        "code_model": "gpt-3.5-turbo",
        "max_steps": 2
    }

    result = await run_mact_on_question_async(
        question=question,
        tables_data=tables,
        config=config
    )

    print(f"Question: {result['question']}")
    print(f"Has error: {result['has_error']}")
    print(f"Error message: {result.get('error_message', 'None')}")
    print(f"Final answer: {result['final_answer']}")
    print()


async def example_streaming_execution():
    """Example: Streaming execution to monitor progress."""
    print("Example 5: Streaming Execution")
    print("-" * 40)

    question = "How many departments are there?"
    tables = [
        {
            "table_columns": ["Department_ID", "Name"],
            "table_content": [
                [1, "State"],
                [2, "Treasury"],
                [3, "Defense"]
            ]
        }
    ]

    config = {
        "plan_model": "gpt-3.5-turbo",
        "code_model": "gpt-3.5-turbo",
        "max_steps": 3
    }

    # Create initial state
    initial_state = create_initial_state(
        question=question,
        tables_data=tables,
        config=config
    )

    # Create graph and stream execution
    graph = MACTGraph(config)

    print("Streaming execution...")
    step_count = 0
    async for state_update in graph.stream_async(initial_state):
        step_count += 1
        current_node = list(state_update.keys())[0] if state_update else "unknown"
        print(f"  Step {step_count}: {current_node}")

        # Get the state from the update
        if state_update:
            state = list(state_update.values())[0]
            if state.get('is_finished') or state.get('is_halted'):
                print(f"  Final answer: {state.get('final_answer', 'None')}")
                break

    print()


async def example_batch_processing():
    """Example: Process multiple questions efficiently."""
    print("Example 6: Batch Processing")
    print("-" * 40)

    # Multiple questions with same table structure
    questions = [
        "How many departments are there?",
        "What is the total budget?",
        "Which department has the highest ranking?"
    ]

    tables = [
        {
            "table_columns": ["Department_ID", "Name", "Ranking", "Budget_in_Billions"],
            "table_content": [
                [1, "State", 1, 9.96],
                [2, "Treasury", 2, 11.1],
                [3, "Defense", 3, 439.3]
            ]
        }
    ]

    config = {
        "plan_model": "gpt-3.5-turbo",
        "code_model": "gpt-3.5-turbo",
        "max_steps": 3
    }

    print("Processing multiple questions:")
    for i, question in enumerate(questions):
        print(f"\nQuestion {i+1}: {question}")

        result = await run_mact_on_question_async(
            question=question,
            tables_data=tables,
            config=config
        )

        print(f"Answer: {result['final_answer']}")
        print(f"Steps: {result['steps_taken']}")


async def main():
    """Run all examples."""
    # Setup environment
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please set up your .env file with your OpenAI API key.")
        return

    print("MACT LangGraph Examples")
    print("=" * 50)
    print()

    try:
        await example_single_question()
        await example_different_reward_functions()
        await example_multi_table_join()
        await example_error_handling()
        await example_streaming_execution()
        await example_batch_processing()

        print("All examples completed successfully!")

    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())