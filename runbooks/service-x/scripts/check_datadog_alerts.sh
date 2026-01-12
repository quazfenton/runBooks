#!/bin/bash
# Check Datadog Alerts
# Query Datadog for active alerts related to the service

set -euo pipefail

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

# URL-encode the service name
SERVICE_ENCODED=$(printf %s "$SERVICE" | jq -sRr @uri)

response=$(curl -s -X GET \
  "https://api.datadoghq.com/api/v1/monitor?group_states=alert,warn,no%20data&tags=service:$SERVICE_ENCODED" \
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

if [ -n "$alerts" ] && [ "$alerts" != "" ]; then
    echo "## Active Datadog Alerts for $SERVICE" >> "$RUNBOOK_PATH"
    echo "$alerts" >> "$RUNBOOK_PATH"
    echo "$alerts"
else
    echo "No active alerts found for service: $SERVICE"
    echo "## Active Datadog Alerts for $SERVICE" >> "$RUNBOOK_PATH"
    echo "No active alerts found." >> "$RUNBOOK_PATH"
fi

echo "Datadog alerts info appended to $RUNBOOK_PATH"