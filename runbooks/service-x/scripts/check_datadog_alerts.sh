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

# Check if the runbook is in YAML format (by extension or front matter)
if [[ "$RUNBOOK_PATH" =~ \.ya?ml$ ]] || head -n 1 "$RUNBOOK_PATH" | grep -q '^---'; then
    # Handle YAML format by adding alerts as structured data
    TEMP_FILE=$(mktemp)
    cp "$RUNBOOK_PATH" "$TEMP_FILE"

    # Use Python to update the YAML file with alerts data
    python3 -c "
import sys
import yaml
import json
from datetime import datetime

if len(sys.argv) != 4:
    print('Usage: python3 script.py <input_file> <output_file> <alerts>')
    sys.exit(1)

input_file, output_file, alerts_str = sys.argv[1], sys.argv[2], sys.argv[3]
service = '$SERVICE'
heading_exists = $HEADING_EXISTS

# Parse alerts string - split by newlines
alerts_list = [line.strip() for line in alerts_str.split('\n') if line.strip()]

# Load existing YAML
with open(input_file, 'r') as f:
    data = yaml.safe_load(f)

# Add or update datadog_alerts section
if data is None:
    data = {}

# Prepare alert data
alert_data = {
    'timestamp': datetime.utcnow().isoformat(),
    'service': service,
    'alerts_found': len(alerts_list) > 0 and alerts_list != ['No active alerts found.'],
    'alerts': alerts_list if len(alerts_list) > 0 and alerts_list != ['No active alerts found.'] else []
}

if 'datadog_alerts' not in data:
    data['datadog_alerts'] = []

# Add this check to the list
data['datadog_alerts'].append(alert_data)

# Write back to file
with open(output_file, 'w') as f:
    yaml.dump(data, f, default_flow_style=False)
" "$RUNBOOK_PATH" "$TEMP_FILE" "$alerts"
    echo "$alerts"
else
    # Handle Markdown format by appending headings
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
fi

# Atomically replace the original file
mv "$TEMP_FILE" "$RUNBOOK_PATH"

# Release the lock
exec 200>&-

echo "Datadog alerts info appended to $RUNBOOK_PATH"