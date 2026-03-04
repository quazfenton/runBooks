# runBookS - Technical Implementation Plan
**Date:** March 3, 2026
**Version:** 2.1.1 (Security Patch Release)
**Status:** APPROVED FOR IMPLEMENTATION

---

## Executive Summary

This technical plan outlines the prioritized implementation tasks to address critical security vulnerabilities, incomplete implementations, and production hardening needs identified during the deep code review.

### Implementation Phases

| Phase | Duration | Focus | Risk Level |
|-------|----------|-------|------------|
| Phase 1 | Week 1 | Critical Security Fixes | 🔴 High (breaking changes) |
| Phase 2 | Week 2 | Error Handling & Retries | 🟡 Medium |
| Phase 3 | Week 3 | Test Coverage Expansion | 🟢 Low |
| Phase 4 | Week 4 | Production Hardening | 🟢 Low |

---

## Phase 1: Critical Security Fixes (Week 1)

### Epic 1.1: Path Traversal Protection
**Priority:** P0 - Blocker
**Estimated Effort:** 8 hours
**Risk:** Low (backward compatible)

#### Tasks

**Task 1.1.1: Implement Atomic Path Validation**
- **File:** `slack/handler.py`
- **Lines:** 44-78
- **Description:** Replace vulnerable path validation with atomic open
- **Code Diff:** See `docs/review-results.md` Issue 1.1
- **Tests:** `tests/test_security.py::test_path_traversal_race_condition`
- **Migration:** None required (drop-in replacement)
- **Rollback:** Revert to previous handler.py

**Task 1.1.2: Add Path Validation Utility Module**
- **File:** `lib/security/path_utils.py` (NEW)
- **Description:** Centralized path validation for all modules
- **Code:**
```python
"""Secure path utilities for runBookS"""
import os
import errno
from pathlib import Path
from typing import Tuple, Optional

class PathSecurityError(Exception):
    """Raised when path validation fails."""
    pass

def safe_path_join(base: Path, *paths: str) -> Path:
    """
    Securely join paths, preventing traversal attacks.
    
    Args:
        base: Base directory that result must be within
        *paths: Path components to join
        
    Returns:
        Resolved Path within base directory
        
    Raises:
        PathSecurityError: If result escapes base directory
    """
    base = base.resolve()
    result = (base / Path(*paths)).resolve()
    
    try:
        result.relative_to(base)
    except ValueError:
        raise PathSecurityError(
            f"Path traversal detected: {result} is not within {base}"
        )
    
    return result

def atomic_file_read(path: Path) -> Tuple[Path, str]:
    """
    Atomically read file with symlink protection.
    
    Args:
        path: Path to file
        
    Returns:
        Tuple of (resolved_path, content)
        
    Raises:
        PathSecurityError: If path is symlink or escapes allowed directory
        FileNotFoundError: If file doesn't exist
    """
    # Check for symlinks
    if path.is_symlink():
        raise PathSecurityError(f"Symlinks not allowed: {path}")
    
    # Check parent directories for symlinks
    for parent in path.parents:
        if parent.is_symlink():
            raise PathSecurityError(f"Symlink in path: {parent}")
    
    # Open with O_NOFOLLOW
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'r', encoding='utf-8') as f:
            content = f.read()
        return path, content
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise PathSecurityError(f"Symlink detected: {path}")
        raise

def validate_path_within_directory(path: Path, allowed_dir: Path) -> bool:
    """
    Validate that path is within allowed directory.
    
    Returns:
        True if valid, raises PathSecurityError otherwise
    """
    path = path.resolve()
    allowed_dir = allowed_dir.resolve()
    
    try:
        path.relative_to(allowed_dir)
        return True
    except ValueError:
        raise PathSecurityError(
            f"Path {path} is not within allowed directory {allowed_dir}"
        )
```
- **Tests:** `tests/test_security.py::test_safe_path_join_*`

---

### Epic 1.2: Webhook Security Hardening
**Priority:** P0 - Blocker
**Estimated Effort:** 6 hours
**Risk:** Low

#### Tasks

**Task 1.2.1: Add Timestamp Validation to All Webhooks**
- **Files:** `slack/app.py`, `incident_sources/*.py`
- **Description:** Prevent replay attacks with timestamp validation
- **Code Diff:** See `docs/review-results.md` Issue 1.2
- **Tests:** `tests/test_security.py::test_webhook_replay_attack`
- **Migration:** Update webhook clients to send current timestamp
- **Rollback:** Revert timestamp validation

**Task 1.2.2: Implement Sentry Signature Validation**
- **File:** `incident_sources/sentry.py`
- **Lines:** Add after line 50
- **Code:**
```python
def validate_webhook_signature(
    self,
    payload: bytes,
    signature: str,
    timestamp: str
) -> bool:
    """
    Validate Sentry webhook signature.
    
    Sentry uses HMAC-SHA256 with the webhook secret.
    Signature format: v0=base64(hmac-sha256(secret, body))
    
    Args:
        payload: Raw request body bytes
        signature: Signature header
        timestamp: Timestamp header
        
    Returns:
        True if signature is valid
    """
    if not self.webhook_secret:
        return True  # Skip if not configured
    
    try:
        import time
        import base64
        
        # Validate timestamp
        if not timestamp or not timestamp.isdigit():
            return False
        
        current_time = int(time.time())
        if abs(current_time - int(timestamp)) > 300:  # 5 minutes
            logger.warning(f"Sentry webhook timestamp too old: {timestamp}")
            return False
        
        # Parse signature
        if '=' not in signature:
            return False
        
        version, provided_sig = signature.split('=', 1)
        if version != 'v0':
            return False
        
        # Calculate expected signature
        message = payload
        expected_sig = base64.b64encode(
            hmac.new(
                self.webhook_secret.encode('utf-8'),
                message,
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return hmac.compare_digest(provided_sig, expected_sig)
        
    except Exception as e:
        logger.error(f"Error validating Sentry webhook: {e}", exc_info=True)
        return False
```
- **Tests:** `tests/test_incident_sources.py::test_sentry_webhook_signature`

---

### Epic 1.3: Rate Limiting
**Priority:** P0 - Blocker
**Estimated Effort:** 4 hours
**Risk:** Medium (may affect high-volume users)

#### Tasks

**Task 1.3.1: Add FastAPI-Limiter to API**
- **File:** `api/app.py`
- **Lines:** Add after imports
- **Code:**
```python
# Add to imports
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from fastapi import Request

# Add to startup event
@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("Starting Living Runbooks API...")
    
    # Initialize rate limiter with Redis
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    import redis
    redis_client = redis.from_url(redis_url)
    await FastAPILimiter.init(redis_client)
    
    asyncio.create_task(broadcast_metrics_updates())
    logger.info("Background metrics broadcast started")

# Add to webhook endpoints
@app.post("/api/incidents/webhooks/pagerduty")
async def pagerduty_webhook(
    request: Request,
    _ = Depends(RateLimiter(times=10, seconds=60))  # 10 per minute
):
    """Receive PagerDuty incident webhooks (rate limited)."""
    ...
```
- **Tests:** `tests/test_api.py::test_rate_limiting`
- **Migration:** Deploy Redis alongside API
- **Rollback:** Remove RateLimiter dependency

**Task 1.3.2: Add Rate Limit Configuration**
- **File:** `.env.example`
- **Add:**
```bash
# Rate limiting
REDIS_URL=redis://localhost:6379
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

---

## Phase 2: Error Handling & Retries (Week 2)

### Epic 2.1: HTTP Timeout & Retry Logic
**Priority:** P1 - High
**Estimated Effort:** 12 hours
**Risk:** Low

#### Tasks

**Task 2.1.1: Add Timeouts to All HTTP Requests**
- **Files:** `incident_sources/*.py`, `ai/*.py`
- **Description:** Prevent hanging requests
- **Code Pattern:**
```python
# In all HTTP client classes
DEFAULT_TIMEOUT = int(os.environ.get('HTTP_TIMEOUT', '30'))

response = self.session.get(
    url,
    params=params,
    timeout=DEFAULT_TIMEOUT  # Add this to ALL requests
)
```
- **Tests:** `tests/test_timeouts.py::test_http_timeout`

**Task 2.1.2: Implement Retry with Exponential Backoff**
- **File:** `lib/utils/retry.py` (NEW)
- **Code:**
```python
"""Retry utilities with exponential backoff"""
from functools import wraps
from typing import Callable, Type, Tuple
import time
import random
import logging

logger = logging.getLogger(__name__)

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to delay
        exceptions: Tuple of exception types to retry
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    # Add jitter
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    time.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator

# Usage example:
@retry_with_backoff(
    max_retries=3,
    exceptions=(requests.RequestException,)
)
def fetch_incidents():
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()
```
- **Tests:** `tests/test_retry.py::test_exponential_backoff`

---

## Phase 3: Test Coverage Expansion (Week 3)

### Epic 3.1: Security Test Suite
**Priority:** P1 - High
**Estimated Effort:** 16 hours
**Risk:** None

#### Tasks

**Task 3.1.1: Create Security Test Module**
- **File:** `tests/test_security.py`
- **Tests to Add:**
  - Path traversal attacks
  - Symlink attacks
  - Webhook replay attacks
  - YAML injection
  - Input validation
  - Rate limiting
  - JWT validation (when added)

**Task 3.1.2: Add Integration Tests**
- **File:** `tests/test_integration_enhanced.py`
- **Tests to Add:**
  - End-to-end webhook processing
  - Database transaction rollback
  - Concurrent annotation handling
  - Error recovery scenarios

---

## Phase 4: Production Hardening (Week 4)

### Epic 4.1: Monitoring & Observability
**Priority:** P2 - Medium
**Estimated Effort:** 8 hours
**Risk:** None

#### Tasks

**Task 4.1.1: Add Structured Logging**
- **File:** `lib/logging_config.py` (NEW)
- **Code:**
```python
"""Structured logging configuration"""
import logging
import sys
import json
from typing import Any, Dict

class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "level": record.levelname,
            "timestamp": self.formatTime(record),
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'lineno', 'funcName', 'created',
                          'msecs', 'relativeCreated', 'thread', 'threadName',
                          'processName', 'process', 'message']:
                log_data[key] = value
        
        return json.dumps(log_data)

def setup_logging(log_level: str = "INFO", log_file: str = None):
    """Configure structured logging."""
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers
    )
    
    # Set JSON formatter for all handlers
    json_formatter = JSONFormatter()
    for handler in logging.getLogger().handlers:
        handler.setFormatter(json_formatter)
```

---

## CI/CD Changes

### GitHub Actions Workflow (NEW)
**.github/workflows/ci.yml:**
```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install black mypy flake8
      - name: Run linters
        run: |
          black --check .
          mypy .
          flake8 .

  test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt pytest pytest-cov
      - name: Run tests
        run: pytest tests/ -v --cov=. --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run security scan
        run: pip install bandit && bandit -r . -ll
```

---

## Test Coverage Goals

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| slack.handler | 95% | 98% | High |
| incident_sources.* | 92% | 95% | High |
| api.app | 85% | 90% | High |
| ai.* | 85% | 90% | Medium |
| version_control.* | 82% | 85% | Medium |
| **Overall** | **88%** | **92%** | High |

---

## Migration & Rollback Plan

### Migration Steps

1. **Pre-deployment:**
   - Backup all runbook YAML files
   - Export current incident data
   - Notify users of maintenance window

2. **Deployment:**
   - Deploy to staging first
   - Run security test suite
   - Deploy to production with feature flags

3. **Post-deployment:**
   - Monitor error rates
   - Verify webhook processing
   - Check rate limiting behavior

### Rollback Triggers

Rollback immediately if:
- Error rate increases > 5%
- Webhook processing fails > 10%
- Path validation blocks legitimate requests

### Rollback Procedure

```bash
# Revert to previous version
git revert HEAD
docker-compose restart api
docker-compose restart slack

# Verify rollback
curl http://localhost:8000/health
```

---

## Implementation Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Security Fixes | Path validation, webhook security, rate limiting |
| 2 | Error Handling | Timeouts, retries, circuit breakers |
| 3 | Testing | Security tests, integration tests |
| 4 | Hardening | Logging, monitoring, documentation |

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking changes to webhooks | Low | High | Feature flags, gradual rollout |
| Rate limiting affects users | Medium | Medium | High burst limits, monitoring |
| Path validation blocks legit requests | Low | Medium | Extensive testing, rollback plan |
| Redis dependency for rate limiting | Medium | Low | Graceful degradation if Redis unavailable |

---

## Success Metrics

- **Security:** 0 critical vulnerabilities in security scan
- **Reliability:** 99.9% webhook processing success rate
- **Performance:** < 200ms average API response time
- **Coverage:** > 92% test coverage
- **Errors:** < 1% error rate in production

---

*Technical Plan Approved: March 3, 2026*
*Next Review: March 10, 2026*
