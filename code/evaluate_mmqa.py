"""
MMQA Evaluation Script - Comprehensive evaluation for all 4 subtasks.

This script evaluates model predictions against ground truth for:
1. Answer: EM (Exact Match), PM (Partial Match)
2. SQL: Rouge-1, Rouge-L, BLEU (not implemented - requires proper SQL generation)
3. Primary Keys: PKS accuracy
4. Foreign Keys: FKS accuracy
"""

import json
import argparse
from typing import List, Dict, Any
from collections import Counter


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    return str(text).strip().lower()


def exact_match(pred: str, target: str) -> bool:
    """Exact Match (EM) metric."""
    pred_norm = normalize_text(pred)
    target_norm = normalize_text(target)

    # Handle numeric comparisons
    try:
        pred_val = float(pred_norm.replace(',', ''))
        target_val = float(target_norm.replace(',', ''))
        return abs(pred_val - target_val) < 0.01
    except:
        pass

    return pred_norm == target_norm


def partial_match(pred: str, target: str) -> float:
    """Partial Match (PM) metric - token overlap ratio."""
    pred_tokens = set(normalize_text(pred).split())
    target_tokens = set(normalize_text(target).split())

    if not pred_tokens or not target_tokens:
        return 0.0

    intersection = pred_tokens & target_tokens
    union = pred_tokens | target_tokens

    if not union:
        return 0.0

    return len(intersection) / len(union)


def list_accuracy(pred_list: List[str], target_list: List[str]) -> float:
    """Calculate accuracy for list predictions (FK/PK)."""
    if not target_list:
        return 1.0 if not pred_list else 0.0

    if not pred_list:
        return 0.0

    # Normalize both lists
    pred_norm = [normalize_text(item) for item in pred_list]
    target_norm = [normalize_text(item) for item in target_list]

    # Calculate overlap
    correct = sum(1 for item in pred_norm if item in target_norm)

    # Accuracy = correct / total_expected
    return correct / len(target_norm) if target_norm else 0.0


def evaluate_answer(pred: str, target: str) -> Dict[str, float]:
    """Evaluate answer prediction (SUBTASK 1)."""
    return {
        'em': 1.0 if exact_match(pred, target) else 0.0,
        'pm': partial_match(pred, target)
    }


def evaluate_primary_keys(pred_pks: List[str], target_pks: List[str]) -> float:
    """Evaluate primary key predictions (SUBTASK 3)."""
    return list_accuracy(pred_pks, target_pks)


def evaluate_foreign_keys(pred_fks: List[str], target_fks: List[str]) -> float:
    """Evaluate foreign key predictions (SUBTASK 4)."""
    return list_accuracy(pred_fks, target_fks)


def load_predictions(file_path: str) -> List[Dict[str, Any]]:
    """Load predictions from JSONL file."""
    predictions = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                predictions.append(json.loads(line))
    return predictions


def evaluate_dataset(predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate all predictions and compute aggregate metrics."""
    results = {
        'answer': {'em': [], 'pm': []},
        'primary_keys': [],
        'foreign_keys': []
    }

    detailed_results = []

    for pred in predictions:
        # SUBTASK 1: Answer
        answer_eval = evaluate_answer(
            pred.get('pred_answer', ''),
            pred.get('answer', '')
        )
        results['answer']['em'].append(answer_eval['em'])
        results['answer']['pm'].append(answer_eval['pm'])

        # SUBTASK 3: Primary Keys
        pks_eval = evaluate_primary_keys(
            pred.get('pred_primary_keys', []),
            pred.get('primary_keys', [])
        )
        results['primary_keys'].append(pks_eval)

        # SUBTASK 4: Foreign Keys
        fks_eval = evaluate_foreign_keys(
            pred.get('pred_foreign_keys', []),
            pred.get('foreign_keys', [])
        )
        results['foreign_keys'].append(fks_eval)

        # Store detailed result
        detailed_results.append({
            'id': pred.get('id_', 'unknown'),
            'question': pred.get('Question', ''),
            'answer_em': answer_eval['em'],
            'answer_pm': answer_eval['pm'],
            'pks_acc': pks_eval,
            'fks_acc': fks_eval,
            'pred_answer': pred.get('pred_answer', ''),
            'target_answer': pred.get('answer', ''),
            'pred_pks': pred.get('pred_primary_keys', []),
            'target_pks': pred.get('primary_keys', []),
            'pred_fks': pred.get('pred_foreign_keys', []),
            'target_fks': pred.get('foreign_keys', [])
        })

    # Compute aggregate metrics
    aggregate_metrics = {
        'answer': {
            'em': sum(results['answer']['em']) / len(results['answer']['em']) if results['answer']['em'] else 0.0,
            'pm': sum(results['answer']['pm']) / len(results['answer']['pm']) if results['answer']['pm'] else 0.0,
            'total': len(results['answer']['em']),
            'correct': sum(results['answer']['em'])
        },
        'primary_keys': {
            'accuracy': sum(results['primary_keys']) / len(results['primary_keys']) if results['primary_keys'] else 0.0,
            'total': len(results['primary_keys'])
        },
        'foreign_keys': {
            'accuracy': sum(results['foreign_keys']) / len(results['foreign_keys']) if results['foreign_keys'] else 0.0,
            'total': len(results['foreign_keys'])
        }
    }

    return {
        'aggregate_metrics': aggregate_metrics,
        'detailed_results': detailed_results
    }


def print_evaluation_report(eval_results: Dict[str, Any], output_path: str = None):
    """Print comprehensive evaluation report."""
    metrics = eval_results['aggregate_metrics']

    print("\n" + "=" * 60)
    print("MMQA COMPREHENSIVE EVALUATION REPORT")
    print("=" * 60)

    print("\n📊 SUBTASK 1: Answer Prediction")
    print("-" * 60)
    print(f"Exact Match (EM):     {metrics['answer']['em']:.3f} ({int(metrics['answer']['correct'])}/{metrics['answer']['total']})")
    print(f"Partial Match (PM):   {metrics['answer']['pm']:.3f}")

    print("\n📊 SUBTASK 3: Primary Key Selection (PKS)")
    print("-" * 60)
    print(f"Accuracy:             {metrics['primary_keys']['accuracy']:.3f}")

    print("\n📊 SUBTASK 4: Foreign Key Selection (FKS)")
    print("-" * 60)
    print(f"Accuracy:             {metrics['foreign_keys']['accuracy']:.3f}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total items evaluated: {metrics['answer']['total']}")
    print(f"Answer EM:            {metrics['answer']['em']:.1%}")
    print(f"Answer PM:            {metrics['answer']['pm']:.1%}")
    print(f"PKS Accuracy:         {metrics['primary_keys']['accuracy']:.1%}")
    print(f"FKS Accuracy:         {metrics['foreign_keys']['accuracy']:.1%}")
    print("=" * 60)

    # Save detailed results if output path provided
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(eval_results, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Detailed results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="MMQA Comprehensive Evaluation")
    parser.add_argument('--predictions', type=str, required=True,
                        help="Path to predictions JSONL file")
    parser.add_argument('--output', type=str, default=None,
                        help="Path to save detailed evaluation results (JSON)")
    parser.add_argument('--verbose', action='store_true',
                        help="Print detailed per-item results")

    args = parser.parse_args()

    print(f"Loading predictions from: {args.predictions}")
    predictions = load_predictions(args.predictions)
    print(f"Loaded {len(predictions)} predictions")

    print("\nEvaluating predictions...")
    eval_results = evaluate_dataset(predictions)

    print_evaluation_report(eval_results, args.output)

    if args.verbose:
        print("\n" + "=" * 60)
        print("DETAILED RESULTS (First 5 items)")
        print("=" * 60)
        for i, result in enumerate(eval_results['detailed_results'][:5]):
            print(f"\n[{i+1}] ID: {result['id']}")
            print(f"Question: {result['question'][:80]}...")
            print(f"Answer EM: {result['answer_em']:.0f}, PM: {result['answer_pm']:.2f}")
            print(f"  Pred: {result['pred_answer']}")
            print(f"  Target: {result['target_answer']}")
            print(f"PKS Acc: {result['pks_acc']:.2f}")
            print(f"  Pred PKs: {result['pred_pks']}")
            print(f"  Target PKs: {result['target_pks']}")
            print(f"FKS Acc: {result['fks_acc']:.2f}")
            print(f"  Pred FKs: {result['pred_fks']}")
            print(f"  Target FKs: {result['target_fks']}")


if __name__ == '__main__':
    main()
