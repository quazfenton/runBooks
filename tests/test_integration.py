#!/usr/bin/env python3
"""
Integration Tests for Living Runbooks

Comprehensive tests for all modules.
Run with: python -m pytest tests/test_integration.py -v
"""

import unittest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import yaml


class TestSlackHandlerIntegration(unittest.TestCase):
    """Integration tests for Slack handler."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create test runbook within the runbooks directory for security validation
        self.runbooks_dir = Path(__file__).parent.parent / "runbooks" / "test-temp"
        self.runbooks_dir.mkdir(exist_ok=True)
        self.runbook_path = self.runbooks_dir / "test-runbook.yaml"
        
        initial_runbook = {
            'title': 'Test Runbook',
            'version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'owner': 'test-team',
            'steps': [
                {
                    'check': 'Verify service health',
                    'command': 'curl http://localhost/health'
                }
            ],
            'annotations': []
        }
        
        with open(self.runbook_path, 'w') as f:
            yaml.dump(initial_runbook, f)
    
    def tearDown(self):
        """Clean up test files."""
        import shutil
        if self.runbook_path.exists():
            self.runbook_path.unlink()
        if self.runbooks_dir.exists():
            shutil.rmtree(self.runbooks_dir, ignore_errors=True)
    
    def test_annotation_flow(self):
        """Test complete annotation flow."""
        from slack.handler import (
            create_annotation_from_slack_payload,
            append_annotation_to_runbook,
            handle_slack_annotation
        )
        
        # Use relative path from runbooks directory
        relative_path = f"test-temp/{self.runbook_path.name}"
        
        # Simulate Slack payload
        payload = {
            'view': {
                'state': {
                    'values': {
                        'incident_id': {
                            'input': {'value': 'INC-TEST-001'}
                        },
                        'symptoms': {
                            'input': {'value': 'High latency\n5xx errors'}
                        },
                        'root_cause': {
                            'input': {'value': 'Database connection pool exhausted'}
                        },
                        'fix_applied': {
                            'input': {'value': 'Increased connection pool size'}
                        },
                        'runbook_gaps': {
                            'input': {'value': 'Missing connection pool monitoring'}
                        },
                        'runbook_path': {
                            'input': {'value': relative_path}
                        }
                    }
                }
            }
        }
        
        # Test annotation creation
        annotation, runbook_path = create_annotation_from_slack_payload(payload)
        
        self.assertEqual(annotation['incident_id'], 'INC-TEST-001')
        self.assertEqual(annotation['cause'], 'Database connection pool exhausted')
        self.assertEqual(annotation['fix'], 'Increased connection pool size')
        self.assertIn('High latency', annotation['symptoms'])
        
        # Test annotation append with relative path
        append_annotation_to_runbook(relative_path, annotation)
        
        # Verify annotation was added
        with open(self.runbook_path, 'r') as f:
            runbook = yaml.safe_load(f)
        
        self.assertEqual(len(runbook['annotations']), 1)
        self.assertEqual(runbook['annotations'][0]['incident_id'], 'INC-TEST-001')
    
    def test_security_path_traversal(self):
        """Test path traversal protection."""
        from slack.handler import validate_runbook_path_secure
        
        base_dir = self.runbooks_dir.parent  # runbooks directory
        
        # Valid path should work
        valid_path = self.runbooks_dir / "runbook.yaml"
        valid_path.touch()
        
        result = validate_runbook_path_secure("test-temp/runbook.yaml", base_dir)
        self.assertEqual(result, valid_path.resolve())
        
        # Path traversal should fail
        with self.assertRaises(ValueError):
            validate_runbook_path_secure("../etc/passwd", base_dir)
        
        # Absolute path outside base should fail
        with self.assertRaises(ValueError):
            validate_runbook_path_secure("/etc/passwd", base_dir)


class TestIncidentSourcesIntegration(unittest.TestCase):
    """Integration tests for incident sources."""
    
    def test_pagerduty_webhook_parsing(self):
        """Test PagerDuty webhook parsing."""
        from incident_sources.pagerduty import PagerDutyIntegration
        
        pd = PagerDutyIntegration.__new__(PagerDutyIntegration)
        
        webhook_payload = {
            'id': 'test-event-id',
            'type': 'incident.triggered',
            'incident': {
                'id': 'INC123',
                'incident_number': 456,
                'title': 'Service Down',
                'service': {'summary': 'API Service'},
                'status': 'triggered',
                'urgency': 'high',
                'created_at': '2026-03-03T12:00:00Z',
                'updated_at': '2026-03-03T12:00:00Z',
                'description': 'API service is not responding'
            }
        }
        
        incident = pd.parse_webhook(webhook_payload)
        
        self.assertEqual(incident.external_id, 'INC123')
        self.assertEqual(incident.incident_number, 456)
        self.assertEqual(incident.title, 'Service Down')
        self.assertEqual(incident.service, 'API Service')
        self.assertEqual(incident.severity, 'high')
        self.assertEqual(incident.status, 'triggered')
        self.assertEqual(incident.source, 'pagerduty')
    
    def test_datadog_webhook_parsing(self):
        """Test Datadog webhook parsing."""
        from incident_sources.datadog import DatadogIntegration
        
        dd = DatadogIntegration.__new__(DatadogIntegration)
        
        webhook_payload = {
            'id': 789,
            'id_str': '789',
            'title': 'High Memory Usage',
            'alert_type': 'metric alert',
            'status': 'triggered',
            'alert_transition': 'triggered',
            'date': 1709467200,
            'hostname': 'prod-server-1',
            'tags': ['service:backend', 'env:production', 'team:platform'],
            'metric': 'system.mem.used_pct',
            'scope': 'host:prod-server-1',
            'message': 'Memory usage is above 90%'
        }
        
        alert = dd.parse_webhook(webhook_payload)
        
        self.assertEqual(alert.external_id, '789')
        self.assertEqual(alert.title, 'High Memory Usage')
        self.assertEqual(alert.service, 'backend')
        self.assertEqual(alert.severity, 'high')
        self.assertEqual(alert.metric, 'system.mem.used_pct')
        self.assertIn('service:backend', alert.tags)
    
    def test_alertmanager_webhook_parsing(self):
        """Test AlertManager webhook parsing."""
        from incident_sources.alertmanager import AlertManagerIntegration
        
        am = AlertManagerIntegration.__new__(AlertManagerIntegration)
        
        webhook_payload = {
            'version': '4',
            'groupKey': 'test-group',
            'status': 'firing',
            'receiver': 'runbooks-webhook',
            'alerts': [
                {
                    'status': 'firing',
                    'labels': {
                        'alertname': 'HighCPU',
                        'severity': 'warning',
                        'instance': 'server-1',
                        'job': 'node'
                    },
                    'annotations': {
                        'summary': 'CPU usage is above 80%',
                        'description': 'CPU usage on server-1 is 85%'
                    },
                    'startsAt': '2026-03-03T12:00:00Z',
                    'endsAt': '0001-01-01T00:00:00Z',
                    'generatorURL': 'http://prometheus:9090/graph?g0.expr=...',
                    'fingerprint': 'abc123'
                }
            ],
            'groupLabels': {'alertname': 'HighCPU'},
            'commonLabels': {'severity': 'warning'},
            'commonAnnotations': {'summary': 'CPU usage is above 80%'}
        }
        
        alert = am.parse_webhook(webhook_payload)
        
        self.assertEqual(alert.alert_name, 'HighCPU')
        self.assertEqual(alert.service, 'node')
        self.assertEqual(alert.severity, 'warning')
        self.assertEqual(alert.status, 'firing')
        self.assertEqual(alert.instance, 'server-1')
    
    def test_sentry_webhook_parsing(self):
        """Test Sentry webhook parsing."""
        from incident_sources.sentry import SentryIntegration
        
        sentry = SentryIntegration.__new__(SentryIntegration)
        
        webhook_payload = {
            'id': 'sentry-event-123',
            'project': {
                'slug': 'backend-api',
                'name': 'Backend API'
            },
            'issue': {
                'id': 'ISSUE-456',
                'title': 'DatabaseConnectionError: Connection timeout',
                'culprit': 'database.py in execute_query',
                'level': 'error',
                'status': 'unresolved',
                'firstSeen': '2026-03-03T10:00:00Z',
                'lastSeen': '2026-03-03T12:00:00Z',
                'count': 15,
                'userCount': 5
            },
            'event': {
                'type': 'error',
                'message': 'Connection timeout after 30s'
            },
            'url': 'https://sentry.io/issues/ISSUE-456'
        }
        
        issue = sentry.parse_webhook(webhook_payload)
        
        self.assertEqual(issue.external_id, 'ISSUE-456')
        self.assertEqual(issue.title, 'DatabaseConnectionError: Connection timeout')
        self.assertEqual(issue.service, 'backend-api')
        self.assertEqual(issue.severity, 'high')
        self.assertEqual(issue.level, 'error')
        self.assertEqual(issue.event_count, 15)


class TestAIModuleIntegration(unittest.TestCase):
    """Integration tests for AI module."""
    
    def test_llm_suggestion_engine_fallback(self):
        """Test LLM suggestion engine fallback mode."""
        from ai.llm_suggestion_engine import LLMRunbookEvolution
        
        # Test without API key (fallback mode)
        engine = LLMRunbookEvolution(provider='anthropic', api_key=None)
        
        incident = {
            'incident_id': 'INC-001',
            'cause': 'Memory leak in cache service',
            'fix': 'Restarted service and increased memory limits'
        }
        
        runbook = {
            'title': 'Test Runbook',
            'steps': [
                {'check': 'Check service health', 'command': 'curl localhost/health'}
            ]
        }
        
        # Should work in fallback mode
        suggestions = engine.analyze_incident(incident, runbook)
        
        # Should have at least one suggestion
        self.assertGreater(len(suggestions), 0)
        
        # Check suggestion structure
        for suggestion in suggestions:
            self.assertIsNotNone(suggestion.suggestion_type)
            self.assertIsNotNone(suggestion.action)
            self.assertIsNotNone(suggestion.reasoning)
    
    def test_semantic_correlator_offline(self):
        """Test semantic correlator without model."""
        from ai.semantic_correlator import SemanticCorrelator
        
        # Test without sentence-transformers
        correlator = SemanticCorrelator()
        
        # Should handle missing model gracefully
        if not correlator.model:
            result = correlator.embed_incident(
                incident_id='test',
                cause='test cause',
                fix='test fix'
            )
            self.assertIsNone(result)
    
    def test_report_generator_template(self):
        """Test report generator in template mode."""
        from ai.report_generator import IncidentReportGenerator, PostIncidentReport
        
        generator = IncidentReportGenerator(provider='template')
        
        incident_data = {
            'incident_id': 'INC-2026-001',
            'title': 'Service Outage',
            'service': 'api-gateway',
            'severity': 'high',
            'cause': 'Database connection pool exhausted',
            'fix': 'Increased pool size and restarted service',
            'duration_minutes': 45,
            'created_at': '2026-03-03T10:00:00Z',
            'resolved_at': '2026-03-03T10:45:00Z'
        }
        
        annotations = [
            {
                'incident_id': 'INC-2026-001',
                'timestamp': '2026-03-03T10:15:00Z',
                'cause': 'Connection pool exhausted',
                'fix': 'Increased pool size'
            }
        ]
        
        report = generator.generate_report(incident_data, annotations=annotations)
        
        self.assertIsInstance(report, PostIncidentReport)
        self.assertEqual(report.incident_id, 'INC-2026-001')
        self.assertEqual(report.service, 'api-gateway')
        self.assertGreater(report.duration_minutes, 0)
        
        # Test markdown generation
        markdown = report.to_markdown()
        self.assertIn('INC-2026-001', markdown)
        self.assertIn('api-gateway', markdown)
        self.assertIn('Root Cause', markdown)


class TestVersionControlIntegration(unittest.TestCase):
    """Integration tests for version control."""
    
    def setUp(self):
        """Set up test git repository."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)
        
        # Initialize git repo
        os.system(f'cd {self.temp_dir} && git init')
        os.system(f'cd {self.temp_dir} && git config user.name "Test User"')
        os.system(f'cd {self.temp_dir} && git config user.email "test@example.com"')
        
        # Create initial runbook
        self.runbook_path = self.repo_path / "test-runbook.yaml"
        initial_content = {
            'title': 'Test Runbook',
            'version': '1.0',
            'steps': []
        }
        
        with open(self.runbook_path, 'w') as f:
            yaml.dump(initial_content, f)
        
        # Initial commit
        os.system(f'cd {self.temp_dir} && git add . && git commit -m "Initial commit"')
    
    def tearDown(self):
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_git_version_control(self):
        """Test git version control operations."""
        # Check if gitpython is installed
        try:
            from git import Repo
        except ImportError:
            self.skipTest("gitpython not installed")
        
        try:
            from version_control.git_manager import RunbookVersionControl
        except ImportError:
            self.skipTest("version_control module not available")

        vcs = RunbookVersionControl(str(self.repo_path))
        
        # Test commit annotation
        annotation = {
            'incident_id': 'INC-001',
            'timestamp': datetime.now().isoformat(),
            'cause': 'Test cause',
            'fix': 'Test fix'
        }
        
        commit_hash = vcs.commit_annotation(
            'test-runbook.yaml',
            annotation,
            author='test@example.com'
        )
        
        self.assertIsNotNone(commit_hash)
        self.assertEqual(len(commit_hash), 40)
        
        # Test history
        history = vcs.get_runbook_history('test-runbook.yaml', limit=10)
        
        self.assertGreater(len(history), 0)
        self.assertEqual(history[0]['short_hash'], commit_hash[:7])
    
    def test_diff_engine(self):
        """Test diff engine."""
        try:
            from version_control.diff_engine import RunbookDiffEngine, ChangeType
        except ImportError:
            self.skipTest("Dependencies not installed")
        
        engine = RunbookDiffEngine()
        
        old_runbook = {
            'title': 'Test',
            'version': '1.0',
            'steps': [
                {'check': 'Step 1', 'command': 'cmd1'}
            ]
        }
        
        new_runbook = {
            'title': 'Test',
            'version': '2.0',
            'steps': [
                {'check': 'Step 1', 'command': 'cmd1'},
                {'check': 'Step 2', 'command': 'cmd2'}
            ]
        }
        
        changes = engine.diff_runbooks(old_runbook, new_runbook)
        
        # Should detect version change and step addition
        self.assertGreater(len(changes), 0)


class TestAPIEndpoints(unittest.TestCase):
    """Test API endpoints."""

    def test_metrics_endpoint_structure(self):
        """Test metrics endpoint returns correct structure."""
        # Dynamic import to handle service-x naming (hyphen not valid in module name)
        import sys
        from pathlib import Path
        
        scripts_path = Path(__file__).parent.parent / "runbooks" / "service-x" / "scripts"
        if str(scripts_path) not in sys.path:
            sys.path.insert(0, str(scripts_path))
        
        from generate_metrics import generate_dashboard_data

        # Test with current runbooks directory
        metrics = generate_dashboard_data('runbooks')

        # Check required fields
        self.assertIn('totalRunbooks', metrics)
        self.assertIn('totalAnnotations', metrics)
        self.assertIn('incidentsByService', metrics)
        self.assertIn('topFixes', metrics)

        # Check types
        self.assertIsInstance(metrics['totalRunbooks'], int)
        self.assertIsInstance(metrics['totalAnnotations'], int)
        self.assertIsInstance(metrics['incidentsByService'], dict)


if __name__ == '__main__':
    unittest.main()
