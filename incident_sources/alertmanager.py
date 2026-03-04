"""
Prometheus AlertManager Integration

Provides integration with Prometheus AlertManager for alert ingestion.
"""

import os
import hashlib
import hmac
from typing import Dict, Any, List, Optional
from datetime import datetime
import requests
from incident_sources.base import IncidentSource, Incident


class AlertManagerAlert(Incident):
    """Represents an alert from Prometheus AlertManager."""
    
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
        alert_name: Optional[str] = None,
        instance: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        annotations: Optional[Dict[str, str]] = None,
        generator_url: Optional[str] = None
    ):
        super().__init__(
            external_id=external_id,
            title=title,
            service=service,
            severity=severity,
            status=status,
            created_at=created_at,
            source='alertmanager',
            updated_at=updated_at,
            resolved_at=resolved_at,
            raw_payload=raw_payload,
            runbook_path=runbook_path
        )
        
        self.alert_name = alert_name
        self.instance = instance
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.generator_url = generator_url


class AlertManagerIntegration(IncidentSource):
    """
    Prometheus AlertManager integration.
    
    Supports:
    - Webhook parsing for real-time alert ingestion
    - Alertmanager API for querying alerts
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        webhook_secret: Optional[str] = None
    ):
        """
        Initialize AlertManager integration.
        
        Args:
            base_url: Alertmanager base URL (e.g., http://localhost:9093)
            webhook_secret: Optional secret for webhook validation
        """
        self.base_url = base_url or os.environ.get('ALERTMANAGER_URL', 'http://localhost:9093')
        self.webhook_secret = webhook_secret or os.environ.get('ALERTMANAGER_WEBHOOK_SECRET')
        
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json"
        })
    
    @property
    def source_name(self) -> str:
        return "alertmanager"
    
    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: str
    ) -> bool:
        """
        Validate AlertManager webhook signature.
        
        Note: AlertManager doesn't have built-in signature validation.
        This can be used with a proxy that adds signatures.
        """
        if not self.webhook_secret:
            return True  # Skip validation if no secret configured
        
        try:
            message = (timestamp + payload.decode('utf-8')).encode('utf-8')
            expected_sig = hmac.new(
                self.webhook_secret.encode(),
                message,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_sig)
        except Exception:
            return False
    
    def parse_webhook(self, payload: Dict[str, Any]) -> AlertManagerAlert:
        """
        Parse AlertManager webhook payload.
        
        Webhook payload structure:
        {
            "version": "4",
            "groupKey": "...",
            "status": "firing|resolved",
            "receiver": "...",
            "groupLabels": {...},
            "commonLabels": {...},
            "commonAnnotations": {...},
            "alerts": [
                {
                    "status": "firing|resolved",
                    "labels": {...},
                    "annotations": {...},
                    "startsAt": "2026-01-01T12:00:00Z",
                    "endsAt": "2026-01-01T13:00:00Z",
                    "generatorURL": "..."
                }
            ]
        }
        """
        # For webhook, we'll use the first alert in the group
        alerts = payload.get('alerts', [])
        
        if not alerts:
            raise ValueError("No alerts in webhook payload")
        
        alert = alerts[0]
        labels = alert.get('labels', {})
        annotations = alert.get('annotations', {})
        
        # Parse timestamps
        starts_at = self._parse_timestamp(alert.get('startsAt'))
        ends_at = self._parse_timestamp(alert.get('endsAt'))
        
        # Determine status
        status = alert.get('status', 'unknown')
        is_resolved = status == 'resolved' or (ends_at and ends_at < datetime.now(starts_at.tzinfo))
        
        # Map severity
        severity = labels.get('severity', labels.get('level', 'warning'))
        
        # Extract service from labels
        service = self._extract_service_from_labels(labels)
        
        # Generate ID from group key and fingerprint
        group_key = payload.get('groupKey', '')
        fingerprint = alert.get('fingerprint', '')
        external_id = f"{group_key}:{fingerprint}" if fingerprint else group_key
        
        # Create title
        alert_name = labels.get('alertname', 'Unknown Alert')
        title = annotations.get('summary', annotations.get('description', alert_name))
        
        return AlertManagerAlert(
            external_id=external_id,
            title=title,
            service=service,
            severity=severity,
            status=status,
            created_at=starts_at,
            updated_at=datetime.now() if not is_resolved else ends_at,
            resolved_at=ends_at if is_resolved else None,
            alert_name=alert_name,
            instance=labels.get('instance'),
            labels=labels,
            annotations=annotations,
            generator_url=alert.get('generatorURL'),
            raw_payload=payload
        )
    
    def sync_incidents(
        self,
        service_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
        filter_active: bool = True
    ) -> List[AlertManagerAlert]:
        """
        Sync alerts from AlertManager API.
        
        Args:
            service_id: Filter by service
            since: Filter by start time
            limit: Maximum alerts to fetch
            filter_active: If True, only fetch active alerts
        
        Returns:
            List of AlertManagerAlert objects
        """
        params = {
            'limit': limit,
            'active': str(filter_active).lower()
        }
        
        if service_id:
            params['filter'] = f'service="{service_id}"'
        
        try:
            response = self.session.get(
                f"{self.base_url}/api/v2/alerts",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            alerts_data = response.json()
            alerts = []
            
            for alert_data in alerts_data:
                alert = self._parse_api_alert(alert_data)
                alerts.append(alert)
            
            return alerts
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to sync alerts from AlertManager: {e}")
    
    def _parse_api_alert(self, alert_data: Dict[str, Any]) -> AlertManagerAlert:
        """Parse alert from AlertManager API response."""
        labels = alert_data.get('labels', {})
        annotations = alert_data.get('annotations', {})
        
        status = alert_data.get('status', {}).get('state', 'unknown')
        starts_at = self._parse_timestamp(alert_data.get('startsAt'))
        ends_at = self._parse_timestamp(alert_data.get('endsAt'))
        updated_at = self._parse_timestamp(alert_data.get('updatedAt'))
        
        severity = labels.get('severity', labels.get('level', 'warning'))
        service = self._extract_service_from_labels(labels)
        
        alert_name = labels.get('alertname', 'Unknown Alert')
        title = annotations.get('summary', annotations.get('description', alert_name))
        
        return AlertManagerAlert(
            external_id=alert_data.get('fingerprint', ''),
            title=title,
            service=service,
            severity=severity,
            status=status,
            created_at=starts_at,
            updated_at=updated_at,
            resolved_at=ends_at if status == 'resolved' else None,
            alert_name=alert_name,
            instance=labels.get('instance'),
            labels=labels,
            annotations=annotations,
            generator_url=alert_data.get('generatorURL'),
            raw_payload=alert_data
        )
    
    def _extract_service_from_labels(self, labels: Dict[str, str]) -> str:
        """Extract service name from alert labels."""
        # Try common service label names
        for key in ['service', 'service_name', 'job', 'namespace']:
            if key in labels:
                return labels[key]
        
        # Try to extract from alertname
        alertname = labels.get('alertname', '')
        if alertname:
            return alertname.lower().replace('_', '-')
        
        return 'unknown'
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO 8601 timestamp string."""
        if not timestamp_str:
            return None
        
        try:
            # Handle 'Z' suffix
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            return None
    
    def get_alert_groups(self) -> List[Dict[str, Any]]:
        """
        Get grouped alerts from AlertManager.
        
        Returns:
            List of alert groups
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/v2/alerts/groups",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to get alert groups: {e}")
    
    def silence_alert(
        self,
        matchers: List[Dict[str, str]],
        duration: str = "1h",
        created_by: str = "runbooks",
        comment: str = ""
    ) -> Dict[str, Any]:
        """
        Create a silence for matching alerts.
        
        Args:
            matchers: List of label matchers (e.g., [{"name": "alertname", "value": "HighCPU"}])
            duration: Silence duration (e.g., "1h", "30m", "2d")
            created_by: Creator name
            comment: Optional comment
        
        Returns:
            Silence ID
        """
        from datetime import timedelta
        
        # Parse duration
        duration_map = {
            's': timedelta(seconds=1),
            'm': timedelta(minutes=1),
            'h': timedelta(hours=1),
            'd': timedelta(days=1)
        }
        
        duration_unit = duration[-1]
        duration_value = int(duration[:-1])
        delta = duration_map.get(duration_unit, timedelta(hours=1)) * duration_value
        
        starts_at = datetime.utcnow()
        ends_at = starts_at + delta
        
        silence_data = {
            "matchers": matchers,
            "startsAt": starts_at.isoformat() + 'Z',
            "endsAt": ends_at.isoformat() + 'Z',
            "createdBy": created_by,
            "comment": comment
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/silences",
                json=silence_data,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to create silence: {e}")
    
    def delete_silence(self, silence_id: str) -> bool:
        """
        Delete a silence.
        
        Args:
            silence_id: Silence ID to delete
        
        Returns:
            True if successful
        """
        try:
            response = self.session.delete(
                f"{self.base_url}/api/v2/silence/{silence_id}",
                timeout=10
            )
            response.raise_for_status()
            return True
        
        except requests.RequestException:
            return False


def main():
    """Example usage of AlertManager integration."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(
        description="AlertManager integration"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:9093",
        help="AlertManager URL"
    )
    parser.add_argument(
        "--action",
        choices=['list', 'groups', 'silence'],
        default='list',
        help="Action to perform"
    )
    parser.add_argument(
        "--service",
        help="Filter by service"
    )
    parser.add_argument(
        "--active-only",
        action='store_true',
        help="Only show active alerts"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum alerts to show"
    )
    
    args = parser.parse_args()
    
    integration = AlertManagerIntegration(base_url=args.url)
    
    if args.action == 'list':
        alerts = integration.sync_incidents(
            service_id=args.service,
            filter_active=args.active_only,
            limit=args.limit
        )
        
        print(f"Found {len(alerts)} alerts:\n")
        for alert in alerts:
            status_icon = "🔴" if alert.status == 'firing' else "🟢"
            print(f"{status_icon} [{alert.severity}] {alert.alert_name}")
            print(f"   Service: {alert.service}")
            print(f"   Instance: {alert.instance}")
            print(f"   Summary: {alert.annotations.get('summary', 'N/A')}")
            print(f"   Started: {alert.created_at}")
            print()
    
    elif args.action == 'groups':
        groups = integration.get_alert_groups()
        print(json.dumps(groups, indent=2))
    
    elif args.action == 'silence':
        print("Silence action requires --matcher argument")


if __name__ == "__main__":
    main()
