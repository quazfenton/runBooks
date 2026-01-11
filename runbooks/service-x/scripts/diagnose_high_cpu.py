#!/usr/bin/env python3
"""
Diagnose High CPU Usage

This script fetches top CPU-consuming processes during an incident
and appends the diagnostic data to the runbook.
"""

import subprocess
import yaml
import json
import hashlib
from datetime import datetime
from pathlib import Path
import argparse


def get_top_processes(limit=10):
    """Return top CPU processes as a structured dictionary."""
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,%cpu,comm", "--sort=-%cpu", "--no-headers"],
            capture_output=True, text=True, timeout=10
        )
        
        processes = []
        for line in result.stdout.splitlines()[:limit]:
            parts = line.strip().split(None, 2)
            if len(parts) >= 3:
                pid, cpu, comm = parts[0], parts[1], parts[2]
                processes.append({
                    "pid": pid,
                    "cpu_percent": float(cpu),
                    "command": comm
                })
        
        return processes
    except Exception as e:
        return [{"error": str(e)}]


def generate_result_hash(result_blob):
    """Generate a hash of the diagnostic result for comparison."""
    result_str = json.dumps(result_blob, sort_keys=True, default=str)
    return hashlib.sha256(result_str.encode()).hexdigest()


def append_diagnostic_to_runbook(runbook_path, diagnostic_data):
    """Append diagnostic data to runbook YAML."""
    with open(runbook_path, "r") as f:
        runbook = yaml.safe_load(f) or {}
    
    # Create diagnostic record following the schema
    diagnostic_record = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": "system_monitor",
        "query": "get_top_processes",
        "result_hash": generate_result_hash(diagnostic_data),
        "result_blob": diagnostic_data,
        "provenance": "automated"
    }
    
    runbook.setdefault("diagnostics", []).append(diagnostic_record)
    
    with open(runbook_path, "w") as f:
        yaml.dump(runbook, f, default_flow_style=False)


def main():
    parser = argparse.ArgumentParser(description="Diagnose high CPU usage")
    parser.add_argument("--runbook", required=True, help="Path to runbook YAML")
    parser.add_argument("--limit", type=int, default=10, help="Number of top processes to show")
    
    args = parser.parse_args()
    
    top_processes = get_top_processes(args.limit)
    append_diagnostic_to_runbook(args.runbook, {"top_processes": top_processes})
    
    print(f"CPU diagnostics appended to {args.runbook}")
    for proc in top_processes[:5]:  # Show top 5
        if 'error' not in proc:
            print(f"  PID {proc['pid']}: {proc['cpu_percent']}% - {proc['command']}")


if __name__ == "__main__":
    main()