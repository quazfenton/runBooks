# Living Runbooks - Quick Start Guide

## 5-Minute Setup

### Option 1: Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/your-org/runbooks.git
cd runbooks

# Copy environment template
cp .env.example .env

# Edit .env with your API keys (optional)
# - SLACK_SIGNING_SECRET (for Slack integration)
# - PAGERDUTY_API_KEY (for PagerDuty integration)
# - ANTHROPIC_API_KEY (for AI suggestions)

# Start with Docker
docker-compose up -d

# View logs
docker-compose logs -f

# Access dashboard
open http://localhost:8000/dashboard

# Access API docs
open http://localhost:8000/docs
```

### Option 2: Local Python

```bash
# Clone repository
git clone https://github.com/your-org/runbooks.git
cd runbooks

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize git (for version control)
git init
git config user.name "Your Name"
git config user.email "you@example.com"
git add .
git commit -m "Initial commit"

# Start API server
python -m uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

# In another terminal, start Slack webhook (optional)
python slack/app.py
```

---

## Configure Integrations

### Slack Integration

1. **Create Slack App**
   - Go to https://api.slack.com/apps
   - Click "Create New App" → "From scratch"
   - Name: Living Runbooks

2. **Enable Features**
   - **Event Subscriptions**: Enable, add `/slack/events`
   - **Interactive Components**: Enable, add `/slack/interactions`
   - **Socket Mode**: Enable (for modals)

3. **Get Credentials**
   - Signing Secret → Add to `.env` as `SLACK_SIGNING_SECRET`
   - Bot Token → Add to `.env` as `SLACK_BOT_TOKEN`

4. **Install App**
   - Go to "Install App" → "Install to Workspace"

### PagerDuty Integration

1. **Get API Key**
   - Settings → Integrations → API Access
   - Create API token → Add to `.env` as `PAGERDUTY_API_KEY`

2. **Set Up Webhook**
   - Settings → Integrations → Webhooks
   - Add webhook: `https://your-server.com/api/incidents/webhooks/pagerduty`
   - Set secret → Add to `.env` as `PAGERDUTY_WEBHOOK_SECRET`

### Datadog Integration

1. **Get API Keys**
   - Organization Settings → API
   - Copy API Key → Add to `.env` as `DATADOG_API_KEY`
   - Copy Application Key → Add to `.env` as `DATADOG_APP_KEY`

2. **Set Up Webhook**
   - Integrations → Webhooks → New
   - URL: `https://your-server.com/api/incidents/webhooks/datadog`
   - Set secret → Add to `.env` as `DATADOG_WEBHOOK_SECRET`

---

## First Runbook

### Create Service Runbook

```bash
mkdir -p runbooks/my-service
cat > runbooks/my-service/runbook.yaml << 'EOF'
title: "My Service Outage Runbook"
version: "1.0"
last_updated: "2026-03-03T12:00:00Z"
owner: "my-team"
triggers: ["high_cpu", "5xx_errors", "latency"]
steps:
  - check: "Verify service health"
    command: "curl http://localhost:8080/health"
    description: "Check if service is responding"
  - check: "Check recent deployments"
    command: "kubectl rollout history deployment/my-service"
    description: "Look for recent changes"
  - check: "Check CPU and memory"
    command: "kubectl top pods -l app=my-service"
    description: "Identify resource constraints"
annotations: []
diagnostics: []
EOF
```

### Annotate Your First Incident

```bash
python runbooks/service-x/scripts/annotate_incident.py \
  --runbook runbooks/my-service/runbook.yaml \
  --incident INC-20260303-001 \
  --cause "High memory usage due to cache growth" \
  --fix "Cleared cache and increased memory limits" \
  --symptoms "Slow response times, OOM errors" \
  --gap "Missing cache size monitoring"
```

### Generate AI Suggestions

```bash
# With Anthropic (requires API key)
export ANTHROPIC_API_KEY=sk-ant-...
python -m ai.llm_suggestion_engine \
  --runbook runbooks/my-service/runbook.yaml \
  --incident '{"incident_id": "INC-001", "cause": "Memory leak", "fix": "Increased limits"}' \
  --provider anthropic

# Without API key (fallback mode)
python -m ai.llm_suggestion_engine \
  --runbook runbooks/my-service/runbook.yaml \
  --incident '{"incident_id": "INC-001", "cause": "Memory leak", "fix": "Increased limits"}' \
  --provider template
```

---

## Common Operations

### View Dashboard
```bash
open http://localhost:8000/dashboard
```

### View API Documentation
```bash
open http://localhost:8000/docs
```

### List Runbooks
```bash
curl http://localhost:8000/api/runbooks
```

### Get Metrics
```bash
curl http://localhost:8000/api/metrics
```

### View Runbook History (Git)
```bash
python -m version_control.git_manager \
  --runbook runbooks/my-service/runbook.yaml \
  --action history
```

### Generate Post-Incident Report
```bash
# Create incident data file
cat > incident-001.json << 'EOF'
{
  "incident_id": "INC-20260303-001",
  "title": "Service Outage",
  "service": "my-service",
  "severity": "high",
  "cause": "Database connection pool exhausted",
  "fix": "Increased pool size",
  "duration_minutes": 45
}
EOF

# Generate report
python -m ai.report_generator \
  --incident incident-001.json \
  --runbook runbooks/my-service/runbook.yaml \
  --output reports/incident-001.md \
  --format markdown
```

---

## Troubleshooting

### API Server Won't Start

```bash
# Check if port is in use
lsof -i :8000

# Kill process if needed
kill -9 <PID>

# Restart
python -m uvicorn api.app:app --reload
```

### Slack Webhook Not Working

1. Check signing secret matches
2. Verify URL is publicly accessible (use ngrok for testing)
3. Check Slack app permissions

```bash
# Test with ngrok
ngrok http 3000
# Update Slack app URLs to ngrok URL
```

### Git Operations Fail

```bash
# Initialize git if not done
git init
git config user.name "Your Name"
git config user.email "you@example.com"
git add .
git commit -m "Initial commit"

# Install gitpython
pip install gitpython
```

### AI Features Not Working

```bash
# Check API key is set
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY

# Install required packages
pip install anthropic
pip install openai
pip install sentence-transformers
```

---

## Next Steps

1. **Add More Runbooks**
   - Create runbooks for all critical services
   - Document common failure scenarios
   - Add automation scripts

2. **Set Up Monitoring**
   - Connect PagerDuty/Datadog
   - Configure alert routing
   - Test webhook delivery

3. **Enable AI Features**
   - Get Anthropic/OpenAI API key
   - Test suggestion generation
   - Configure report templates

4. **Deploy to Production**
   - Set up Docker in production
   - Configure HTTPS
   - Set up backups

---

## Getting Help

- **Documentation**: https://github.com/your-org/runbooks/wiki
- **API Docs**: http://localhost:8000/docs
- **Issues**: https://github.com/your-org/runbooks/issues
- **Examples**: See `runbooks/service-x/` for template

---

*For more details, see README.md and PHASE2_SUMMARY_2026-03-03.md*
