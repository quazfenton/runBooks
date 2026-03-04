"""
Sentry Integration

Provides integration with Sentry for error tracking and incident creation.
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import requests
from incident_sources.base import IncidentSource, Incident


class SentryIssue(Incident):
    """Represents an issue from Sentry."""
    
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
        issue_culprit: Optional[str] = None,
        issue_type: Optional[str] = None,
        event_count: int = 0,
        user_count: int = 0,
        last_seen: Optional[datetime] = None,
        first_seen: Optional[datetime] = None,
        level: Optional[str] = None
    ):
        super().__init__(
            external_id=external_id,
            title=title,
            service=service,
            severity=severity,
            status=status,
            created_at=created_at,
            source='sentry',
            updated_at=updated_at,
            resolved_at=resolved_at,
            raw_payload=raw_payload,
            runbook_path=runbook_path
        )
        
        self.issue_culprit = issue_culprit
        self.issue_type = issue_type
        self.event_count = event_count
        self.user_count = user_count
        self.last_seen = last_seen
        self.first_seen = first_seen
        self.level = level


class SentryIntegration(IncidentSource):
    """
    Sentry integration for error tracking.
    
    Supports:
    - API sync for issue retrieval
    - Webhook parsing for real-time alerts
    - Issue resolution and updates
    """
    
    def __init__(
        self,
        api_token: Optional[str] = None,
        org_slug: Optional[str] = None,
        base_url: str = "https://sentry.io/api/0"
    ):
        """
        Initialize Sentry integration.
        
        Args:
            api_token: Sentry API token (or set SENTRY_API_TOKEN env var)
            org_slug: Sentry organization slug (or set SENTRY_ORG_SLUG env var)
            base_url: Sentry API base URL
        """
        self.api_token = api_token or os.environ.get('SENTRY_API_TOKEN')
        self.org_slug = org_slug or os.environ.get('SENTRY_ORG_SLUG')
        self.base_url = base_url
        
        if not self.api_token:
            raise ValueError(
                "Sentry API token required. Set SENTRY_API_TOKEN environment variable."
            )
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        })
    
    @property
    def source_name(self) -> str:
        return "sentry"
    
    def parse_webhook(self, payload: Dict[str, Any]) -> SentryIssue:
        """
        Parse Sentry webhook payload.
        
        Webhook payload structure:
        {
            "id": "...",
            "project": {...},
            "issue": {...},
            "url": "...",
            "event": {...}
        }
        """
        issue_data = payload.get('issue', {})
        event_data = payload.get('event', {})
        project_data = payload.get('project', {})
        
        # Parse issue
        issue_id = issue_data.get('id', '')
        title = issue_data.get('title', 'Untitled Issue')
        culprit = issue_data.get('culprit', '')
        level = issue_data.get('level', 'error')
        
        # Map Sentry level to severity
        severity_map = {
            'sample': 'low',
            'info': 'low',
            'warning': 'medium',
            'error': 'high',
            'fatal': 'critical',
            'unknown': 'medium'
        }
        severity = severity_map.get(level, 'medium')
        
        # Map status
        status = issue_data.get('status', 'unresolved')
        is_resolved = status == 'resolved'
        
        # Parse timestamps
        first_seen = self._parse_timestamp(issue_data.get('firstSeen'))
        last_seen = self._parse_timestamp(issue_data.get('lastSeen'))
        
        # Extract service from project
        service = project_data.get('slug', 'unknown')
        
        return SentryIssue(
            external_id=issue_id,
            title=title,
            service=service,
            severity=severity,
            status=status,
            created_at=first_seen or datetime.now(),
            updated_at=last_seen,
            resolved_at=last_seen if is_resolved else None,
            issue_culprit=culprit,
            issue_type=event_data.get('type'),
            event_count=issue_data.get('count', 0),
            user_count=issue_data.get('userCount', 0),
            last_seen=last_seen,
            first_seen=first_seen,
            level=level,
            raw_payload=payload
        )
    
    def sync_incidents(
        self,
        service_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[SentryIssue]:
        """
        Sync issues from Sentry API.
        
        Args:
            service_id: Filter by project slug
            since: Filter by first seen date
            limit: Maximum issues to fetch
            status: Filter by status (unresolved, resolved, ignored)
        
        Returns:
            List of SentryIssue objects
        """
        if not self.org_slug:
            raise ValueError("Organization slug required")
        
        # Determine project
        project_slug = service_id or ''
        
        params = {
            'limit': min(limit, 1000),
            'sort': 'date'
        }
        
        if status:
            params['status'] = status
        
        if since:
            params['query'] = f'first_seen:>={since.isoformat()}'
        
        # Build URL
        if project_slug:
            url = f"{self.base_url}/projects/{self.org_slug}/{project_slug}/issues/"
        else:
            url = f"{self.base_url}/organizations/{self.org_slug}/issues/"
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            issues_data = response.json()
            issues = []
            
            for issue_data in issues_data:
                issue = self._parse_api_issue(issue_data)
                issues.append(issue)
            
            return issues
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to sync issues from Sentry: {e}")
    
    def _parse_api_issue(self, issue_data: Dict[str, Any]) -> SentryIssue:
        """Parse issue from Sentry API response."""
        level = issue_data.get('level', 'error')
        status = issue_data.get('status', 'unresolved')
        
        severity_map = {
            'sample': 'low',
            'info': 'low',
            'warning': 'medium',
            'error': 'high',
            'fatal': 'critical'
        }
        severity = severity_map.get(level, 'medium')
        
        first_seen = self._parse_timestamp(issue_data.get('firstSeen'))
        last_seen = self._parse_timestamp(issue_data.get('lastSeen'))
        
        return SentryIssue(
            external_id=issue_data.get('id', ''),
            title=issue_data.get('title', 'Untitled Issue'),
            service=issue_data.get('project', {}).get('slug', 'unknown'),
            severity=severity,
            status=status,
            created_at=first_seen or datetime.now(),
            updated_at=last_seen,
            resolved_at=last_seen if status == 'resolved' else None,
            issue_culprit=issue_data.get('culprit'),
            event_count=int(issue_data.get('count', 0)),
            user_count=int(issue_data.get('userCount', 0)),
            last_seen=last_seen,
            first_seen=first_seen,
            level=level,
            raw_payload=issue_data
        )
    
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
    
    def get_issue_details(self, issue_id: str) -> SentryIssue:
        """
        Get detailed information about an issue.
        
        Args:
            issue_id: Sentry issue ID
        
        Returns:
            SentryIssue with full details
        """
        if not self.org_slug:
            raise ValueError("Organization slug required")
        
        try:
            response = self.session.get(
                f"{self.base_url}/organizations/{self.org_slug}/issues/{issue_id}/"
            )
            response.raise_for_status()
            
            issue_data = response.json()
            return self._parse_api_issue(issue_data)
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch issue {issue_id}: {e}")
    
    def get_issue_events(
        self,
        issue_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get events for an issue.
        
        Args:
            issue_id: Sentry issue ID
            limit: Maximum events to fetch
        
        Returns:
            List of event data
        """
        if not self.org_slug:
            raise ValueError("Organization slug required")
        
        try:
            response = self.session.get(
                f"{self.base_url}/organizations/{self.org_slug}/issues/{issue_id}/events/",
                params={'limit': limit}
            )
            response.raise_for_status()
            return response.json()
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch events for issue {issue_id}: {e}")
    
    def resolve_issue(
        self,
        issue_id: str,
        status_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resolve a Sentry issue.
        
        Args:
            issue_id: Sentry issue ID
            status_details: Optional status details
        
        Returns:
            Updated issue data
        """
        if not self.org_slug:
            raise ValueError("Organization slug required")
        
        update_data = {
            'status': 'resolved'
        }
        
        if status_details:
            update_data['statusDetails'] = status_details
        
        try:
            response = self.session.put(
                f"{self.base_url}/organizations/{self.org_slug}/issues/{issue_id}/",
                json=update_data
            )
            response.raise_for_status()
            return response.json()
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to resolve issue {issue_id}: {e}")
    
    def ignore_issue(
        self,
        issue_id: str,
        ignore_duration: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Ignore a Sentry issue.
        
        Args:
            issue_id: Sentry issue ID
            ignore_duration: Optional duration in seconds to ignore
        
        Returns:
            Updated issue data
        """
        if not self.org_slug:
            raise ValueError("Organization slug required")
        
        update_data = {
            'status': 'ignored'
        }
        
        if ignore_duration:
            update_data['statusDetails'] = {
                'ignoreUntil': (datetime.now() + timedelta(seconds=ignore_duration)).isoformat()
            }
        
        try:
            response = self.session.put(
                f"{self.base_url}/organizations/{self.org_slug}/issues/{issue_id}/",
                json=update_data
            )
            response.raise_for_status()
            return response.json()
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to ignore issue {issue_id}: {e}")
    
    def assign_issue(
        self,
        issue_id: str,
        assignee: str
    ) -> Dict[str, Any]:
        """
        Assign a Sentry issue.
        
        Args:
            issue_id: Sentry issue ID
            assignee: User or team ID to assign to
        
        Returns:
            Updated issue data
        """
        if not self.org_slug:
            raise ValueError("Organization slug required")
        
        try:
            response = self.session.put(
                f"{self.base_url}/organizations/{self.org_slug}/issues/{issue_id}/",
                json={'assignedTo': assignee}
            )
            response.raise_for_status()
            return response.json()
        
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to assign issue {issue_id}: {e}")


def main():
    """Example usage of Sentry integration."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Sentry integration"
    )
    parser.add_argument(
        "--org",
        help="Organization slug"
    )
    parser.add_argument(
        "--action",
        choices=['list', 'details', 'resolve', 'ignore', 'assign'],
        default='list',
        help="Action to perform"
    )
    parser.add_argument(
        "--issue",
        help="Issue ID (for details/resolve/ignore/assign)"
    )
    parser.add_argument(
        "--project",
        help="Filter by project"
    )
    parser.add_argument(
        "--status",
        choices=['unresolved', 'resolved', 'ignored'],
        help="Filter by status"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum issues to show"
    )
    
    args = parser.parse_args()
    
    try:
        integration = SentryIntegration(org_slug=args.org)
        
        if args.action == 'list':
            issues = integration.sync_incidents(
                service_id=args.project,
                status=args.status,
                limit=args.limit
            )
            
            print(f"Found {len(issues)} issues:\n")
            for issue in issues:
                status_icon = {
                    'unresolved': '🔴',
                    'resolved': '🟢',
                    'ignored': '⚪'
                }.get(issue.status, '•')
                
                print(f"{status_icon} [{issue.level}] {issue.title}")
                print(f"   Project: {issue.service}")
                print(f"   Events: {issue.event_count} | Users: {issue.user_count}")
                print(f"   First seen: {issue.first_seen}")
                print()
        
        elif args.action == 'details':
            if not args.issue:
                print("Error: --issue required for details action")
                return
            
            issue = integration.get_issue_details(args.issue)
            print(f"Issue: {issue.title}")
            print(f"Status: {issue.status}")
            print(f"Level: {issue.level}")
            print(f"Culprit: {issue.issue_culprit}")
            print(f"Events: {issue.event_count}")
        
        elif args.action == 'resolve':
            if not args.issue:
                print("Error: --issue required for resolve action")
                return
            
            result = integration.resolve_issue(args.issue)
            print(f"Issue {args.issue} resolved")
        
        elif args.action == 'ignore':
            if not args.issue:
                print("Error: --issue required for ignore action")
                return
            
            result = integration.ignore_issue(args.issue)
            print(f"Issue {args.issue} ignored")
        
        elif args.action == 'assign':
            if not args.issue:
                print("Error: --issue required for assign action")
                return
            print("Use Sentry web UI for assignment")
    
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
