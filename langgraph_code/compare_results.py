#!/usr/bin/env python3
"""
Compare Original MACT and LangGraph MACT results on MMQA dataset.

This script compares:
1. Answer accuracy (EM Score)
2. Subtask extraction quality (SQL, FK, PK)
3. Execution time
4. Format compliance with MMQA dataset

Author: CS8903 Benchmark Team
Date: 2025-10-12
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

def load_jsonl(file_path: Path) -> List[Dict]:
    """Load JSONL file into list of dicts."""
    results = []
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results

def calculate_subtask_metrics(results: List[Dict]) -> Dict[str, Any]:
    """Calculate metrics for subtask extraction."""
    # Support both field name formats
    sql_count = sum(1 for r in results if (r.get('predicted_sql') or r.get('pred_sql', 'N/A')) not in ['N/A', '', None])
    fk_count = sum(1 for r in results if (r.get('predicted_foreign_keys') or r.get('pred_foreign_keys', [])) and len(r.get('predicted_foreign_keys') or r.get('pred_foreign_keys', [])) > 0)
    pk_count = sum(1 for r in results if (r.get('predicted_primary_keys') or r.get('pred_primary_keys', [])) and len(r.get('predicted_primary_keys') or r.get('pred_primary_keys', [])) > 0)

    total = len(results)

    return {
        'sql_extraction_rate': sql_count / total if total > 0 else 0,
        'fk_extraction_rate': fk_count / total if total > 0 else 0,
        'pk_extraction_rate': pk_count / total if total > 0 else 0,
        'sql_count': sql_count,
        'fk_count': fk_count,
        'pk_count': pk_count,
        'total': total
    }

def calculate_answer_accuracy(results: List[Dict]) -> Dict[str, Any]:
    """Calculate answer accuracy metrics."""
    correct = 0
    total = 0

    for r in results:
        gold = r.get('gold_answer', '').strip().lower()
        pred = r.get('pred_answer', '').strip().lower()

        if gold and gold != 'n/a':
            total += 1
            if pred == gold:
                correct += 1

    return {
        'correct': correct,
        'total': total,
        'accuracy': correct / total if total > 0 else 0
    }

def print_comparison(original_file: Path, langgraph_file: Path):
    """Print comparison between Original and LangGraph MACT."""

    print("="*80)
    print("MACT IMPLEMENTATION COMPARISON - MMQA Dataset")
    print("="*80)
    print()

    # Load results
    original_results = load_jsonl(original_file)
    langgraph_results = load_jsonl(langgraph_file)

    print(f"Original MACT:   {len(original_results)} results loaded from {original_file.name}")
    print(f"LangGraph MACT:  {len(langgraph_results)} results loaded from {langgraph_file.name}")
    print()

    # Answer Accuracy
    print("-" * 80)
    print("1. ANSWER ACCURACY (SUBTASK 1)")
    print("-" * 80)

    orig_acc = calculate_answer_accuracy(original_results)
    lang_acc = calculate_answer_accuracy(langgraph_results)

    print(f"Original MACT:   {orig_acc['correct']}/{orig_acc['total']} correct = {orig_acc['accuracy']:.1%}")
    print(f"LangGraph MACT:  {lang_acc['correct']}/{lang_acc['total']} correct = {lang_acc['accuracy']:.1%}")
    print(f"Difference:      {lang_acc['accuracy'] - orig_acc['accuracy']:+.1%}")
    print()

    # Subtask Extraction
    print("-" * 80)
    print("2. SUBTASK EXTRACTION QUALITY (SUBTASKS 2-4)")
    print("-" * 80)

    orig_sub = calculate_subtask_metrics(original_results)
    lang_sub = calculate_subtask_metrics(langgraph_results)

    print(f"\nSQL Extraction (SUBTASK 2):")
    print(f"  Original MACT:   {orig_sub['sql_count']}/{orig_sub['total']} = {orig_sub['sql_extraction_rate']:.1%}")
    print(f"  LangGraph MACT:  {lang_sub['sql_count']}/{lang_sub['total']} = {lang_sub['sql_extraction_rate']:.1%}")

    print(f"\nForeign Keys Extraction (SUBTASK 3):")
    print(f"  Original MACT:   {orig_sub['fk_count']}/{orig_sub['total']} = {orig_sub['fk_extraction_rate']:.1%}")
    print(f"  LangGraph MACT:  {lang_sub['fk_count']}/{lang_sub['total']} = {lang_sub['fk_extraction_rate']:.1%}")

    print(f"\nPrimary Keys Extraction (SUBTASK 4):")
    print(f"  Original MACT:   {orig_sub['pk_count']}/{orig_sub['total']} = {orig_sub['pk_extraction_rate']:.1%}")
    print(f"  LangGraph MACT:  {lang_sub['pk_count']}/{lang_sub['total']} = {lang_sub['pk_extraction_rate']:.1%}")
    print()

    # Format Compliance
    print("-" * 80)
    print("3. MMQA FORMAT COMPLIANCE")
    print("-" * 80)

    # Check FK/PK format (should be lowercase with spaces)
    orig_format_ok = 0
    lang_format_ok = 0

    for r in original_results:
        fks = r.get('predicted_foreign_keys', [])
        pks = r.get('predicted_primary_keys', [])
        all_keys = fks + pks
        # Check if all are lowercase and no dots/underscores
        if all_keys and all(k.islower() and '.' not in k for k in all_keys):
            orig_format_ok += 1

    for r in langgraph_results:
        fks = r.get('predicted_foreign_keys', [])
        pks = r.get('predicted_primary_keys', [])
        all_keys = fks + pks
        if all_keys and all(k.islower() and '.' not in k for k in all_keys):
            lang_format_ok += 1

    print(f"Original MACT:   {orig_format_ok}/{orig_sub['total']} items with correct format")
    print(f"LangGraph MACT:  {lang_format_ok}/{lang_sub['total']} items with correct format")
    print(f"  Format: lowercase with spaces (e.g., 'department id', 'head id')")
    print()

    # Sample outputs
    print("-" * 80)
    print("4. SAMPLE OUTPUTS (First Item)")
    print("-" * 80)

    if original_results:
        print("\nOriginal MACT:")
        print(f"  Question: {original_results[0].get('question', 'N/A')[:80]}...")
        print(f"  Predicted Answer: {original_results[0].get('pred_answer', 'N/A')}")
        print(f"  Gold Answer: {original_results[0].get('gold_answer', 'N/A')}")
        print(f"  SQL: {original_results[0].get('predicted_sql', 'N/A')[:100]}...")
        print(f"  FKs: {original_results[0].get('predicted_foreign_keys', [])}")
        print(f"  PKs: {original_results[0].get('predicted_primary_keys', [])}")

    if langgraph_results:
        print("\nLangGraph MACT:")
        print(f"  Question: {langgraph_results[0].get('question', 'N/A')[:80]}...")
        print(f"  Predicted Answer: {langgraph_results[0].get('pred_answer', 'N/A')}")
        print(f"  Gold Answer: {langgraph_results[0].get('gold_answer', 'N/A')}")
        print(f"  SQL: {langgraph_results[0].get('predicted_sql', 'N/A')[:100]}...")
        print(f"  FKs: {langgraph_results[0].get('predicted_foreign_keys', [])}")
        print(f"  PKs: {langgraph_results[0].get('predicted_primary_keys', [])}")

    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Answer Accuracy:     LangGraph {lang_acc['accuracy']:.1%} vs Original {orig_acc['accuracy']:.1%} ({lang_acc['accuracy'] - orig_acc['accuracy']:+.1%})")
    print(f"SQL Extraction:      LangGraph {lang_sub['sql_extraction_rate']:.1%} vs Original {orig_sub['sql_extraction_rate']:.1%}")
    print(f"FK Extraction:       LangGraph {lang_sub['fk_extraction_rate']:.1%} vs Original {orig_sub['fk_extraction_rate']:.1%}")
    print(f"PK Extraction:       LangGraph {lang_sub['pk_extraction_rate']:.1%} vs Original {orig_sub['pk_extraction_rate']:.1%}")
    print("="*80)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python compare_results.py <original_jsonl> <langgraph_jsonl>")
        sys.exit(1)

    original_file = Path(sys.argv[1])
    langgraph_file = Path(sys.argv[2])

    if not original_file.exists():
        print(f"Error: Original MACT file not found: {original_file}")
        sys.exit(1)

    if not langgraph_file.exists():
        print(f"Error: LangGraph MACT file not found: {langgraph_file}")
        sys.exit(1)

    print_comparison(original_file, langgraph_file)
