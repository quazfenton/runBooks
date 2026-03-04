"""
API Routes for Incident Management

Provides REST API endpoints for incident ingestion and management.
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta
import os
import logging

from incident_sources.pagerduty import PagerDutyIntegration
from incident_sources.datadog import DatadogIntegration
from slack.handler import append_annotation_to_runbook

logger = logging.getLogger(__name__)

incidents_bp = Blueprint('incidents', __name__, url_prefix='/api/incidents')


def get_pagerduty_integration():
    """Get PagerDuty integration instance."""
    api_key = os.environ.get('PAGERDUTY_API_KEY')
    webhook_secret = os.environ.get('PAGERDUTY_WEBHOOK_SECRET')
    
    if not api_key:
        return None
    
    return PagerDutyIntegration(
        api_key=api_key,
        webhook_secret=webhook_secret
    )


def get_datadog_integration():
    """Get Datadog integration instance."""
    api_key = os.environ.get('DATADOG_API_KEY')
    app_key = os.environ.get('DATADOG_APP_KEY')
    webhook_secret = os.environ.get('DATADOG_WEBHOOK_SECRET')
    
    if not api_key or not app_key:
        return None
    
    return DatadogIntegration(
        api_key=api_key,
        app_key=app_key,
        webhook_secret=webhook_secret
    )


@incidents_bp.route('/webhooks/pagerduty', methods=['POST'])
def pagerduty_webhook():
    """
    Receive PagerDuty incident webhooks.
    
    Expected headers:
    - X-PagerDuty-Signature: HMAC signature
    - X-PagerDuty-Timestamp: Unix timestamp
    
    Returns:
        JSON response with incident details
    """
    try:
        payload = request.get_json()
        signature = request.headers.get('X-PagerDuty-Signature')
        timestamp = request.headers.get('X-PagerDuty-Timestamp')
        
        if not payload:
            return jsonify({'error': 'Invalid payload'}), 400
        
        # Get integration
        pd = get_pagerduty_integration()
        if not pd:
            logger.warning("PagerDuty integration not configured")
            return jsonify({'status': 'ok', 'warning': 'PagerDuty not configured'}), 200
        
        # Validate signature (if configured)
        if pd.webhook_secret and signature and timestamp:
            if not pd.validate_webhook_signature(
                request.get_data(),
                signature,
                timestamp
            ):
                logger.warning("Invalid PagerDuty webhook signature")
                return jsonify({'error': 'Invalid signature'}), 401
        
        # Parse incident
        incident = pd.parse_webhook(payload)
        
        logger.info(
            f"Received PagerDuty incident: {incident.external_id} - {incident.title}"
        )
        
        # Find matching runbook
        runbook_path = find_runbook_for_service(incident.service)
        
        if runbook_path:
            incident.runbook_path = runbook_path
            
            # Create annotation for tracking
            annotation = {
                'incident_id': f"PD-{incident.external_id}",
                'timestamp': incident.created_at.isoformat(),
                'cause': 'Pending investigation',
                'fix': 'Pending',
                'symptoms': [incident.title],
                'source': 'pagerduty',
                'severity': incident.severity,
                'status': incident.status
            }
            
            # Note: In production, you'd store this in a database
            # For now, we just log it
            logger.info(f"Mapped incident to runbook: {runbook_path}")
        
        return jsonify({
            'status': 'ok',
            'incident': {
                'id': incident.external_id,
                'title': incident.title,
                'service': incident.service,
                'severity': incident.severity,
                'status': incident.status,
                'runbook_path': runbook_path
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error processing PagerDuty webhook: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@incidents_bp.route('/webhooks/datadog', methods=['POST'])
def datadog_webhook():
    """
    Receive Datadog alert webhooks.
    
    Expected headers:
    - X-Datadog-Signature: HMAC signature (base64)
    - X-Datadog-Timestamp: Unix timestamp
    
    Returns:
        JSON response with alert details
    """
    try:
        payload = request.get_json()
        signature = request.headers.get('X-Datadog-Signature')
        timestamp = request.headers.get('X-Datadog-Timestamp')
        
        if not payload:
            return jsonify({'error': 'Invalid payload'}), 400
        
        # Get integration
        dd = get_datadog_integration()
        if not dd:
            logger.warning("Datadog integration not configured")
            return jsonify({'status': 'ok', 'warning': 'Datadog not configured'}), 200
        
        # Validate signature (if configured)
        if dd.webhook_secret and signature and timestamp:
            if not dd.validate_webhook_signature(
                request.get_data(),
                signature,
                timestamp
            ):
                logger.warning("Invalid Datadog webhook signature")
                return jsonify({'error': 'Invalid signature'}), 401
        
        # Parse alert
        alert = dd.parse_webhook(payload)
        
        logger.info(
            f"Received Datadog alert: {alert.external_id} - {alert.title}"
        )
        
        # Find matching runbook
        runbook_path = find_runbook_for_service(alert.service)
        
        if runbook_path:
            alert.runbook_path = runbook_path
            
            logger.info(f"Mapped alert to runbook: {runbook_path}")
        
        return jsonify({
            'status': 'ok',
            'alert': {
                'id': alert.external_id,
                'title': alert.title,
                'service': alert.service,
                'severity': alert.severity,
                'status': alert.status,
                'runbook_path': runbook_path
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error processing Datadog webhook: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@incidents_bp.route('/sync/pagerduty', methods=['POST'])
def sync_pagerduty_incidents():
    """
    Manually trigger PagerDuty incident sync.
    
    Request body (optional):
    - service_id: Filter by service
    - since: ISO 8601 timestamp
    - limit: Max incidents to fetch (default: 100)
    
    Returns:
        JSON response with synced incidents
    """
    try:
        data = request.get_json() or {}
        
        pd = get_pagerduty_integration()
        if not pd:
            return jsonify({'error': 'PagerDuty not configured'}), 503
        
        # Parse parameters
        service_id = data.get('service_id')
        since_str = data.get('since')
        limit = data.get('limit', 100)
        
        since = None
        if since_str:
            try:
                since = datetime.fromisoformat(since_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid since timestamp'}), 400
        
        # Sync incidents
        incidents = pd.sync_incidents(
            service_id=service_id,
            since=since,
            limit=limit
        )
        
        logger.info(f"Synced {len(incidents)} incidents from PagerDuty")
        
        return jsonify({
            'status': 'ok',
            'count': len(incidents),
            'incidents': [
                {
                    'id': inc.external_id,
                    'title': inc.title,
                    'service': inc.service,
                    'severity': inc.severity,
                    'status': inc.status,
                    'created_at': inc.created_at.isoformat()
                }
                for inc in incidents
            ]
        }), 200
    
    except Exception as e:
        logger.error(f"Error syncing PagerDuty incidents: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@incidents_bp.route('/sync/datadog', methods=['POST'])
def sync_datadog_monitors():
    """
    Manually trigger Datadog monitor sync.
    
    Request body (optional):
    - service_id: Filter by service
    - group_states: List of states to include
    
    Returns:
        JSON response with synced monitors
    """
    try:
        data = request.get_json() or {}
        
        dd = get_datadog_integration()
        if not dd:
            return jsonify({'error': 'Datadog not configured'}), 503
        
        # Parse parameters
        service_id = data.get('service_id')
        group_states = data.get('group_states', ['alert', 'warn', 'no data'])
        
        # Sync monitors
        alerts = dd.sync_monitors(
            group_states=group_states,
            tags=[f"service:{service_id}"] if service_id else None
        )
        
        logger.info(f"Synced {len(alerts)} monitors from Datadog")
        
        return jsonify({
            'status': 'ok',
            'count': len(alerts),
            'alerts': [
                {
                    'id': alert.external_id,
                    'title': alert.title,
                    'service': alert.service,
                    'severity': alert.severity,
                    'status': alert.status
                }
                for alert in alerts
            ]
        }), 200
    
    except Exception as e:
        logger.error(f"Error syncing Datadog monitors: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@incidents_bp.route('/recent', methods=['GET'])
def get_recent_incidents():
    """
    Get recent incidents from all sources.
    
    Query parameters:
    - limit: Max incidents to return (default: 50)
    - service: Filter by service
    - source: Filter by source (pagerduty, datadog)
    
    Returns:
        JSON response with recent incidents
    """
    try:
        limit = int(request.args.get('limit', 50))
        service = request.args.get('service')
        source = request.args.get('source')
        
        # In production, you'd query a database
        # For now, return empty list
        # This endpoint is a placeholder for future database integration
        
        return jsonify({
            'status': 'ok',
            'count': 0,
            'incidents': [],
            'note': 'Database integration required for incident history'
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting recent incidents: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


def find_runbook_for_service(service_name: str) -> str:
    """
    Find runbook path for a service.
    
    Args:
        service_name: Service name to match
    
    Returns:
        Runbook path if found, None otherwise
    """
    import os
    from pathlib import Path
    
    runbooks_dir = Path('runbooks')
    
    if not runbooks_dir.exists():
        return None
    
    # Try exact match first
    service_dir = runbooks_dir / service_name
    runbook_file = service_dir / 'runbook.yaml'
    
    if runbook_file.exists():
        return str(runbook_file)
    
    # Try fuzzy match
    for service_dir in runbooks_dir.iterdir():
        if service_dir.is_dir():
            if service_name.lower() in service_dir.name.lower():
                runbook_file = service_dir / 'runbook.yaml'
                if runbook_file.exists():
                    return str(runbook_file)
    
    return None
