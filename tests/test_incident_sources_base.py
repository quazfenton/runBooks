"""
Comprehensive tests for incident_sources.base module
"""
import pytest
from datetime import datetime, timedelta
from incident_sources.base import (
    Incident,
    IncidentSource,
    VALID_SEVERITIES,
    VALID_STATUSES
)


class TestIncidentDataclass:
    """Test Incident dataclass validation and behavior"""
    
    def test_valid_incident_creation(self):
        """Should create valid incident without errors"""
        now = datetime.now()
        incident = Incident(
            external_id="INC-001",
            title="Test Incident",
            service="test-service",
            severity="high",
            status="triggered",
            created_at=now,
            source="test"
        )
        
        assert incident.external_id == "INC-001"
        assert incident.title == "Test Incident"
        assert incident.severity == "high"
        assert incident.status == "triggered"
        assert incident.source == "test"
    
    def test_rejects_empty_external_id(self):
        """Should reject empty external_id"""
        with pytest.raises(ValueError, match="external_id must be a non-empty string"):
            Incident(
                external_id="",
                title="Test",
                service="test",
                severity="high",
                status="triggered",
                created_at=datetime.now(),
                source="test"
            )
    
    def test_rejects_non_string_external_id(self):
        """Should reject non-string external_id"""
        with pytest.raises(ValueError, match="external_id must be a non-empty string"):
            Incident(
                external_id=123,
                title="Test",
                service="test",
                severity="high",
                status="triggered",
                created_at=datetime.now(),
                source="test"
            )
    
    def test_rejects_empty_title(self):
        """Should reject empty title"""
        with pytest.raises(ValueError, match="title must be a non-empty string"):
            Incident(
                external_id="INC-001",
                title="",
                service="test",
                severity="high",
                status="triggered",
                created_at=datetime.now(),
                source="test"
            )
    
    def test_rejects_empty_service(self):
        """Should reject empty service"""
        with pytest.raises(ValueError, match="service must be a non-empty string"):
            Incident(
                external_id="INC-001",
                title="Test",
                service="",
                severity="high",
                status="triggered",
                created_at=datetime.now(),
                source="test"
            )
    
    def test_rejects_invalid_severity(self):
        """Should reject invalid severity values"""
        with pytest.raises(ValueError, match=f"severity must be one of {VALID_SEVERITIES}"):
            Incident(
                external_id="INC-001",
                title="Test",
                service="test",
                severity="INVALID",
                status="triggered",
                created_at=datetime.now(),
                source="test"
            )
    
    def test_accepts_all_valid_severities(self):
        """Should accept all valid severity values"""
        for severity in VALID_SEVERITIES:
            incident = Incident(
                external_id=f"INC-{severity}",
                title="Test",
                service="test",
                severity=severity,
                status="triggered",
                created_at=datetime.now(),
                source="test"
            )
            assert incident.severity == severity
    
    def test_rejects_invalid_status(self):
        """Should reject invalid status values"""
        with pytest.raises(ValueError, match=f"status must be one of {VALID_STATUSES}"):
            Incident(
                external_id="INC-001",
                title="Test",
                service="test",
                severity="high",
                status="INVALID",
                created_at=datetime.now(),
                source="test"
            )
    
    def test_accepts_all_valid_statuses(self):
        """Should accept all valid status values"""
        for status in VALID_STATUSES:
            incident = Incident(
                external_id=f"INC-{status}",
                title="Test",
                service="test",
                severity="high",
                status=status,
                created_at=datetime.now(),
                source="test"
            )
            assert incident.status == status
    
    def test_rejects_resolved_before_created(self):
        """Should reject resolved_at before created_at"""
        created = datetime.now()
        resolved = created - timedelta(hours=1)
        
        with pytest.raises(ValueError, match="resolved_at.*cannot be before.*created_at"):
            Incident(
                external_id="INC-001",
                title="Test",
                service="test",
                severity="high",
                status="resolved",
                created_at=created,
                resolved_at=resolved,
                source="test"
            )
    
    def test_rejects_updated_before_created(self):
        """Should reject updated_at before created_at"""
        created = datetime.now()
        updated = created - timedelta(hours=1)
        
        with pytest.raises(ValueError, match="updated_at.*cannot be before.*created_at"):
            Incident(
                external_id="INC-001",
                title="Test",
                service="test",
                severity="high",
                status="acknowledged",
                created_at=created,
                updated_at=updated,
                source="test"
            )
    
    def test_rejects_non_datetime_created_at(self):
        """Should reject non-datetime created_at"""
        with pytest.raises(ValueError, match="created_at must be datetime"):
            Incident(
                external_id="INC-001",
                title="Test",
                service="test",
                severity="high",
                status="triggered",
                created_at="not-a-datetime",
                source="test"
            )
    
    def test_rejects_empty_source(self):
        """Should reject empty source"""
        with pytest.raises(ValueError, match="source must be a non-empty string"):
            Incident(
                external_id="INC-001",
                title="Test",
                service="test",
                severity="high",
                status="triggered",
                created_at=datetime.now(),
                source=""
            )
    
    def test_to_dict_serialization(self):
        """Should serialize to dict correctly"""
        now = datetime.now()
        incident = Incident(
            external_id="INC-001",
            title="Test Incident",
            service="test-service",
            severity="high",
            status="triggered",
            created_at=now,
            updated_at=now,
            resolved_at=None,
            source="test",
            runbook_path="runbooks/test/runbook.yaml",
            raw_payload={"key": "value"}
        )
        
        result = incident.to_dict()
        assert result['external_id'] == "INC-001"
        assert result['title'] == "Test Incident"
        assert result['service'] == "test-service"
        assert result['severity'] == "high"
        assert result['status'] == "triggered"
        assert result['created_at'] == now.isoformat()
        assert result['updated_at'] == now.isoformat()
        assert result['resolved_at'] is None
        assert result['source'] == "test"
        assert result['runbook_path'] == "runbooks/test/runbook.yaml"
        assert result['raw_payload'] == {"key": "value"}
    
    def test_to_dict_handles_none_values(self):
        """to_dict should handle None optional fields"""
        incident = Incident(
            external_id="INC-001",
            title="Test",
            service="test",
            severity="high",
            status="triggered",
            created_at=datetime.now(),
            source="test",
            updated_at=None,
            resolved_at=None,
            raw_payload=None
        )
        
        result = incident.to_dict()
        assert result['external_id'] == "INC-001"
        assert result['updated_at'] is None
        assert result['resolved_at'] is None
        assert result['raw_payload'] is None
    
    def test_valid_incident_with_all_optional_fields(self):
        """Should create incident with all optional fields"""
        now = datetime.now()
        incident = Incident(
            external_id="INC-001",
            title="Test Incident",
            service="test-service",
            severity="high",
            status="resolved",
            created_at=now,
            updated_at=now + timedelta(hours=1),
            resolved_at=now + timedelta(hours=2),
            source="test",
            runbook_path="runbooks/test/runbook.yaml",
            raw_payload={"incident_data": "value"}
        )
        
        assert incident.external_id == "INC-001"
        assert incident.runbook_path == "runbooks/test/runbook.yaml"
        assert incident.raw_payload == {"incident_data": "value"}
        assert incident.updated_at > incident.created_at
        assert incident.resolved_at > incident.updated_at


class TestIncidentSourceAbstractClass:
    """Test IncidentSource abstract base class"""
    
    def test_cannot_instantiate_abstract_class(self):
        """Should not allow direct instantiation"""
        with pytest.raises(TypeError):
            IncidentSource()
    
    def test_subclass_must_implement_source_name(self):
        """Subclass must implement source_name property"""
        class IncompleteSource(IncidentSource):
            def parse_webhook(self, payload):
                pass
            
            def sync_incidents(self):
                pass
        
        with pytest.raises(TypeError):
            IncompleteSource()
    
    def test_subclass_must_implement_parse_webhook(self):
        """Subclass must implement parse_webhook method"""
        class IncompleteSource(IncidentSource):
            @property
            def source_name(self) -> str:
                return "test"
            
            def sync_incidents(self):
                pass
        
        with pytest.raises(TypeError):
            IncompleteSource()
    
    def test_subclass_must_implement_sync_incidents(self):
        """Subclass must implement sync_incidents method"""
        class IncompleteSource(IncidentSource):
            @property
            def source_name(self) -> str:
                return "test"
            
            def parse_webhook(self, payload):
                pass
        
        with pytest.raises(TypeError):
            IncompleteSource()
    
    def test_validate_webhook_signature_default_returns_false(self, caplog):
        """Default signature validation should return False and log warning"""
        class TestSource(IncidentSource):
            @property
            def source_name(self) -> str:
                return "test"
            
            def parse_webhook(self, payload):
                pass
            
            def sync_incidents(self):
                pass
        
        source = TestSource()
        result = source.validate_webhook_signature(b"payload", "signature", "1234567890")
        
        assert result is False
        assert "validate_webhook_signature() called but not implemented" in caplog.text
        assert source.source_name == "test"
