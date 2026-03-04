#!/usr/bin/env python3
"""
Slack App Handler for Incident Annotations

This module handles Slack interactions for capturing incident annotations
and appending them to runbooks.
"""

import json
import yaml
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field, field_validator


class AnnotationInput(BaseModel):
    """Validated annotation input schema with security constraints."""
    incident_id: str = Field(..., min_length=1, max_length=100)
    symptoms: Optional[str] = Field(None, max_length=5000)
    root_cause: str = Field(..., min_length=1, max_length=2000)
    fix_applied: str = Field(..., min_length=1, max_length=2000)
    runbook_gaps: Optional[str] = Field(None, max_length=2000)
    runbook_path: str = Field(..., min_length=1, max_length=500)
    
    @field_validator('incident_id')
    @classmethod
    def validate_incident_id(cls, v):
        """Validate incident ID format - alphanumeric with dashes/underscores only."""
        if not re.match(r'^[A-Z0-9\-_]+$', v, re.IGNORECASE):
            raise ValueError(f'Invalid incident ID format: {v}. Use alphanumeric characters, dashes, and underscores only.')
        return v
    
    @field_validator('runbook_path')
    @classmethod
    def validate_runbook_path(cls, v):
        """Validate runbook path to prevent path traversal and injection."""
        if not v.endswith(('.yaml', '.yml')):
            raise ValueError('Runbook path must be a YAML file (.yaml or .yml)')
        if '..' in v:
            raise ValueError('Path traversal sequences (..) not allowed')
        if v.startswith('/') or v.startswith('\\'):
            raise ValueError('Absolute paths not allowed')
        if any(c in v for c in ['<', '>', '|', '&', ';', '$', '`']):
            raise ValueError('Invalid characters in path')
        return v


def validate_runbook_path_secure(user_path: str, base_dir: Path) -> Path:
    """
    Securely validate runbook path to prevent path traversal and symlink attacks.
    
    This implementation:
    1. Resolves to canonical paths
    2. Checks for symlink attacks
    3. Validates path prefix
    4. Ensures file exists within allowed directory
    
    Args:
        user_path: User-provided path (relative to base_dir)
        base_dir: Base directory that paths must be within
    
    Returns:
        Resolved Path object if valid
    
    Raises:
        ValueError: If path is invalid or attempts traversal
    """
    base_dir = base_dir.resolve()
    
    # Construct full path and resolve
    if Path(user_path).is_absolute():
        user_path_obj = Path(user_path).resolve()
    else:
        user_path_obj = (base_dir / user_path).resolve()
    
    # Check canonical path starts with base
    try:
        user_path_obj.relative_to(base_dir)
    except ValueError:
        raise ValueError(
            f"Path traversal detected: {user_path} resolves to {user_path_obj}, "
            f"which is outside allowed directory {base_dir}"
        )
    
    # Check for symlinks in path components (security hardening)
    for parent in user_path_obj.parents:
        if parent.is_symlink():
            raise ValueError(f"Symlinks not allowed in path: {parent}")
    
    if user_path_obj.is_symlink():
        raise ValueError(f"Runbook path cannot be a symlink: {user_path_obj}")
    
    # Verify file exists
    if not user_path_obj.exists():
        raise FileNotFoundError(f"Runbook file not found: {user_path_obj}")
    
    return user_path_obj


def create_annotation_from_slack_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cause": root_cause,
        "fix": fix_applied
    }
    
    if symptoms:
        annotation["symptoms"] = symptoms
    
    if runbook_gap_list:
        annotation["runbook_gap"] = runbook_gap_list[0] if len(runbook_gap_list) == 1 else runbook_gap_list
    
    return annotation, runbook_path


def append_annotation_to_runbook(runbook_path: str, annotation: Dict[str, Any]) -> None:
    """
    Append an annotation to the runbook YAML file with secure path validation.
    
    Args:
        runbook_path: Path to runbook YAML file (relative to project root)
        annotation: Annotation data to append
    
    Raises:
        ValueError: If path is invalid or security check fails
        FileNotFoundError: If runbook file doesn't exist
    """
    # Use secure path validation
    base_dir = Path(__file__).parent.parent  # Project root
    resolved_path = validate_runbook_path_secure(runbook_path, base_dir / "runbooks")
    
    # Read existing runbook
    with open(resolved_path, 'r', encoding='utf-8') as f:
        runbook = yaml.safe_load(f)
        if runbook is None:
            runbook = {}

    # Ensure annotations list exists
    if 'annotations' not in runbook:
        runbook['annotations'] = []
    
    # Validate annotations is a list
    if not isinstance(runbook['annotations'], list):
        runbook['annotations'] = []

    # Append annotation
    runbook['annotations'].append(annotation)

    # Atomic write using temporary file
    import tempfile
    import os
    
    temp_fd, temp_path = tempfile.mkstemp(
        suffix='.yaml',
        prefix='runbook_',
        dir=resolved_path.parent
    )
    
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            yaml.dump(runbook, f, default_flow_style=False, allow_unicode=True)
        
        # Atomic replace
        os.replace(temp_path, resolved_path)
    except Exception:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def handle_slack_annotation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a Slack modal submission and update the runbook with validation.
    
    Args:
        payload: Slack view_submission payload
    
    Returns:
        Slack response dict
    """
    try:
        # Extract and validate input
        annotation, runbook_path = create_annotation_from_slack_payload(payload)
        
        # Validate using Pydantic model
        try:
            validated_input = AnnotationInput(
                incident_id=annotation['incident_id'],
                symptoms='\n'.join(annotation.get('symptoms', [])) if annotation.get('symptoms') else None,
                root_cause=annotation['cause'],
                fix_applied=annotation['fix'],
                runbook_gaps=annotation.get('runbook_gap'),
                runbook_path=runbook_path
            )
        except ValueError as e:
            return {
                "response_action": "errors",
                "errors": {
                    "incident_id": str(e) if 'incident' in str(e).lower() else "runbook_path",
                    "runbook_path": str(e) if 'path' in str(e).lower() else None
                }
            }
        
        # Append with secure path handling
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
                            "text": f"✅ Successfully added annotation for incident *{validated_input.incident_id}* to `{validated_input.runbook_path}`"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Root cause: {validated_input.root_cause[:100]}..."
                            }
                        ]
                    }
                ]
            }
        }
    except FileNotFoundError as e:
        return {
            "response_action": "errors",
            "errors": {
                "runbook_path": f"Runbook file not found: {str(e)}"
            }
        }
    except ValueError as e:
        return {
            "response_action": "errors",
            "errors": {
                "runbook_path": f"Invalid path or input: {str(e)}"
            }
        }
    except Exception as e:
        # Log error in production (add proper logging)
        import logging
        logging.error(f"Error processing annotation: {e}", exc_info=True)
        
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