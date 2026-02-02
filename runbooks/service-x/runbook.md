# Service X Outage Runbook

## Overview
This runbook provides steps to diagnose and resolve outages for Service X.

## Triggers
- High CPU alerts
- 5xx error alerts

## Steps

### 1. Verify alert in Datadog
```bash
datadog alert list --filter 'service:x'
```
Automation script: `scripts/check_datadog.py`

### 2. Check recent deployments
```bash
kubectl rollout history deployment -n prod
```
Automation script: `scripts/check_deployments.sh`

## Annotations
No annotations yet.

## Diagnostics
No diagnostics yet.