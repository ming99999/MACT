"""
Result saving and metric calculation utilities for MACT LangGraph.

Handles large-scale datasets and flexible metric evaluation.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


def generate_result_filename(model_name: str, dataset_name: str, output_dir: str = "results") -> tuple[str, str]:
    """
    Generate unique result filenames for predictions and metrics.

    Args:
        model_name: Name of the model used
        dataset_name: Name of the dataset
        output_dir: Directory to save results

    Returns:
        Tuple of (predictions_file, metrics_file)
    """
    # Clean model name for filename
    clean_model = model_name.replace("/", "_").replace(":", "_").replace(" ", "_")

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)

    # Generate filenames
    base_name = f"{clean_model}_{dataset_name}_{timestamp}"
    predictions_file = os.path.join(output_dir, f"predictions_{base_name}.jsonl")
    metrics_file = os.path.join(output_dir, f"metrics_{base_name}.json")

    return predictions_file, metrics_file


def save_prediction_item(item_result: Dict[str, Any], predictions_file: str) -> None:
    """
    Save a single prediction item to JSONL file (for streaming/large datasets).

    Args:
        item_result: Result dictionary for single item
        predictions_file: Path to predictions JSONL file
    """
    # Prepare minimal prediction item
    prediction_item = {
        "id": item_result.get("id", "unknown"),
        "question": item_result.get("question", ""),
        "predicted": item_result.get("predicted", ""),
        "target": item_result.get("target", ""),
        "confidence": item_result.get("confidence", 0.0),
        "steps_taken": item_result.get("steps_taken", 0),
        "has_error": item_result.get("has_error", False),
        "error_message": item_result.get("error_message", ""),

        # Additional attributes for flexible metric calculation
        "pred_answer": item_result.get("predicted", ""),  # TAT-style attribute
        "gold_answer": item_result.get("target", ""),
        "execution_time": item_result.get("execution_time", 0.0),
        "model_info": {
            "plan_model": item_result.get("plan_model", ""),
            "code_model": item_result.get("code_model", ""),
            "reward_type": item_result.get("reward_type", "")
        }
    }

    # Optional detailed information (can be excluded for large datasets)
    if item_result.get("include_details", True):
        prediction_item.update({
            "execution_log": item_result.get("execution_log", []),
            "step_history": item_result.get("step_history", []),
            "scratchpad": item_result.get("scratchpad", ""),
            "sql_reference": item_result.get("sql_reference", "")
        })

    # Append to JSONL file
    with open(predictions_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(prediction_item, ensure_ascii=False) + "\n")


def calculate_comprehensive_metrics(predictions_file: str) -> Dict[str, Any]:
    """
    Calculate comprehensive metrics from predictions JSONL file.

    Args:
        predictions_file: Path to predictions JSONL file

    Returns:
        Dictionary with calculated metrics
    """
    from .table_utils import exact_match

    if not os.path.exists(predictions_file):
        return {"error": "Predictions file not found"}

    predictions = []
    with open(predictions_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                predictions.append(json.loads(line))

    if not predictions:
        return {"error": "No predictions found"}

    total = len(predictions)

    # Basic metrics
    exact_matches = 0
    total_steps = 0
    total_confidence = 0.0
    error_count = 0

    # Advanced metrics
    step_distribution = {}
    confidence_ranges = {"low": 0, "medium": 0, "high": 0}
    error_types = {}

    for pred in predictions:
        predicted = str(pred.get("predicted", "")).strip()
        target = str(pred.get("target", "")).strip()

        # Exact match
        if exact_match(predicted, target):
            exact_matches += 1

        # Steps and confidence
        steps = pred.get("steps_taken", 0)
        total_steps += steps

        confidence = pred.get("confidence", 0.0)
        total_confidence += confidence

        # Step distribution
        step_distribution[steps] = step_distribution.get(steps, 0) + 1

        # Confidence ranges
        if confidence < 0.3:
            confidence_ranges["low"] += 1
        elif confidence < 0.7:
            confidence_ranges["medium"] += 1
        else:
            confidence_ranges["high"] += 1

        # Error analysis
        if pred.get("has_error", False):
            error_count += 1
            error_msg = pred.get("error_message", "unknown")
            error_types[error_msg] = error_types.get(error_msg, 0) + 1

    # Calculate metrics
    exact_match_score = exact_matches / total if total > 0 else 0.0
    avg_steps = total_steps / total if total > 0 else 0.0
    avg_confidence = total_confidence / total if total > 0 else 0.0

    return {
        "basic_metrics": {
            "exact_match": exact_match_score,
            "accuracy": exact_match_score,
            "correct": exact_matches,
            "total": total,
            "error_rate": error_count / total if total > 0 else 0.0
        },
        "performance_metrics": {
            "avg_steps": avg_steps,
            "avg_confidence": avg_confidence,
            "step_distribution": step_distribution,
            "confidence_ranges": confidence_ranges
        },
        "error_analysis": {
            "error_count": error_count,
            "error_types": error_types
        },
        "dataset_info": {
            "total_items": total,
            "processing_completed": True
        }
    }


def save_metrics(metrics: Dict[str, Any], config: Dict[str, Any], metrics_file: str) -> None:
    """
    Save comprehensive metrics to JSON file.

    Args:
        metrics: Calculated metrics
        config: Experiment configuration
        metrics_file: Path to metrics JSON file
    """
    result_data = {
        "experiment_info": {
            "timestamp": datetime.now().isoformat(),
            "config": config
        },
        "metrics": metrics
    }

    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)


def load_predictions_for_analysis(predictions_file: str) -> List[Dict[str, Any]]:
    """
    Load predictions from JSONL file for custom analysis.

    Args:
        predictions_file: Path to predictions JSONL file

    Returns:
        List of prediction dictionaries
    """
    predictions = []
    with open(predictions_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                predictions.append(json.loads(line))
    return predictions


def calculate_custom_metrics(predictions: List[Dict[str, Any]], metric_functions: Dict[str, callable]) -> Dict[str, Any]:
    """
    Calculate custom metrics using provided functions.

    Args:
        predictions: List of prediction dictionaries
        metric_functions: Dictionary of metric name -> function mappings

    Returns:
        Dictionary with custom metric results
    """
    custom_metrics = {}

    for metric_name, metric_func in metric_functions.items():
        try:
            custom_metrics[metric_name] = metric_func(predictions)
        except Exception as e:
            custom_metrics[metric_name] = {"error": str(e)}

    return custom_metrics


# Example custom metric functions
def calculate_bleu_score(predictions: List[Dict[str, Any]]) -> float:
    """Example: Calculate BLEU score (requires nltk)."""
    try:
        from nltk.translate.bleu_score import sentence_bleu
        import nltk
        nltk.download('punkt', quiet=True)

        scores = []
        for pred in predictions:
            reference = [pred.get("target", "").split()]
            candidate = pred.get("predicted", "").split()
            if reference[0] and candidate:
                score = sentence_bleu(reference, candidate)
                scores.append(score)

        return sum(scores) / len(scores) if scores else 0.0
    except ImportError:
        return {"error": "NLTK not available"}


def calculate_semantic_similarity(predictions: List[Dict[str, Any]]) -> float:
    """Example: Calculate semantic similarity (placeholder)."""
    # This would require sentence-transformers or similar
    # For now, return a placeholder
    return 0.0