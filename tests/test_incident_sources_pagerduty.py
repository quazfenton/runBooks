"""
Comprehensive tests for incident_sources.pagerduty module
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import requests
from incident_sources.pagerduty import PagerDutyIntegration, PagerDutyIncident


class TestPagerDutyIncident:
    """Test PagerDutyIncident class"""
    
    def test_valid_incident_creation(self):
        """Should create valid PagerDuty incident"""
        now = datetime.now()
        incident = PagerDutyIncident(
            external_id="INC-001",
            title="Test Incident",
            service="test-service",
            severity="high",
            status="triggered",
            created_at=now,
            incident_number=123,
            description="Test description"
        )
        
        assert incident.external_id == "INC-001"
        assert incident.incident_number == 123
        assert incident.source == "pagerduty"
        assert incident.description == "Test description"
    
    def test_escalations_default_to_empty_list(self):
        """Should default escalations to empty list"""
        incident = PagerDutyIncident(
            external_id="INC-001",
            title="Test",
            service="test",
            severity="high",
            status="triggered",
            created_at=datetime.now()
        )
        
        assert incident.escalations == []
    
    def test_validates_escalations(self):
        """Should validate escalation data structure"""
        valid_escalations = [
            {'level': 1, 'user': 'user1'},
            {'level': 2, 'user': 'user2'}
        ]
        invalid_escalations = [
            {'level': 1},  # Valid
            'invalid',     # Invalid - not a dict
            {'no_level': 'value'}  # Invalid - no level key
        ]
        
        incident_valid = PagerDutyIncident(
            external_id="INC-001",
            title="Test",
            service="test",
            severity="high",
            status="triggered",
            created_at=datetime.now(),
            escalations=valid_escalations
        )
        assert len(incident_valid.escalations) == 2
        
        incident_invalid = PagerDutyIncident(
            external_id="INC-002",
            title="Test",
            service="test",
            severity="high",
            status="triggered",
            created_at=datetime.now(),
            escalations=invalid_escalations
        )
        # Should filter out invalid escalations
        assert len(incident_invalid.escalations) == 1


class TestPagerDutyIntegration:
    """Test PagerDutyIntegration class"""
    
    @pytest.fixture
    def pd_integration(self):
        """Create integration instance for testing"""
        with patch.dict('os.environ', {'PAGERDUTY_API_KEY': 'test_key'}):
            yield PagerDutyIntegration()
    
    @pytest.fixture
    def pd_integration_with_secret(self):
        """Create integration instance with webhook secret"""
        with patch.dict('os.environ', {
            'PAGERDUTY_API_KEY': 'test_key',
            'PAGERDUTY_WEBHOOK_SECRET': 'test_secret'
        }):
            yield PagerDutyIntegration()
    
    def test_init_requires_api_key(self):
        """Should require API key"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="PagerDuty API key required"):
                PagerDutyIntegration()
    
    def test_init_uses_env_timeout(self):
        """Should use timeout from environment variable"""
        with patch.dict('os.environ', {
            'PAGERDUTY_API_KEY': 'test_key',
            'PAGERDUTY_TIMEOUT_MS': '60000'
        }):
            pd = PagerDutyIntegration()
            assert pd.request_timeout == 60.0
    
    def test_init_default_timeout(self):
        """Should use default 30 second timeout"""
        with patch.dict('os.environ', {
            'PAGERDUTY_API_KEY': 'test_key',
            'PAGERDUTY_TIMEOUT_MS': '30000'
        }):
            pd = PagerDutyIntegration()
            assert pd.request_timeout == 30.0
    
    def test_init_accepts_custom_timeout(self):
        """Should accept custom timeout parameter"""
        with patch.dict('os.environ', {'PAGERDUTY_API_KEY': 'test_key'}):
            pd = PagerDutyIntegration(request_timeout=45.0)
            assert pd.request_timeout == 45.0
    
    def test_validate_webhook_signature_returns_false_when_no_secret(self, pd_integration, caplog):
        """Should return False when webhook secret is not configured"""
        result = pd_integration.validate_webhook_signature(
            b"payload", "v0=signature", "1234567890"
        )
        
        assert result is False
        assert "webhook secret not configured" in caplog.text.lower()
    
    def test_validate_webhook_signature_invalid_format(self, pd_integration_with_secret, caplog):
        """Should return False on invalid signature format"""
        result = pd_integration_with_secret.validate_webhook_signature(
            b"payload", "invalid_signature", "1234567890"
        )
        
        assert result is False
        assert "Invalid signature format" in caplog.text
    
    def test_validate_webhook_signature_unknown_version(self, pd_integration_with_secret, caplog):
        """Should return False on unknown signature version"""
        result = pd_integration_with_secret.validate_webhook_signature(
            b"payload", "v1=signature", "1234567890"
        )
        
        assert result is False
        assert "Unknown signature version" in caplog.text
    
    def test_parse_webhook_extracts_incident_data(self, pd_integration):
        """Should correctly parse webhook payload"""
        payload = {
            'incident': {
                'id': 'INC-001',
                'incident_number': 123,
                'title': 'Service Down',
                'service': {'summary': 'API Service'},
                'status': 'triggered',
                'urgency': 'high',
                'created_at': '2026-03-03T12:00:00Z',
                'updated_at': '2026-03-03T12:00:00Z',
                'description': 'API not responding'
            }
        }
        
        incident = pd_integration.parse_webhook(payload)
        
        assert incident.external_id == 'INC-001'
        assert incident.incident_number == 123
        assert incident.title == 'Service Down'
        assert incident.service == 'API Service'
        assert incident.severity == 'high'
        assert incident.status == 'triggered'
    
    def test_parse_webhook_handles_missing_incident_key(self, pd_integration):
        """Should handle payload without 'incident' key"""
        payload = {
            'id': 'INC-001',
            'title': 'Direct Incident',
            'service': {'summary': 'Direct Service'},
            'status': 'acknowledged',
            'urgency': 'low'
        }
        
        incident = pd_integration.parse_webhook(payload)
        
        assert incident.external_id == 'INC-001'
        assert incident.title == 'Direct Incident'
        assert incident.service == 'Direct Service'
    
    def test_parse_webhook_uses_defaults_for_missing_fields(self, pd_integration):
        """Should use defaults for missing fields"""
        payload = {
            'incident': {
                'id': 'INC-001'
                # Missing other fields
            }
        }
        
        incident = pd_integration.parse_webhook(payload)
        
        assert incident.title == 'Untitled Incident'
        assert incident.service == 'Unknown Service'
        assert incident.severity == 'unknown'
        assert incident.status == 'unknown'
    
    def test_parse_timestamp_handles_z_suffix(self, pd_integration):
        """Should parse timestamps with Z suffix"""
        result = pd_integration._parse_timestamp('2026-03-03T12:00:00Z')
        
        assert result is not None
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 3
        assert result.hour == 12
    
    def test_parse_timestamp_handles_offset(self, pd_integration):
        """Should parse timestamps with timezone offset"""
        result = pd_integration._parse_timestamp('2026-03-03T12:00:00+00:00')
        
        assert result is not None
        assert result.year == 2026
        assert result.month == 3
    
    def test_parse_timestamp_returns_none_on_empty(self, pd_integration):
        """Should return None on empty timestamp"""
        result = pd_integration._parse_timestamp('')
        assert result is None
        
        result = pd_integration._parse_timestamp(None)
        assert result is None
    
    def test_parse_timestamp_returns_none_on_invalid(self, pd_integration, caplog):
        """Should return None and log warning on invalid timestamp"""
        result = pd_integration._parse_timestamp('invalid-timestamp')
        
        assert result is None
        assert "Failed to parse PagerDuty timestamp" in caplog.text
    
    def test_source_name_property(self, pd_integration):
        """Should return 'pagerduty' as source name"""
        assert pd_integration.source_name == "pagerduty"
    
    @patch('requests.Session')
    def test_sync_incidents_uses_timeout(self, mock_session_class, pd_integration):
        """Should configure timeout on HTTP requests"""
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {'incidents': []}
        mock_session_class.return_value = mock_session
        
        pd_integration.sync_incidents()
        
        mock_session.get.assert_called_once()
        call_kwargs = mock_session.get.call_args[1]
        assert 'timeout' in call_kwargs
        assert call_kwargs['timeout'] == 30.0  # Default 30s
    
    @patch('requests.Session')
    def test_sync_incidents_handles_pagination(self, mock_session_class, pd_integration):
        """Should handle API pagination correctly"""
        page1 = {
            'incidents': [{'id': f'i{n}', 'title': f'Incident {n}'} for n in range(100)],
            'more': True,
            'offset': 100
        }
        page2 = {
            'incidents': [{'id': f'i{n}', 'title': f'Incident {n}'} for n in range(100, 150)],
            'more': False
        }
        
        mock_session = MagicMock()
        mock_session.get.side_effect = [
            MagicMock(json=MagicMock(return_value=page1)),
            MagicMock(json=MagicMock(return_value=page2))
        ]
        mock_session_class.return_value = mock_session
        
        result = pd_integration.sync_incidents(limit=150)
        
        assert len(result) == 150
        assert mock_session.get.call_count == 2
    
    @patch('requests.Session')
    def test_sync_incidents_respects_limit(self, mock_session_class, pd_integration):
        """Should not fetch more incidents than limit"""
        page1 = {
            'incidents': [{'id': f'i{n}', 'title': f'Incident {n}'} for n in range(100)],
            'more': True,
            'offset': 100
        }
        page2 = {
            'incidents': [{'id': f'i{n}', 'title': f'Incident {n}'} for n in range(100, 200)],
            'more': False
        }
        
        mock_session = MagicMock()
        mock_session.get.side_effect = [
            MagicMock(json=MagicMock(return_value=page1)),
            MagicMock(json=MagicMock(return_value=page2))
        ]
        mock_session_class.return_value = mock_session
        
        result = pd_integration.sync_incidents(limit=50)
        
        assert len(result) == 50
        # Should only make one call since we only need 50
        assert mock_session.get.call_count == 1
    
    @patch('requests.Session')
    def test_sync_incidents_retries_on_failure(self, mock_session_class, pd_integration):
        """Should retry on transient failures"""
        mock_session = MagicMock()
        mock_session.get.side_effect = [
            requests.RequestException("timeout"),
            requests.RequestException("timeout"),
            MagicMock(json=MagicMock(return_value={'incidents': []}))
        ]
        mock_session_class.return_value = mock_session
        
        result = pd_integration.sync_incidents()
        
        assert mock_session.get.call_count == 3
        assert len(result) == 0
    
    @patch('requests.Session')
    def test_get_incident_details(self, mock_session_class, pd_integration):
        """Should fetch incident details"""
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {
            'incident': {
                'id': 'INC-001',
                'title': 'Test Incident',
                'service': {'summary': 'Test Service'},
                'status': 'triggered',
                'urgency': 'high'
            }
        }
        mock_session_class.return_value = mock_session
        
        incident = pd_integration.get_incident_details('INC-001')
        
        assert incident.external_id == 'INC-001'
        assert incident.title == 'Test Incident'
        mock_session.get.assert_called_once()
    
    @patch('requests.Session')
    def test_acknowledge_incident(self, mock_session_class, pd_integration):
        """Should acknowledge incident"""
        mock_session = MagicMock()
        mock_session.put.return_value.json.return_value = {'status': 'acknowledged'}
        mock_session_class.return_value = mock_session
        
        result = pd_integration.acknowledge_incident('INC-001', 'USER-001')
        
        assert result == {'status': 'acknowledged'}
        mock_session.put.assert_called_once()
    
    @patch('requests.Session')
    def test_resolve_incident(self, mock_session_class, pd_integration):
        """Should resolve incident"""
        mock_session = MagicMock()
        mock_session.put.return_value.json.return_value = {'status': 'resolved'}
        mock_session_class.return_value = mock_session
        
        result = pd_integration.resolve_incident('INC-001', 'USER-001')
        
        assert result == {'status': 'resolved'}
        mock_session.put.assert_called_once()
    
    @patch('requests.Session')
    def test_resolve_incident_with_notes(self, mock_session_class, pd_integration):
        """Should resolve incident with resolution notes"""
        mock_session = MagicMock()
        mock_session.put.return_value.json.return_value = {'status': 'resolved'}
        mock_session_class.return_value = mock_session
        
        result = pd_integration.resolve_incident(
            'INC-001', 'USER-001', resolution_notes='Fixed by restarting service'
        )
        
        assert result == {'status': 'resolved'}
        call_kwargs = mock_session.put.call_args[1]
        assert call_kwargs['json']['incident']['resolution_notes'] == 'Fixed by restarting service'
