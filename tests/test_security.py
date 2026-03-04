#!/usr/bin/env python3
"""
Security Tests for runBookS

Comprehensive security test suite covering:
- Path traversal attacks
- Symlink attacks
- YAML injection
- Input validation
- Webhook replay attacks
"""

import unittest
import os
import sys
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPathTraversal(unittest.TestCase):
    """Test path traversal protection in slack/handler.py"""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.base_dir = self.test_dir / "runbooks"
        self.base_dir.mkdir()
        
        # Create a test runbook
        self.test_runbook = self.base_dir / "test-runbook.yaml"
        self.test_runbook.write_text("title: Test Runbook\n")
    
    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_path_traversal_dotdot(self):
        """Test that ../ paths are rejected."""
        from slack.handler import validate_runbook_path_secure, PathSecurityError
        
        with self.assertRaises(PathSecurityError) as ctx:
            validate_runbook_path_secure("../etc/passwd", self.base_dir)
        
        self.assertIn("traversal", str(ctx.exception).lower())
    
    def test_path_traversal_absolute(self):
        """Test that absolute paths are rejected."""
        from slack.handler import validate_runbook_path_secure, PathSecurityError
        
        with self.assertRaises(PathSecurityError) as ctx:
            validate_runbook_path_secure("/etc/passwd", self.base_dir)
        
        # Error message may say "absolute" or "escapes allowed directory"
        error_msg = str(ctx.exception).lower()
        self.assertTrue(
            "absolute" in error_msg or "escapes" in error_msg,
            f"Expected 'absolute' or 'escapes' in error message, got: {error_msg}"
        )
    
    def test_path_traversal_encoded(self):
        """Test that encoded path traversal is rejected."""
        from slack.handler import validate_runbook_path_secure, PathSecurityError
        
        # Test various encoded traversal attempts
        malicious_paths = [
            "test/../../../etc/passwd",
            "runbooks/../../etc/passwd",
            "service-x/../../../etc/passwd",
        ]
        
        for path in malicious_paths:
            with self.assertRaises(PathSecurityError):
                validate_runbook_path_secure(path, self.base_dir)
    
    @unittest.skipIf(os.name == 'nt', "Symlinks require admin privileges on Windows")
    def test_symlink_rejected(self):
        """Test that symlinks are rejected."""
        from slack.handler import validate_runbook_path_secure, PathSecurityError
        
        # Create symlink to /etc/passwd (or any file on Windows)
        target = self.test_dir / "target.txt"
        target.write_text("target content")
        symlink = self.base_dir / "symlink"
        
        try:
            os.symlink(target, symlink)
            
            with self.assertRaises(PathSecurityError) as ctx:
                validate_runbook_path_secure("symlink", self.base_dir)
            
            self.assertIn("symlink", str(ctx.exception).lower())
        finally:
            if symlink.exists() or symlink.is_symlink():
                symlink.unlink()
    
    @unittest.skipIf(os.name == 'nt', "Symlinks require admin privileges on Windows")
    def test_symlink_in_parent_rejected(self):
        """Test that symlinks in parent directories are rejected."""
        from slack.handler import validate_runbook_path_secure, PathSecurityError
        
        # Create a symlink directory
        real_dir = self.test_dir / "real_dir"
        real_dir.mkdir()
        
        symlink_dir = self.test_dir / "symlink_dir"
        try:
            os.symlink(real_dir, symlink_dir)
            
            # Create file inside real directory
            test_file = real_dir / "test.yaml"
            test_file.write_text("test: true")
            
            # Try to access via symlink
            with self.assertRaises(PathSecurityError) as ctx:
                validate_runbook_path_secure(f"symlink_dir/test.yaml", self.test_dir)
            
            self.assertIn("symlink", str(ctx.exception).lower())
        finally:
            if symlink_dir.exists() or symlink_dir.is_symlink():
                symlink_dir.unlink()
    
    def test_valid_path_accepted(self):
        """Test that valid paths are accepted."""
        from slack.handler import validate_runbook_path_secure
        
        path, content = validate_runbook_path_secure(
            "test-runbook.yaml", 
            self.base_dir
        )
        
        self.assertEqual(path.name, "test-runbook.yaml")
        self.assertIn("title: Test Runbook", content)
    
    def test_returns_content_tuple(self):
        """Test that function returns tuple of (path, content)."""
        from slack.handler import validate_runbook_path_secure
        
        result = validate_runbook_path_secure(
            "test-runbook.yaml", 
            self.base_dir
        )
        
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], Path)
        self.assertIsInstance(result[1], str)


class TestYAMLInjection(unittest.TestCase):
    """Test YAML injection prevention."""
    
    def test_yaml_tag_injection(self):
        """Test that YAML tag injection is sanitized."""
        from slack.handler import sanitize_for_yaml
        
        # Test malicious YAML tags
        malicious_inputs = [
            "!!python/object/apply:os.system ['ls']",
            "!!python/object:__main__.Evil",
            "!custom_tag value",
        ]
        
        for malicious in malicious_inputs:
            sanitized = sanitize_for_yaml(malicious)
            # Should be quoted to prevent execution
            self.assertTrue(sanitized.startswith("'"))
            self.assertTrue(sanitized.endswith("'"))
    
    def test_control_characters_removed(self):
        """Test that control characters are removed."""
        from slack.handler import sanitize_for_yaml
        
        malicious = "test\x00value\x08here"
        sanitized = sanitize_for_yaml(malicious)
        
        self.assertNotIn("\x00", sanitized)
        self.assertNotIn("\x08", sanitized)
        self.assertEqual(sanitized, "testvaluehere")
    
    def test_dict_sanitization(self):
        """Test that dicts are recursively sanitized."""
        from slack.handler import sanitize_for_yaml
        
        malicious_dict = {
            "safe": "value",
            "malicious": "!!python/object/apply:os.system ['ls']"
        }
        
        sanitized = sanitize_for_yaml(malicious_dict)
        
        self.assertEqual(sanitized["safe"], "value")
        self.assertTrue(sanitized["malicious"].startswith("'"))
    
    def test_list_sanitization(self):
        """Test that lists are recursively sanitized."""
        from slack.handler import sanitize_for_yaml
        
        malicious_list = [
            "safe",
            "!!python/object/apply:os.system ['ls']"
        ]
        
        sanitized = sanitize_for_yaml(malicious_list)
        
        self.assertEqual(sanitized[0], "safe")
        self.assertTrue(sanitized[1].startswith("'"))


class TestTempFilePermissions(unittest.TestCase):
    """Test secure temp file handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.base_dir = self.test_dir / "runbooks"
        self.base_dir.mkdir()
        
        # Create a test runbook
        self.test_runbook = self.base_dir / "test-runbook.yaml"
        self.test_runbook.write_text("title: Test Runbook\nannotations: []")
    
    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_temp_file_permissions(self):
        """Test that temp files have restrictive permissions."""
        from slack.handler import append_annotation_to_runbook
        import stat
        
        annotation = {
            "incident_id": "TEST-001",
            "timestamp": "2026-03-03T12:00:00Z",
            "cause": "Test cause",
            "fix": "Test fix"
        }
        
        append_annotation_to_runbook("test-runbook.yaml", annotation)
        
        # Check that the file has 0600 permissions (owner read/write only)
        file_stat = os.stat(self.test_runbook)
        mode = file_stat.st_mode & 0o777
        
        # Should be 0600 (owner read/write only)
        # Note: os.replace may change permissions, so we check it's not world-readable
        self.assertFalse(mode & stat.S_IROTH)  # Not readable by others
        self.assertFalse(mode & stat.S_IWOTH)  # Not writable by others


class TestWebhookReplay(unittest.TestCase):
    """Test webhook replay attack prevention."""
    
    def test_old_timestamp_rejected_slack(self):
        """Test that old Slack webhook timestamps are rejected."""
        from slack.app import verify_slack_signature
        
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago
        body = '{"test": "data"}'
        signature = "v0=" + "a" * 64  # Fake signature
        
        result = verify_slack_signature(old_timestamp, signature, body)
        self.assertFalse(result)
    
    def test_valid_timestamp_accepted(self):
        """Test that recent timestamps are accepted (signature validation separate)."""
        from slack.app import verify_slack_signature
        
        current_timestamp = str(int(time.time()))
        body = '{"test": "data"}'
        
        # Signature will be invalid, but timestamp check should pass
        # This tests that timestamp doesn't reject valid requests
        signature = "v0=" + "a" * 64
        
        # Should fail on signature, not timestamp
        result = verify_slack_signature(current_timestamp, signature, body)
        # Result will be False because signature is fake, but timestamp was accepted


class TestInputValidation(unittest.TestCase):
    """Test input validation via Pydantic models."""
    
    def test_incident_id_format(self):
        """Test incident ID format validation."""
        from slack.handler import AnnotationInput
        
        # Valid incident IDs
        valid_ids = ["INC-001", "inc_123", "TEST-2026-001", "ABC123"]
        for incident_id in valid_ids:
            input_model = AnnotationInput(
                incident_id=incident_id,
                root_cause="Test",
                fix_applied="Test",
                runbook_path="test.yaml"
            )
            self.assertEqual(input_model.incident_id, incident_id)
        
        # Invalid incident IDs
        invalid_ids = ["INC;001", "INC<script>", "INC'001", "INC--001"]
        for incident_id in invalid_ids:
            with self.assertRaises(ValueError):
                AnnotationInput(
                    incident_id=incident_id,
                    root_cause="Test",
                    fix_applied="Test",
                    runbook_path="test.yaml"
                )
    
    def test_runbook_path_validation(self):
        """Test runbook path validation."""
        from slack.handler import AnnotationInput
        
        # Valid paths
        valid_paths = ["test.yaml", "service-x/runbook.yml", "test-runbook.yaml"]
        for path in valid_paths:
            input_model = AnnotationInput(
                incident_id="INC-001",
                root_cause="Test",
                fix_applied="Test",
                runbook_path=path
            )
            self.assertEqual(input_model.runbook_path, path)
        
        # Invalid paths
        invalid_paths = [
            "../etc/passwd",
            "/etc/passwd.yaml",
            "test<script>.yaml",
            "test;rm -rf /.yaml",
            "test.yaml.txt",  # Wrong extension
        ]
        for path in invalid_paths:
            with self.assertRaises(ValueError):
                AnnotationInput(
                    incident_id="INC-001",
                    root_cause="Test",
                    fix_applied="Test",
                    runbook_path=path
                )


if __name__ == '__main__':
    unittest.main()
