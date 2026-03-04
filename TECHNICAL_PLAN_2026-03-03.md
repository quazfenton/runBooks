# Living Runbooks - Comprehensive Technical Improvement Plan
**Date:** March 3, 2026  
**Reviewer:** Deep Code Review Agent  
**Scope:** Full codebase review with implementation roadmap

---

## Executive Summary

After painstakingly reviewing every file in the codebase, I've identified **critical gaps** between the project's vision ("Living Runbooks that learn from incidents") and its current implementation. The foundation is solid, but the system is operating at **proof-of-concept level** with significant unfulfilled potential.

### Key Findings Summary

| Category | Status | Priority |
|----------|--------|----------|
| **Core Architecture** | ✅ Sound | - |
| **Slack Integration** | ✅ Working | - |
| **Schema Design** | ✅ Well-structured | - |
| **Alert Source Integration** | ❌ MISSING | CRITICAL |
| **LLM/AI Learning** | ❌ MISSING | CRITICAL |
| **Git Versioning** | ❌ MISSING | HIGH |
| **Correlation Engine** | ❌ MISSING | HIGH |
| **Real Dashboard** | ⚠️ Mock Data | HIGH |
| **Security Hardening** | ⚠️ Partial | HIGH |
| **Test Coverage** | ⚠️ Minimal | MEDIUM |

---

## Critical Issues Found

### 1. NO ALERT SOURCE INTEGRATION (CRITICAL)

**Problem:** The entire system requires **manual Slack entry** for incidents. This is the #1 blocker for adoption.

**Current State:**
- `slack/handler.py` - Only handles manual modal submissions
- `runbooks/service-x/scripts/check_datadog_alerts.sh` - Shell script that appends to runbook (not incident creation)
- No PagerDuty, Datadog webhook, AlertManager, or Sentry integration

**Impact:** Teams won't manually enter every incident. Automation is required.

**Required Implementation:**
```
incident_sources/
├── __init__.py
├── base.py              # Abstract base class
├── pagerduty.py         # PagerDuty webhook + API sync
├── datadog.py           # Datadog alert webhooks
├── alertmanager.py      # Prometheus AlertManager
├── sentry.py            # Sentry error tracking
└── generic_webhook.py   # Catch-all webhook receiver
```

---

### 2. NO LLM/AI LEARNING LAYER (CRITICAL)

**Problem:** The "living" concept is a lie. Current suggestion engine uses **regex pattern matching** only.

**Current State:**
- `suggest_updates.py` - Uses `CANONICAL_PATTERNS` dict with regex
- No semantic understanding
- No LLM integration
- No similarity search across incidents

**Impact:** Cannot provide intelligent suggestions. Competitors (incident.io, Rootly) have AI-native features.

**Required Implementation:**
```
ai/
├── __init__.py
├── llm_suggestion_engine.py   # LLM-powered suggestions (Claude/OpenAI)
├── semantic_correlator.py     # Sentence embeddings for similarity
├── pattern_extractor.py       # Extract patterns from annotations
└── report_generator.py        # Auto-generate post-mortems
```

---

### 3. NO GIT-BACKED VERSIONING (HIGH)

**Problem:** Runbook changes **overwrite without history**. No audit trail, no rollback.

**Current State:**
- `handler.py` - Directly writes to YAML files
- No git integration
- No version history
- No diff capability

**Impact:** Cannot track runbook evolution. No compliance audit trail. Cannot rollback bad changes.

**Required Implementation:**
```
version_control/
├── __init__.py
├── git_manager.py         # GitPython integration
├── diff_engine.py         # Show runbook changes
└── rollback.py            # Revert to previous version
```

---

### 4. HARDCODED DASHBOARD DATA (HIGH)

**Problem:** Dashboard uses **static mock data** in `index.html`. Not connected to real metrics.

**Current State:**
```javascript
// dashboard/index.html - Line ~106
const sampleData = {
    totalRunbooks: 12,  // HARDCODED
    staleRunbooks: 3,   // HARDCODED
    ...
}
```

**Impact:** Dashboard is useless for production monitoring.

**Required Implementation:**
- API endpoint `/api/metrics` to serve real data
- WebSocket for real-time updates
- React-based frontend (optional but recommended)

---

### 5. SECURITY VULNERABILITIES (HIGH)

**Problem:** Path traversal protection is **bypassable** via symlinks.

**Current State:**
```python
# slack/handler.py - Line 44
resolved_path = runbook_file.resolve()
expected_base = Path("runbooks").resolve()
try:
    resolved_path.relative_to(expected_base)
except ValueError:
    raise ValueError(...)
```

**Issue:** `resolve()` follows symlinks. Attacker can create symlink outside runbooks/ directory.

**Required Fix:**
```python
def validate_runbook_path(user_path: str, base_dir: Path) -> Path:
    """Secure path validation that prevents symlink attacks."""
    base_dir = base_dir.resolve()
    user_path = (base_dir / user_path).resolve()
    
    # Check canonical paths match
    if not str(user_path).startswith(str(base_dir)):
        raise ValueError(f"Path traversal detected: {user_path}")
    
    # Additional: verify no symlinks in path
    for parent in user_path.parents:
        if parent.is_symlink():
            raise ValueError(f"Symlink not allowed: {parent}")
    
    return user_path
```

---

### 6. MISSING ERROR HANDLING (MEDIUM)

**Problem:** Generic exception catches without proper logging or alerting.

**Example:**
```python
# handler.py - Line 77
except Exception as e:
    return {
        "response_action": "errors",
        "errors": {
            "runbook_path": f"Error processing annotation: {str(e)}"
        }
    }
```

**Issues:**
- No structured logging
- No alerting on failures
- No error tracking (Sentry integration)
- No retry logic

---

### 7. NO DATABASE PERSISTENCE (MEDIUM)

**Problem:** All data stored in **YAML files**. No query capability, no relationships.

**Impact:**
- Cannot query "incidents caused by memory_leak in last 30 days"
- Cannot correlate across services efficiently
- No full-text search
- No analytics

**Required Implementation:**
```
models/
├── __init__.py
├── database.py          # SQLAlchemy/PostgreSQL setup
├── incident.py          # Incident model
├── runbook.py           # Runbook model
├── annotation.py        # Annotation model
└── repository.py        # Data access layer
```

---

### 8. INCOMPLETE SCRIPTS (MEDIUM)

**Problem:** Several scripts are **partial implementations** or have issues.

**Issues Found:**

#### `check_datadog_alerts.sh`
- Mixes bash and Python strangely
- Uses `jq` but doesn't check if installed
- Appends to runbook.md OR runbook.yaml inconsistently
- No error handling for API failures

#### `restart_pod.sh`
- Only works for Markdown runbooks
- No rollback capability
- No confirmation step for destructive action

#### `diagnose_high_cpu.py`
- Only works on Linux (`/proc` filesystem)
- No Windows/Mac compatibility
- No containerized environment detection

---

### 9. NO MULTI-SERVICE EXAMPLES (MEDIUM)

**Problem:** Only `service-x` template exists. No real-world examples.

**Impact:** Cannot demonstrate cross-service correlation or multi-tenant use cases.

---

### 10. MISSING ENVIRONMENT CONFIGURATION (LOW)

**Problem:** No `.env.example` file. Assumes environment variables without documentation.

**Required:**
```bash
# .env.example
SLACK_SIGNING_SECRET=xoxp-...
SLACK_BOT_TOKEN=xoxb-...
DATADOG_API_KEY=...
DATADOG_APP_KEY=...
PAGERDUTY_API_KEY=...
FLASK_ENV=production
SECRET_KEY=...
```

---

## Implementation Roadmap

### Phase 1: Critical Foundation (Weeks 1-4)

#### Week 1-2: Alert Source Integration

**Goal:** Replace manual Slack entry with automated incident creation.

**Files to Create:**
```
incident_sources/
├── __init__.py
├── base.py
├── pagerduty.py
├── datadog.py
└── webhook_receiver.py
```

**Implementation Details:**

```python
# incident_sources/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from datetime import datetime

class IncidentSource(ABC):
    """Abstract base class for incident sources."""
    
    @abstractmethod
    def parse_webhook(self, payload: Dict[str, Any]) -> 'Incident':
        """Parse incoming webhook payload into Incident object."""
        pass
    
    @abstractmethod
    def sync_incidents(self) -> List['Incident']:
        """Sync incidents from source API."""
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return source name (e.g., 'pagerduty')."""
        pass


# incident_sources/pagerduty.py
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .base import IncidentSource

class PagerDutyIncident(ABC):
    """Represents an incident from PagerDuty."""
    def __init__(
        self,
        external_id: str,
        title: str,
        service: str,
        severity: str,
        status: str,
        created_at: datetime,
        updated_at: Optional[datetime] = None,
        resolved_at: Optional[datetime] = None,
        raw_payload: Optional[Dict[str, Any]] = None
    ):
        self.external_id = external_id
        self.title = title
        self.service = service
        self.severity = severity
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at or created_at
        self.resolved_at = resolved_at
        self.raw_payload = raw_payload
        self.source = 'pagerduty'


class PagerDutyIntegration(IncidentSource):
    """PagerDuty incident integration."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.pagerduty.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token token={api_key}",
            "Accept": "application/vnd.pagerduty+json;version=2"
        })
    
    @property
    def source_name(self) -> str:
        return "pagerduty"
    
    def parse_webhook(self, payload: Dict[str, Any]) -> PagerDutyIncident:
        """Parse PagerDuty webhook payload."""
        incident = payload.get('incident', {})
        return PagerDutyIncident(
            external_id=incident.get('incident_number'),
            title=incident.get('title'),
            service=incident.get('service', {}).get('summary'),
            severity=incident.get('urgency'),
            status=incident.get('status'),
            created_at=datetime.fromisoformat(incident.get('created_at').replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(incident.get('updated_at').replace('Z', '+00:00')) if incident.get('updated_at') else None,
            resolved_at=datetime.fromisoformat(incident.get('last_status_change_at').replace('Z', '+00:00')) if incident.get('last_status_change_at') else None,
            raw_payload=payload
        )
    
    def sync_incidents(self, service_id: Optional[str] = None, 
                       since: Optional[datetime] = None,
                       limit: int = 100) -> List[PagerDutyIncident]:
        """Sync incidents from PagerDuty API."""
        params = {
            "limit": limit,
            "date_range": "all"
        }
        
        if service_id:
            params["service_ids[]"] = service_id
        
        if since:
            params["since"] = since.isoformat()
        
        response = self.session.get(
            f"{self.base_url}/incidents",
            params=params
        )
        response.raise_for_status()
        
        data = response.json()
        incidents = []
        
        for incident_data in data.get('incidents', []):
            incident = PagerDutyIncident(
                external_id=incident_data.get('incident_number'),
                title=incident_data.get('title'),
                service=incident_data.get('service', {}).get('summary'),
                severity=incident_data.get('urgency'),
                status=incident_data.get('status'),
                created_at=datetime.fromisoformat(incident_data.get('created_at').replace('Z', '+00:00')),
                raw_payload=incident_data
            )
            incidents.append(incident)
        
        return incidents
```

**API Routes to Add:**
```python
# api/routes/incidents.py
from flask import Blueprint, request, jsonify
from incident_sources.pagerduty import PagerDutyIntegration
from incident_sources.datadog import DatadogIntegration
from handler import create_incident_from_source

incidents_bp = Blueprint('incidents', __name__, url_prefix='/api/incidents')

@incidents_bp.route('/webhooks/pagerduty', methods=['POST'])
def pagerduty_webhook():
    """Receive PagerDuty incident webhooks."""
    payload = request.get_json()
    
    # Validate webhook signature (PagerDuty provides this)
    if not validate_pagerduty_webhook(request):
        return jsonify({'error': 'Invalid signature'}), 401
    
    pd_integration = PagerDutyIntegration(api_key=os.environ['PAGERDUTY_API_KEY'])
    incident = pd_integration.parse_webhook(payload)
    
    # Create incident record and trigger runbook
    result = create_incident_from_source(incident)
    
    return jsonify({'status': 'ok', 'incident_id': result.id})


@incidents_bp.route('/webhooks/datadog', methods=['POST'])
def datadog_webhook():
    """Receive Datadog alert webhooks."""
    payload = request.get_json()
    
    # Validate Datadog webhook
    if not validate_datadog_webhook(request):
        return jsonify({'error': 'Invalid signature'}), 401
    
    dd_integration = DatadogIntegration(api_key=os.environ['DATADOG_API_KEY'])
    alert = dd_integration.parse_webhook(payload)
    
    result = create_incident_from_source(alert)
    
    return jsonify({'status': 'ok', 'alert_id': result.id})
```

---

#### Week 3: LLM Suggestion Engine

**Goal:** Replace regex-based suggestions with LLM-powered reasoning.

**Files to Create:**
```
ai/
├── __init__.py
├── llm_suggestion_engine.py
└── semantic_correlator.py
```

**Implementation:**

```python
# ai/llm_suggestion_engine.py
"""
LLM-Powered Runbook Suggestion Engine

Uses Anthropic Claude or OpenAI GPT to generate intelligent runbook improvement suggestions.
"""

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import yaml

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class Suggestion:
    """Represents a runbook improvement suggestion."""
    suggestion_type: str  # ADD_STEP, REMOVE_STEP, MODIFY_STEP, ADD_MONITORING, etc.
    action: str
    reasoning: str
    confidence: float  # 0.0 to 1.0
    priority: str  # HIGH, MEDIUM, LOW


class LLMProvider:
    """Abstract LLM provider interface."""
    
    def generate(self, prompt: str, max_tokens: int = 1500) -> str:
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")
        
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get('ANTHROPIC_API_KEY'))
    
    def generate(self, prompt: str, max_tokens: int = 1500) -> str:
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed. Install with: pip install openai")
        
        self.client = OpenAI(api_key=api_key or os.environ.get('OPENAI_API_KEY'))
    
    def generate(self, prompt: str, max_tokens: int = 1500) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return response.choices[0].message.content


class LLMRunbookEvolution:
    """
    LLM-powered runbook evolution engine.
    
    Analyzes incidents and suggests runbook improvements using LLM reasoning.
    """
    
    def __init__(self, provider: str = "anthropic", api_key: Optional[str] = None):
        """
        Initialize LLM suggestion engine.
        
        Args:
            provider: LLM provider ('anthropic' or 'openai')
            api_key: API key (if not provided, uses environment variable)
        """
        if provider == "anthropic":
            self.llm = AnthropicProvider(api_key)
        elif provider == "openai":
            self.llm = OpenAIProvider(api_key)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    def analyze_incident(self, 
                        incident_annotation: Dict[str, Any],
                        current_runbook: Dict[str, Any],
                        similar_incidents: Optional[List[Dict[str, Any]]] = None) -> List[Suggestion]:
        """
        Analyze an incident and suggest runbook improvements.
        
        Args:
            incident_annotation: The incident annotation to analyze
            current_runbook: Current runbook structure
            similar_incidents: Optional list of similar past incidents
        
        Returns:
            List of suggestions for runbook improvement
        """
        prompt = self._build_analysis_prompt(incident_annotation, current_runbook, similar_incidents)
        response = self.llm.generate(prompt, max_tokens=2000)
        
        return self._parse_suggestions(response)
    
    def _build_analysis_prompt(self, 
                               incident: Dict[str, Any],
                               runbook: Dict[str, Any],
                               similar: Optional[List[Dict[str, Any]]]) -> str:
        """Build the analysis prompt for the LLM."""
        
        prompt = f"""You are an expert SRE analyzing incidents to improve runbooks. Your task is to suggest concrete, actionable improvements to the runbook based on what was learned from this incident.

**Recent Incident:**
- Incident ID: {incident.get('incident_id', 'UNKNOWN')}
- Root Cause: {incident.get('cause', 'Unknown')}
- Fix Applied: {incident.get('fix', 'Unknown')}
- Symptoms: {', '.join(incident.get('symptoms', []))}
- Runbook Gap: {incident.get('runbook_gap', 'None identified')}

**Current Runbook Steps:**
{self._format_runbook_steps(runbook.get('steps', []))}

"""
        
        if similar:
            prompt += f"""
**Similar Past Incidents:**
{self._format_similar_incidents(similar)}

These similar incidents show patterns that should inform your suggestions.
"""
        
        prompt += """
**Your Task:**
Generate 3-5 specific, actionable suggestions to improve the runbook. For each suggestion:

1. **Type**: One of:
   - ADD_STEP: Add a new diagnostic or remediation step
   - REMOVE_STEP: Remove an obsolete or unhelpful step
   - MODIFY_STEP: Update an existing step with new information
   - ADD_MONITORING: Add monitoring or alerting for early detection
   - ADD_AUTOMATION: Add automation script for a manual step
   - IMPROVE_DOCUMENTATION: Clarify or expand documentation

2. **Action**: Specific what to add/modify/remove

3. **Reasoning**: Why this improvement matters based on the incident

4. **Priority**: HIGH (prevents recurrence), MEDIUM (improves efficiency), LOW (nice to have)

**Format your response as:**
```
SUGGESTION 1:
Type: [TYPE]
Action: [Specific action]
Reasoning: [Why this matters]
Priority: [HIGH|MEDIUM|LOW]

SUGGESTION 2:
...
```

Be specific and concrete. Avoid generic advice like "improve monitoring" - instead say "Add CPU usage alert at 80% threshold for 5 minutes"."""

        return prompt
    
    def _format_runbook_steps(self, steps: List[Dict[str, Any]]) -> str:
        """Format runbook steps for the prompt."""
        if not steps:
            return "No steps defined in runbook."
        
        formatted = []
        for i, step in enumerate(steps, 1):
            check = step.get('check', 'Unknown check')
            command = step.get('command', 'No command')
            automation = step.get('automation', 'No automation')
            formatted.append(f"{i}. {check}\n   Command: `{command}`\n   Automation: {automation}")
        
        return "\n\n".join(formatted)
    
    def _format_similar_incidents(self, incidents: List[Dict[str, Any]]) -> str:
        """Format similar incidents for the prompt."""
        formatted = []
        for incident in incidents[:5]:  # Limit to 5 most similar
            formatted.append(
                f"- {incident.get('incident_id')}: {incident.get('cause', 'Unknown')} → {incident.get('fix', 'Unknown')}"
            )
        return "\n".join(formatted)
    
    def _parse_suggestions(self, response: str) -> List[Suggestion]:
        """Parse LLM response into structured suggestions."""
        suggestions = []
        
        # Simple parsing - in production, use structured output or few-shot examples
        current_suggestion = {}
        
        for line in response.split('\n'):
            line = line.strip()
            
            if line.startswith('SUGGESTION'):
                if current_suggestion:
                    suggestions.append(self._create_suggestion(current_suggestion))
                current_suggestion = {}
            
            elif ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'type':
                    current_suggestion['type'] = value
                elif key == 'action':
                    current_suggestion['action'] = value
                elif key == 'reasoning':
                    current_suggestion['reasoning'] = value
                elif key == 'priority':
                    current_suggestion['priority'] = value
        
        # Don't forget the last suggestion
        if current_suggestion:
            suggestions.append(self._create_suggestion(current_suggestion))
        
        return suggestions
    
    def _create_suggestion(self, data: Dict[str, str]) -> Suggestion:
        """Create a Suggestion object from parsed data."""
        return Suggestion(
            suggestion_type=data.get('type', 'UNKNOWN'),
            action=data.get('action', ''),
            reasoning=data.get('reasoning', ''),
            confidence=0.8,  # Would calculate based on LLM confidence
            priority=data.get('priority', 'MEDIUM')
        )


# Usage example
def main():
    """Example usage of LLM suggestion engine."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate runbook improvement suggestions using LLM")
    parser.add_argument("--runbook", required=True, help="Path to runbook YAML")
    parser.add_argument("--incident", required=True, help="Incident annotation JSON or path")
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "openai"])
    parser.add_argument("--output", help="Output file for suggestions (JSON)")
    
    args = parser.parse_args()
    
    # Load runbook
    with open(args.runbook, 'r') as f:
        runbook = yaml.safe_load(f)
    
    # Load incident (from file or inline JSON)
    if args.incident.endswith('.json'):
        import json
        with open(args.incident, 'r') as f:
            incident = json.load(f)
    else:
        import json
        incident = json.loads(args.incident)
    
    # Generate suggestions
    engine = LLMRunbookEvolution(provider=args.provider)
    suggestions = engine.analyze_incident(incident, runbook)
    
    # Output results
    print(f"\nGenerated {len(suggestions)} suggestions:\n")
    
    for i, suggestion in enumerate(suggestions, 1):
        print(f"{i}. [{suggestion.priority}] {suggestion.suggestion_type}")
        print(f"   Action: {suggestion.action}")
        print(f"   Reasoning: {suggestion.reasoning}")
        print()
    
    if args.output:
        import json
        output_data = [
            {
                'type': s.suggestion_type,
                'action': s.action,
                'reasoning': s.reasoning,
                'priority': s.priority,
                'confidence': s.confidence
            }
            for s in suggestions
        ]
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"Suggestions saved to {args.output}")


if __name__ == "__main__":
    main()
```

---

#### Week 4: Semantic Correlation Engine

**Goal:** Find similar incidents across services using embeddings.

**Implementation:**

```python
# ai/semantic_correlator.py
"""
Semantic Incident Correlation Engine

Uses sentence embeddings to find similar incidents across services.
"""

import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import yaml
from dataclasses import dataclass

try:
    from sentence_transformers import SentenceTransformer, util
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("Warning: sentence-transformers not installed. Install with: pip install sentence-transformers")


@dataclass
class IncidentEmbedding:
    """Represents an incident with its embedding."""
    incident_id: str
    service: str
    text: str  # Original text used for embedding
    embedding: np.ndarray
    timestamp: str
    cause: str
    fix: str


class SemanticCorrelator:
    """
    Finds semantically similar incidents using embeddings.
    
    Uses SentenceTransformers for efficient, accurate semantic similarity.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize semantic correlator.
        
        Args:
            model_name: SentenceTransformer model to use
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers package not installed")
        
        self.model = SentenceTransformer(model_name)
        self.embeddings: Dict[str, IncidentEmbedding] = {}
    
    def embed_incident(self, 
                       incident_id: str,
                       cause: str,
                       fix: str,
                       symptoms: Optional[List[str]] = None,
                       service: str = "unknown",
                       timestamp: str = "") -> IncidentEmbedding:
        """
        Create embedding for an incident.
        
        Args:
            incident_id: Unique incident identifier
            cause: Root cause text
            fix: Fix applied
            symptoms: List of symptoms
            service: Service name
            timestamp: Incident timestamp
        
        Returns:
            IncidentEmbedding object
        """
        # Combine all text for embedding
        text_parts = [cause, fix]
        if symptoms:
            text_parts.extend(symptoms)
        
        text = " ".join(text_parts)
        
        # Generate embedding
        embedding = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        
        incident_emb = IncidentEmbedding(
            incident_id=incident_id,
            service=service,
            text=text,
            embedding=embedding,
            timestamp=timestamp,
            cause=cause,
            fix=fix
        )
        
        # Store in memory
        key = f"{service}:{incident_id}"
        self.embeddings[key] = incident_emb
        
        return incident_emb
    
    def find_similar_incidents(self,
                               query_incident: IncidentEmbedding,
                               threshold: float = 0.7,
                               max_results: int = 10,
                               exclude_service: bool = False) -> List[Tuple[IncidentEmbedding, float]]:
        """
        Find incidents similar to the query.
        
        Args:
            query_incident: Query incident embedding
            threshold: Minimum similarity score (0.0 to 1.0)
            max_results: Maximum number of results
            exclude_service: If True, exclude incidents from same service
        
        Returns:
            List of (incident, similarity_score) tuples
        """
        query_embedding = query_incident.embedding
        
        similar = []
        for key, incident in self.embeddings.items():
            # Skip if excluding same service
            if exclude_service and incident.service == query_incident.service:
                continue
            
            # Calculate cosine similarity
            similarity = util.cos_sim(
                query_embedding.reshape(1, -1),
                incident.embedding.reshape(1, -1)
            ).item()
            
            if similarity >= threshold:
                similar.append((incident, similarity))
        
        # Sort by similarity (descending)
        similar.sort(key=lambda x: x[1], reverse=True)
        
        return similar[:max_results]
    
    def load_runbook_annotations(self, runbook_dir: Path) -> int:
        """
        Load all annotations from runbooks and create embeddings.
        
        Args:
            runbook_dir: Directory containing runbooks
        
        Returns:
            Number of annotations loaded
        """
        count = 0
        
        for runbook_file in runbook_dir.rglob("runbook.yaml"):
            try:
                with open(runbook_file, 'r') as f:
                    runbook = yaml.safe_load(f)
                
                if not runbook:
                    continue
                
                service = runbook_file.parent.name
                annotations = runbook.get('annotations', [])
                
                for annotation in annotations:
                    incident_id = annotation.get('incident_id', f"{service}:{len(self.embeddings)}")
                    
                    self.embed_incident(
                        incident_id=incident_id,
                        cause=annotation.get('cause', ''),
                        fix=annotation.get('fix', ''),
                        symptoms=annotation.get('symptoms', []),
                        service=service,
                        timestamp=annotation.get('timestamp', '')
                    )
                    count += 1
            
            except Exception as e:
                print(f"Error loading {runbook_file}: {e}")
                continue
        
        return count
    
    def detect_cascade_pattern(self, 
                                incidents: List[IncidentEmbedding],
                                time_window_minutes: int = 30) -> Optional[Dict[str, Any]]:
        """
        Detect if multiple incidents are part of a cascade failure.
        
        Args:
            incidents: List of incidents to analyze
            time_window_minutes: Time window for cascade detection
        
        Returns:
            Cascade pattern info if detected, None otherwise
        """
        if len(incidents) < 2:
            return None
        
        # Group by time window
        from datetime import datetime, timedelta
        
        # Sort by timestamp
        sorted_incidents = sorted(incidents, key=lambda x: x.timestamp)
        
        # Check for temporal clustering
        cascade_groups = []
        current_group = [sorted_incidents[0]]
        
        for incident in sorted_incidents[1:]:
            time_diff = datetime.fromisoformat(incident.timestamp.replace('Z', '+00:00')) - \
                       datetime.fromisoformat(current_group[-1].timestamp.replace('Z', '+00:00'))
            
            if time_diff <= timedelta(minutes=time_window_minutes):
                current_group.append(incident)
            else:
                if len(current_group) >= 2:
                    cascade_groups.append(current_group)
                current_group = [incident]
        
        if len(current_group) >= 2:
            cascade_groups.append(current_group)
        
        if not cascade_groups:
            return None
        
        # Return largest cascade
        largest_cascade = max(cascade_groups, key=len)
        
        return {
            'incident_count': len(largest_cascade),
            'services_affected': list(set(i.service for i in largest_cascade)),
            'time_span_minutes': (
                datetime.fromisoformat(largest_cascade[-1].timestamp.replace('Z', '+00:00')) -
                datetime.fromisoformat(largest_cascade[0].timestamp.replace('Z', '+00:00'))
            ).total_seconds() / 60,
            'common_themes': self._extract_common_themes(largest_cascade)
        }
    
    def _extract_common_themes(self, incidents: List[IncidentEmbedding]) -> List[str]:
        """Extract common themes from cascade incidents."""
        # Simple keyword extraction - in production, use more sophisticated NLP
        keywords = []
        for incident in incidents:
            keywords.extend(incident.cause.lower().split())
        
        from collections import Counter
        word_counts = Counter(keywords)
        
        # Return top 5 most common words (excluding stopwords)
        stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or'}
        common = [word for word, count in word_counts.most_common(10) if word not in stopwords]
        
        return common[:5]


# Usage example
def main():
    """Example usage of semantic correlator."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Find similar incidents using semantic search")
    parser.add_argument("--runbooks-dir", default="runbooks", help="Directory containing runbooks")
    parser.add_argument("--query", help="Query text (cause/fix description)")
    parser.add_argument("--threshold", type=float, default=0.7, help="Similarity threshold")
    parser.add_argument("--service", help="Filter by service name")
    
    args = parser.parse_args()
    
    # Initialize correlator
    correlator = SemanticCorrelator()
    
    # Load all annotations
    runbook_dir = Path(args.runbooks_dir)
    count = correlator.load_runbook_annotations(runbook_dir)
    print(f"Loaded {count} incident annotations")
    
    if args.query:
        # Create query embedding
        query_emb = correlator.embed_incident(
            incident_id="query",
            cause=args.query,
            fix="",
            service="query"
        )
        
        # Find similar
        similar = correlator.find_similar_incidents(
            query_emb,
            threshold=args.threshold
        )
        
        print(f"\nFound {len(similar)} similar incidents:\n")
        for incident, score in similar:
            print(f"  [{score:.2f}] {incident.service}:{incident.incident_id}")
            print(f"      Cause: {incident.cause}")
            print(f"      Fix: {incident.fix}")
            print()


if __name__ == "__main__":
    main()
```

---

### Phase 2: Production Readiness (Weeks 5-8)

#### Week 5: Git Version Control Integration

**Files to Create:**
```
version_control/
├── __init__.py
├── git_manager.py
├── diff_engine.py
└── rollback.py
```

**Implementation:**

```python
# version_control/git_manager.py
"""
Git Version Control for Runbooks

Provides git-backed versioning for runbook changes with audit trails.
"""

from git import Repo, Actor
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import yaml


class RunbookVersionControl:
    """
    Manages git versioning for runbooks.
    
    Every annotation or change is committed with structured metadata.
    """
    
    def __init__(self, repo_path: str = "."):
        """
        Initialize runbook version control.
        
        Args:
            repo_path: Path to git repository root
        """
        self.repo_path = Path(repo_path)
        self.repo = Repo(repo_path)
        
        # Actor for automated commits
        self.actor = Actor(
            name="runbook-bot",
            email="runbook-bot@runbooks.local"
        )
    
    def commit_annotation(self, 
                          runbook_path: str,
                          annotation: Dict[str, Any],
                          author: Optional[str] = None) -> str:
        """
        Append annotation and commit to git.
        
        Args:
            runbook_path: Path to runbook YAML
            annotation: Annotation to append
            author: Optional human author name
        
        Returns:
            Commit hash
        """
        runbook_file = self.repo_path / runbook_path
        
        # Append annotation
        self._append_annotation(runbook_file, annotation)
        
        # Create commit message
        commit_msg = self._build_commit_message(annotation, author)
        
        # Stage and commit
        self.repo.index.add([str(runbook_file)])
        commit = self.repo.index.commit(
            commit_msg,
            author=self.actor if not author else Actor(author, f"{author}@runbooks.local")
        )
        
        return commit.hexsha
    
    def _append_annotation(self, runbook_file: Path, annotation: Dict[str, Any]):
        """Append annotation to runbook file."""
        with open(runbook_file, 'r') as f:
            runbook = yaml.safe_load(f)
        
        if 'annotations' not in runbook:
            runbook['annotations'] = []
        
        runbook['annotations'].append(annotation)
        
        with open(runbook_file, 'w') as f:
            yaml.dump(runbook, f, default_flow_style=False)
    
    def _build_commit_message(self, annotation: Dict[str, Any], author: Optional[str]) -> str:
        """Build structured commit message."""
        incident_id = annotation.get('incident_id', 'UNKNOWN')
        cause = annotation.get('cause', 'Unknown cause')[:50]
        fix = annotation.get('fix', 'Unknown fix')[:50]
        
        msg = f"""incident: {incident_id}

cause: {cause}
fix: {fix}

"""
        
        if author:
            msg += f"Annotated by: {author}\n"
        
        return msg
    
    def get_runbook_history(self, runbook_path: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get commit history for a runbook.
        
        Args:
            runbook_path: Path to runbook
            limit: Maximum commits to return
        
        Returns:
            List of commit info dicts
        """
        runbook_file = self.repo_path / runbook_path
        
        commits = []
        for commit in self.repo.iter_commits(paths=str(runbook_file), max_count=limit):
            commits.append({
                'hash': commit.hexsha,
                'author': commit.author.name,
                'email': commit.author.email,
                'message': commit.message.strip(),
                'timestamp': datetime.fromtimestamp(commit.committed_date).isoformat(),
                'stats': commit.stats.files.get(str(runbook_file), {})
            })
        
        return commits
    
    def get_commit_diff(self, commit_hash: str) -> Dict[str, Any]:
        """
        Get diff for a specific commit.
        
        Args:
            commit_hash: Git commit hash
        
        Returns:
            Diff information
        """
        commit = self.repo.commit(commit_hash)
        parent = commit.parents[0] if commit.parents else None
        
        diff = parent.diff(commit) if parent else commit.diff()
        
        changes = []
        for d in diff:
            if d.a_blob and d.b_blob:
                # Modified file
                changes.append({
                    'path': d.b_path,
                    'type': 'modified',
                    'additions': d.diff.count('\n+') if d.diff else 0,
                    'deletions': d.diff.count('\n-') if d.diff else 0
                })
            elif d.b_blob:
                # Added file
                changes.append({'path': d.b_path, 'type': 'added'})
            elif d.a_blob:
                # Deleted file
                changes.append({'path': d.a_path, 'type': 'deleted'})
        
        return {
            'commit': commit_hash,
            'author': commit.author.name,
            'message': commit.message.strip(),
            'timestamp': datetime.fromtimestamp(commit.committed_date).isoformat(),
            'changes': changes
        }
    
    def rollback_runbook(self, 
                         runbook_path: str,
                         target_commit: str) -> str:
        """
        Rollback runbook to a specific commit.
        
        Args:
            runbook_path: Path to runbook
            target_commit: Commit hash to rollback to
        
        Returns:
            New commit hash for rollback
        """
        runbook_file = self.repo_path / runbook_path
        
        # Checkout the target version
        self.repo.git.checkout(target_commit, '--', str(runbook_file))
        
        # Commit the rollback
        commit_msg = f"rollback: {runbook_path} to {target_commit[:7]}"
        
        self.repo.index.add([str(runbook_file)])
        commit = self.repo.index.commit(commit_msg, author=self.actor)
        
        return commit.hexsha
    
    def create_branch(self, 
                      branch_name: str,
                      from_commit: Optional[str] = None) -> str:
        """
        Create a new branch for runbook changes.
        
        Args:
            branch_name: Name for new branch
            from_commit: Optional commit to branch from (default: HEAD)
        
        Returns:
            Branch name
        """
        self.repo.git.branch(branch_name, from_commit or 'HEAD')
        return branch_name
    
    def merge_branch(self, 
                     source_branch: str,
                     target_branch: str = "main") -> bool:
        """
        Merge a branch into target.
        
        Args:
            source_branch: Branch to merge from
            target_branch: Branch to merge into
        
        Returns:
            True if merge successful
        """
        try:
            self.repo.git.checkout(target_branch)
            self.repo.git.merge(source_branch, '--no-ff', '-m', f"Merge {source_branch} into {target_branch}")
            return True
        except Exception as e:
            print(f"Merge failed: {e}")
            return False
```

---

#### Week 6: Real-Time Dashboard API

**Files to Create:**
```
api/
├── __init__.py
├── app.py              # FastAPI application
├── routes/
│   ├── __init__.py
│   ├── metrics.py
│   ├── incidents.py
│   └── runbooks.py
└── websocket.py
```

**Implementation:**

```python
# api/app.py
"""
FastAPI Application for Living Runbooks

Provides REST API and WebSocket for real-time dashboard updates.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import asyncio
import json

from api.routes import metrics, incidents, runbooks


app = FastAPI(
    title="Living Runbooks API",
    description="API for Living Runbooks incident management platform",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(runbooks.router, prefix="/api/runbooks", tags=["runbooks"])


# WebSocket manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Could handle client messages here
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/")
async def root():
    """API health check."""
    return {
        "service": "Living Runbooks API",
        "version": "2.0.0",
        "status": "healthy"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Background task to periodically broadcast metrics updates
async def broadcast_metrics_updates():
    """Broadcast metrics updates every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        
        # Get current metrics
        from api.routes.metrics import calculate_metrics
        metrics_data = calculate_metrics()
        
        # Broadcast to all connected clients
        await manager.broadcast({
            "type": "metrics_update",
            "data": metrics_data
        })


# Start background task on startup
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_metrics_updates())
```

---

#### Week 7-8: Database Layer + Multi-Tenant Support

**Files to Create:**
```
models/
├── __init__.py
├── database.py
├── incident.py
├── runbook.py
├── annotation.py
└── organization.py
```

---

## Security Fixes Required

### 1. Path Traversal Fix

```python
# slack/handler.py - REPLACE validate_runbook_path function

def validate_runbook_path(user_path: str, base_dir: Path) -> Path:
    """
    Securely validate runbook path to prevent path traversal attacks.
    
    This implementation:
    1. Resolves to canonical paths
    2. Checks for symlink attacks
    3. Validates path prefix
    """
    base_dir = base_dir.resolve()
    
    # Construct full path and resolve
    if Path(user_path).is_absolute():
        user_path_obj = Path(user_path).resolve()
    else:
        user_path_obj = (base_dir / user_path).resolve()
    
    # Check canonical path starts with base
    if not str(user_path_obj).startswith(str(base_dir)):
        raise ValueError(
            f"Path traversal detected: {user_path} resolves to {user_path_obj}"
        )
    
    # Check for symlinks in path components
    for parent in user_path_obj.parents:
        if parent.is_symlink():
            raise ValueError(f"Symlinks not allowed in path: {parent}")
    
    if user_path_obj.is_symlink():
        raise ValueError(f"Runbook path cannot be a symlink: {user_path_obj}")
    
    return user_path_obj
```

### 2. Input Validation

```python
# Add to slack/handler.py

from pydantic import BaseModel, validator, Field
import re

class AnnotationInput(BaseModel):
    """Validated annotation input schema."""
    incident_id: str = Field(..., min_length=1, max_length=100)
    symptoms: Optional[str] = Field(None, max_length=5000)
    root_cause: str = Field(..., min_length=1, max_length=2000)
    fix_applied: str = Field(..., min_length=1, max_length=2000)
    runbook_gaps: Optional[str] = Field(None, max_length=2000)
    runbook_path: str = Field(..., min_length=1, max_length=500)
    
    @validator('incident_id')
    def validate_incident_id(cls, v):
        if not re.match(r'^[A-Z0-9\-_]+$', v):
            raise ValueError('Invalid incident ID format')
        return v
    
    @validator('runbook_path')
    def validate_runbook_path(cls, v):
        if not v.endswith(('.yaml', '.yml')):
            raise ValueError('Runbook path must be YAML file')
        if '..' in v:
            raise ValueError('Invalid path characters')
        return v
```

---

## Third-Party Integration Opportunities

### High Priority

| Service | Purpose | Implementation Effort |
|---------|---------|----------------------|
| **PagerDuty** | Incident triggering | 2 days |
| **Datadog** | Alert webhooks | 2 days |
| **Sentry** | Error tracking integration | 1 day |
| **Anthropic/OpenAI** | LLM suggestions | 1 day |
| **GitHub** | Version control (alternative to GitPython) | 2 days |

### Medium Priority

| Service | Purpose | Implementation Effort |
|---------|---------|----------------------|
| **Linear/Jira** | Auto-create tasks from runbook gaps | 2 days |
| **Slack** | Enhanced bot interactions | 1 day |
| **Prometheus AlertManager** | Alert ingestion | 1 day |
| **CloudWatch** | AWS alert integration | 1 day |

---

## File Structure After Implementation

```
runbooks/
├── README.md
├── .env.example
├── requirements.txt
├── main.py                  # Flask/FastAPI entry point
│
├── api/                     # NEW: API layer
│   ├── __init__.py
│   ├── app.py
│   ├── websocket.py
│   └── routes/
│       ├── metrics.py
│       ├── incidents.py
│       └── runbooks.py
│
├── incident_sources/        # NEW: Alert integrations
│   ├── __init__.py
│   ├── base.py
│   ├── pagerduty.py
│   ├── datadog.py
│   ├── alertmanager.py
│   └── generic_webhook.py
│
├── ai/                      # NEW: AI/ML layer
│   ├── __init__.py
│   ├── llm_suggestion_engine.py
│   ├── semantic_correlator.py
│   └── report_generator.py
│
├── version_control/         # NEW: Git integration
│   ├── __init__.py
│   ├── git_manager.py
│   ├── diff_engine.py
│   └── rollback.py
│
├── models/                  # NEW: Database models
│   ├── __init__.py
│   ├── database.py
│   ├── incident.py
│   ├── runbook.py
│   └── annotation.py
│
├── slack/
│   ├── app.py
│   ├── handler.py           # FIXED: Security hardened
│   ├── modal.json
│   └── requirements.txt
│
├── runbooks/
│   └── service-x/
│       ├── runbook.md
│       ├── runbook.yaml
│       └── scripts/
│
├── schemas/
│   ├── runbook.schema.json
│   ├── annotation.schema.json
│   ├── diagnostics.schema.json
│   └── action-record.schema.json
│
├── dashboard/
│   ├── index.html           # UPDATED: Fetch from API
│   └── data.json
│
└── tests/                   # NEW: Comprehensive tests
    ├── __init__.py
    ├── test_incident_sources.py
    ├── test_ai_engine.py
    ├── test_version_control.py
    └── test_api.py
```

---

## Testing Strategy

### Unit Tests
- Test each incident source parser
- Test LLM suggestion engine (mock LLM responses)
- Test semantic correlator
- Test git version control operations

### Integration Tests
- Test PagerDuty webhook → incident creation
- Test Slack modal → annotation → git commit
- Test API endpoints with database

### End-to-End Tests
- Full incident lifecycle: alert → runbook → annotation → suggestion

---

## Deployment Recommendations

### Docker Compose (Development)
```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/runbooks
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=runbooks
  
  redis:
    image: redis:7
```

### Kubernetes (Production)
- Deploy with Helm chart
- Use Secrets for API keys
- Horizontal Pod Autoscaler for API
- PersistentVolume for database

---

## Success Metrics

| Metric | Target | Timeline |
|--------|--------|----------|
| Automated incident ingestion | 80% of incidents | Week 4 |
| Suggestion acceptance rate | >50% | Week 6 |
| MTTR reduction | 30% improvement | Week 8 |
| Runbook freshness | <30 days old | Ongoing |

---

## Conclusion

This plan transforms Living Runbooks from a proof-of-concept into a **production-ready incident intelligence platform**. The implementation is modular, allowing for incremental deployment and testing.

**Next Steps:**
1. Review and approve this plan
2. Begin Phase 1 implementation (Week 1-2: Alert Sources)
3. Iterate based on user feedback
4. Deploy to production environment
