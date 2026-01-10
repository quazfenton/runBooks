# Living Runbooks

This repository contains "Living Runbooks" - runbooks that update themselves, annotate incidents, and learn from fixes.

## Project Structure

```
runbooks/
├── service-x/
│   ├── runbook.md       # Human-readable runbook
│   ├── runbook.yaml     # Structured data
│   └── scripts/
│       ├── diagnose_high_cpu.py
│       ├── check_datadog_alerts.sh
│       ├── annotate_incident.py
│       └── suggest_updates.py
schemas/
├── runbook.schema.json
├── annotation.schema.json
├── diagnostics.schema.json
└── action-record.schema.json
```

## Runbook Schema

Runbooks are stored as structured YAML/JSON following the schema in `schemas/runbook.schema.json`. This enables programmatic updates, diffs, and integration with automation.

## Getting Started

1. Create a new runbook following the template structure
2. Add automation scripts to the `scripts/` directory
3. Integrate with your incident response workflow
4. Use the annotation system to capture learnings from incidents