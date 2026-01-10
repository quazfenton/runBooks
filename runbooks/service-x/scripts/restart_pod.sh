#!/bin/bash
# Restart Pod Remediation Script

set -euo pipefail

if [ $# -ne 3 ]; then
    echo "Usage: $0 <pod_name> <namespace> <runbook_path>"
    exit 1
fi

POD=$1
NAMESPACE=$2
RUNBOOK_PATH=$3

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed or not in PATH"
    exit 1
fi

echo "Restarting pod $POD in namespace $NAMESPACE"

# Get pod info before restart for documentation
echo "## Pod Info Before Restart" >> "$RUNBOOK_PATH"
kubectl -n "$NAMESPACE" get pod "$POD" -o wide >> "$RUNBOOK_PATH" 2>&1 || echo "Could not get pod info" >> "$RUNBOOK_PATH"
echo "" >> "$RUNBOOK_PATH"

# Delete the pod to trigger restart
kubectl -n "$NAMESPACE" delete pod "$POD" --wait=false

# Log the action in the runbook
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "## Remediation Action" >> "$RUNBOOK_PATH"
echo "- Timestamp: $TIMESTAMP" >> "$RUNBOOK_PATH"
echo "- Action: Pod restart triggered" >> "$RUNBOOK_PATH"
echo "- Pod: $POD" >> "$RUNBOOK_PATH"
echo "- Namespace: $NAMESPACE" >> "$RUNBOOK_PATH"
echo "- Command: kubectl -n $NAMESPACE delete pod $POD" >> "$RUNBOOK_PATH"
echo "" >> "$RUNBOOK_PATH"

echo "Restarted pod $POD in namespace $NAMESPACE"
echo "Action logged to $RUNBOOK_PATH"