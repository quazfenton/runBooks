#!/usr/bin/env python3
"""
Test Suite for Incident Sources Module

Tests for PagerDuty and Datadog integrations.
"""

import unittest
from datetime import datetime
from incident_sources.base import Incident
from incident_sources.pagerduty import PagerDutyIntegration, PagerDutyIncident
from incident_sources.datadog import DatadogIntegration, DatadogAlert


class TestIncidentBase(unittest.TestCase):
    """Test base Incident class."""
    
    def test_incident_to_dict(self):
        """Test incident serialization."""
        incident = Incident(
            external_id="INC-001",
            title="Test Incident",
            service="test-service",
            severity="high",
            status="triggered",
            created_at=datetime(2026, 1, 1, 12, 0, 0),
            source="test"
        )
        
        result = incident.to_dict()
        
        self.assertEqual(result['external_id'], "INC-001")
        self.assertEqual(result['title'], "Test Incident")
        self.assertEqual(result['service'], "test-service")
        self.assertEqual(result['source'], "test")


class TestPagerDutyIntegration(unittest.TestCase):
    """Test PagerDuty integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_webhook = {
            "id": "abc123",
            "type": "incident.triggered",
            "incident": {
                "id": "INC001",
                "incident_number": 123,
                "title": "Service X is down",
                "service": {
                    "summary": "Service X"
                },
                "status": "triggered",
                "urgency": "high",
                "created_at": "2026-01-01T12:00:00Z",
                "updated_at": "2026-01-01T12:00:00Z",
                "description": "Service X is not responding"
            }
        }
    
    def test_parse_webhook(self):
        """Test webhook parsing."""
        # Create integration without API key (for testing)
        pd = PagerDutyIntegration.__new__(PagerDutyIntegration)
        
        incident = pd.parse_webhook(self.sample_webhook)
        
        self.assertIsInstance(incident, PagerDutyIncident)
        self.assertEqual(incident.external_id, "INC001")
        self.assertEqual(incident.incident_number, 123)
        self.assertEqual(incident.title, "Service X is down")
        self.assertEqual(incident.service, "Service X")
        self.assertEqual(incident.severity, "high")
        self.assertEqual(incident.status, "triggered")
        self.assertEqual(incident.source, "pagerduty")
    
    def test_source_name(self):
        """Test source name property."""
        pd = PagerDutyIntegration.__new__(PagerDutyIntegration)
        self.assertEqual(pd.source_name, "pagerduty")


class TestDatadogIntegration(unittest.TestCase):
    """Test Datadog integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_webhook = {
            "id": 12345,
            "id_str": "12345",
            "title": "High CPU usage on host-1",
            "alert_type": "metric alert",
            "status": "triggered",
            "alert_transition": "triggered",
            "date": 1704110400,  # 2024-01-01 12:00:00
            "hostname": "host-1",
            "tags": ["service:api", "env:production"],
            "org_id": "org123",
            "metric": "system.cpu.user",
            "scope": "host:host-1",
            "message": "CPU usage is above 90%"
        }
    
    def test_parse_webhook(self):
        """Test webhook parsing."""
        dd = DatadogIntegration.__new__(DatadogIntegration)
        
        alert = dd.parse_webhook(self.sample_webhook)
        
        self.assertIsInstance(alert, DatadogAlert)
        self.assertEqual(alert.external_id, "12345")
        self.assertEqual(alert.title, "High CPU usage on host-1")
        self.assertEqual(alert.service, "api")  # Extracted from tags
        self.assertEqual(alert.severity, "high")
        self.assertEqual(alert.status, "triggered")
        self.assertEqual(alert.source, "datadog")
        self.assertEqual(alert.metric, "system.cpu.user")
        self.assertIn("service:api", alert.tags)
    
    def test_extract_service_from_tags(self):
        """Test service extraction from tags."""
        dd = DatadogIntegration.__new__(DatadogIntegration)
        
        # Test service: tag
        service = dd._extract_service_from_tags(["service:api", "env:prod"])
        self.assertEqual(service, "api")
        
        # Test no service tag
        service = dd._extract_service_from_tags(["env:prod", "team:backend"])
        self.assertEqual(service, "unknown")
    
    def test_source_name(self):
        """Test source name property."""
        dd = DatadogIntegration.__new__(DatadogIntegration)
        self.assertEqual(dd.source_name, "datadog")


class TestIncidentCreation(unittest.TestCase):
    """Test end-to-end incident creation."""
    
    def test_pagerduty_incident_creation(self):
        """Test creating incident from PagerDuty webhook."""
        webhook = {
            "incident": {
                "id": "INC001",
                "incident_number": 456,
                "title": "Database connection failed",
                "service": {"summary": "Database"},
                "status": "acknowledged",
                "urgency": "high",
                "created_at": "2026-01-15T10:30:00Z",
                "updated_at": "2026-01-15T10:35:00Z"
            }
        }
        
        pd = PagerDutyIntegration.__new__(PagerDutyIntegration)
        incident = pd.parse_webhook(webhook)
        
        self.assertEqual(incident.status, "acknowledged")
        self.assertIsNotNone(incident.created_at)
    
    def test_datadog_recovered_alert(self):
        """Test parsing recovered Datadog alert."""
        webhook = {
            "id": 99999,
            "title": "Memory usage recovered",
            "status": "recovered",
            "alert_transition": "recovered",
            "date": 1704110400,
            "tags": ["service:cache"]
        }
        
        dd = DatadogIntegration.__new__(DatadogIntegration)
        alert = dd.parse_webhook(webhook)
        
        self.assertEqual(alert.status, "recovered")
        self.assertEqual(alert.severity, "resolved")
        self.assertIsNotNone(alert.resolved_at)


if __name__ == '__main__':
    unittest.main()
