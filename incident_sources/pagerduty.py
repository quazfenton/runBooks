"""
PagerDuty Incident Integration

Provides integration with PagerDuty for automatic incident creation and sync.
"""

import os
import hmac
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from incident_sources.base import IncidentSource, Incident, logger


class PagerDutyIncident(Incident):
    """Represents an incident from PagerDuty."""
    
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
        incident_number: Optional[int] = None,
        description: Optional[str] = None,
        escalations: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(
            external_id=external_id,
            title=title,
            service=service,
            severity=severity,
            status=status,
            created_at=created_at,
            source='pagerduty',
            updated_at=updated_at,
            resolved_at=resolved_at,
            raw_payload=raw_payload,
            runbook_path=runbook_path
        )
        
        self.incident_number = incident_number
        self.description = description
        self.escalations = self._validate_escalations(escalations)
    
    @staticmethod
    def _validate_escalations(escalations: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Validate escalation data structure.
        
        Args:
            escalations: List of escalation dictionaries
            
        Returns:
            List of validated escalation dicts, empty list if none provided
        """
        if not escalations:
            return []
        
        validated = []
        for esc in escalations:
            if isinstance(esc, dict) and 'level' in esc:
                validated.append(esc)
            else:
                logger.warning(f"Invalid escalation data structure: {esc!r}")
        
        return validated


class PagerDutyIntegration(IncidentSource):
    """
    PagerDuty incident integration.
    
    Supports:
    - Webhook parsing for real-time incident creation
    - API sync for historical incident retrieval
    - Signature validation for webhook security
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.pagerduty.com",
        webhook_secret: Optional[str] = None,
        request_timeout: Optional[float] = None
    ):
        """
        Initialize PagerDuty integration.

        Args:
            api_key: PagerDuty API token (or set PAGERDUTY_API_KEY env var)
            base_url: PagerDuty API base URL
            webhook_secret: Secret for webhook signature validation
            request_timeout: HTTP request timeout in seconds (default: 30s from env)
        """
        self.api_key = api_key or os.environ.get('PAGERDUTY_API_KEY')
        self.base_url = base_url
        self.webhook_secret = webhook_secret or os.environ.get('PAGERDUTY_WEBHOOK_SECRET')
        
        # Configurable timeout with env var fallback (default 30 seconds)
        timeout_ms = int(os.getenv('PAGERDUTY_TIMEOUT_MS', '30000'))
        self.request_timeout = request_timeout if request_timeout is not None else (timeout_ms / 1000.0)

        if not self.api_key:
            raise ValueError(
                "PagerDuty API key required. Set PAGERDUTY_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token token={self.api_key}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Content-Type": "application/json"
        })
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _make_request_with_retry(self, method: str, url: str, **kwargs):
        """
        Make HTTP request with retry for transient failures.
        
        Uses exponential backoff: 2s, 4s, 8s (max 3 attempts)
        
        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            url: Request URL
            **kwargs: Additional arguments passed to session.request()
        
        Returns:
            requests.Response object
        
        Raises:
            requests.RequestException: After all retries exhausted
        """
        # Ensure timeout is set
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.request_timeout
        
        return self.session.request(method, url, **kwargs)

    @property
    def source_name(self) -> str:
        return "pagerduty"
    
    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: str
    ) -> bool:
        """
        Validate PagerDuty webhook signature with replay attack prevention.

        PagerDuty signs webhooks with HMAC-SHA256. The signature format is:
        v0=base64(hmac-sha256(secret, timestamp + body))

        SECURITY ENHANCED:
        - Timestamp validation to prevent replay attacks (5-minute window)
        - Constant-time signature comparison
        - Signature version validation

        Args:
            payload: Raw request body bytes
            signature: X-PagerDuty-Signature header
            timestamp: X-PagerDuty-Timestamp header

        Returns:
            bool: True if signature is valid, False if invalid or not configured

        Note:
            Returns False (not True) when no secret is configured to prevent
            accidental acceptance of unvalidated webhooks in production.
        """
        import time
        
        if not self.webhook_secret:
            # Log warning and return False to prevent unvalidated webhooks
            logger.warning(
                "PagerDuty webhook secret not configured. "
                "Webhook signature validation disabled - rejecting webhook. "
                "Set PAGERDUTY_WEBHOOK_SECRET environment variable."
            )
            return False

        try:
            # SECURITY: Validate timestamp format
            if not timestamp or not timestamp.isdigit():
                logger.warning("Invalid timestamp format: not numeric")
                return False

            # SECURITY: Prevent replay attacks - reject timestamps older than 5 minutes
            current_time = int(time.time())
            try:
                webhook_time = int(timestamp)
                time_diff = abs(current_time - webhook_time)
                if time_diff > 300:  # 5 minutes
                    logger.warning(
                        f"Webhook timestamp too old: {time_diff}s difference. "
                        "Possible replay attack."
                    )
                    return False
            except ValueError:
                logger.warning("Invalid timestamp: cannot parse as integer")
                return False

            # Parse signature (format: "v0=base64_signature")
            if '=' not in signature:
                logger.warning("Invalid signature format: missing '=' separator")
                return False

            version, provided_sig = signature.split('=', 1)
            if version != 'v0':
                logger.warning(f"Unknown signature version: {version}")
                return False

            # Construct message
            message = (timestamp + payload.decode('utf-8')).encode('utf-8')

            # Calculate expected signature
            secret_bytes = self.webhook_secret.encode('utf-8')
            expected_sig = hmac.new(
                secret_bytes,
                message,
                hashlib.sha256
            ).hexdigest()

            # Compare signatures securely (constant-time)
            is_valid = hmac.compare_digest(provided_sig, expected_sig)

            if not is_valid:
                logger.warning("PagerDuty webhook signature validation failed")

            return is_valid

        except Exception as e:
            logger.error(f"Error validating PagerDuty webhook signature: {e}", exc_info=True)
            return False
    
    def parse_webhook(self, payload: Dict[str, Any]) -> PagerDutyIncident:
        """
        Parse PagerDuty webhook payload into Incident object.
        
        Webhook payload structure:
        {
            "id": "...",
            "type": "incident",
            "incident": {
                "id": "...",
                "incident_number": 123,
                "title": "...",
                "service": {"summary": "..."},
                "status": "triggered|acknowledged|resolved",
                "urgency": "high|low",
                "created_at": "...",
                "updated_at": "...",
                "last_status_change_at": "..."
            }
        }
        
        Args:
            payload: Webhook payload
        
        Returns:
            PagerDutyIncident object
        """
        incident_data = payload.get('incident', payload)
        
        # Parse timestamps
        created_at = self._parse_timestamp(incident_data.get('created_at'))
        updated_at = self._parse_timestamp(incident_data.get('updated_at'))
        resolved_at = self._parse_timestamp(
            incident_data.get('last_status_change_at')
            if incident_data.get('status') == 'resolved'
            else None
        )
        
        return PagerDutyIncident(
            external_id=incident_data.get('id', ''),
            incident_number=incident_data.get('incident_number'),
            title=incident_data.get('title', 'Untitled Incident'),
            service=incident_data.get('service', {}).get('summary', 'Unknown Service'),
            severity=incident_data.get('urgency', 'unknown'),
            status=incident_data.get('status', 'unknown'),
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=resolved_at,
            description=incident_data.get('description'),
            raw_payload=payload
        )
    
    def sync_incidents(
        self,
        service_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
        statuses: Optional[List[str]] = None
    ) -> List[PagerDutyIncident]:
        """
        Sync incidents from PagerDuty API.
        
        Args:
            service_id: Filter by service ID
            since: Only fetch incidents since this time
            until: Only fetch incidents until this time
            limit: Maximum number of incidents to fetch
            statuses: Filter by incident statuses (e.g., ['triggered', 'acknowledged'])
        
        Returns:
            List of PagerDutyIncident objects
        """
        params = {
            "limit": min(limit, 1000),  # PagerDuty max is 1000
            "date_range": "all"
        }
        
        if service_id:
            params["service_ids[]"] = service_id
        
        if since:
            params["since"] = since.isoformat()
        
        if until:
            params["until"] = until.isoformat()
        
        if statuses:
            params["statuses[]"] = statuses
        
        incidents = []
        
        try:
            response = self._make_request_with_retry(
                'GET',
                f"{self.base_url}/incidents",
                params=params
            )
            
            data = response.json()

            for incident_data in data.get('incidents', []):
                incident = self._parse_api_incident(incident_data)
                incidents.append(incident)

            # Handle pagination - fetch only what's needed
            while (len(incidents) < limit and
                   data.get('more', False) and
                   data.get('offset') is not None):
                
                # Calculate how many more we need
                remaining = limit - len(incidents)
                params['offset'] = data['offset']
                params['limit'] = min(remaining, 1000)  # Don't fetch more than needed
                
                response = self._make_request_with_retry(
                    'GET',
                    f"{self.base_url}/incidents",
                    params=params
                )
                
                data = response.json()
                for incident_data in data.get('incidents', []):
                    if len(incidents) >= limit:
                        break  # Stop when we have enough
                    incident = self._parse_api_incident(incident_data)
                    incidents.append(incident)

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to sync incidents from PagerDuty: {e}")

        return incidents
    
    def _parse_api_incident(self, incident_data: Dict[str, Any]) -> PagerDutyIncident:
        """Parse incident from PagerDuty API response."""
        return PagerDutyIncident(
            external_id=incident_data.get('id', ''),
            incident_number=incident_data.get('incident_number'),
            title=incident_data.get('title', 'Untitled Incident'),
            service=incident_data.get('service', {}).get('summary', 'Unknown Service'),
            severity=incident_data.get('urgency', 'unknown'),
            status=incident_data.get('status', 'unknown'),
            created_at=self._parse_timestamp(incident_data.get('created_at')),
            updated_at=self._parse_timestamp(incident_data.get('updated_at')),
            resolved_at=self._parse_timestamp(
                incident_data.get('last_status_change_at')
                if incident_data.get('status') == 'resolved'
                else None
            ),
            description=incident_data.get('description'),
            raw_payload=incident_data
        )
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """
        Parse ISO 8601 timestamp string with logging on failure.
        
        Args:
            timestamp_str: Timestamp string in ISO 8601 format
        
        Returns:
            datetime object or None if parsing fails
        
        Note:
            Logs warning on parse failure for debugging
        """
        if not timestamp_str:
            return None
        
        try:
            # Handle 'Z' suffix
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp_str)
        except ValueError as e:
            logger.warning(
                f"Failed to parse PagerDuty timestamp '{timestamp_str}': {e}"
            )
            return None
    
    def get_incident_details(self, incident_id: str) -> PagerDutyIncident:
        """
        Fetch full details for a specific incident.

        Args:
            incident_id: PagerDuty incident ID

        Returns:
            PagerDutyIncident with full details
        
        Raises:
            RuntimeError: If API request fails
        """
        try:
            response = self._make_request_with_retry(
                'GET',
                f"{self.base_url}/incidents/{incident_id}"
            )

            incident_data = response.json().get('incident', {})
            return self._parse_api_incident(incident_data)

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch incident {incident_id}: {e}")
    
    def acknowledge_incident(self, incident_id: str, user_id: str) -> Dict[str, Any]:
        """
        Acknowledge a PagerDuty incident.

        Args:
            incident_id: PagerDuty incident ID
            user_id: ID of user acknowledging

        Returns:
            API response
        
        Raises:
            RuntimeError: If API request fails
        """
        try:
            response = self._make_request_with_retry(
                'PUT',
                f"{self.base_url}/incidents/{incident_id}",
                json={
                    "incident": {
                        "type": "incident_reference",
                        "id": incident_id,
                        "status": "acknowledged"
                    }
                },
                headers={
                    "X-PagerDuty-Requester-Id": user_id
                }
            )
            return response.json()

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to acknowledge incident {incident_id}: {e}")
    
    def resolve_incident(
        self,
        incident_id: str,
        user_id: str,
        resolution_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolve a PagerDuty incident.

        Args:
            incident_id: PagerDuty incident ID
            user_id: ID of user resolving
            resolution_notes: Optional notes about the resolution

        Returns:
            API response
        
        Raises:
            RuntimeError: If API request fails
        """
        data = {
            "incident": {
                "type": "incident_reference",
                "id": incident_id,
                "status": "resolved"
            }
        }

        if resolution_notes:
            data["incident"]["resolution_notes"] = resolution_notes

        try:
            response = self._make_request_with_retry(
                'PUT',
                f"{self.base_url}/incidents/{incident_id}",
                json=data,
                headers={
                    "X-PagerDuty-Requester-Id": user_id
                }
            )
            return response.json()

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to resolve incident {incident_id}: {e}")
