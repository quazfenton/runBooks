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

# Check if RUNBOOK_PATH is appropriate for appending Markdown
if [ -d "$RUNBOOK_PATH" ] || [[ "$RUNBOOK_PATH" =~ \.(md|markdown)$ ]]; then
    # OK to append to Markdown files or directories
    :
else
    echo "Error: RUNBOOK_PATH ($RUNBOOK_PATH) is not a Markdown file or directory, refusing to modify."
    exit 1
fi

echo "Restarting pod $POD in namespace $NAMESPACE"

# Get pod info before restart for documentation
echo "## Pod Info Before Restart" >> "$RUNBOOK_PATH"
kubectl -n "$NAMESPACE" get pod "$POD" -o wide >> "$RUNBOOK_PATH" 2>&1 || echo "Could not get pod info" >> "$RUNBOOK_PATH"
echo "" >> "$RUNBOOK_PATH"

# Check if pod is controller-managed by inspecting ownerReferences
OWNER_REF=$(kubectl -n "$NAMESPACE" get pod "$POD" -o jsonpath='{.metadata.ownerReferences}' 2>/dev/null || echo "")
if [ -z "$OWNER_REF" ] || [ "$OWNER_REF" = "[]" ]; then
    echo "Warning: Pod $POD has no owner references (may be a standalone pod). Skipping deletion for safety."
    echo "Warning: Pod $POD has no owner references (may be a standalone pod). Skipping deletion for safety." >> "$RUNBOOK_PATH"
    exit 1
fi

# Delete the pod to trigger restart
kubectl -n "$NAMESPACE" delete pod "$POD" --wait=false 2>&1 || { echo "Error: Failed to delete pod $POD" >> "$RUNBOOK_PATH"; exit 1; }

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