"""
Base Incident Source Module

Abstract base class for all incident source integrations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# Valid severity and status values for validation
VALID_SEVERITIES: Set[str] = {'critical', 'high', 'medium', 'low', 'unknown'}
VALID_STATUSES: Set[str] = {'triggered', 'acknowledged', 'resolved', 'closed', 'unknown'}


@dataclass
class Incident:
    """
    Represents an incident from any source.
    
    Attributes:
        external_id: Unique identifier from the source system
        title: Human-readable incident title
        service: Affected service name
        severity: Incident severity (critical/high/medium/low/unknown)
        status: Current status (triggered/acknowledged/resolved/closed/unknown)
        created_at: Incident creation timestamp
        source: Source system name (e.g., 'pagerduty', 'datadog')
        updated_at: Last update timestamp
        resolved_at: Resolution timestamp
        raw_payload: Original payload from source
        runbook_path: Path to associated runbook
    """
    external_id: str
    title: str
    service: str
    severity: str
    status: str
    created_at: datetime
    source: str
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    raw_payload: Optional[Dict[str, Any]] = field(default_factory=dict)
    runbook_path: Optional[str] = None
    
    def __post_init__(self):
        """Validate incident data after initialization."""
        # Validate required fields
        if not self.external_id or not isinstance(self.external_id, str):
            raise ValueError(f"external_id must be a non-empty string, got: {self.external_id!r}")
        
        if not self.title or not isinstance(self.title, str):
            raise ValueError(f"title must be a non-empty string, got: {self.title!r}")
        
        if not self.service or not isinstance(self.service, str):
            raise ValueError(f"service must be a non-empty string, got: {self.service!r}")
        
        # Validate severity is known value
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"severity must be one of {VALID_SEVERITIES}, got: {self.severity!r}"
            )
        
        # Validate status is known value
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"status must be one of {VALID_STATUSES}, got: {self.status!r}"
            )
        
        # Validate created_at is datetime
        if not isinstance(self.created_at, datetime):
            raise ValueError(
                f"created_at must be datetime, got: {type(self.created_at)}"
            )
        
        # Validate source is set
        if not self.source or not isinstance(self.source, str):
            raise ValueError(f"source must be a non-empty string, got: {self.source!r}")
        
        # Validate resolved_at is after created_at if both exist
        if self.resolved_at and self.created_at:
            if self.resolved_at < self.created_at:
                raise ValueError(
                    f"resolved_at ({self.resolved_at}) cannot be before "
                    f"created_at ({self.created_at})"
                )
        
        # Validate updated_at is after created_at if both exist
        if self.updated_at and self.created_at:
            if self.updated_at < self.created_at:
                raise ValueError(
                    f"updated_at ({self.updated_at}) cannot be before "
                    f"created_at ({self.created_at})"
                )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert incident to dictionary for JSON serialization.
        
        Returns:
            Dict with all incident fields, None for optional fields not set
        """
        return {
            'external_id': self.external_id,
            'title': self.title,
            'service': self.service,
            'severity': self.severity,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'source': self.source,
            'runbook_path': self.runbook_path,
            'raw_payload': self.raw_payload if self.raw_payload else None
        }


class IncidentSource(ABC):
    """Abstract base class for incident sources."""
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return source name (e.g., 'pagerduty', 'datadog')."""
        pass
    
    @abstractmethod
    def parse_webhook(self, payload: Dict[str, Any]) -> Incident:
        """
        Parse incoming webhook payload into Incident object.
        
        Args:
            payload: Webhook payload from source
        
        Returns:
            Incident object
        """
        pass
    
    @abstractmethod
    def sync_incidents(
        self,
        service_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Incident]:
        """
        Sync incidents from source API.
        
        Args:
            service_id: Filter by service ID
            since: Only fetch incidents since this time
            limit: Maximum number of incidents to fetch
        
        Returns:
            List of Incident objects
        """
        pass
    
    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: str
    ) -> bool:
        """
        Validate webhook signature.
        
        Default implementation returns False to force explicit override.
        Subclasses that require signature validation MUST override this method.
        
        Args:
            payload: Raw request body bytes
            signature: Signature header value
            timestamp: Timestamp header value

        Returns:
            bool: False - indicates validation not implemented
                  Subclasses should return True only if signature is valid
        """
        # Explicitly return False to indicate validation not implemented
        # This prevents accidental acceptance of unvalidated webhooks
        logger.warning(
            f"{self.__class__.__name__}.validate_webhook_signature() called but not implemented. "
            "Webhook will be rejected. Implement this method in subclass if signature validation is required."
        )
        return False
