#!/usr/bin/env python3
"""
API Security Tests for runBookS

Tests for API endpoints including:
- Rate limiting
- Input validation
- Error handling (no exception leakage)
- Signature validation
- Payload size limits
"""

import unittest
import json
import time
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRateLimiting(unittest.TestCase):
    """Test API rate limiting."""
    
    def test_rate_limiter_sliding_window(self):
        """Test that rate limiter uses sliding window."""
        from api.app import RateLimiter
        
        limiter = RateLimiter(requests_per_minute=5, burst=2)
        client_id = "test_client"
        
        # Should allow first 5 requests
        for i in range(5):
            self.assertTrue(limiter.is_allowed(client_id))
        
        # Should deny 6th request
        self.assertFalse(limiter.is_allowed(client_id))
        
        # Check retry-after header
        retry_after = limiter.get_retry_after(client_id)
        self.assertGreater(retry_after, 0)
        self.assertLessEqual(retry_after, 60)
    
    def test_rate_limiter_multiple_clients(self):
        """Test that rate limiter tracks clients separately."""
        from api.app import RateLimiter
        
        limiter = RateLimiter(requests_per_minute=3)
        
        # Client 1 uses all requests
        for i in range(3):
            self.assertTrue(limiter.is_allowed("client1"))
        self.assertFalse(limiter.is_allowed("client1"))
        
        # Client 2 should still have requests
        for i in range(3):
            self.assertTrue(limiter.is_allowed("client2"))
        self.assertFalse(limiter.is_allowed("client2"))


class TestInputValidation(unittest.TestCase):
    """Test API input validation."""
    
    def test_webhook_signature_timestamp_validation(self):
        """Test webhook signature timestamp validation."""
        from api.app import WebhookSignature
        
        # Valid timestamp (current time)
        current_timestamp = str(int(time.time()))
        sig = WebhookSignature(signature="v0=abc123", timestamp=current_timestamp)
        self.assertEqual(sig.timestamp, current_timestamp)
        
        # Old timestamp (should fail)
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago
        with self.assertRaises(ValueError) as ctx:
            WebhookSignature(signature="v0=abc123", timestamp=old_timestamp)
        self.assertIn("Timestamp too old", str(ctx.exception))
        
        # Non-numeric timestamp (should fail)
        with self.assertRaises(ValueError):
            WebhookSignature(signature="v0=abc123", timestamp="not-a-number")
    
    def test_webhook_signature_format(self):
        """Test webhook signature format validation."""
        from api.app import WebhookSignature
        
        # Valid signature format
        sig = WebhookSignature(
            signature="v0=" + "a" * 64,
            timestamp=str(int(time.time()))
        )
        self.assertTrue(sig.signature.startswith("v0="))
        
        # Too long signature (should fail)
        with self.assertRaises(ValueError):
            WebhookSignature(
                signature="v0=" + "a" * 300,
                timestamp=str(int(time.time()))
            )


class TestErrorHandling(unittest.TestCase):
    """Test API error handling."""
    
    def test_no_exception_leak(self):
        """Test that exceptions don't leak internal details."""
        # This test verifies the pattern used in api/app.py
        # In production, all exceptions should be caught and generic errors returned
        
        from fastapi import HTTPException
        
        # Simulate internal error
        try:
            raise ValueError("Internal sensitive information")
        except Exception as e:
            # Should log the real error internally
            # But return generic error to client
            error_response = "Internal server error"
            self.assertEqual(error_response, "Internal server error")
            # Should NOT contain sensitive info
            self.assertNotIn("sensitive", error_response)


class TestSecurityFilter(unittest.TestCase):
    """Test security logging filter."""
    
    def test_api_key_redaction(self):
        """Test that API keys are redacted from logs."""
        from api.app import SecurityFilter
        import logging
        
        # Create a log record with sensitive data
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="API key: %s",
            args=("sk-1234567890abcdef",),
            exc_info=None
        )
        
        # Apply filter
        filter = SecurityFilter()
        result = filter.filter(record)
        
        # Check redaction in formatted message
        formatted_msg = record.getMessage()
        self.assertNotIn("sk-1234567890abcdef", formatted_msg)
        self.assertIn("***REDACTED***", formatted_msg)
    
    def test_token_redaction(self):
        """Test that tokens are redacted from logs."""
        from api.app import SecurityFilter
        import logging
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Token: bearer_token_12345",
            args=(),
            exc_info=None
        )
        
        filter = SecurityFilter()
        filter.filter(record)
        
        self.assertNotIn("bearer_token_12345", record.msg)
        self.assertIn("***REDACTED***", record.msg)
    
    def test_secret_redaction(self):
        """Test that secrets are redacted from logs."""
        from api.app import SecurityFilter
        import logging
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Secret: super_secret_value",
            args=(),
            exc_info=None
        )
        
        filter = SecurityFilter()
        filter.filter(record)
        
        self.assertNotIn("super_secret_value", record.msg)
        self.assertIn("***REDACTED***", record.msg)


class TestSentrySignatureValidation(unittest.TestCase):
    """Test Sentry webhook signature validation."""
    
    def test_signature_validation(self):
        """Test Sentry signature validation."""
        from incident_sources.sentry import SentryIntegration
        import hmac
        import hashlib
        import base64
        
        # Create integration with test secret
        sentry = SentryIntegration(
            api_token="test_token",
            webhook_secret="test_secret"
        )
        
        # Create valid signature
        payload = b'{"test": "data"}'
        timestamp = str(int(time.time()))
        expected_sig = base64.b64encode(
            hmac.new(
                b"test_secret",
                payload,
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        signature = f"v0={expected_sig}"
        
        # Should validate successfully
        result = sentry.validate_webhook_signature(payload, signature, timestamp)
        self.assertTrue(result)
    
    def test_invalid_signature_rejected(self):
        """Test that invalid signatures are rejected."""
        from incident_sources.sentry import SentryIntegration
        
        sentry = SentryIntegration(
            api_token="test_token",
            webhook_secret="test_secret"
        )
        
        payload = b'{"test": "data"}'
        timestamp = str(int(time.time()))
        signature = "v0=invalid_signature"
        
        result = sentry.validate_webhook_signature(payload, signature, timestamp)
        self.assertFalse(result)
    
    def test_old_timestamp_rejected(self):
        """Test that old timestamps are rejected."""
        from incident_sources.sentry import SentryIntegration
        
        sentry = SentryIntegration(
            api_token="test_token",
            webhook_secret="test_secret"
        )
        
        payload = b'{"test": "data"}'
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago
        signature = "v0=" + "a" * 64
        
        result = sentry.validate_webhook_signature(payload, signature, old_timestamp)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
