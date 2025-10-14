"""
Main entry point for Multi-Agent Table QA system.

Usage:
    python multi_agent_main.py --dataset_path ../datasets_examples/mmqa_samples.json \
                               --plan_model gpt-3.5-turbo \
                               --code_model gpt-3.5-turbo \
                               --output_format mmqa_json \
                               --output_dir multi_agent_results

Example with different output formats:
    # MMQA JSON format (for evaluation)
    python multi_agent_main.py ... --output_format mmqa_json

    # Business report format
    python multi_agent_main.py ... --output_format business_report

    # Detailed research format
    python multi_agent_main.py ... --output_format research_detailed

    # Simple answer only
    python multi_agent_main.py ... --output_format simple_answer
"""

import argparse
import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from multi_agent.graph import MultiAgentGraph
from multi_agent.state import create_multi_agent_initial_state
from multi_agent.utils.env_utils import load_env_config, print_api_status
from mact_langgraph.utils.mmqa_utils import load_mmqa_dataset
from mact_langgraph.utils.result_utils import save_prediction_item

# Load environment variables from .env file
load_env_config()


async def run_multi_agent_on_dataset(
    dataset: List[Dict[str, Any]],
    config: Dict[str, Any],
    output_format: str,
    output_dir: str,
    debug: bool = False,
    debug_limit: int = None
) -> List[Dict[str, Any]]:
    """
    Run Multi-Agent framework on a dataset.

    Args:
        dataset: List of questions with tables
        config: Configuration for agents
        output_format: Output format (mmqa_json, business_report, etc.)
        output_dir: Directory to save results
        debug: Enable debug mode
        debug_limit: Limit number of questions in debug mode

    Returns:
        List of results
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Limit dataset in debug mode
    if debug and debug_limit:
        dataset = dataset[:debug_limit]
        print(f"\n🐛 DEBUG MODE: Processing only {debug_limit} questions\n")

    # Initialize graph
    graph = MultiAgentGraph(config)

    results = []
    total_time = 0

    print(f"\n{'='*80}")
    print(f"Multi-Agent Table QA - Processing {len(dataset)} questions")
    print(f"Output Format: {output_format}")
    print(f"Models: Planning={config.get('plan_model')}, Coding={config.get('code_model')}")
    print(f"{'='*80}\n")

    for idx, item in enumerate(dataset, 1):
        print(f"\n{'='*80}")
        print(f"Question {idx}/{len(dataset)}")
        print(f"{'='*80}")

        question = item.get("question") or item.get("statement")
        tables_data = item.get("tables", [])

        # Extract ground truth
        ground_truth = {
            "answer": item.get("answer", []),
            "foreign_keys": item.get("foreign_keys", []),
            "primary_keys": item.get("primary_keys", []),
            "sql": item.get("sql", "")
        }

        print(f"Question: {question}\n")

        try:
            # Create initial state
            initial_state = create_multi_agent_initial_state(
                question=question,
                tables_data=tables_data,
                output_format=output_format,
                config=config
            )

            # Run Multi-Agent graph
            start_time = time.time()
            final_state = await graph.run(initial_state)
            execution_time = time.time() - start_time
            total_time += execution_time

            # Get summary
            summary = graph.get_execution_summary(final_state)

            # Add metadata
            result = {
                "question_id": idx - 1,
                "question": question,
                "predicted_answer": final_state.get("final_answer", ""),
                "formatted_output": final_state.get("formatted_output", {}),
                "ground_truth": ground_truth,
                "confidence": final_state.get("confidence_score", 0.0),
                "confidence_breakdown": final_state.get("confidence_breakdown", {}),
                "execution_time": execution_time,
                "num_steps": final_state.get("current_step", 0) - 1,
                "is_finished": final_state.get("is_finished", False),
                "has_error": final_state.get("has_error", False),
                "eda_context_length": len(final_state.get("eda_context", "")),
                "detected_fks": final_state.get("detected_foreign_keys", []),
                "execution_log": final_state.get("execution_log", [])
            }

            # For MMQA format, add subtask predictions
            if output_format == "mmqa_json":
                result["predicted_foreign_keys"] = final_state.get("predicted_foreign_keys", [])
                result["predicted_primary_keys"] = final_state.get("predicted_primary_keys", [])
                result["predicted_sql"] = final_state.get("predicted_sql", "")

            results.append(result)

            # Print result
            print(f"\n{'─'*80}")
            print(f"✅ Answer: {result['predicted_answer']}")
            print(f"   Confidence: {result['confidence']:.2%}")
            print(f"   Steps: {result['num_steps']}")
            print(f"   Time: {execution_time:.2f}s")
            print(f"   Detected FKs: {len(result['detected_fks'])}")
            print(f"{'─'*80}\n")

            # Save intermediate result
            save_prediction_item(
                result,
                output_dir,
                f"multi_agent_{output_format}"
            )

        except Exception as e:
            print(f"\n❌ Error processing question {idx}: {str(e)}")
            import traceback
            traceback.print_exc()

            result = {
                "question_id": idx - 1,
                "question": question,
                "predicted_answer": "",
                "formatted_output": {"error": str(e)},
                "ground_truth": ground_truth,
                "has_error": True,
                "error_message": str(e),
                "execution_time": 0,
                "num_steps": 0
            }
            results.append(result)

    # Print summary
    avg_time = total_time / len(dataset) if dataset else 0
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total questions: {len(dataset)}")
    print(f"Completed: {sum(1 for r in results if not r.get('has_error'))}")
    print(f"Errors: {sum(1 for r in results if r.get('has_error'))}")
    print(f"Average time: {avg_time:.2f}s/question")
    print(f"Total time: {total_time:.2f}s")
    print(f"{'='*80}\n")

    return results


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Table QA System")

    # Dataset arguments
    parser.add_argument("--dataset_path", type=str, required=True,
                        help="Path to dataset (MMQA JSON format)")
    parser.add_argument("--output_dir", type=str, default="multi_agent_results",
                        help="Directory to save results")

    # Model arguments
    parser.add_argument("--plan_model", type=str, default="gpt-3.5-turbo",
                        help="Model for planning agent")
    parser.add_argument("--code_model", type=str, default="gpt-3.5-turbo",
                        help="Model for coding agent")

    # Agent configuration
    parser.add_argument("--plan_sample", type=int, default=3,
                        help="Number of action candidates to generate")
    parser.add_argument("--code_sample", type=int, default=3,
                        help="Number of code samples for majority voting")
    parser.add_argument("--max_steps", type=int, default=6,
                        help="Maximum reasoning steps")
    parser.add_argument("--reward_type", type=str, default="consistency",
                        choices=["consistency", "llm", "logp", "rollout", "combined"],
                        help="Reward function for action selection")

    # Output format
    parser.add_argument("--output_format", type=str, default="mmqa_json",
                        choices=["mmqa_json", "business_report", "research_detailed", "simple_answer"],
                        help="Output format")

    # Debug options
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug mode")
    parser.add_argument("--debug_limit", type=int, default=3,
                        help="Number of questions to process in debug mode")

    args = parser.parse_args()

    # Load dataset
    print(f"\nLoading dataset from {args.dataset_path}...")
    dataset = load_mmqa_dataset(args.dataset_path)
    print(f"Loaded {len(dataset)} questions\n")

    # Prepare configuration
    config = {
        "plan_model": args.plan_model,
        "code_model": args.code_model,
        "plan_sample": args.plan_sample,
        "code_sample": args.code_sample,
        "max_steps": args.max_steps,
        "reward_type": args.reward_type
    }

    # Run Multi-Agent framework
    results = asyncio.run(
        run_multi_agent_on_dataset(
            dataset=dataset,
            config=config,
            output_format=args.output_format,
            output_dir=args.output_dir,
            debug=args.debug,
            debug_limit=args.debug_limit if args.debug else None
        )
    )

    # Save final results
    output_file = os.path.join(
        args.output_dir,
        f"multi_agent_{args.output_format}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Results saved to {output_file}\n")


if __name__ == "__main__":
    main()
