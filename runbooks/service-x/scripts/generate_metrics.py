#!/usr/bin/env python3
"""
Runbook Health Metrics Generator

This script analyzes runbooks to generate health metrics for the dashboard.
"""

import yaml
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter, defaultdict
import argparse


def get_runbook_age(runbook_path):
    """Calculate the age of a runbook based on its last updated field."""
    with open(runbook_path, 'r') as f:
        runbook = yaml.safe_load(f)
    
    last_updated_str = runbook.get('last_updated')
    if not last_updated_str:
        # Fallback to file modification time
        return (datetime.now() - datetime.fromtimestamp(runbook_path.stat().st_mtime)).days
    
    try:
        last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
        return (datetime.now(last_updated.tzinfo) - last_updated).days
    except ValueError:
        # If date parsing fails, use file modification time
        return (datetime.now() - datetime.fromtimestamp(runbook_path.stat().st_mtime)).days


def categorize_age(days):
    """Categorize runbook age."""
    if days <= 30:
        return '0-30 days'
    elif days <= 60:
        return '31-60 days'
    elif days <= 90:
        return '61-90 days'
    else:
        return '90+ days'


def analyze_runbook(runbook_path):
    """Analyze a single runbook for metrics."""
    with open(runbook_path, 'r') as f:
        runbook = yaml.safe_load(f)
    
    annotations = runbook.get('annotations', [])
    diagnostics = runbook.get('diagnostics', [])
    
    # Calculate metrics
    age = get_runbook_age(runbook_path)
    annotation_count = len(annotations)
    diagnostic_count = len(diagnostics)
    
    # Extract causes and fixes from annotations
    causes = []
    fixes = []
    for annotation in annotations:
        if 'cause' in annotation:
            causes.append(annotation['cause'])
        if 'fix' in annotation:
            fixes.append(annotation['fix'])
    
    return {
        'path': str(runbook_path),
        'title': runbook.get('title', 'Unknown'),
        'age': age,
        'age_category': categorize_age(age),
        'annotation_count': annotation_count,
        'diagnostic_count': diagnostic_count,
        'causes': causes,
        'fixes': fixes,
        'last_updated': runbook.get('last_updated')
    }


def analyze_all_runbooks(runbooks_dir):
    """Analyze all runbooks in a directory."""
    runbooks_dir = Path(runbooks_dir)
    runbook_files = list(runbooks_dir.rglob('runbook.yaml'))
    
    all_metrics = []
    for runbook_file in runbook_files:
        try:
            metrics = analyze_runbook(runbook_file)
            all_metrics.append(metrics)
        except Exception as e:
            print(f"Error analyzing {runbook_file}: {e}")
    
    return all_metrics


def generate_dashboard_data(runbooks_dir):
    """Generate dashboard data from runbook analysis."""
    metrics = analyze_all_runbooks(runbooks_dir)
    
    if not metrics:
        return {
            'totalRunbooks': 0,
            'staleRunbooks': 0,
            'totalAnnotations': 0,
            'avgResolutionTime': 0,
            'incidentsByService': {},
            'usageByService': {},
            'topFixes': [],
            'runbookAges': []
        }
    
    # Calculate aggregate metrics
    total_runbooks = len(metrics)
    stale_runbooks = sum(1 for m in metrics if m['age'] > 90)  # More than 90 days old
    total_annotations = sum(m['annotation_count'] for m in metrics)
    
    # Calculate average resolution time (placeholder - would need actual incident data)
    avg_resolution_time = 24.5  # Placeholder value
    
    # Count incidents by service (extract from runbook titles or paths)
    incidents_by_service = Counter()
    usage_by_service = Counter()
    all_fixes = []
    
    for metric in metrics:
        service_name = Path(metric['path']).parent.name
        incidents_by_service[service_name] += metric['annotation_count']
        usage_by_service[service_name] += 1  # Each runbook represents usage
        
        # Collect all fixes
        all_fixes.extend(metric['fixes'])
    
    # Count top fixes
    fix_counts = Counter(all_fixes)
    top_fixes = [{'name': fix, 'count': count} for fix, count in fix_counts.most_common(10)]
    
    # Age distribution
    age_distribution = Counter(m['age_category'] for m in metrics)
    runbook_ages = [{'label': label, 'count': count} for label, count in age_distribution.items()]
    
    return {
        'totalRunbooks': total_runbooks,
        'staleRunbooks': stale_runbooks,
        'totalAnnotations': total_annotations,
        'avgResolutionTime': avg_resolution_time,
        'incidentsByService': dict(incidents_by_service),
        'usageByService': dict(usage_by_service),
        'topFixes': top_fixes,
        'runbookAges': runbook_ages
    }


def main():
    parser = argparse.ArgumentParser(description="Generate runbook health metrics for dashboard")
    parser.add_argument("--runbooks-dir", default="runbooks", help="Directory containing runbooks")
    parser.add_argument("--output", default="dashboard/data.json", help="Output file for dashboard data")
    
    args = parser.parse_args()
    
    dashboard_data = generate_dashboard_data(args.runbooks_dir)
    
    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write data to JSON file
    with open(output_path, 'w') as f:
        json.dump(dashboard_data, f, indent=2)
    
    print(f"Dashboard data generated and saved to {args.output}")
    print(f"Analyzed {dashboard_data['totalRunbooks']} runbooks")
    print(f"Found {dashboard_data['totalAnnotations']} total annotations")


if __name__ == "__main__":
    main()