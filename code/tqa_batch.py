#!/usr/bin/env python3
"""
Standalone LLM-based Table Question Answering (TQA) Module

This module performs TQA tasks using only LLM calls without additional tools or agents.
Supports both OpenAI GPT models and open-source models via RunPod vLLM endpoints.

Usage:
    python tqa_batch.py --model_name gpt-3.5-turbo --dataset_path data.jsonl --task tat
    python tqa_batch.py --model_name Qwen/Qwen3-8B --dataset_path data.jsonl --task mmqa
"""

import argparse
import json
import time
import asyncio
from typing import List, Dict, Any
from pathlib import Path
from tqdm import tqdm

from llm import UnifiedLLM, extract_answer_from_response
from utils import (
    load_dataset, 
    save_results, 
    format_table_for_prompt, 
    create_tqa_prompt,
    calculate_metrics,
    print_sample_results
)


class TQAProcessor:
    """Standalone TQA processor using only LLM calls."""
    
    def __init__(self, 
                 model_name: str,
                 max_tokens: int = 1000,
                 temperature: float = 0.1,
                 num_attempts: int = 1):
        """
        Initialize TQA processor.
        
        Args:
            model_name: Name of the LLM model to use
            max_tokens: Maximum tokens for generation
            temperature: Sampling temperature
            num_attempts: Number of generation attempts per question
        """
        self.model_name = model_name
        self.llm = UnifiedLLM(model_name)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.num_attempts = num_attempts
        
    def _create_prompt_and_metadata(self, item: Dict[str, Any], task_type: str) -> Dict[str, Any]:
        question = item.get("question", item.get("statement", item.get("Question", "")))
        table_data = item.get("table_text", item.get("table", item.get("tables", "")))
        
        # Handle MMQA's multi-table format
        if task_type == "mmqa" and "tables" in item and isinstance(item["tables"], list):
            formatted_tables = []
            for i, table_info in enumerate(item["tables"]):
                # Reconstruct table from columns and content
                if "table_columns" in table_info and "table_content" in table_info:
                    table_list = [table_info["table_columns"]] + table_info["table_content"]
                    table_str = format_table_for_prompt(table_list)
                    formatted_tables.append(f"Table {i+1}:\n{table_str}")
            table_data = "\n\n".join(formatted_tables)
        
        formatted_table = format_table_for_prompt(table_data) if not isinstance(table_data, str) else table_data
        context = item.get("text", item.get("context", ""))
        
        prompt = create_tqa_prompt(
            question=question, table=formatted_table, context=context, task_type=task_type
        )
        
        return {"prompt": prompt, "item": item, "formatted_table": formatted_table}

    def _process_responses(self, metadata: Dict[str, Any], responses: List[str], processing_time: float) -> Dict[str, Any]:
        """Helper to process LLM responses and format the result."""
        item = metadata["item"]
        question = item.get("question", item.get("statement", item.get("Question", "")))
        target_answer = item.get("answer", item.get("target", ""))
        
        if responses and responses[0]:
            extracted = extract_answer_from_response(responses[0], "smart")
            predicted_answer = extracted if extracted else responses[0].strip()
        else:
            predicted_answer = ""

        return {
            "question": question,
            "table": metadata["formatted_table"][:200] + "...",
            "context": item.get("text", ""),
            "target": target_answer,
            "predicted": predicted_answer,
            "raw_response": responses[0] if responses else "",
            "model_name": self.model_name,
            "task_type": metadata.get("task_type", "general"),
            "processing_time": processing_time,
            "original_item": item
        }

    def process_single_item(self, 
                           item: Dict[str, Any], 
                           task_type: str = "general") -> Dict[str, Any]:
        """
        Process a single TQA item.
        
        Args:
            item: Dataset item containing question, table, context, answer
            task_type: Type of task (tat, mmqa, wtq, etc.)
            
        Returns:
            Result dictionary with prediction and metadata
        """
        metadata_dict = self._create_prompt_and_metadata(item, task_type)
        prompt = metadata_dict["prompt"]
        
        # Generate responses
        responses = self.llm(
            prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            num_return_sequences=self.num_attempts
        )
        
        metadata = {"item": item, "formatted_table": metadata_dict["formatted_table"], "task_type": task_type}
        return self._process_responses(metadata, responses, 0)

    async def _process_batch(self, batch_items: List[Dict[str, Any]], task_type: str) -> List[Dict[str, Any]]:
        """Processes a single batch of items asynchronously."""
        start_time = time.time()
        
        prompts_and_metadata = [self._create_prompt_and_metadata(item, task_type) for item in batch_items]
        batch_prompts = [d["prompt"] for d in prompts_and_metadata]

        try:
            batch_responses = await self.llm.generate_batch(
                prompts=batch_prompts,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                num_return_sequences=self.num_attempts
            )
        except Exception as e:
            print(f"Error during batch generation: {e}")
            batch_responses = [[""] * self.num_attempts] * len(batch_items)

        processing_time = (time.time() - start_time) / len(batch_items)
        
        batch_results = []
        for metadata, responses in zip(prompts_and_metadata, batch_responses):
            result = self._process_responses(metadata, responses, processing_time)
            batch_results.append(result)
            
        return batch_results

    async def process_dataset(self,
                              dataset: List[Dict[str, Any]],
                              task_type: str = "general",
                              batch_size: int = 1,
                              save_interval: int = 10) -> List[Dict[str, Any]]:
        """
        Process entire dataset, using batching if batch_size > 1.
        """
        results = []
        print(f"Processing {len(dataset)} items with model {self.model_name}")
        print(f"Task type: {task_type}, Batch size: {batch_size}")
        print(f"Parameters: max_tokens={self.max_tokens}, temperature={self.temperature}")
        print("-" * 60)

        if batch_size > 1:
            # Asynchronous batch processing
            for i in tqdm(range(0, len(dataset), batch_size), desc="Processing batches"):
                batch_items = dataset[i:i + batch_size]
                # Ensure batch_items is list of dicts
                if isinstance(batch_items, list) and all(isinstance(x, str) for x in batch_items):
                    batch_items = [json.loads(x) if isinstance(x, str) else x for x in batch_items]
                batch_results = await self._process_batch(batch_items, task_type)
                results.extend(batch_results)
                
                if (i // batch_size + 1) % (save_interval // batch_size or 1) == 0:
                    metrics = calculate_metrics(results)
                    print(f"Progress {len(results)}/{len(dataset)}: Accuracy = {metrics['exact_match']:.3f}")
        else:
            # Synchronous single-item processing
            for i, item in enumerate(tqdm(dataset, desc="Processing items")):
                try:
                    # Some items may already be dict, avoid double json.loads
                    if isinstance(item, str):
                        item = json.loads(item)
                    start_time = time.time()
                    result = self.process_single_item(item, task_type)
                    result["processing_time"] = time.time() - start_time
                    results.append(result)
                    
                    if (i + 1) % save_interval == 0:
                        metrics = calculate_metrics(results)
                        print(f"Progress {i + 1}/{len(dataset)}: Accuracy = {metrics['exact_match']:.3f}")
                except Exception as e:
                    print(f"Error processing item {i+1}: {e}")
                    results.append({"error": str(e), "original_item": item})

        return results


async def main():
    """Main function for TQA processing."""
    parser = argparse.ArgumentParser(description="Standalone LLM-based TQA Processing")
    
    # Model and generation parameters
    parser.add_argument("--model_name", type=str, required=True,
                       help="Model name (e.g., gpt-3.5-turbo, Qwen/Qwen3-8B)")
    parser.add_argument("--max_tokens", type=int, default=1000,
                       help="Maximum tokens for generation")
    parser.add_argument("--temperature", type=float, default=0.1,
                       help="Sampling temperature")
    parser.add_argument("--num_attempts", type=int, default=1,
                       help="Number of generation attempts per question")
    parser.add_argument("--batch_size", type=int, default=1,
                       help="Batch size for processing. If 1, runs synchronously.")
    
    # Dataset parameters
    parser.add_argument("--dataset_path", type=str, required=True,
                       help="Path to dataset JSONL file")
    parser.add_argument("--task", type=str, default="general",
                       choices=["tat", "mmqa", "wtq", "scitab", "general"],
                       help="Task type for prompt formatting")
    parser.add_argument("--limit", type=int, default=None,
                       help="Limit number of items to process (for testing)")
    
    # Output parameters
    parser.add_argument("--output_dir", type=str, default="./outputs",
                       help="Output directory for results")
    parser.add_argument("--output_name", type=str, default=None,
                       help="Custom output filename (without extension)")
    
    # Processing parameters
    parser.add_argument("--save_interval", type=int, default=10,
                       help="Save and report progress every N items")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug mode with detailed output")
    
    args = parser.parse_args()
    
    # Load dataset
    print(f"Loading dataset from {args.dataset_path}...")
    dataset = load_dataset(args.dataset_path)
    
    if not dataset:
        print("Error: No data loaded from dataset file.")
        return
    
    # Fix dataset structure if needed (handle 2D list datasets)
    if len(dataset) == 1 and isinstance(dataset[0], list):
        dataset = dataset[0]
    
    print(f"Loaded {len(dataset)} items")
    
    # Apply limit AFTER any dataset structure fixes
    if args.limit:
        dataset = dataset[:args.limit]
        print(f"Limited to {len(dataset)} items for processing")
    
    # Initialize processor
    processor = TQAProcessor(
        model_name=args.model_name,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        num_attempts=args.num_attempts
    )
    
    # Process dataset
    results = await processor.process_dataset(
        dataset=dataset,
        task_type=args.task,
        batch_size=args.batch_size,
        save_interval=args.save_interval
    )
    
    # Calculate final metrics
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    metrics = calculate_metrics(results)
    print(f"Total Items: {metrics['total']}")
    print(f"Correct: {metrics['correct']}")
    print(f"Exact Match Accuracy: {metrics['exact_match']:.4f}")
    
    # Print sample results if debug mode
    if args.debug:
        print_sample_results(results, num_samples=5)
    
    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    if args.output_name:
        output_filename = f"{args.output_name}.jsonl"
    else:
        model_name_safe = args.model_name.replace("/", "_").replace("-", "_")
        output_filename = f"tqa_{args.task}_{model_name_safe}_{len(results)}items.jsonl"
    
    output_path = output_dir / output_filename
    save_results(results, str(output_path))
    
    # Save summary
    summary = {
        "model_name": args.model_name,
        "task_type": args.task,
        "dataset_path": args.dataset_path,
        "total_items": len(results),
        "metrics": metrics,
        "parameters": {
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "num_attempts": args.num_attempts
        }
    }
    
    summary_path = output_dir / f"summary_{output_filename.replace('.jsonl', '.json')}"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {output_path}")
    print(f"Summary saved to: {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())

# Calling Example
#python cs8903_benchmark/MACT/code/tqa_batch.py --model_name gpt-3.5-turbo --dataset_path cs8903_benchmark/MACT/datasets_examples/mmqa_samples.json --task mmqa --batch_size 2 --limit 10