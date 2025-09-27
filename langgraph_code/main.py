"""
Main execution script for MACT LangGraph.

This script provides a command-line interface for running MACT on MMQA datasets.
"""

import asyncio
import argparse
import json
import os
import sys
from typing import Dict, Any, List
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mact_langgraph.graph import MACTGraph
from mact_langgraph.state import create_initial_state
from mact_langgraph.utils.mmqa_utils import (
    load_mmqa_dataset, format_mmqa_item_for_processing,
    create_mmqa_config, calculate_mmqa_metrics
)
from mact_langgraph.utils.table_utils import exact_match


def setup_environment():
    """Setup environment variables and configurations."""
    load_dotenv()

    # Check required environment variables
    required_vars = ["OPENAI_API_KEY"]
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables in your .env file or environment.")
        sys.exit(1)


async def process_single_item(item: Dict[str, Any], config: Dict[str, Any], graph: MACTGraph) -> Dict[str, Any]:
    """
    Process a single MMQA item.

    Args:
        item: Formatted MMQA item
        config: Configuration dictionary
        graph: MACT graph instance

    Returns:
        Result dictionary
    """
    try:
        # Create initial state
        initial_state = create_initial_state(
            question=item['question'],
            tables_data=item['tables'],
            table_names=item['table_names'],
            foreign_keys=item['foreign_keys'],
            primary_keys=item['primary_keys'],
            context=item['context'],
            config=config
        )

        # Run the graph
        final_state = await graph.run(initial_state)

        # Create result
        result = {
            'id': item['id'],
            'question': item['question'],
            'predicted': final_state.get('final_answer', ''),
            'target': item['answer'],
            'correct': exact_match(
                final_state.get('final_answer', ''),
                item['answer']
            ),
            'confidence': final_state.get('confidence_score', 0.0),
            'steps_taken': final_state.get('current_step', 0) - 1,
            'execution_log': final_state.get('execution_log', []),
            'step_history': final_state.get('step_history', []),
            'has_error': final_state.get('has_error', False),
            'error_message': final_state.get('error_message', ''),
            'scratchpad': final_state.get('scratchpad', ''),
            'sql_reference': item.get('sql', ''),  # Reference SQL (not used in execution)
            'original_item': item.get('original_item', {})
        }

        return result

    except Exception as e:
        return {
            'id': item.get('id', 'unknown'),
            'question': item.get('question', ''),
            'predicted': '',
            'target': item.get('answer', ''),
            'correct': False,
            'confidence': 0.0,
            'steps_taken': 0,
            'has_error': True,
            'error_message': str(e),
            'execution_log': [f"Error: {str(e)}"],
            'step_history': [],
            'scratchpad': ''
        }


async def main_async(args):
    """Main async execution function."""
    print("MACT LangGraph - MMQA Processing")
    print("=" * 50)

    # Setup environment
    setup_environment()

    # Load dataset
    print(f"Loading dataset from: {args.dataset_path}")
    dataset = load_mmqa_dataset(args.dataset_path)

    if not dataset:
        print("Error: No valid items found in dataset")
        return

    print(f"Loaded {len(dataset)} items")

    # Limit dataset size for debugging
    if args.debug:
        dataset = dataset[:args.debug_limit]
        print(f"Debug mode: Processing only first {len(dataset)} items")

    # Create configuration
    config = create_mmqa_config(
        plan_model=args.plan_model,
        code_model=args.code_model,
        reward_type=args.reward_type,
        plan_sample=args.plan_sample,
        code_sample=args.code_sample,
        max_steps=args.max_steps,
        max_actual_steps=args.max_actual_steps,
        use_pre_answer=args.use_pre_answer,
        answer_threshold=args.answer_threshold
    )

    print(f"Configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    print()

    # Create MACT graph
    graph = MACTGraph(config)

    # Process items
    results = []
    for i, item in enumerate(dataset):
        print(f"\nProcessing item {i+1}/{len(dataset)}")
        print(f"Question: {item['Question'][:100]}...")

        # Format item for processing
        formatted_item = format_mmqa_item_for_processing(item)

        # Process the item
        result = await process_single_item(formatted_item, config, graph)

        results.append(result)

        # Print progress
        if result['correct']:
            status = "✓ CORRECT"
        elif result['has_error']:
            status = "✗ ERROR"
        else:
            status = "✗ INCORRECT"

        print(f"Status: {status}")
        print(f"Predicted: {result['predicted']}")
        print(f"Target: {result['target']}")

        # Running statistics
        correct_count = sum(1 for r in results if r['correct'])
        accuracy = correct_count / len(results)
        print(f"Running accuracy: {accuracy:.3f} ({correct_count}/{len(results)})")

        # Save intermediate results
        if args.save_intermediate and (i + 1) % args.save_every == 0:
            intermediate_path = f"{args.output_path}.intermediate_{i+1}.json"
            with open(intermediate_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Saved intermediate results to: {intermediate_path}")

    # Calculate final metrics
    metrics = calculate_mmqa_metrics(results)

    # Print final results
    print("\n" + "=" * 50)
    print("FINAL RESULTS")
    print("=" * 50)
    print(f"Total items: {metrics['total']}")
    print(f"Correct: {metrics['correct']}")
    print(f"Accuracy: {metrics['exact_match']:.3f}")

    # Error analysis
    error_count = sum(1 for r in results if r['has_error'])
    if error_count > 0:
        print(f"Errors: {error_count}")

    # Save final results
    output_data = {
        'config': config,
        'metrics': metrics,
        'results': results,
        'summary': {
            'total_items': len(results),
            'correct_answers': metrics['correct'],
            'accuracy': metrics['exact_match'],
            'error_count': error_count
        }
    }

    with open(args.output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nResults saved to: {args.output_path}")


def main():
    """Main synchronous entry point."""
    parser = argparse.ArgumentParser(description="MACT LangGraph for MMQA dataset")

    # Data arguments
    parser.add_argument('--dataset_path', type=str, required=True,
                        help="Path to MMQA dataset JSON file")
    parser.add_argument('--output_path', type=str, default="results.json",
                        help="Path to save results")

    # Model arguments
    parser.add_argument('--plan_model', type=str, default="gpt-3.5-turbo",
                        help="Model for planning")
    parser.add_argument('--code_model', type=str, default="gpt-3.5-turbo",
                        help="Model for code generation")

    # Agent configuration
    parser.add_argument('--reward_type', type=str, default="consistency",
                        choices=["consistency", "llm", "logp", "rollout", "combined"],
                        help="Reward function type")
    parser.add_argument('--plan_sample', type=int, default=5,
                        help="Number of planning samples")
    parser.add_argument('--code_sample', type=int, default=5,
                        help="Number of code samples")
    parser.add_argument('--max_steps', type=int, default=6,
                        help="Maximum reasoning steps")
    parser.add_argument('--max_actual_steps', type=int, default=6,
                        help="Maximum actual steps")

    # Answer processing
    parser.add_argument('--use_pre_answer', action='store_true', default=True,
                        help="Use preliminary answers")
    parser.add_argument('--answer_threshold', type=float, default=1.0,
                        help="Answer agreement threshold")

    # Execution options
    parser.add_argument('--debug', action='store_true',
                        help="Enable debug mode")
    parser.add_argument('--debug_limit', type=int, default=3,
                        help="Number of items to process in debug mode")
    parser.add_argument('--save_intermediate', action='store_true',
                        help="Save intermediate results")
    parser.add_argument('--save_every', type=int, default=10,
                        help="Save intermediate results every N items")

    args = parser.parse_args()

    # Run the main async function
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()