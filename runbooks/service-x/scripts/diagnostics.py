#!/usr/bin/env python3
"""
Structured Diagnostics System for Living Runbooks

This module provides functionality to:
1. Generate diagnostic records following the diagnostics schema
2. Append diagnostic records to runbooks
3. Compare diagnostic records across incidents
"""

import json
import yaml
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


def generate_result_hash(result_blob: Dict[str, Any]) -> str:
    """Generate a hash of the diagnostic result for comparison."""
    result_str = json.dumps(result_blob, sort_keys=True, default=str)
    return hashlib.sha256(result_str.encode()).hexdigest()


def create_diagnostic_record(
    source: str, 
    query: str, 
    result_blob: Dict[str, Any], 
    provenance: str = "automated"
) -> Dict[str, Any]:
    """Create a structured diagnostic record following the schema."""
    timestamp = datetime.utcnow().isoformat()
    result_hash = generate_result_hash(result_blob)
    
    return {
        "timestamp": timestamp,
        "source": source,
        "query": query,
        "result_hash": result_hash,
        "result_blob": result_blob,
        "provenance": provenance
    }


def append_diagnostic_to_runbook(runbook_path: Path, diagnostic_record: Dict[str, Any]) -> None:
    """Append a diagnostic record to the runbook YAML file."""
    with open(runbook_path, 'r') as f:
        runbook = yaml.safe_load(f)
    
    if 'diagnostics' not in runbook:
        runbook['diagnostics'] = []
    
    runbook['diagnostics'].append(diagnostic_record)
    
    with open(runbook_path, 'w') as f:
        yaml.dump(runbook, f, default_flow_style=False)


def get_system_processes() -> Dict[str, Any]:
    """Get top CPU-consuming processes as an example diagnostic."""
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,%cpu,comm", "--sort=-%cpu", "-H", "--no-headers"],
            capture_output=True, 
            text=True,
            timeout=10
        )
        
        processes = []
        for line in result.stdout.splitlines()[:10]:  # Top 10 processes
            parts = line.strip().split(None, 2)
            if len(parts) >= 3:
                pid, cpu, comm = parts[0], parts[1], parts[2]
                processes.append({
                    "pid": pid,
                    "cpu_percent": float(cpu),
                    "command": comm
                })
        
        return {
            "processes": processes,
            "total_processes": len(processes)
        }
    except Exception as e:
        return {
            "error": str(e),
            "processes": []
        }


def get_system_metrics() -> Dict[str, Any]:
    """Get system metrics as an example diagnostic."""
    try:
        # Get CPU usage
        with open('/proc/loadavg', 'r') as f:
            load_avg = f.read().strip().split()
        
        # Get memory usage
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.readlines()
        
        mem_total = mem_free = 0
        for line in meminfo:
            if line.startswith('MemTotal:'):
                mem_total = int(line.split()[1])
            elif line.startswith('MemFree:'):
                mem_free = int(line.split()[1])
        
        memory_usage = {
            "total_kb": mem_total,
            "free_kb": mem_free,
            "used_kb": mem_total - mem_free,
            "used_percent": (mem_total - mem_free) / mem_total * 100 if mem_total > 0 else 0
        } if mem_total > 0 else {}
        
        return {
            "load_average": {
                "1min": float(load_avg[0]),
                "5min": float(load_avg[1]),
                "15min": float(load_avg[2])
            },
            "memory": memory_usage
        }
    except Exception as e:
        return {
            "error": str(e),
            "load_average": {},
            "memory": {}
        }


def main():
    """Example usage of the diagnostics system."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate structured diagnostics for Living Runbooks")
    parser.add_argument("--runbook", required=True, help="Path to runbook YAML file")
    parser.add_argument("--source", required=True, help="Source of diagnostic (e.g., kubectl, datadog)")
    parser.add_argument("--query", required=True, help="Query that generated the diagnostic")
    parser.add_argument("--data", help="JSON string of diagnostic data (alternative to built-in diagnostics)")
    
    args = parser.parse_args()
    
    runbook_path = Path(args.runbook)
    
    if args.data:
        # Use provided data
        try:
            result_blob = json.loads(args.data)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON provided: {e}")
            exit(1)
    elif args.source == "system":
        # Generate system diagnostics
        result_blob = {
            "processes": get_system_processes(),
            "metrics": get_system_metrics()
        }
    else:
        print(f"Unknown diagnostic source: {args.source}")
        exit(1)
    
    diagnostic_record = create_diagnostic_record(
        source=args.source,
        query=args.query,
        result_blob=result_blob,
        provenance="automated"
    )
    
    append_diagnostic_to_runbook(runbook_path, diagnostic_record)
    print(f"Diagnostics appended to {runbook_path}")


if __name__ == "__main__":
    main()