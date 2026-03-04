"""
Incident Sources Module

Provides integrations with external incident management and alerting systems.
"""

from incident_sources.base import IncidentSource, Incident
from incident_sources.pagerduty import PagerDutyIntegration, PagerDutyIncident
from incident_sources.datadog import DatadogIntegration, DatadogAlert
from incident_sources.alertmanager import AlertManagerIntegration, AlertManagerAlert
from incident_sources.sentry import SentryIntegration, SentryIssue

__all__ = [
    'IncidentSource',
    'Incident',
    'PagerDutyIntegration',
    'PagerDutyIncident',
    'DatadogIntegration',
    'DatadogAlert',
    'AlertManagerIntegration',
    'AlertManagerAlert',
    'SentryIntegration',
    'SentryIssue',
]
