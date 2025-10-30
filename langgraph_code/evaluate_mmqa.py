"""
MMQA Benchmark Evaluation Script

This script evaluates MMQA subtask performance by comparing model predictions
with ground truth annotations.

Usage:
    python evaluate_mmqa.py --dataset <path> --predictions <path> [--output <path>]

Evaluates:
    - Answer: Exact match accuracy
    - SQL: ROUGE-1, ROUGE-L, BLEU scores
    - Foreign Keys: Set-based exact match
    - Primary Keys: Set-based exact match
"""

import argparse
import json
import sys
from typing import Dict, List, Any, Set, Tuple
from pathlib import Path
import re

try:
    from rouge_score import rouge_scorer
    from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
    ROUGE_BLEU_AVAILABLE = True
except ImportError:
    ROUGE_BLEU_AVAILABLE = False
    print("Warning: rouge-score or nltk not installed. SQL evaluation will be limited.")


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    return text.lower().strip()


def normalize_sql(sql: str) -> str:
    """Normalize SQL query for comparison."""
    # Remove extra whitespace
    sql = re.sub(r'\s+', ' ', sql.strip())
    # Lowercase
    sql = sql.lower()
    # Remove trailing semicolon
    sql = sql.rstrip(';')
    return sql


def normalize_keys(keys: List[str]) -> Set[str]:
    """Normalize FK/PK list to set."""
    return set([k.lower().strip() for k in keys])


def exact_match_answer(pred: str, gt: str) -> bool:
    """Check if answer matches exactly (case-insensitive, whitespace normalized)."""
    return normalize_text(pred) == normalize_text(gt)


def exact_match_sql(pred: str, gt: str) -> bool:
    """Check if SQL queries match (normalized)."""
    return normalize_sql(pred) == normalize_sql(gt)


def exact_match_keys(pred: List[str], gt: List[str]) -> bool:
    """Check if FK/PK sets match exactly."""
    return normalize_keys(pred) == normalize_keys(gt)


def load_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    """Load MMQA dataset."""
    with open(dataset_path, 'r') as f:
        data = json.load(f)

    print(f"✓ Loaded {len(data)} items from dataset")
    return data


def load_predictions(predictions_path: str) -> List[Dict[str, Any]]:
    """Load predictions from JSONL file."""
    predictions = []
    with open(predictions_path, 'r') as f:
        for line in f:
            if line.strip():
                predictions.append(json.loads(line))

    print(f"✓ Loaded {len(predictions)} predictions")
    return predictions


def evaluate_mmqa(dataset: List[Dict], predictions: List[Dict]) -> Dict[str, Any]:
    """
    Evaluate MMQA subtask performance.

    Returns comprehensive metrics for Answer, SQL, FK, PK subtasks.
    """
    assert len(dataset) == len(predictions), \
        f"Dataset size {len(dataset)} != Predictions size {len(predictions)}"

    # Initialize counters
    metrics = {
        'answer': {'correct': 0, 'total': 0},
        'sql': {'rouge1': [], 'rougeL': [], 'bleu': [], 'total': 0},
        'fk': {'correct': 0, 'total': 0},
        'pk': {'correct': 0, 'total': 0}
    }

    # Track mismatches for analysis
    mismatches = {
        'answer': [],
        'sql': [],
        'fk': [],
        'pk': []
    }

    # Initialize ROUGE scorer if available
    if ROUGE_BLEU_AVAILABLE:
        scorer = rouge_scorer.RougeScorer(['rouge1', 'rougeL'], use_stemmer=True)
        smoothing = SmoothingFunction().method1

    # Evaluate each item
    for i, (gt_item, pred_item) in enumerate(zip(dataset, predictions)):
        item_id = gt_item.get('id_', i)

        # 1. Answer evaluation
        gt_answer = gt_item.get('answer', '')
        pred_answer = pred_item.get('predicted', pred_item.get('pred_answer', ''))

        if exact_match_answer(pred_answer, gt_answer):
            metrics['answer']['correct'] += 1
        else:
            mismatches['answer'].append({
                'id': item_id,
                'gt': gt_answer,
                'pred': pred_answer
            })
        metrics['answer']['total'] += 1

        # 2. SQL evaluation (ROUGE & BLEU)
        gt_sql = gt_item.get('SQL', '')
        pred_sql = pred_item.get('predicted_sql', '')

        if gt_sql and pred_sql:  # Only evaluate if both exist
            if ROUGE_BLEU_AVAILABLE:
                # Normalize SQL for scoring
                gt_sql_norm = normalize_sql(gt_sql)
                pred_sql_norm = normalize_sql(pred_sql)

                # Calculate ROUGE scores
                rouge_scores = scorer.score(gt_sql_norm, pred_sql_norm)
                metrics['sql']['rouge1'].append(rouge_scores['rouge1'].fmeasure)
                metrics['sql']['rougeL'].append(rouge_scores['rougeL'].fmeasure)

                # Calculate BLEU score
                reference = [gt_sql_norm.split()]
                candidate = pred_sql_norm.split()
                bleu = sentence_bleu(reference, candidate, smoothing_function=smoothing)
                metrics['sql']['bleu'].append(bleu)

                # Track low-scoring cases as mismatches
                if rouge_scores['rougeL'].fmeasure < 0.5:
                    mismatches['sql'].append({
                        'id': item_id,
                        'gt': gt_sql[:100],
                        'pred': pred_sql[:100],
                        'rouge1': rouge_scores['rouge1'].fmeasure,
                        'rougeL': rouge_scores['rougeL'].fmeasure,
                        'bleu': bleu
                    })
            else:
                # Fallback to exact match if ROUGE/BLEU not available
                if exact_match_sql(pred_sql, gt_sql):
                    metrics['sql']['rouge1'].append(1.0)
                    metrics['sql']['rougeL'].append(1.0)
                    metrics['sql']['bleu'].append(1.0)
                else:
                    metrics['sql']['rouge1'].append(0.0)
                    metrics['sql']['rougeL'].append(0.0)
                    metrics['sql']['bleu'].append(0.0)
                    mismatches['sql'].append({
                        'id': item_id,
                        'gt': gt_sql[:100],
                        'pred': pred_sql[:100]
                    })
            metrics['sql']['total'] += 1

        # 3. Foreign Keys evaluation
        gt_fk = gt_item.get('foreign_keys', [])
        pred_fk = pred_item.get('predicted_foreign_keys', [])

        if exact_match_keys(pred_fk, gt_fk):
            metrics['fk']['correct'] += 1
        else:
            gt_set = normalize_keys(gt_fk)
            pred_set = normalize_keys(pred_fk)
            mismatches['fk'].append({
                'id': item_id,
                'gt': sorted(list(gt_set)),
                'pred': sorted(list(pred_set)),
                'missing': sorted(list(gt_set - pred_set)),
                'extra': sorted(list(pred_set - gt_set))
            })
        metrics['fk']['total'] += 1

        # 4. Primary Keys evaluation
        gt_pk = gt_item.get('primary_keys', [])
        pred_pk = pred_item.get('predicted_primary_keys', [])

        if exact_match_keys(pred_pk, gt_pk):
            metrics['pk']['correct'] += 1
        else:
            gt_set = normalize_keys(gt_pk)
            pred_set = normalize_keys(pred_pk)
            mismatches['pk'].append({
                'id': item_id,
                'gt': sorted(list(gt_set)),
                'pred': sorted(list(pred_set)),
                'missing': sorted(list(gt_set - pred_set)),
                'extra': sorted(list(pred_set - gt_set))
            })
        metrics['pk']['total'] += 1

    # Calculate accuracy percentages and average scores
    results = {
        'summary': {
            'total_items': len(dataset),
            'answer_accuracy': metrics['answer']['correct'] / metrics['answer']['total'] * 100,
            'sql_rouge1': sum(metrics['sql']['rouge1']) / len(metrics['sql']['rouge1']) * 100 if metrics['sql']['rouge1'] else 0.0,
            'sql_rougeL': sum(metrics['sql']['rougeL']) / len(metrics['sql']['rougeL']) * 100 if metrics['sql']['rougeL'] else 0.0,
            'sql_bleu': sum(metrics['sql']['bleu']) / len(metrics['sql']['bleu']) * 100 if metrics['sql']['bleu'] else 0.0,
            'sql_total': metrics['sql']['total'],
            'fk_accuracy': metrics['fk']['correct'] / metrics['fk']['total'] * 100,
            'pk_accuracy': metrics['pk']['correct'] / metrics['pk']['total'] * 100
        },
        'detailed': metrics,
        'mismatches': mismatches
    }

    return results


def print_results(results: Dict[str, Any], verbose: bool = False):
    """Print evaluation results in a formatted way."""
    print("\n" + "=" * 80)
    print("📊 MMQA SUBTASK EVALUATION RESULTS")
    print("=" * 80)

    summary = results['summary']
    print(f"\nTotal Items: {summary['total_items']}")
    print("\n" + "-" * 80)
    print(f"{'Subtask':<20} {'Metric':<15} {'Score':<12}")
    print("-" * 80)

    detailed = results['detailed']
    print(f"{'Answer':<20} {'Exact Match':<15} {summary['answer_accuracy']:.1f}%")
    print(f"{'SQL':<20} {'ROUGE-1':<15} {summary['sql_rouge1']:.1f}%")
    print(f"{'SQL':<20} {'ROUGE-L':<15} {summary['sql_rougeL']:.1f}%")
    print(f"{'SQL':<20} {'BLEU':<15} {summary['sql_bleu']:.1f}%")
    print(f"{'SQL':<20} {'Total Items':<15} {summary['sql_total']}")
    print(f"{'Foreign Keys':<20} {'Exact Match':<15} {summary['fk_accuracy']:.1f}%")
    print(f"{'Primary Keys':<20} {'Exact Match':<15} {summary['pk_accuracy']:.1f}%")
    print("-" * 80)

    if verbose:
        print("\n" + "=" * 80)
        print("🔍 MISMATCH ANALYSIS")
        print("=" * 80)

        for subtask in ['answer', 'sql', 'fk', 'pk']:
            mismatches = results['mismatches'][subtask]
            if mismatches:
                print(f"\n{subtask.upper()} Mismatches: {len(mismatches)} items")
                for i, mismatch in enumerate(mismatches[:3]):  # Show first 3
                    print(f"\n  Item {mismatch['id']}:")
                    if subtask in ['fk', 'pk']:
                        print(f"    Missing: {mismatch['missing']}")
                        print(f"    Extra:   {mismatch['extra']}")
                    else:
                        print(f"    GT:   {mismatch['gt']}")
                        print(f"    Pred: {mismatch['pred']}")
                if len(mismatches) > 3:
                    print(f"\n  ... and {len(mismatches) - 3} more mismatches")


def save_results(results: Dict[str, Any], output_path: str):
    """Save results to JSON file."""
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate MMQA subtask performance")

    parser.add_argument('--dataset', type=str, required=True,
                        help="Path to MMQA dataset JSON file")
    parser.add_argument('--predictions', type=str, required=True,
                        help="Path to predictions JSONL file")
    parser.add_argument('--output', type=str, default=None,
                        help="Path to save evaluation results JSON")
    parser.add_argument('--verbose', '-v', action='store_true',
                        help="Show detailed mismatch analysis")

    args = parser.parse_args()

    # Load data
    print("\n🔄 Loading data...")
    dataset = load_dataset(args.dataset)
    predictions = load_predictions(args.predictions)

    # Evaluate
    print("\n🔄 Evaluating...")
    results = evaluate_mmqa(dataset, predictions)

    # Print results
    print_results(results, verbose=args.verbose)

    # Save results if requested
    if args.output:
        save_results(results, args.output)

    print("\n✨ Evaluation complete!\n")


if __name__ == "__main__":
    main()
