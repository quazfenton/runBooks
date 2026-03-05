"""
LLM-Powered Runbook Suggestion Engine

Uses Anthropic Claude or OpenAI GPT to generate intelligent runbook improvement suggestions.
"""

import os
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import yaml

# Try to import LLM libraries
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'type': self.suggestion_type,
            'action': self.action,
            'reasoning': self.reasoning,
            'priority': self.priority,
            'confidence': self.confidence
        }


class LLMProvider:
    """Abstract LLM provider interface."""
    
    def generate(self, prompt: str, max_tokens: int = 1500) -> str:
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic package not installed. Install with: pip install anthropic"
            )
        
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get('ANTHROPIC_API_KEY')
        )
    
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
            raise ImportError(
                "openai package not installed. Install with: pip install openai"
            )
        
        self.client = OpenAI(
            api_key=api_key or os.environ.get('OPENAI_API_KEY')
        )
    
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
            if not ANTHROPIC_AVAILABLE:
                print("Warning: Anthropic not available. Install with: pip install anthropic")
            self.llm = AnthropicProvider(api_key) if ANTHROPIC_AVAILABLE else None
        elif provider == "openai":
            if not OPENAI_AVAILABLE:
                print("Warning: OpenAI not available. Install with: pip install openai")
            self.llm = OpenAIProvider(api_key) if OPENAI_AVAILABLE else None
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    def analyze_incident(
        self,
        incident_annotation: Dict[str, Any],
        current_runbook: Dict[str, Any],
        similar_incidents: Optional[List[Dict[str, Any]]] = None
    ) -> List[Suggestion]:
        """
        Analyze an incident and suggest runbook improvements.

        Args:
            incident_annotation: The incident annotation to analyze
            current_runbook: Current runbook structure
            similar_incidents: Optional list of similar past incidents

        Returns:
            List of suggestions for runbook improvement
            
        Raises:
            ValueError: If input data is invalid
            RuntimeError: If LLM provider fails
        """
        # Validate inputs
        if not incident_annotation:
            raise ValueError("incident_annotation cannot be empty")
        if not current_runbook:
            raise ValueError("current_runbook cannot be empty")
        
        # Check if LLM is available
        if not self.llm:
            logger.warning("LLM provider not available, using fallback analysis")
            return self._fallback_analyze(incident_annotation, current_runbook)

        try:
            prompt = self._build_analysis_prompt(
                incident_annotation,
                current_runbook,
                similar_incidents
            )
            response = self.llm.generate(prompt, max_tokens=2000)
            return self._parse_suggestions(response)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}", exc_info=True)
            # Fallback to basic analysis
            return self._fallback_analyze(incident_annotation, current_runbook)
    
    def _build_analysis_prompt(
        self,
        incident: Dict[str, Any],
        runbook: Dict[str, Any],
        similar: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Build the analysis prompt for the LLM."""
        
        prompt = f"""You are an expert SRE analyzing incidents to improve runbooks. Your task is to suggest concrete, actionable improvements to the runbook based on what was learned from this incident.

**Recent Incident:**
- Incident ID: {incident.get('incident_id', 'UNKNOWN')}
- Root Cause: {incident.get('cause', 'Unknown')}
- Fix Applied: {incident.get('fix', 'Unknown')}
- Symptoms: {', '.join(incident.get('symptoms', [])) if incident.get('symptoms') else 'None specified'}
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
            formatted.append(
                f"{i}. {check}\n   Command: `{command}`\n   Automation: {automation}"
            )
        
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
                    current_suggestion['type'] = value.upper()
                elif key == 'action':
                    current_suggestion['action'] = value
                elif key == 'reasoning':
                    current_suggestion['reasoning'] = value
                elif key == 'priority':
                    current_suggestion['priority'] = value.upper()
        
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
            confidence=0.8,
            priority=data.get('priority', 'MEDIUM')
        )
    
    def _fallback_analyze(
        self,
        incident: Dict[str, Any],
        runbook: Dict[str, Any]
    ) -> List[Suggestion]:
        """Fallback analysis when LLM is not available."""
        suggestions = []
        
        cause = incident.get('cause', '').lower()
        fix = incident.get('fix', '').lower()
        
        # Simple rule-based suggestions
        if 'memory' in cause:
            suggestions.append(Suggestion(
                suggestion_type='ADD_MONITORING',
                action='Add memory usage monitoring with alerts at 70% and 85% thresholds',
                reasoning='Memory-related incident occurred; early detection could prevent future incidents',
                confidence=0.7,
                priority='HIGH'
            ))
        
        if 'cpu' in cause:
            suggestions.append(Suggestion(
                suggestion_type='ADD_STEP',
                action='Add step to check CPU usage and top processes during incident',
                reasoning='CPU-related issue detected; diagnostic step would help future troubleshooting',
                confidence=0.7,
                priority='HIGH'
            ))
        
        if 'restart' in fix:
            suggestions.append(Suggestion(
                suggestion_type='ADD_AUTOMATION',
                action='Create automated restart script for quick remediation',
                reasoning='Manual restart was required; automation would reduce MTTR',
                confidence=0.6,
                priority='MEDIUM'
            ))
        
        return suggestions


def main():
    """Example usage of LLM suggestion engine."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate runbook improvement suggestions using LLM"
    )
    parser.add_argument(
        "--runbook",
        required=True,
        help="Path to runbook YAML"
    )
    parser.add_argument(
        "--incident",
        required=True,
        help="Incident annotation JSON or path to file"
    )
    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic", "openai"],
        help="LLM provider to use"
    )
    parser.add_argument(
        "--output",
        help="Output file for suggestions (JSON)"
    )
    
    args = parser.parse_args()
    
    # Load runbook
    with open(args.runbook, 'r') as f:
        runbook = yaml.safe_load(f)
    
    # Load incident (from file or inline JSON)
    if args.incident.endswith('.json'):
        with open(args.incident, 'r') as f:
            incident = json.load(f)
    else:
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
        output_data = [s.to_dict() for s in suggestions]
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"Suggestions saved to {args.output}")


if __name__ == "__main__":
    main()
