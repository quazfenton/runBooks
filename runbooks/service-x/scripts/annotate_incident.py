#!/usr/bin/env python3
"""
Annotate Incident

Append incident annotations to the runbook YAML.
"""

import yaml
import argparse
from datetime import datetime


def annotate_runbook(runbook_path, incident_id, cause, fix, symptoms=None, runbook_gap=None):
    with open(runbook_path, "r") as f:
        runbook = yaml.safe_load(f)
    
    annotation = {
        "incident_id": incident_id,
        "timestamp": datetime.utcnow().isoformat(),
        "cause": cause,
        "fix": fix
    }
    
    if symptoms:
        annotation["symptoms"] = symptoms if isinstance(symptoms, list) else [symptoms]
    if runbook_gap:
        annotation["runbook_gap"] = runbook_gap
    
    runbook.setdefault("annotations", []).append(annotation)
    
    with open(runbook_path, "w") as f:
        yaml.dump(runbook, f, default_flow_style=False)


def main():
    parser = argparse.ArgumentParser(description="Annotate a runbook with incident information")
    parser.add_argument("--runbook", required=True, help="Path to runbook YAML")
    parser.add_argument("--incident", required=True, help="Incident ID")
    parser.add_argument("--cause", required=True, help="Root cause")
    parser.add_argument("--fix", required=True, help="Fix applied")
    parser.add_argument("--symptoms", help="Symptoms observed (comma-separated)")
    parser.add_argument("--gap", help="Runbook gap identified")
    
    args = parser.parse_args()

    symptoms_list = args.symptoms.split(',') if args.symptoms else None
    annotate_runbook(args.runbook, args.incident, args.cause, args.fix, symptoms_list, args.gap)
    print(f"Annotation added to {args.runbook}")


if __name__ == "__main__":
    main()