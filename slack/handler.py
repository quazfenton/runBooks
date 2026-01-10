#!/usr/bin/env python3
"""
Slack App Handler for Incident Annotations

This module handles Slack interactions for capturing incident annotations
and appending them to runbooks.
"""

import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


def create_annotation_from_slack_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create an annotation from a Slack modal submission payload."""
    state_values = payload['view']['state']['values']
    
    # Extract values from the modal
    incident_id = state_values['incident_id']['input']['value']
    symptoms_text = state_values['symptoms']['input']['value']
    root_cause = state_values['root_cause']['input']['value']
    fix_applied = state_values['fix_applied']['input']['value']
    runbook_gaps = state_values['runbook_gaps']['input']['value']
    runbook_path = state_values['runbook_path']['input']['value']
    
    # Parse symptoms and runbook gaps as lists if they contain multiple items
    symptoms = [s.strip() for s in symptoms_text.split('\n') if s.strip()]
    runbook_gap_list = [g.strip() for g in runbook_gaps.split('\n') if g.strip()]
    
    annotation = {
        "incident_id": incident_id,
        "timestamp": datetime.utcnow().isoformat(),
        "cause": root_cause,
        "fix": fix_applied
    }
    
    if symptoms:
        annotation["symptoms"] = symptoms
    
    if runbook_gap_list:
        annotation["runbook_gap"] = runbook_gap_list[0] if len(runbook_gap_list) == 1 else runbook_gap_list
    
    return annotation, runbook_path


def append_annotation_to_runbook(runbook_path: str, annotation: Dict[str, Any]) -> None:
    """Append an annotation to the runbook YAML file."""
    runbook_file = Path(runbook_path)
    
    with open(runbook_file, 'r') as f:
        runbook = yaml.safe_load(f)
    
    if 'annotations' not in runbook:
        runbook['annotations'] = []
    
    runbook['annotations'].append(annotation)
    
    with open(runbook_file, 'w') as f:
        yaml.dump(runbook, f, default_flow_style=False)


def handle_slack_annotation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle a Slack modal submission and update the runbook."""
    try:
        annotation, runbook_path = create_annotation_from_slack_payload(payload)
        append_annotation_to_runbook(runbook_path, annotation)
        
        return {
            "response_action": "push",
            "view": {
                "type": "modal",
                "callback_id": "annotation_confirmation",
                "title": {
                    "type": "plain_text",
                    "text": "Annotation Saved"
                },
                "close": {
                    "type": "plain_text",
                    "text": "Close"
                },
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Successfully added annotation for incident {annotation['incident_id']} to {runbook_path}"
                        }
                    }
                ]
            }
        }
    except Exception as e:
        return {
            "response_action": "errors",
            "errors": {
                "runbook_path": f"Error processing annotation: {str(e)}"
            }
        }


def main():
    """Example usage - this would typically be called from a web framework like Flask/Django."""
    # This is a simplified example of what the payload would look like
    example_payload = {
        "view": {
            "state": {
                "values": {
                    "incident_id": {
                        "input": {
                            "value": "INC-20260104-001"
                        }
                    },
                    "symptoms": {
                        "input": {
                            "value": "High CPU usage\n5xx errors in logs"
                        }
                    },
                    "root_cause": {
                        "input": {
                            "value": "Memory leak in service X"
                        }
                    },
                    "fix_applied": {
                        "input": {
                            "value": "Increased pod memory limits"
                        }
                    },
                    "runbook_gaps": {
                        "input": {
                            "value": "Missing step to check pod memory usage"
                        }
                    },
                    "runbook_path": {
                        "input": {
                            "value": "runbooks/service-x/runbook.yaml"
                        }
                    }
                }
            }
        }
    }
    
    result = handle_slack_annotation(example_payload)
    print("Slack response:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()