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
    load_mmqa_dataset, load_dataset_universal, format_mmqa_item_for_processing,
    create_mmqa_config, calculate_mmqa_metrics
)
from mact_langgraph.utils.table_utils import exact_match
from mact_langgraph.utils.result_utils import (
    generate_result_filename, save_prediction_item,
    calculate_comprehensive_metrics, save_metrics
)


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
            'original_item': item.get('original_item', {}),

            # MMQA Subtask outputs (Phase 2)
            'predicted_sql': final_state.get('predicted_sql', ''),
            'predicted_foreign_keys': final_state.get('predicted_foreign_keys', []),
            'predicted_primary_keys': final_state.get('predicted_primary_keys', [])
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
    """Main async execution function with improved storage system."""
    print("MACT LangGraph - MMQA Processing")
    print("=" * 50)

    # Setup environment
    setup_environment()

    # Load dataset
    print(f"Loading dataset from: {args.dataset_path}")
    dataset = load_dataset_universal(args.dataset_path)

    if not dataset:
        print("Error: No valid items found in dataset")
        return

    print(f"Loaded {len(dataset)} items")

    # Limit dataset size for debugging
    if args.debug:
        dataset = dataset[:args.debug_limit]
        print(f"Debug mode: Processing only first {len(dataset)} items")

    # Determine if examples should be used
    use_examples = not args.no_examples if hasattr(args, 'no_examples') else args.use_examples

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
        answer_threshold=args.answer_threshold,
        use_examples=use_examples
    )

    print(f"Configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    print()

    # Generate result filenames
    dataset_name = os.path.splitext(os.path.basename(args.dataset_path))[0]
    model_name = f"{args.plan_model}+{args.code_model}" if args.plan_model != args.code_model else args.plan_model
    predictions_file, metrics_file = generate_result_filename(model_name, dataset_name, args.output_dir)

    print(f"Output files:")
    print(f"  Predictions: {predictions_file}")
    print(f"  Metrics: {metrics_file}")
    print()

    # Create MACT graph
    graph = MACTGraph(config)

    # Process items with streaming save
    import time
    start_time = time.time()

    for i, item in enumerate(dataset):
        print(f"\nProcessing item {i+1}/{len(dataset)}")
        print(f"Question: {item['Question'][:100]}...")

        # Format item for processing
        formatted_item = format_mmqa_item_for_processing(item)

        # Process the item
        item_start_time = time.time()
        result = await process_single_item(formatted_item, config, graph)
        execution_time = time.time() - item_start_time

        # Add additional metadata
        result.update({
            "execution_time": execution_time,
            "plan_model": args.plan_model,
            "code_model": args.code_model,
            "reward_type": args.reward_type,
            "include_details": not args.minimal_output  # For large datasets, can exclude details
        })

        # Save prediction immediately (streaming for large datasets)
        save_prediction_item(result, predictions_file)

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

        # Calculate running statistics from saved predictions
        if (i + 1) % 10 == 0 or i == len(dataset) - 1:  # Every 10 items or last item
            temp_metrics = calculate_comprehensive_metrics(predictions_file)
            basic_metrics = temp_metrics.get("basic_metrics", {})
            print(f"Running accuracy: {basic_metrics.get('accuracy', 0):.3f} ({basic_metrics.get('correct', 0)}/{basic_metrics.get('total', 0)})")

    total_time = time.time() - start_time

    # Calculate final comprehensive metrics
    print("\n" + "=" * 50)
    print("CALCULATING FINAL METRICS...")
    print("=" * 50)

    metrics = calculate_comprehensive_metrics(predictions_file)
    basic_metrics = metrics.get("basic_metrics", {})
    performance_metrics = metrics.get("performance_metrics", {})
    error_analysis = metrics.get("error_analysis", {})

    # Print comprehensive results
    print(f"\n📊 FINAL RESULTS")
    print("=" * 50)
    print(f"Total items: {basic_metrics.get('total', 0)}")
    print(f"Correct: {basic_metrics.get('correct', 0)}")
    print(f"Accuracy: {basic_metrics.get('accuracy', 0):.3f}")
    print(f"Error rate: {basic_metrics.get('error_rate', 0):.3f}")
    print(f"Average steps: {performance_metrics.get('avg_steps', 0):.1f}")
    print(f"Average confidence: {performance_metrics.get('avg_confidence', 0):.2f}")
    print(f"Total execution time: {total_time:.1f}s")

    if error_analysis.get("error_count", 0) > 0:
        print(f"\n🚨 Error Analysis:")
        print(f"Total errors: {error_analysis['error_count']}")
        for error_type, count in error_analysis.get("error_types", {}).items():
            print(f"  {error_type}: {count}")

    # Add experiment metadata to config
    config.update({
        "experiment_metadata": {
            "dataset_path": args.dataset_path,
            "dataset_size": len(dataset),
            "total_execution_time": total_time,
            "processing_date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    })

    # Save comprehensive metrics
    save_metrics(metrics, config, metrics_file)

    print(f"\n💾 Results saved:")
    print(f"  📋 Predictions: {predictions_file}")
    print(f"  📈 Metrics: {metrics_file}")

    # Backward compatibility: save legacy format if requested
    if args.legacy_output:
        from src.mact_langgraph.utils.mmqa_utils import load_predictions_for_analysis
        predictions = load_predictions_for_analysis(predictions_file)
        legacy_data = {
            'config': config,
            'metrics': basic_metrics,
            'results': predictions[:100],  # Limit for legacy compatibility
            'summary': {
                'total_items': basic_metrics.get('total', 0),
                'correct_answers': basic_metrics.get('correct', 0),
                'accuracy': basic_metrics.get('accuracy', 0),
                'error_count': error_analysis.get('error_count', 0)
            }
        }
        legacy_path = args.output_path or "results.json"
        with open(legacy_path, 'w') as f:
            json.dump(legacy_data, f, indent=2)
        print(f"  🔄 Legacy format: {legacy_path}")


def main():
    """Main synchronous entry point."""
    parser = argparse.ArgumentParser(description="MACT LangGraph for MMQA dataset")

    # Data arguments
    parser.add_argument('--dataset_path', type=str, required=True,
                        help="Path to MMQA dataset JSON file")
    parser.add_argument('--output_path', type=str, default="results.json",
                        help="Path to save results")
    parser.add_argument('--output_dir', type=str, default="results",
                        help="Directory to save result files")
    parser.add_argument('--minimal_output', action='store_true',
                        help="Exclude detailed logs for large datasets")
    parser.add_argument('--legacy_output', action='store_true',
                        help="Also save results in legacy JSON format")

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

    # Prompt configuration
    parser.add_argument('--use_examples', action='store_true', default=True,
                        help="Include MMQA REACT examples in prompts (few-shot)")
    parser.add_argument('--no_examples', action='store_true',
                        help="Exclude MMQA REACT examples from prompts (zero-shot)")

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