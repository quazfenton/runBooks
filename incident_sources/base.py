"""
Base Incident Source Module

Abstract base class for all incident source integrations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Incident:
    """Represents an incident from any source."""
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert incident to dictionary."""
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
            'runbook_path': self.runbook_path
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
        Validate webhook signature (optional, override in subclasses).
        
        Args:
            payload: Raw request body
            signature: Signature header value
            timestamp: Timestamp header value
        
        Returns:
            True if valid, False otherwise
        """
        # Default implementation - override in subclasses that require signature validation
        return True
