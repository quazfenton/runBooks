#!/usr/bin/env python3
"""
Diagnostics Comparison Tool

This module provides functionality to compare diagnostic records
across different incidents to identify patterns or changes.
"""

import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


def load_diagnostics_from_runbook(runbook_path: Path) -> List[Dict[str, Any]]:
    """Load all diagnostic records from a runbook."""
    with open(runbook_path, 'r') as f:
        runbook = yaml.safe_load(f)
    
    return runbook.get('diagnostics', [])


def find_similar_diagnostics(
    runbook_path: Path, 
    target_hash: str, 
    max_results: int = 5
) -> List[Dict[str, Any]]:
    """Find diagnostics with similar result hashes."""
    all_diagnostics = load_diagnostics_from_runbook(runbook_path)
    similar = []
    
    for diagnostic in all_diagnostics:
        if diagnostic.get('result_hash') == target_hash:
            similar.append(diagnostic)
            if len(similar) >= max_results:
                break
    
    return similar


def compare_diagnostics(
    diagnostic1: Dict[str, Any], 
    diagnostic2: Dict[str, Any]
) -> Dict[str, Any]:
    """Compare two diagnostic records and return differences."""
    result1 = diagnostic1.get('result_blob', {})
    result2 = diagnostic2.get('result_blob', {})
    
    # Simple comparison - in practice, you might want more sophisticated diffing
    comparison = {
        'timestamp1': diagnostic1.get('timestamp'),
        'timestamp2': diagnostic2.get('timestamp'),
        'source1': diagnostic1.get('source'),
        'source2': diagnostic2.get('source'),
        'differences': {}
    }
    
    # Compare keys that exist in both
    common_keys = set(result1.keys()) & set(result2.keys())
    for key in common_keys:
        if result1[key] != result2[key]:
            comparison['differences'][key] = {
                'value1': result1[key],
                'value2': result2[key]
            }
    
    # Keys only in first
    for key in set(result1.keys()) - set(result2.keys()):
        comparison['differences'][key] = {
            'value1': result1[key],
            'value2': None
        }
    
    # Keys only in second
    for key in set(result2.keys()) - set(result1.keys()):
        comparison['differences'][key] = {
            'value1': None,
            'value2': result2[key]
        }
    
    return comparison


def main():
    """Example usage of the diagnostics comparison tool."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare diagnostics from Living Runbooks")
    parser.add_argument("--runbook", required=True, help="Path to runbook YAML file")
    parser.add_argument("--compare-hash", help="Compare diagnostics with this hash")
    parser.add_argument("--list-all", action="store_true", help="List all diagnostics in the runbook")
    
    args = parser.parse_args()
    
    runbook_path = Path(args.runbook)
    
    if args.list_all:
        diagnostics = load_diagnostics_from_runbook(runbook_path)
        print(f"Found {len(diagnostics)} diagnostics in {runbook_path}:")
        for i, diagnostic in enumerate(diagnostics):
            print(f"{i+1}. {diagnostic.get('timestamp')} - {diagnostic.get('source')}: {diagnostic.get('query')}")
    
    if args.compare_hash:
        similar = find_similar_diagnostics(runbook_path, args.compare_hash)
        print(f"Found {len(similar)} similar diagnostics:")
        for diagnostic in similar:
            print(json.dumps(diagnostic, indent=2))


if __name__ == "__main__":
    main()