"""
Datadog Alert Integration

Provides integration with Datadog for automatic alert ingestion.
"""

import os
import hashlib
import hmac
from typing import Dict, Any, List, Optional
from datetime import datetime
import requests
from incident_sources.base import IncidentSource, Incident


class DatadogAlert(Incident):
    """Represents an alert from Datadog."""
    
    def __init__(
        self,
        external_id: str,
        title: str,
        service: str,
        severity: str,
        status: str,
        created_at: datetime,
        updated_at: Optional[datetime] = None,
        resolved_at: Optional[datetime] = None,
        raw_payload: Optional[Dict[str, Any]] = None,
        runbook_path: Optional[str] = None,
        alert_type: Optional[str] = None,
        metric: Optional[str] = None,
        scope: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        super().__init__(
            external_id=external_id,
            title=title,
            service=service,
            severity=severity,
            status=status,
            created_at=created_at,
            source='datadog',
            updated_at=updated_at,
            resolved_at=resolved_at,
            raw_payload=raw_payload,
            runbook_path=runbook_path
        )
        
        self.alert_type = alert_type
        self.metric = metric
        self.scope = scope
        self.tags = tags or []


class DatadogIntegration(IncidentSource):
    """
    Datadog alert integration.
    
    Supports:
    - Webhook parsing for real-time alert ingestion
    - API sync for historical alert retrieval
    - Monitor management
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        app_key: Optional[str] = None,
        base_url: str = "https://api.datadoghq.com",
        webhook_secret: Optional[str] = None
    ):
        """
        Initialize Datadog integration.
        
        Args:
            api_key: Datadog API key (or set DATADOG_API_KEY env var)
            app_key: Datadog application key (or set DATADOG_APP_KEY env var)
            base_url: Datadog API base URL (use https://api.datadoghq.eu for EU)
            webhook_secret: Secret for webhook signature validation
        """
        self.api_key = api_key or os.environ.get('DATADOG_API_KEY')
        self.app_key = app_key or os.environ.get('DATADOG_APP_KEY')
        self.base_url = base_url
        self.webhook_secret = webhook_secret or os.environ.get('DATADOG_WEBHOOK_SECRET')
        
        if not self.api_key:
            raise ValueError(
                "Datadog API key required. Set DATADOG_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.session = requests.Session()
        self.session.headers.update({
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
            "Content-Type": "application/json"
        })
    
    @property
    def source_name(self) -> str:
        return "datadog"
    
    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: str
    ) -> bool:
        """
        Validate Datadog webhook signature.
        
        Datadog signs webhooks with HMAC-SHA256.
        
        Args:
            payload: Raw request body bytes
            signature: X-Datadog-Signature header (base64-encoded)
            timestamp: X-Datadog-Timestamp header
        
        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            return True
        
        try:
            import base64
            
            # Construct message
            message = (timestamp + payload.decode('utf-8')).encode('utf-8')
            
            # Calculate expected signature
            secret_bytes = self.webhook_secret.encode('utf-8')
            expected_sig = base64.b64encode(
                hmac.new(secret_bytes, message, hashlib.sha256).digest()
            ).decode('utf-8')
            
            # Compare signatures securely
            return hmac.compare_digest(signature, expected_sig)
        
        except Exception:
            return False
    
    def parse_webhook(self, payload: Dict[str, Any]) -> DatadogAlert:
        """
        Parse Datadog webhook payload into Alert object.
        
        Webhook payload structure:
        {
            "id": "...",
            "id_str": "...",
            "title": "...",
            "alert_type": "metric alert|log alert|...",
            "status": "triggered|recovered|warn|no data",
            "alert_transition": "triggered|recovered",
            "date": 1234567890,
            "hostname": "...",
            "tags": ["tag1:value1", ...],
            "org_id": "...",
            "org_name": "...",
            "metric": "...",
            "scope": "...",
            "event_id": "...",
            "message": "..."
        }
        
        Args:
            payload: Webhook payload
        
        Returns:
            DatadogAlert object
        """
        # Parse status
        status = payload.get('status', 'unknown')
        alert_transition = payload.get('alert_transition', '')
        
        # Map Datadog status to our severity
        severity_map = {
            'triggered': 'high',
            'recovered': 'resolved',
            'warn': 'medium',
            'no data': 'low'
        }
        severity = severity_map.get(status, 'unknown')
        
        # Parse timestamp
        alert_date = payload.get('date')
        created_at = datetime.fromtimestamp(alert_date) if alert_date else datetime.now()
        
        # Extract service from tags
        tags = payload.get('tags', [])
        service = self._extract_service_from_tags(tags)
        
        # Determine resolved time if recovered
        resolved_at = None
        if status == 'recovered' or alert_transition == 'recovered':
            resolved_at = created_at
        
        return DatadogAlert(
            external_id=str(payload.get('id', '')),
            title=payload.get('title', 'Untitled Alert'),
            service=service,
            severity=severity,
            status=status,
            created_at=created_at,
            resolved_at=resolved_at,
            alert_type=payload.get('alert_type'),
            metric=payload.get('metric'),
            scope=payload.get('scope'),
            tags=tags,
            raw_payload=payload
        )
    
    def sync_monitors(
        self,
        group_states: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[DatadogAlert]:
        """
        Sync monitors/alerts from Datadog API.
        
        Args:
            group_states: Filter by states (e.g., ['alert', 'warn', 'no data'])
            tags: Filter by tags
            limit: Maximum number of monitors to fetch
        
        Returns:
            List of DatadogAlert objects
        """
        params = {
            "limit": limit
        }
        
        if group_states:
            params["group_states"] = ",".join(group_states)
        
        if tags:
            params["tags"] = ",".join(tags)
        
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/monitor",
                params=params
            )
            response.raise_for_status()
            
            monitors = response.json()
            alerts = []
            
            for monitor in monitors:
                # Only include monitors in alert/warn/no data state
                overall_state = monitor.get('overall_state', '')
                if group_states and overall_state not in group_states:
                    continue
                
                alert = self._parse_monitor(monitor)
                alerts.append(alert)
            
            return alerts
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to sync monitors from Datadog: {e}")
    
    def sync_incidents(
        self,
        service_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[DatadogAlert]:
        """
        Sync incidents (alerts) from Datadog.
        
        Note: Datadog doesn't have a direct "incidents" API like PagerDuty.
        We sync monitors in alert state instead.
        
        Args:
            service_id: Filter by service (via tags)
            since: Filter by last updated
            limit: Maximum number to fetch
        
        Returns:
            List of DatadogAlert objects
        """
        group_states = ['alert', 'warn', 'no data']
        tags = [f"service:{service_id}"] if service_id else None
        
        return self.sync_monitors(group_states=group_states, tags=tags, limit=limit)
    
    def _parse_monitor(self, monitor_data: Dict[str, Any]) -> DatadogAlert:
        """Parse monitor from Datadog API response."""
        overall_state = monitor_data.get('overall_state', 'unknown')
        
        # Map state to severity
        severity_map = {
            'alert': 'high',
            'warn': 'medium',
            'no data': 'low',
            'OK': 'resolved'
        }
        severity = severity_map.get(overall_state, 'unknown')
        
        # Map state to status
        status_map = {
            'alert': 'triggered',
            'warn': 'warn',
            'no data': 'no_data',
            'OK': 'resolved'
        }
        status = status_map.get(overall_state, 'unknown')
        
        # Extract service from tags
        tags = monitor_data.get('tags', [])
        service = self._extract_service_from_tags(tags)
        
        return DatadogAlert(
            external_id=str(monitor_data.get('id', '')),
            title=monitor_data.get('name', 'Untitled Monitor'),
            service=service,
            severity=severity,
            status=status,
            created_at=datetime.now(),  # Monitors don't have created_at
            alert_type=monitor_data.get('type'),
            tags=tags,
            raw_payload=monitor_data
        )
    
    def _extract_service_from_tags(self, tags: List[str]) -> str:
        """Extract service name from Datadog tags."""
        for tag in tags:
            if tag.startswith('service:'):
                return tag.split(':', 1)[1]
            if tag.startswith('service_name:'):
                return tag.split(':', 1)[1]
        
        return 'unknown'
    
    def get_monitor_details(self, monitor_id: int) -> Dict[str, Any]:
        """
        Fetch full details for a specific monitor.
        
        Args:
            monitor_id: Datadog monitor ID
        
        Returns:
            Monitor details
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/monitor/{monitor_id}"
            )
            response.raise_for_status()
            return response.json()
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch monitor {monitor_id}: {e}")
    
    def mute_monitor(
        self,
        monitor_id: int,
        duration: Optional[int] = None,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mute a Datadog monitor.
        
        Args:
            monitor_id: Monitor ID to mute
            duration: Mute duration in seconds (None for indefinite)
            message: Optional mute message
        
        Returns:
            API response
        """
        data = {}
        
        if duration:
            data['duration'] = duration
        
        if message:
            data['message'] = message
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/monitor/{monitor_id}/mute"
            )
            response.raise_for_status()
            return response.json()
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to mute monitor {monitor_id}: {e}")
    
    def unmute_monitor(self, monitor_id: int) -> Dict[str, Any]:
        """
        Unmute a Datadog monitor.
        
        Args:
            monitor_id: Monitor ID to unmute
        
        Returns:
            API response
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/monitor/{monitor_id}/unmute"
            )
            response.raise_for_status()
            return response.json()
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to unmute monitor {monitor_id}: {e}")
    
    def search_logs(
        self,
        query: str,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search Datadog logs.
        
        Args:
            query: Log search query
            from_time: Start time
            to_time: End time
            limit: Maximum logs to return
        
        Returns:
            List of log entries
        """
        from v2 import ApiClient, Configuration
        from datadog_api_client.v2.api.logs_api import LogsApi
        
        # This would use the official Datadog API client
        # For now, return empty list - implement with official SDK if needed
        return []
