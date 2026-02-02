#!/bin/bash
# Generate Runbook Health Metrics

set -euo pipefail

echo "Generating runbook health metrics..."

# Run the metrics generator
python3 runbooks/service-x/scripts/generate_metrics.py --runbooks-dir runbooks --output dashboard/data.json

echo "Metrics generated successfully!"
echo "Dashboard data available at dashboard/data.json"

# If we have a web server available, we could serve the dashboard
# For now, just let the user know where to find it
echo ""
echo "To view the dashboard:"
echo "1. Open dashboard/index.html in a web browser"
echo "2. The dashboard will automatically use the generated data.json"


