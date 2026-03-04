# code-server & VSIX Integration Guide

**Version:** 1.0  
**Date:** March 3, 2026

---

## Overview

Living Runbooks now supports **code-server** for web-based development and a **VS Code extension (VSIX)** for integrated runbook management within VS Code.

---

## code-server Setup

### What is code-server?

code-server is VS Code running in the browser. It provides:
- Full VS Code experience in a web browser
- Access to VS Code extensions
- Remote development capabilities
- Integrated terminal and debugging

### Quick Start

```bash
# Start code-server with Docker Compose
docker-compose --profile dev up code-server

# Access at http://localhost:8080
# Default password: admin (change with CODE_SERVER_PASSWORD env var)
```

### Custom Password

```bash
# Set custom password
export CODE_SERVER_PASSWORD=mysecurepassword
docker-compose --profile dev up code-server
```

### Dockerfile.code-server

The `Dockerfile.code-server` extends the official code-server image with:

- Python 3 and pip
- Project dependencies installed
- Recommended VS Code extensions pre-installed:
  - `ms-python.python` - Python language support
  - `ms-python.vscode-pylance` - Python type checking
  - `redhat.vscode-yaml` - YAML language support
  - `ms-azuretools.vscode-docker` - Docker integration
  - `fastapi.fastapi-snippets` - FastAPI snippets
  - `littlefoxteam.vscode-python-test-adapter` - Test adapter

### Pre-configured Settings

The code-server environment includes:

```json
{
    "python.defaultInterpreterPath": "/usr/bin/python3",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "python.testing.pytestEnabled": true
}
```

---

## VS Code Extension (VSIX)

### Features

The Living Runbooks VS Code extension provides:

1. **Runbooks View** - Browse and open runbooks from sidebar
2. **Incident Annotation** - Annotate incidents directly from VS Code
3. **AI Suggestions** - Generate AI-powered runbook improvements
4. **Similar Incidents** - Find similar incidents using semantic search
5. **Post-Incident Reports** - Generate comprehensive reports

### Installation

#### Option 1: From VSIX File

```bash
# Build the extension
cd vscode-extension
npm install
npm run compile
npm run package

# Install the .vsix file
code --install-extension living-runbooks-2.1.0.vsix
```

#### Option 2: From Source (Development)

```bash
# Clone repository
git clone https://github.com/living-runbooks/runbooks.git
cd runbooks/vscode-extension

# Install dependencies
npm install

# Run extension (opens new VS Code window)
npm run watch

# In another terminal
code --extensionDevelopmentPath=$PWD
```

### Configuration

Add to VS Code settings (`settings.json`):

```json
{
    "livingRunbooks.api_url": "http://localhost:8000",
    "livingRunbooks.api_key": "",
    "livingRunbooks.runbooks_path": "./runbooks"
}
```

### Commands

| Command | Description |
|---------|-------------|
| `living-runbooks.refresh` | Refresh runbooks list |
| `living-runbooks.openRunbook` | Open a runbook |
| `living-runbooks.annotateIncident` | Annotate incident |
| `living-runbooks.generateSuggestions` | Generate AI suggestions |
| `living-runbooks.findSimilarIncidents` | Find similar incidents |
| `living-runbooks.generateReport` | Generate post-incident report |

### Usage

#### 1. Open Runbook from Sidebar

1. Click Living Runbooks icon in activity bar
2. Expand "Runbooks" view
3. Click on a runbook to open

#### 2. Annotate Incident

1. Right-click on a runbook
2. Select "Annotate Incident"
3. Enter incident ID, cause, and fix
4. Annotation is saved to runbook

#### 3. Generate AI Suggestions

1. Right-click on a runbook
2. Select "Generate AI Suggestions"
3. View suggestions in information popup

#### 4. Find Similar Incidents

1. Open command palette (`Ctrl+Shift+P`)
2. Type "Living Runbooks: Find Similar Incidents"
3. Enter incident description
4. View similar incidents with similarity scores

### Development

#### Project Structure

```
vscode-extension/
├── src/
│   └── extension.ts      # Main extension code
├── package.json          # Extension manifest
├── tsconfig.json         # TypeScript config
├── webpack.config.js     # Webpack bundling
└── resources/
    └── icon.svg          # Extension icon
```

#### Build Commands

```bash
# Install dependencies
npm install

# Compile TypeScript
npm run compile

# Watch mode (auto-recompile)
npm run watch

# Package as .vsix
npm run package

# Lint
npm run lint
```

#### Testing

```bash
# Run extension tests
npm test
```

---

## Integration with Living Runbooks API

### API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/runbooks` | GET | List runbooks |
| `/api/runbooks/{path}` | GET | Get runbook |
| `/api/runbooks/{path}/annotate` | POST | Annotate incident |
| `/api/ai/suggest` | POST | Generate suggestions |
| `/api/ai/correlate` | POST | Find similar incidents |
| `/api/ai/report` | POST | Generate report |

### Running the API

```bash
# Start API server
docker-compose up api

# Or run locally
python -m uvicorn api.app:app --reload
```

---

## Troubleshooting

### code-server won't start

**Symptoms:** Container exits immediately

**Solutions:**
1. Check port 8080 is not in use
2. Verify Docker daemon is running
3. Check logs: `docker-compose logs code-server`

### Extension not loading

**Symptoms:** Living Runbooks view not appearing

**Solutions:**
1. Check API is running at configured URL
2. Reload VS Code window (`Ctrl+Shift+P` → "Reload Window")
3. Check extension is enabled: `Extensions` → `Living Runbooks`

### API connection failed

**Symptoms:** "Failed to connect to API" errors

**Solutions:**
1. Verify API is running: `curl http://localhost:8000/health`
2. Check `livingRunbooks.api_url` setting
3. Check firewall/proxy settings

### Extension commands not working

**Symptoms:** Commands show "command not found"

**Solutions:**
1. Rebuild extension: `npm run compile`
2. Reinstall: `code --install-extension living-runbooks-2.1.0.vsix --force`
3. Check VS Code version (need ≥ 1.85.0)

---

## Best Practices

### For code-server

1. **Use HTTPS in production** - Configure reverse proxy with SSL
2. **Set strong password** - Use `CODE_SERVER_PASSWORD` env var
3. **Limit access** - Use firewall or VPN
4. **Mount persistent volumes** - Preserve extensions and settings

### For VSIX Extension

1. **Keep API URL in workspace settings** - Per-project configuration
2. **Use API key for production** - Secure API access
3. **Enable auto-save** - For runbook edits
4. **Use YAML schema validation** - Catch errors early

---

## Summary

**code-server provides:**
- ✅ Web-based VS Code
- ✅ Full development environment
- ✅ Pre-configured extensions
- ✅ Accessible from anywhere

**VSIX Extension provides:**
- ✅ Integrated runbook management
- ✅ One-click annotation
- ✅ AI suggestions in editor
- ✅ Similar incident search

**Get started:**
```bash
# Start code-server
docker-compose --profile dev up code-server

# Install VSIX
cd vscode-extension && npm install && npm run package
code --install-extension living-runbooks-2.1.0.vsix
```

---

*Documentation Version: 1.0*  
*Last Updated: March 3, 2026*
