#!/bin/bash
# Check Datadog Alerts
# Query Datadog for active alerts related to the service

set -euo pipefail

# Check if flock is available
if ! command -v flock &> /dev/null; then
    echo "Error: flock command is not available"
    exit 1
fi

if [ $# -ne 2 ]; then
    echo "Usage: $0 <service_name> <runbook_path>"
    exit 1
fi

SERVICE=$1
RUNBOOK_PATH=$2
API_KEY=${DATADOG_API_KEY:-}
APP_KEY=${DATADOG_APP_KEY:-}

if [ -z "$API_KEY" ] || [ -z "$APP_KEY" ]; then
    echo "Error: DATADOG_API_KEY and DATADOG_APP_KEY environment variables must be set"
    exit 1
fi

# Fetch active alerts for the service
echo "Fetching Datadog alerts for service: $SERVICE"

# Use curl's built-in URL encoding
response=$(curl -s -X GET \
  -G \
  --data-urlencode "tags=service:$SERVICE" \
  --data-urlencode "group_states=alert,warn,no data" \
  "https://api.datadoghq.com/api/v1/monitor" \
  -H "Content-Type: application/json" \
  -H "DD-API-KEY: $API_KEY" \
  -H "DD-APPLICATION-KEY: $APP_KEY")

# Check if the response is valid JSON
if ! echo "$response" | jq empty 2>/dev/null; then
    echo "Error: Invalid response from Datadog API"
    echo "$response"
    exit 1
fi

# Extract alert IDs, names, and statuses
alerts=$(echo "$response" | jq -r '.[] | "ID: \(.id) | Name: \(.name) | Status: \(.overall_state) | Priority: \(.priority)"')

# Use file locking to prevent concurrent writes
exec 200>"$RUNBOOK_PATH.lock"
flock -x 200 || exit 1

# Check if the heading already exists to avoid duplicates (inside lock)
HEADING_EXISTS=$(grep -c "^## Active Datadog Alerts for $SERVICE$" "$RUNBOOK_PATH" || true)

# Create a temporary file for atomic write
TEMP_FILE=$(mktemp)
cp "$RUNBOOK_PATH" "$TEMP_FILE"

if [ -n "$alerts" ]; then
    if [ "$HEADING_EXISTS" -eq 0 ]; then
        echo "## Active Datadog Alerts for $SERVICE" >> "$TEMP_FILE"
    fi
    echo "$alerts" >> "$TEMP_FILE"
    echo "$alerts"
else
    echo "No active alerts found for service: $SERVICE"
    if [ "$HEADING_EXISTS" -eq 0 ]; then
        echo "## Active Datadog Alerts for $SERVICE" >> "$TEMP_FILE"
    fi
    echo "No active alerts found." >> "$TEMP_FILE"
fi

# Atomically replace the original file
mv "$TEMP_FILE" "$RUNBOOK_PATH"

# Release the lock
exec 200>&-

echo "Datadog alerts info appended to $RUNBOOK_PATH"