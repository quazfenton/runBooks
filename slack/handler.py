#!/usr/bin/env python3
"""
Slack App Handler for Incident Annotations

This module handles Slack interactions for capturing incident annotations
and appending them to runbooks.

Security Features:
- Atomic path validation with symlink protection
- Input validation via Pydantic models
- Secure temp file handling
"""

import json
import yaml
import re
import os
import errno
import stat
import tempfile
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Union
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


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


class PathSecurityError(Exception):
    """Raised when path validation fails."""
    pass


def validate_runbook_path_secure(user_path: str, base_dir: Path) -> Tuple[Path, str]:
    """
    Securely validate and read runbook with atomic operations.
    
    This implementation prevents:
    1. TOCTOU (Time-of-Check to Time-of-Use) race conditions
    2. Symlink attacks via O_NOFOLLOW
    3. Path traversal via normpath validation
    
    Args:
        user_path: User-provided path (relative to base_dir)
        base_dir: Base directory that paths must be within
        
    Returns:
        Tuple of (resolved_path, file_content)
        
    Raises:
        PathSecurityError: If path is invalid or attempts traversal
        FileNotFoundError: If runbook file doesn't exist
    """
    base_dir = base_dir.resolve()
    
    # Reject absolute paths immediately
    if Path(user_path).is_absolute():
        raise PathSecurityError("Absolute paths not allowed")
    
    # Reject path traversal sequences
    if '..' in user_path:
        raise PathSecurityError("Path traversal sequences (..) not allowed")
    
    # Normalize path without resolving symlinks
    user_path_obj = base_dir / user_path
    normalized = os.path.normpath(str(user_path_obj))
    
    # Verify normalized path is within base
    if not normalized.startswith(str(base_dir)):
        raise PathSecurityError(
            f"Path escapes allowed directory: {normalized}"
        )
    
    # Check for symlinks before opening
    path_obj = Path(normalized)
    if path_obj.is_symlink():
        raise PathSecurityError(f"Symlinks not allowed: {path_obj}")
    
    # Check parent directories for symlinks
    for parent in path_obj.parents:
        if parent.is_symlink():
            raise PathSecurityError(f"Symlink in path: {parent}")
    
    # Open file with O_NOFOLLOW to prevent symlink race conditions
    # Note: O_NOFOLLOW is not available on Windows, so we do a pre-check
    try:
        # On Windows, we already checked for symlinks above
        # On Unix, use O_NOFOLLOW for additional protection
        if hasattr(os, 'O_NOFOLLOW'):
            fd = os.open(normalized, os.O_RDONLY | os.O_NOFOLLOW)
        else:
            # Windows fallback - already checked for symlinks above
            fd = os.open(normalized, os.O_RDONLY)
        
        with os.fdopen(fd, 'r', encoding='utf-8') as f:
            content = f.read()
        return path_obj, content
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise PathSecurityError(f"Symlink detected: {normalized}")
        if e.errno == errno.ENOENT:
            raise FileNotFoundError(f"Runbook file not found: {normalized}")
        raise PathSecurityError(f"Error accessing file: {e}")


def validate_runbook_path_secure_legacy(user_path: str, base_dir: Path) -> Path:
    """
    Legacy path validation (deprecated - use validate_runbook_path_secure instead).
    
    DEPRECATED: This function has a TOCTOU race condition.
    Only use for backward compatibility during migration.
    
    Args:
        user_path: User-provided path (relative to base_dir)
        base_dir: Base directory that paths must be within
        
    Returns:
        Resolved Path object if valid
        
    Raises:
        ValueError: If path is invalid or attempts traversal
    """
    import warnings
    warnings.warn(
        "validate_runbook_path_secure_legacy is deprecated. "
        "Use validate_runbook_path_secure() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
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


def sanitize_for_yaml(value: Any) -> Any:
    """
    Sanitize values before YAML serialization to prevent tag injection attacks.
    
    YAML deserialization can execute arbitrary code via tags like !!python/object.
    This function escapes potential injection vectors.
    
    Args:
        value: Value to sanitize
        
    Returns:
        Sanitized value safe for YAML serialization
    """
    if isinstance(value, str):
        # Remove potential YAML tag injection
        if value.startswith('!!') or value.startswith('!'):
            value = f"'{value}'"
        # Escape control characters that could cause issues
        value = value.replace('\x00', '').replace('\x08', '')
    elif isinstance(value, dict):
        return {k: sanitize_for_yaml(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [sanitize_for_yaml(v) for v in value]
    return value


def append_annotation_to_runbook(runbook_path: str, annotation: Dict[str, Any]) -> None:
    """
    Append an annotation to the runbook YAML file with secure path validation.
    
    Security features:
    - Atomic path validation with O_NOFOLLOW
    - Secure temp file with 0600 permissions
    - YAML output sanitization
    
    Args:
        runbook_path: Path to runbook YAML file (relative to project root)
        annotation: Annotation data to append

    Raises:
        PathSecurityError: If path is invalid or security check fails
        FileNotFoundError: If runbook file doesn't exist
    """
    # Use secure path validation (returns tuple of path and content)
    base_dir = Path(__file__).parent.parent  # Project root
    resolved_path, content = validate_runbook_path_secure(
        runbook_path, 
        base_dir / "runbooks"
    )

    # Parse existing runbook from secure content
    runbook = yaml.safe_load(content)
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

    # Sanitize runbook before YAML serialization
    runbook = sanitize_for_yaml(runbook)

    # Atomic write using temporary file with secure permissions
    temp_fd, temp_path = tempfile.mkstemp(
        suffix='.yaml',
        prefix='runbook_',
        dir=resolved_path.parent
    )

    try:
        # Set restrictive permissions (owner read/write only - 0600)
        os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
        
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            yaml.dump(
                runbook, 
                f, 
                default_flow_style=False, 
                allow_unicode=True,
                sort_keys=False  # Preserve field order
            )

        # Atomic replace
        os.replace(temp_path, resolved_path)
        logger.info(f"Successfully appended annotation to {resolved_path}")
        
    except Exception as e:
        logger.error(f"Error writing annotation to {resolved_path}: {e}", exc_info=True)
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