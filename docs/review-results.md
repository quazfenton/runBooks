# runBookS - Deep Code Review Results
**Review Start Date:** March 3, 2026
**Review Type:** Line-by-Line Production Engineering Audit
**Reviewer:** Senior Engineering Agent
**Status:** IN PROGRESS

---

## Review Methodology

This review follows a meticulous, line-by-line examination of each file with:
- Control flow and data flow analysis
- Edge case identification
- Security vulnerability scanning
- Type correctness verification
- Cross-reference against provider SDK docs
- Concrete code diffs for each fix
- Accompanying test cases

---

## File Review Queue

| Priority | File | Status | Critical Issues | High Issues | Medium Issues |
|----------|------|--------|-----------------|-------------|---------------|
| P0 | `slack/handler.py` | ⏳ Pending | - | - | - |
| P0 | `api/app.py` | ⏳ Pending | - | - | - |
| P0 | `incident_sources/pagerduty.py` | ⏳ Pending | - | - | - |
| P0 | `incident_sources/datadog.py` | ⏳ Pending | - | - | - |
| P1 | `incident_sources/alertmanager.py` | ⏳ Pending | - | - | - |
| P1 | `incident_sources/sentry.py` | ⏳ Pending | - | - | - |
| P1 | `ai/llm_suggestion_engine.py` | ⏳ Pending | - | - | - |
| P1 | `ai/semantic_correlator.py` | ⏳ Pending | - | - | - |
| P1 | `ai/report_generator.py` | ⏳ Pending | - | - | - |
| P2 | `version_control/git_manager.py` | ⏳ Pending | - | - | - |
| P2 | `version_control/diff_engine.py` | ⏳ Pending | - | - | - |
| P2 | `version_control/rollback.py` | ⏳ Pending | - | - | - |
| P3 | `tests/test_integration.py` | ⏳ Pending | - | - | - |
| P3 | `tests/test_incident_sources.py` | ⏳ Pending | - | - | - |

---

## Critical Findings Summary (Top 10)

| # | Severity | File | Lines | Issue | Remediation |
|---|----------|------|-------|-------|-------------|
| 1 | 🔴 Critical | slack/handler.py | ~44-78 | Path traversal TOCTOU race condition | Add atomic path validation with file descriptor |
| 2 | 🔴 Critical | slack/handler.py | ~94-119 | Webhook replay attack (no timestamp check) | Add timestamp validation with 5-min window |
| 3 | 🔴 Critical | api/app.py | ~284-380 | No rate limiting on webhooks | Add FastAPI-Limiter middleware |
| 4 | 🔴 Critical | incident_sources/*.py | Multiple | Missing timeout on HTTP requests | Add 30s timeout to all requests |
| 5 | 🟠 High | slack/handler.py | ~156-170 | Insecure temp file permissions | Set 0600 permissions on temp files |
| 6 | 🟠 High | api/app.py | ~612 | Raw exception exposure | Return generic error messages |
| 7 | 🟠 High | incident_sources/sentry.py | Missing | No webhook signature validation | Implement HMAC-SHA256 validation |
| 8 | 🟠 High | ai/semantic_correlator.py | ~178-220 | Incomplete datetime parsing | Add robust timestamp parser |
| 9 | 🟡 Medium | slack/handler.py | ~167 | YAML output not sanitized | Add sanitize_for_yaml() function |
| 10 | 🟡 Medium | api/routes/incidents.py | All | Dead code (Flask blueprint never registered) | Remove file or integrate properly |

---

## Detailed File Reviews

### [FILE 1] slack/handler.py
**Status:** ✅ COMPLETE - Security fixes applied
**Lines:** 465 (was 334)
**Responsibilities:** Slack modal handling, runbook annotation, path validation

#### Function Analysis

##### `validate_runbook_path_secure(user_path: str, base_dir: Path) -> Tuple[Path, str]`
**Lines:** 67-124
**Purpose:** Securely validate and read runbook paths with atomic operations

**FIXES APPLIED:**

**Fix 1.1: TOCTOU Race Condition (🔴 CRITICAL) - FIXED**
- **Problem:** Path validated at time T1, file accessed at T2. Attacker can swap file between checks.
- **Solution Implemented:**
  - Atomic open with `os.O_NOFOLLOW` flag prevents symlink race conditions
  - Path normalization without resolving symlinks
  - Returns tuple of (path, content) for atomic read
- **Code Applied:** See lines 67-124 in slack/handler.py
- **Tests Required:** `tests/test_security.py::test_path_traversal_race_condition`

**Fix 1.2: YAML Injection Prevention (🟡 MEDIUM) - FIXED**
- **Problem:** Malicious input could inject YAML tags for code execution
- **Solution Implemented:**
  - Added `sanitize_for_yaml()` function (lines 219-241)
  - Escapes YAML tag injection vectors (!!python/object, etc.)
  - Removes control characters
- **Code Applied:** See lines 219-241 in slack/handler.py
- **Tests Required:** `tests/test_security.py::test_yaml_injection`

**Fix 1.3: Insecure Temp File Permissions (🟠 HIGH) - FIXED**
- **Problem:** `mkstemp()` creates files with default permissions (often 0644)
- **Solution Implemented:**
  - Added `os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)` for 0600 permissions
  - Only owner can read/write temp files
- **Code Applied:** See line 294 in slack/handler.py
- **Tests Required:** `tests/test_security.py::test_temp_file_permissions`

**Additional Improvements:**
- Added `PathSecurityError` custom exception class (line 62)
- Added structured logging for annotation operations
- Preserved field order with `sort_keys=False` in yaml.dump
- Added deprecation warning for legacy path validation function

**Issue 1.2: Missing Timestamp Validation (🔴 CRITICAL)**
- **Problem:** Webhook signature validation doesn't check timestamp, allowing replay attacks
- **Location:** Lines 94-119 (Slack signature validation)
- **Fix Required:**
```python
# BEFORE (vulnerable):
def verify_slack_signature(timestamp, signature, body):
    if not timestamp or not timestamp.isdigit():
        return False
    # Missing: timestamp age check!
    sig_basestring = f"v0:{timestamp}:" + body
    expected_signature = 'v0=' + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

# AFTER (secure):
import time

def verify_slack_signature(timestamp, signature, body):
    """Verify Slack signature with replay attack prevention."""
    if not SLACK_SIGNING_SECRET:
        raise ValueError("SLACK_SIGNING_SECRET environment variable is not set")
    
    # Verify timestamp format
    if not timestamp or not timestamp.isdigit():
        return False
    
    # Prevent replay attacks - reject timestamps older than 5 minutes
    current_time = int(time.time())
    if abs(current_time - int(timestamp)) > 300:  # 5 minutes
        logger.warning(f"Slack webhook timestamp too old: {timestamp}")
        return False
    
    sig_basestring = f"v0:{timestamp}:" + body
    expected_signature = 'v0=' + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)
```
- **Rationale:** 5-minute window prevents replay attacks while allowing for clock skew
- **Tests Required:** `tests/test_security.py::test_webhook_replay_attack`

**Issue 1.3: Insecure Temp File Permissions (🟠 HIGH)**
- **Problem:** `mkstemp()` creates files with default permissions (often 0644)
- **Location:** Lines 156-170
- **Fix Required:**
```python
# BEFORE (insecure):
temp_fd, temp_path = tempfile.mkstemp(
    suffix='.yaml',
    prefix='runbook_',
    dir=resolved_path.parent
)
try:
    with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
        yaml.dump(runbook, f, default_flow_style=False, allow_unicode=True)
    os.replace(temp_path, resolved_path)
except Exception:
    if os.path.exists(temp_path):
        os.unlink(temp_path)
    raise

# AFTER (secure):
import stat

temp_fd, temp_path = tempfile.mkstemp(
    suffix='.yaml',
    prefix='runbook_',
    dir=resolved_path.parent
)
try:
    # Set restrictive permissions (owner read/write only)
    os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    
    with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
        yaml.dump(runbook, f, default_flow_style=False, allow_unicode=True)
    os.replace(temp_path, resolved_path)
except Exception:
    if os.path.exists(temp_path):
        os.unlink(temp_path)
    raise
```
- **Rationale:** 0600 permissions prevent other users from reading sensitive incident data
- **Tests Required:** `tests/test_security.py::test_temp_file_permissions`

**Issue 1.4: YAML Output Not Sanitized (🟡 MEDIUM)**
- **Problem:** Malicious input could inject YAML tags for code execution
- **Location:** Lines 167
- **Fix Required:**
```python
# Add before append_annotation_to_runbook function:
def sanitize_for_yaml(value: Any) -> Any:
    """Sanitize values before YAML serialization to prevent tag injection."""
    if isinstance(value, str):
        # Remove potential YAML tag injection
        if value.startswith('!!') or value.startswith('!'):
            value = f"'{value}'"
        # Escape control characters
        value = value.replace('\x00', '').replace('\x08', '')
    elif isinstance(value, dict):
        return {k: sanitize_for_yaml(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [sanitize_for_yaml(v) for v in value]
    return value

# In append_annotation_to_runbook, before yaml.dump:
runbook = sanitize_for_yaml(runbook)
yaml.dump(runbook, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
```
- **Rationale:** Prevents YAML deserialization attacks
- **Tests Required:** `tests/test_security.py::test_yaml_injection`

---

### [FILE 2] api/app.py
**Status:** ✅ COMPLETE - Security hardening applied
**Lines:** 1066 (was 797)
**Responsibilities:** FastAPI application, webhook endpoints, rate limiting, error handling

**FIXES APPLIED:**

**Fix 2.1: Missing Rate Limiting (🔴 CRITICAL) - FIXED**
- **Problem:** No rate limiting on webhook endpoints, allowing DoS attacks
- **Solution Implemented:**
  - Added `RateLimiter` class with sliding window algorithm
  - Applied 30 requests/minute limit to all webhook endpoints
  - Added `Retry-After` header on rate limit exceeded
- **Code Applied:** Lines 67-131 (RateLimiter class), Lines 404-417 (rate limit check)
- **Tests Required:** `tests/test_api.py::test_rate_limiting_webhooks`

**Fix 2.2: Exception Details Leaked (🟠 HIGH) - FIXED**
- **Problem:** `raise HTTPException(status_code=500, detail=str(e))` leaks internal details
- **Solution Implemented:**
  - Changed all error handlers to return generic "Internal server error"
  - Added structured logging with `exc_info=True` for debugging
  - Added `SecurityFilter` to redact sensitive data from logs
- **Code Applied:** Lines 481-485, Lines 558-562, etc.
- **Tests Required:** `tests/test_security.py::test_no_exception_leak`

**Fix 2.3: Missing Input Validation (🟠 HIGH) - FIXED**
- **Problem:** No validation of webhook payloads or signature headers
- **Solution Implemented:**
  - Added `WebhookSignature` Pydantic model with timestamp validation
  - Added `IncidentWebhookPayload` model for payload validation
  - Added JSON parsing error handling
  - Added payload size limit (1MB)
- **Code Applied:** Lines 134-163 (Pydantic models), Lines 424-439 (validation)
- **Tests Required:** `tests/test_api.py::test_input_validation`

**Fix 2.4: Missing Security Logging (🟡 MEDIUM) - FIXED**
- **Problem:** No security event logging or sensitive data redaction
- **Solution Implemented:**
  - Added `SecurityFilter` logging filter
  - Redacts API keys, tokens, secrets, passwords from logs
  - Added structured logging for webhook events
- **Code Applied:** Lines 36-56 (SecurityFilter class)
- **Tests Required:** `tests/test_security.py::test_log_redaction`

**Additional Improvements:**
- Updated version to 2.1.1 (security patch)
- Added comprehensive docstrings to all webhook endpoints
- Added type hints for Request objects
- Improved error categorization (HTTPException vs generic Exception)

---

### [FILE 3] incident_sources/pagerduty.py
**Status:** ⏳ PENDING
**Lines:** 403
**Responsibilities:** PagerDuty webhook parsing, API sync, signature validation

*(Review continues below)*

---

## Tests To Add

### test_security.py (NEW FILE)
```python
#!/usr/bin/env python3
"""Security tests for runBookS"""

import unittest
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

class TestPathTraversal(unittest.TestCase):
    """Test path traversal protection."""
    
    def test_path_traversal_dotdot(self):
        """Test that ../ paths are rejected."""
        from slack.handler import validate_runbook_path_secure
        
        base_dir = Path("/tmp/test_base")
        base_dir.mkdir(exist_ok=True)
        
        with self.assertRaises(ValueError) as ctx:
            validate_runbook_path_secure("../etc/passwd", base_dir)
        self.assertIn("traversal", str(ctx.exception).lower())
    
    def test_path_traversal_absolute(self):
        """Test that absolute paths are rejected."""
        from slack.handler import validate_runbook_path_secure
        
        base_dir = Path("/tmp/test_base")
        
        with self.assertRaises(ValueError) as ctx:
            validate_runbook_path_secure("/etc/passwd", base_dir)
        self.assertIn("absolute", str(ctx.exception).lower())
    
    def test_symlink_rejected(self):
        """Test that symlinks are rejected."""
        from slack.handler import validate_runbook_path_secure
        import os
        
        base_dir = Path(tempfile.mkdtemp())
        target = Path("/etc/passwd")
        symlink = base_dir / "symlink"
        
        try:
            os.symlink(target, symlink)
            with self.assertRaises(ValueError) as ctx:
                validate_runbook_path_secure("symlink", base_dir)
            self.assertIn("symlink", str(ctx.exception).lower())
        finally:
            import shutil
            shutil.rmtree(base_dir)

class TestWebhookReplay(unittest.TestCase):
    """Test webhook replay attack prevention."""
    
    def test_old_timestamp_rejected(self):
        """Test that old timestamps are rejected."""
        from slack.app import verify_slack_signature
        
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago
        body = '{"test": "data"}'
        signature = "v0=" + "a" * 64  # Fake signature
        
        result = verify_slack_signature(old_timestamp, signature, body)
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
```

---

## Environment Variables To Add

### .env.example Updates
```bash
# ============================================
# Security
# ============================================
# Enable/disable path traversal protection (always true in production)
SECURE_PATH_VALIDATION=true

# Webhook timestamp tolerance (seconds)
WEBHOOK_TIMESTAMP_TOLERANCE=300

# Rate limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_BURST=10

# ============================================
# Timeouts
# ============================================
# HTTP request timeout (seconds)
HTTP_TIMEOUT=30

# Webhook processing timeout (seconds)
WEBHOOK_TIMEOUT=10
```

---

## Next Files To Review

1. **api/app.py** - Check rate limiting, error handling, endpoint security
2. **incident_sources/pagerduty.py** - Verify signature validation, timeouts
3. **incident_sources/datadog.py** - Check signature validation, error handling
4. **incident_sources/sentry.py** - Add missing signature validation
5. **ai/llm_suggestion_engine.py** - Check API key handling, fallback logic

---

*Review in progress. Next update after api/app.py review.*
