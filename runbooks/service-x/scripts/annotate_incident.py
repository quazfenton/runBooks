#!/usr/bin/env python3
"""
Annotate Incident

Append incident annotations to the runbook YAML.
"""

import yaml
import argparse
import tempfile
import os
from datetime import datetime, timezone


def annotate_runbook(runbook_path, incident_id, cause, fix, symptoms=None, runbook_gap=None):
    try:
        with open(runbook_path, "r", encoding='utf-8') as f:
            runbook = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        print(f"Error reading runbook file: {e}")
        raise

    annotation = {
        "incident_id": incident_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cause": cause,
        "fix": fix
    }

    if symptoms:
        annotation["symptoms"] = symptoms if isinstance(symptoms, list) else [symptoms]
    if runbook_gap:
        annotation["runbook_gap"] = runbook_gap

    runbook.setdefault("annotations", []).append(annotation)

    # Perform atomic write using tempfile
    try:
        dir_path = os.path.dirname(runbook_path)
        if not dir_path:
            dir_path = '.'

        with tempfile.NamedTemporaryFile(mode='w', dir=dir_path, delete=False, encoding='utf-8') as tmp_file:
            yaml.dump(runbook, tmp_file, default_flow_style=False)
            tmp_path = tmp_file.name

        os.replace(tmp_path, runbook_path)
    except (yaml.YAMLError, OSError) as e:
        print(f"Error writing runbook file: {e}")
        raise


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