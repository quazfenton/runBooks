#!/usr/bin/env python3
"""
Suggestion Engine with Deterministic Parsing

This module analyzes past annotations to suggest runbook improvements
using rule-based parsing and frequency analysis.
"""

import yaml
import re
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Tuple
import argparse


# Define canonical causes and fixes patterns
CANONICAL_PATTERNS = {
    "causes": {
        r"memory\s+leak": "memory_leak",
        r"cpu\s+(?:usage|spike|high)": "high_cpu_usage",
        r"disk\s+(?:space|full)": "disk_space_issue",
        r"connection\s+(?:timeout|refused)": "connection_timeout",
        r"out\s+of\s+(?:memory|disk)": "resource_exhaustion",
        r"oomkilled": "oom_killed",
        r"network\s+(?:error|issue)": "network_issue",
        r"config(?:uration)?\s+(?:error|issue)": "configuration_error",
        r"dependency\s+(?:failure|down)": "dependency_failure",
        r"rate\s+(?:limit|throttling)": "rate_limiting"
    },
    "fixes": {
        r"increase(?:s|d)?\s+.*?(?:memory|cpu|resource)": "increase_resource_limits",
        r"restart(?:s|ed)?\s+.*?(?:pod|service|container)": "restart_component",
        r"scale(?:s|d)?\s+(?:up|out)": "scale_up_resources",
        r"rollback(?:s)?": "rollback_deployment",
        r"fix(?:es|ed)?\s+(?:config|configuration)": "fix_configuration",
        r"update(?:s|d)?\s+(?:version|image)": "update_component",
        r"add(?:s|ed)?\s+(?:timeout|retry)": "add_timeout_retry",
        r"clear(?:s|ed)?\s+(?:cache|buffer)": "clear_cache",
        r"kill(?:s|ed)?\s+(?:process|pod)": "kill_process",
        r"add(?:s|ed)?\s+(?:monitoring|alert)": "add_monitoring"
    }
}


def normalize_text(text: str) -> str:
    """Normalize text for pattern matching."""
    if not text:
        return ""
    return text.lower().strip()


def extract_canonical_causes(text: str) -> List[str]:
    """Extract canonical causes from text using deterministic patterns."""
    text = normalize_text(text)
    matches = []
    
    for pattern, canonical in CANONICAL_PATTERNS["causes"].items():
        if re.search(pattern, text):
            matches.append(canonical)
    
    return matches


def extract_canonical_fixes(text: str) -> List[str]:
    """Extract canonical fixes from text using deterministic patterns."""
    text = normalize_text(text)
    matches = []
    
    for pattern, canonical in CANONICAL_PATTERNS["fixes"].items():
        if re.search(pattern, text):
            matches.append(canonical)
    
    return matches


def analyze_runbook_annotations(runbook_path: Path) -> Dict[str, any]:
    """Analyze annotations in a runbook to extract patterns."""
    with open(runbook_path, 'r') as f:
    runbook = yaml.safe_load(f) or {}
    
    annotations = runbook.get('annotations', [])
    
    # Count occurrences of causes and fixes
    cause_counter = Counter()
    fix_counter = Counter()
    cause_fix_pairs = defaultdict(Counter)
    
    for annotation in annotations:
        causes = extract_canonical_causes(annotation.get('cause', ''))
        fixes = extract_canonical_fixes(annotation.get('fix', ''))
        
        for cause in causes:
            cause_counter[cause] += 1
        
        for fix in fixes:
            fix_counter[fix] += 1
        
        # Track cause-fix pairs
        for cause in causes:
            for fix in fixes:
                cause_fix_pairs[cause][fix] += 1
    
    return {
        'cause_counts': dict(cause_counter),
        'fix_counts': dict(fix_counter),
        'cause_fix_pairs': {k: dict(v) for k, v in cause_fix_pairs.items()},
        'total_incidents': len(annotations)
    }


def suggest_runbook_updates(runbook_path: Path, min_frequency: int = 2) -> List[Dict[str, str]]:
    """Suggest updates to the runbook based on analysis."""
    analysis = analyze_runbook_annotations(runbook_path)
    
    suggestions = []
    
    # Suggest adding steps for frequently occurring fixes
    for fix, count in analysis['fix_counts'].items():
        if count >= min_frequency:
            suggestions.append({
                'type': 'add_step',
                'item': fix,
                'count': count,
                'reason': f"'{fix}' applied in {count} incidents"
            })
    
    # Suggest adding monitoring for frequently occurring causes
    for cause, count in analysis['cause_counts'].items():
        if count >= min_frequency:
            suggestions.append({
                'type': 'add_monitoring',
                'item': cause,
                'count': count,
                'reason': f"'{cause}' identified as root cause in {count} incidents"
            })
    
    # Suggest cause-fix relationships
    for cause, fix_counts in analysis['cause_fix_pairs'].items():
        for fix, count in fix_counts.items():
            if count >= min_frequency:
                suggestions.append({
                    'type': 'add_relationship',
                    'item': f"{cause} -> {fix}",
                    'count': count,
                    'reason': f"'{cause}' typically fixed with '{fix}' in {count} incidents"
                })
    
    return suggestions


def print_suggestions(suggestions: List[Dict[str, str]]) -> None:
    """Print suggestions in a readable format."""
    if not suggestions:
        print("No suggestions found.")
        return
    
    print(f"Found {len(suggestions)} suggestions:")
    print()
    
    # Group suggestions by type
    by_type = defaultdict(list)
    for suggestion in suggestions:
        by_type[suggestion['type']].append(suggestion)
    
    for suggestion_type, items in by_type.items():
        print(f"{suggestion_type.replace('_', ' ').title()}:")
        for item in items:
            print(f"  - {item['item']} (seen {item['count']} times)")
            print(f"    Reason: {item['reason']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Suggest runbook updates based on past incidents")
    parser.add_argument("--runbook", required=True, help="Path to runbook YAML file")
    parser.add_argument("--min-frequency", type=int, default=2, help="Minimum frequency to suggest an update")
    parser.add_argument("--export", help="Export suggestions to a file")
    
    args = parser.parse_args()
    
    runbook_path = Path(args.runbook)
    
    if not runbook_path.exists():
        print(f"Error: Runbook file {runbook_path} does not exist")
        return
    
    suggestions = suggest_runbook_updates(runbook_path, args.min_frequency)
    print_suggestions(suggestions)
    
    if args.export:
        import json
        with open(args.export, 'w') as f:
            json.dump(suggestions, f, indent=2)
        print(f"Suggestions exported to {args.export}")


if __name__ == "__main__":
    main()