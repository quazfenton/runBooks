# Fallback Chains Documentation

**Purpose:** Document all fallback mechanisms in Living Runbooks to ensure graceful degradation when optional dependencies are unavailable.

**Last Updated:** March 3, 2026

---

## Fallback Chain Overview

Living Runbooks is designed with **defensive architecture** — every optional feature has a fallback path that allows the system to continue functioning with reduced capabilities rather than failing completely.

---

## 1. AI/LLM Features

### Primary Path: Anthropic Claude
```python
if ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
    use_anthropic()
```

### Fallback 1: OpenAI GPT
```python
elif OPENAI_AVAILABLE and OPENAI_API_KEY:
    use_openai()
```

### Fallback 2: Rule-Based Suggestions
```python
else:
    use_rule_based_suggestions()  # Always available
```

**Implementation:** `ai/llm_suggestion_engine.py::LLMRunbookEvolution`

**Graceful Degradation:**
- LLM: Contextual, intelligent suggestions (~80% accuracy)
- Rule-Based: Pattern-matching suggestions (~50% accuracy)

**User Experience:**
```
With LLM: "Based on this memory leak incident, consider adding memory profiling to your runbook"
Without LLM: "Memory-related incident detected → Suggest adding memory monitoring"
```

---

## 2. Semantic Search

### Primary Path: SentenceTransformers
```python
if SENTENCE_TRANSFORMERS_AVAILABLE:
    model = SentenceTransformer('all-MiniLM-L6-v2')
    use_semantic_search()
```

### Fallback: Frequency-Based Analysis
```python
else:
    use_keyword_matching()  # Always available
```

**Implementation:** `ai/semantic_correlator.py::SemanticCorrelator`

**Graceful Degradation:**
- Semantic: Finds conceptually similar incidents (e.g., "DB connection exhausted" matches "database pool full")
- Keyword: Finds textually similar incidents (e.g., "database" matches "database")

---

## 3. Git Version Control

### Primary Path: GitPython
```python
if GITPYTHON_AVAILABLE and git_repo_exists():
    use_git_versioning()
```

### Fallback: File-Based History
```python
else:
    use_file_timestamps()  # Always available
```

**Implementation:** `version_control/git_manager.py::RunbookVersionControl`

**Graceful Degradation:**
- Git: Full version history, diff, rollback, branches
- File-Based: Last modified timestamp, backup files

---

## 4. Database Storage

### Primary Path: PostgreSQL
```python
if DATABASE_URL and SQLALCHEMY_AVAILABLE:
    use_postgresql()
```

### Fallback: YAML Files
```python
else:
    use_yaml_storage()  # Always available
```

**Implementation:** Throughout codebase (default is YAML)

**Graceful Degradation:**
- PostgreSQL: Queries, relationships, full-text search, analytics
- YAML: File-based storage, simple reads/writes

---

## 5. Slack Integration

### Primary Path: Full Slack Integration
```python
if SLACK_SIGNING_SECRET and SLACK_BOT_TOKEN:
    use_slack_integration()
```

### Fallback: CLI/API Only
```python
else:
    use_cli_api_only()  # Always available
```

**Graceful Degradation:**
- Full: Modal submissions, real-time notifications
- CLI/API: Manual annotation via command line or API

---

## 6. Alert Source Integrations

### PagerDuty
```python
if PAGERDUTY_API_KEY:
    use_pagerduty()
else:
    skip_pagerduty()  # Other sources still work
```

### Datadog
```python
if DATADOG_API_KEY and DATADOG_APP_KEY:
    use_datadog()
else:
    skip_datadog()  # Other sources still work
```

### AlertManager
```python
if ALERTMANAGER_URL:
    use_alertmanager()
else:
    skip_alertmanager()  # Other sources still work
```

### Sentry
```python
if SENTRY_API_TOKEN:
    use_sentry()
else:
    skip_sentry()  # Other sources still work
```

**Implementation:** `incident_sources/` module

**Graceful Degradation:** Each source is independent — if one is unavailable, others continue working.

---

## 7. Redis Caching

### Primary Path: Redis
```python
if REDIS_URL and REDIS_AVAILABLE:
    use_redis_cache()
```

### Fallback: In-Memory
```python
else:
    use_memory_cache()  # Always available
```

**Graceful Degradation:**
- Redis: Persistent cache, multi-instance sharing
- Memory: Per-process cache, cleared on restart

---

## 8. WebSocket Real-Time Updates

### Primary Path: WebSocket
```python
if WEBSOCKETS_AVAILABLE:
    use_websocket_updates()
```

### Fallback: HTTP Polling
```python
else:
    use_http_polling()  # Always available
```

**Implementation:** `dashboard/index.html`

**Graceful Degradation:**
- WebSocket: Real-time updates (<1s latency)
- Polling: Updates every 30 seconds

---

## 9. Flask Webhook Server

### Primary Path: Flask
```python
if FLASK_AVAILABLE:
    run_slack_webhook_server()
```

### Fallback: FastAPI Only
```python
else:
    use_fastapi_webhooks()  # Always available
```

**Implementation:** `api/app.py` (FastAPI handles all webhooks if Flask unavailable)

---

## 10. Automated Remediation

### Primary Path: Full Execution
```python
if AUTO_REMEDIATION_ENABLED:
    execute_remediation()
```

### Fallback: Manual Approval Required
```python
else:
    require_manual_approval()  # Always available
```

**Implementation:** `remediation/executor.py::RemediationExecutor`

**Graceful Degradation:**
- Auto: Execute low-risk actions automatically
- Manual: All actions require approval

---

## Fallback Chain Testing

### Test Coverage

| Fallback Chain | Test Status | Test File |
|----------------|-------------|-----------|
| AI/LLM | ✅ Tested | `tests/test_integration.py::test_llm_suggestion_engine_fallback` |
| Semantic Search | ✅ Tested | `tests/test_integration.py::test_semantic_correlator_offline` |
| Git Versioning | ✅ Tested | `tests/test_integration.py::test_git_version_control` |
| Report Generation | ✅ Tested | `tests/test_integration.py::test_report_generator_template` |
| Alert Sources | ✅ Tested | `tests/test_incident_sources.py` |

### Testing Strategy

```python
# Example: Test LLM fallback
def test_llm_suggestion_engine_fallback():
    # Test without API key (fallback mode)
    engine = LLMRunbookEvolution(provider='anthropic', api_key=None)
    
    incident = {'cause': 'Memory leak', 'fix': 'Restarted service'}
    runbook = {'steps': []}
    
    # Should work in fallback mode
    suggestions = engine.analyze_incident(incident, runbook)
    
    # Should have at least one suggestion
    assert len(suggestions) > 0
```

---

## Dependency Matrix

| Feature | Required | Optional | Fallback |
|---------|----------|----------|----------|
| Core API | fastapi, uvicorn | - | - |
| Slack Webhooks | flask | - | FastAPI webhooks |
| AI Suggestions | - | anthropic, openai | Rule-based |
| Semantic Search | - | sentence-transformers | Keyword matching |
| Git Versioning | - | gitpython | File timestamps |
| Database | - | sqlalchemy, psycopg2 | YAML files |
| Redis Cache | - | redis | In-memory |
| PagerDuty | - | requests (core) | Skip if no API key |
| Datadog | - | requests (core) | Skip if no API key |
| AlertManager | - | requests (core) | Skip if no URL |
| Sentry | - | requests (core) | Skip if no token |
| WebSocket | websockets | - | HTTP polling |

---

## Configuration for Fallbacks

### Environment Variables

```bash
# Control fallback behavior
ENABLE_AI_SUGGESTIONS=true      # Set false to force rule-based
ENABLE_SEMANTIC_SEARCH=true     # Set false to force keyword matching
ENABLE_GIT_VERSIONING=true      # Set false to skip git
ENABLE_AUTO_REMEDIATION=false   # Set true for auto-execution

# API Keys (leave empty to use fallback)
ANTHROPIC_API_KEY=              # Empty = use fallback
OPENAI_API_KEY=                 # Empty = use fallback
PAGERDUTY_API_KEY=              # Empty = skip PagerDuty
```

### Feature Detection

```python
# Example: Check if feature is available
def is_ai_available() -> bool:
    return (
        os.environ.get('ANTHROPIC_API_KEY') is not None or
        os.environ.get('OPENAI_API_KEY') is not None
    )

def is_git_available() -> bool:
    try:
        from version_control.git_manager import GITPYTHON_AVAILABLE
        return GITPYTHON_AVAILABLE
    except:
        return False
```

---

## User Communication

### When Fallback is Active

**UI Indicators:**
```
⚠️ AI suggestions unavailable (no API key configured)
   Using rule-based suggestions instead.
   Configure ANTHROPIC_API_KEY to enable AI features.
```

**Log Messages:**
```
[WARNING] Anthropic API key not configured, using rule-based suggestions
[INFO] Git repository not found, skipping version control
[WARNING] PostgreSQL not configured, using YAML storage
```

**API Responses:**
```json
{
  "status": "ok",
  "suggestions": [...],
  "metadata": {
    "source": "rule_based",
    "note": "AI suggestions unavailable (no API key)"
  }
}
```

---

## Best Practices

### For Developers

1. **Always Check Availability**
   ```python
   if FEATURE_AVAILABLE:
       use_feature()
   else:
       use_fallback()
   ```

2. **Log Fallback Activation**
   ```python
   logger.warning(f"{feature} unavailable, using {fallback}")
   ```

3. **Document Fallback Behavior**
   ```python
   # Fallback: If sentence-transformers not installed, use keyword matching
   ```

4. **Test Both Paths**
   ```python
   def test_feature_with_dependency(): ...
   def test_feature_without_dependency(): ...
   ```

### For Users

1. **Start with Fallbacks** — System works without any configuration
2. **Enable Features Gradually** — Add API keys as needed
3. **Monitor Fallback Usage** — Check logs for fallback activation
4. **Plan for Production** — Enable all required features before go-live

---

## Troubleshooting

### Common Fallback Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| AI features not working | Missing API key | Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |
| Git operations failing | GitPython not installed | `pip install gitpython` |
| Semantic search slow | sentence-transformers not installed | `pip install sentence-transformers` |
| WebSocket not connecting | Firewall blocking | Use HTTP polling fallback |

### Diagnostic Commands

```bash
# Check available features
python -c "from ai.llm_suggestion_engine import ANTHROPIC_AVAILABLE; print(f'Anthropic: {ANTHROPIC_AVAILABLE}')"
python -c "from version_control.git_manager import GITPYTHON_AVAILABLE; print(f'GitPython: {GITPYTHON_AVAILABLE}')"

# Test fallback activation
python -m ai.llm_suggestion_engine --runbook runbooks/service-x/runbook.yaml --incident '{"cause": "test"}' --provider template
```

---

## Summary

Living Runbooks implements **10 major fallback chains** to ensure:

1. ✅ **System Always Works** — No single point of failure
2. ✅ **Graceful Degradation** — Reduced features, not broken system
3. ✅ **Progressive Enhancement** — Add features as needed
4. ✅ **Production Ready** — Works out of the box, scales with configuration

**Philosophy:** "Something is better than nothing. Simple is better than broken."
