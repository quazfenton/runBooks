#!/usr/bin/env python3
"""
FastAPI Application for Living Runbooks

Provides REST API and WebSocket for real-time dashboard updates.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
import json
from pathlib import Path
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Living Runbooks API",
    description="API for Living Runbooks incident management platform",
    version="2.1.0"
)

# CORS middleware - configure for production
allowed_origins = os.environ.get('ALLOWED_ORIGINS', '*').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins != ['*'] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent.parent / "dashboard"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# WebSocket manager for real-time updates
class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


# ============================================================================
# WebSocket Endpoints
# ============================================================================

@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to Living Runbooks API",
            "timestamp": datetime.now().isoformat()
        })

        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received from client: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)


# ============================================================================
# Core Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API health check and info."""
    return {
        "service": "Living Runbooks API",
        "version": "2.1.0",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "metrics": "/api/metrics",
            "incidents": "/api/incidents",
            "runbooks": "/api/runbooks",
            "websocket": "/ws/dashboard"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# Metrics Endpoints
# ============================================================================

@app.get("/api/metrics")
async def get_metrics():
    """
    Get runbook health metrics.

    Returns metrics about runbooks, annotations, and incidents.
    """
    try:
        # Dynamic import to handle service-x naming
        import sys
        runbooks_path = Path(__file__).parent.parent / "runbooks" / "service-x" / "scripts"
        if str(runbooks_path) not in sys.path:
            sys.path.insert(0, str(runbooks_path))

        from generate_metrics import generate_dashboard_data

        runbooks_dir = Path(__file__).parent.parent / "runbooks"
        metrics = generate_dashboard_data(str(runbooks_dir))

        return {
            "status": "ok",
            "metrics": metrics,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting metrics: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "metrics": {
                "totalRunbooks": 0,
                "totalAnnotations": 0,
                "incidentsByService": {},
                "topFixes": [],
                "runbookAges": []
            }
        }


# ============================================================================
# Runbook Endpoints
# ============================================================================

@app.get("/api/runbooks")
async def list_runbooks():
    """
    List all runbooks.

    Returns list of runbook paths and metadata.
    """
    try:
        runbooks_dir = Path(__file__).parent.parent / "runbooks"
        runbooks = []

        for runbook_file in runbooks_dir.rglob("runbook.yaml"):
            try:
                import yaml
                with open(runbook_file, 'r', encoding='utf-8') as f:
                    runbook_data = yaml.safe_load(f)

                if runbook_data:
                    runbooks.append({
                        "path": str(runbook_file.relative_to(runbooks_dir)),
                        "title": runbook_data.get('title', 'Unknown'),
                        "service": runbook_file.parent.name,
                        "version": runbook_data.get('version', '1.0'),
                        "owner": runbook_data.get('owner', 'Unknown'),
                        "annotations_count": len(runbook_data.get('annotations', [])),
                        "diagnostics_count": len(runbook_data.get('diagnostics', [])),
                        "triggers": runbook_data.get('triggers', [])
                    })
            except Exception as e:
                logger.warning(f"Error reading runbook {runbook_file}: {e}")
                continue

        return {
            "status": "ok",
            "count": len(runbooks),
            "runbooks": runbooks
        }

    except Exception as e:
        logger.error(f"Error listing runbooks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runbooks/{runbook_path:path}")
async def get_runbook(runbook_path: str):
    """
    Get a specific runbook.

    Args:
        runbook_path: Path to runbook (URL encoded)
    """
    try:
        runbooks_dir = Path(__file__).parent.parent / "runbooks"
        runbook_file = runbooks_dir / runbook_path

        # Security check - prevent path traversal
        try:
            runbook_file.resolve().relative_to(runbooks_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid runbook path")

        if not runbook_file.exists():
            raise HTTPException(status_code=404, detail="Runbook not found")

        import yaml
        with open(runbook_file, 'r', encoding='utf-8') as f:
            runbook_data = yaml.safe_load(f)

        return {
            "status": "ok",
            "path": runbook_path,
            "runbook": runbook_data or {}
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting runbook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Incident Endpoints (Integrated from incident_sources)
# ============================================================================

@app.post("/api/incidents/webhooks/pagerduty")
async def pagerduty_webhook(request: Any):
    """Receive PagerDuty incident webhooks."""
    try:
        from incident_sources.pagerduty import PagerDutyIntegration
        from fastapi import Request
        request_obj = request if hasattr(request, 'json') else None

        # Get request data
        body = await request.json() if hasattr(request, 'json') else {}

        pd = _get_pagerduty_integration()
        if not pd:
            return JSONResponse(
                status_code=200,
                content={'status': 'ok', 'warning': 'PagerDuty not configured'}
            )

        incident = pd.parse_webhook(body)
        runbook_path = _find_runbook_for_service(incident.service)

        return JSONResponse(
            status_code=200,
            content={
                'status': 'ok',
                'incident': {
                    'id': incident.external_id,
                    'title': incident.title,
                    'service': incident.service,
                    'severity': incident.severity,
                    'status': incident.status,
                    'runbook_path': runbook_path
                }
            }
        )

    except Exception as e:
        logger.error(f"Error processing PagerDuty webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/incidents/webhooks/datadog")
async def datadog_webhook(request: Any):
    """Receive Datadog alert webhooks."""
    try:
        from incident_sources.datadog import DatadogIntegration

        body = await request.json() if hasattr(request, 'json') else {}

        dd = _get_datadog_integration()
        if not dd:
            return JSONResponse(
                status_code=200,
                content={'status': 'ok', 'warning': 'Datadog not configured'}
            )

        alert = dd.parse_webhook(body)
        runbook_path = _find_runbook_for_service(alert.service)

        return JSONResponse(
            status_code=200,
            content={
                'status': 'ok',
                'alert': {
                    'id': alert.external_id,
                    'title': alert.title,
                    'service': alert.service,
                    'severity': alert.severity,
                    'status': alert.status,
                    'runbook_path': runbook_path
                }
            }
        )

    except Exception as e:
        logger.error(f"Error processing Datadog webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/incidents/webhooks/alertmanager")
async def alertmanager_webhook(request: Any):
    """Receive Prometheus AlertManager webhooks."""
    try:
        from incident_sources.alertmanager import AlertManagerIntegration

        body = await request.json() if hasattr(request, 'json') else {}

        am = _get_alertmanager_integration()
        if not am:
            return JSONResponse(
                status_code=200,
                content={'status': 'ok', 'warning': 'AlertManager not configured'}
            )

        alert = am.parse_webhook(body)
        runbook_path = _find_runbook_for_service(alert.service)

        return JSONResponse(
            status_code=200,
            content={
                'status': 'ok',
                'alert': {
                    'id': alert.external_id,
                    'title': alert.title,
                    'service': alert.service,
                    'severity': alert.severity,
                    'alert_name': alert.alert_name,
                    'runbook_path': runbook_path
                }
            }
        )

    except Exception as e:
        logger.error(f"Error processing AlertManager webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/incidents/webhooks/sentry")
async def sentry_webhook(request: Any):
    """Receive Sentry issue webhooks."""
    try:
        from incident_sources.sentry import SentryIntegration

        body = await request.json() if hasattr(request, 'json') else {}

        sentry = _get_sentry_integration()
        if not sentry:
            return JSONResponse(
                status_code=200,
                content={'status': 'ok', 'warning': 'Sentry not configured'}
            )

        issue = sentry.parse_webhook(body)
        runbook_path = _find_runbook_for_service(issue.service)

        return JSONResponse(
            status_code=200,
            content={
                'status': 'ok',
                'issue': {
                    'id': issue.external_id,
                    'title': issue.title,
                    'service': issue.service,
                    'severity': issue.severity,
                    'level': issue.level,
                    'runbook_path': runbook_path
                }
            }
        )

    except Exception as e:
        logger.error(f"Error processing Sentry webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/incidents/recent")
async def get_recent_incidents(
    limit: int = Query(default=50, ge=1, le=200),
    service: Optional[str] = None,
    source: Optional[str] = None
):
    """Get recent incidents from all sources."""
    # Placeholder - in production, query from database
    return {
        "status": "ok",
        "count": 0,
        "incidents": [],
        "note": "Database integration required for incident history"
    }


# ============================================================================
# AI Endpoints
# ============================================================================

@app.post("/api/ai/suggest")
async def generate_suggestions(
    runbook_path: str,
    incident: Dict[str, Any],
    provider: str = Query(default="template", enum=["anthropic", "openai", "template"])
):
    """Generate AI-powered runbook improvement suggestions."""
    try:
        from ai.llm_suggestion_engine import LLMRunbookEvolution

        runbooks_dir = Path(__file__).parent.parent / "runbooks"
        runbook_file = runbooks_dir / runbook_path

        if not runbook_file.exists():
            raise HTTPException(status_code=404, detail="Runbook not found")

        import yaml
        with open(runbook_file, 'r', encoding='utf-8') as f:
            runbook = yaml.safe_load(f) or {}

        engine = LLMRunbookEvolution(provider=provider)
        suggestions = engine.analyze_incident(incident, runbook)

        return {
            "status": "ok",
            "suggestions": [s.to_dict() for s in suggestions],
            "count": len(suggestions)
        }

    except Exception as e:
        logger.error(f"Error generating suggestions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai/correlate")
async def find_similar_incidents(
    query: str,
    threshold: float = Query(default=0.7, ge=0.0, le=1.0),
    max_results: int = Query(default=10, ge=1, le=50)
):
    """Find similar incidents using semantic search."""
    try:
        from ai.semantic_correlator import SemanticCorrelator

        correlator = SemanticCorrelator()
        runbooks_dir = Path(__file__).parent.parent / "runbooks"

        # Load annotations
        count = correlator.load_runbook_annotations(runbooks_dir, verbose=False)

        if count == 0:
            return {
                "status": "ok",
                "similar": [],
                "count": 0,
                "message": "No annotations found"
            }

        # Create query embedding
        query_emb = correlator.embed_incident(
            incident_id="query",
            cause=query,
            fix="",
            service="query"
        )

        if not query_emb:
            raise HTTPException(
                status_code=503,
                detail="Semantic search not available (install sentence-transformers)"
            )

        # Find similar
        similar = correlator.find_similar_incidents(
            query_emb,
            threshold=threshold,
            max_results=max_results
        )

        return {
            "status": "ok",
            "similar": [
                {
                    "incident_id": inc.incident_id,
                    "service": inc.service,
                    "cause": inc.cause,
                    "fix": inc.fix,
                    "similarity": float(score)
                }
                for inc, score in similar
            ],
            "count": len(similar)
        }

    except Exception as e:
        logger.error(f"Error finding similar incidents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai/report")
async def generate_report(
    incident: Dict[str, Any],
    runbook_path: Optional[str] = None,
    provider: str = Query(default="template", enum=["anthropic", "openai", "template"]),
    format: str = Query(default="markdown", enum=["markdown", "json"])
):
    """Generate post-incident report."""
    try:
        from ai.report_generator import IncidentReportGenerator

        # Load runbook if provided
        annotations = None
        if runbook_path:
            runbooks_dir = Path(__file__).parent.parent / "runbooks"
            runbook_file = runbooks_dir / runbook_path

            if runbook_file.exists():
                import yaml
                with open(runbook_file, 'r', encoding='utf-8') as f:
                    runbook = yaml.safe_load(f) or {}
                    annotations = runbook.get('annotations', [])

        generator = IncidentReportGenerator(provider=provider)
        report = generator.generate_report(incident, annotations=annotations)

        if format == "json":
            return {
                "status": "ok",
                "report": report.to_dict()
            }
        else:
            return {
                "status": "ok",
                "report": report.to_markdown(),
                "format": "markdown"
            }

    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Version Control Endpoints
# ============================================================================

@app.get("/api/runbooks/{runbook_path:path}/history")
async def get_runbook_history(
    runbook_path: str,
    limit: int = Query(default=10, ge=1, le=100)
):
    """Get git history for a runbook."""
    try:
        from version_control.git_manager import RunbookVersionControl

        if not _is_git_available():
            return {
                "status": "ok",
                "history": [],
                "message": "Git not available"
            }

        runbooks_dir = Path(__file__).parent.parent
        vcs = RunbookVersionControl(str(runbooks_dir))

        history = vcs.get_runbook_history(runbook_path, limit=limit)

        return {
            "status": "ok",
            "history": history,
            "count": len(history)
        }

    except Exception as e:
        logger.error(f"Error getting runbook history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Dashboard Endpoint
# ============================================================================

@app.get("/dashboard")
async def serve_dashboard():
    """Serve the dashboard HTML file."""
    dashboard_file = Path(__file__).parent.parent / "dashboard" / "index.html"

    if dashboard_file.exists():
        return FileResponse(str(dashboard_file))

    raise HTTPException(status_code=404, detail="Dashboard not found")


# ============================================================================
# Helper Functions
# ============================================================================

def _get_pagerduty_integration():
    """Get PagerDuty integration instance."""
    try:
        from incident_sources.pagerduty import PagerDutyIntegration
        api_key = os.environ.get('PAGERDUTY_API_KEY')
        webhook_secret = os.environ.get('PAGERDUTY_WEBHOOK_SECRET')

        if not api_key:
            return None

        return PagerDutyIntegration(api_key=api_key, webhook_secret=webhook_secret)
    except Exception as e:
        logger.error(f"Error creating PagerDuty integration: {e}")
        return None


def _get_datadog_integration():
    """Get Datadog integration instance."""
    try:
        from incident_sources.datadog import DatadogIntegration
        api_key = os.environ.get('DATADOG_API_KEY')
        app_key = os.environ.get('DATADOG_APP_KEY')
        webhook_secret = os.environ.get('DATADOG_WEBHOOK_SECRET')

        if not api_key or not app_key:
            return None

        return DatadogIntegration(
            api_key=api_key,
            app_key=app_key,
            webhook_secret=webhook_secret
        )
    except Exception as e:
        logger.error(f"Error creating Datadog integration: {e}")
        return None


def _get_alertmanager_integration():
    """Get AlertManager integration instance."""
    try:
        from incident_sources.alertmanager import AlertManagerIntegration
        base_url = os.environ.get('ALERTMANAGER_URL', 'http://localhost:9093')
        webhook_secret = os.environ.get('ALERTMANAGER_WEBHOOK_SECRET')

        return AlertManagerIntegration(
            base_url=base_url,
            webhook_secret=webhook_secret
        )
    except Exception as e:
        logger.error(f"Error creating AlertManager integration: {e}")
        return None


def _get_sentry_integration():
    """Get Sentry integration instance."""
    try:
        from incident_sources.sentry import SentryIntegration
        api_token = os.environ.get('SENTRY_API_TOKEN')
        org_slug = os.environ.get('SENTRY_ORG_SLUG')

        if not api_token:
            return None

        return SentryIntegration(api_token=api_token, org_slug=org_slug)
    except Exception as e:
        logger.error(f"Error creating Sentry integration: {e}")
        return None


def _find_runbook_for_service(service_name: str) -> Optional[str]:
    """Find runbook path for a service."""
    runbooks_dir = Path(__file__).parent.parent / "runbooks"

    if not runbooks_dir.exists():
        return None

    # Try exact match
    service_dir = runbooks_dir / service_name
    runbook_file = service_dir / "runbook.yaml"

    if runbook_file.exists():
        return str(runbook_file.relative_to(runbooks_dir))

    # Try fuzzy match
    for service_dir in runbooks_dir.iterdir():
        if service_dir.is_dir():
            if service_name.lower() in service_dir.name.lower():
                runbook_file = service_dir / "runbook.yaml"
                if runbook_file.exists():
                    return str(runbook_file.relative_to(runbooks_dir))

    return None


def _is_git_available() -> bool:
    """Check if git is available."""
    try:
        from version_control.git_manager import GITPYTHON_AVAILABLE
        return GITPYTHON_AVAILABLE
    except:
        return False


# ============================================================================
# Background Tasks
# ============================================================================

async def broadcast_metrics_updates():
    """Broadcast metrics updates every 30 seconds."""
    while True:
        await asyncio.sleep(30)

        try:
            metrics_data = await get_metrics()
            await manager.broadcast({
                "type": "metrics_update",
                "data": metrics_data,
                "timestamp": datetime.now().isoformat()
            })
            logger.debug("Broadcast metrics update")
        except Exception as e:
            logger.error(f"Error broadcasting metrics: {e}", exc_info=True)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("Starting Living Runbooks API...")
    asyncio.create_task(broadcast_metrics_updates())
    logger.info("Background metrics broadcast started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Living Runbooks API...")


def main():
    """Run the API server."""
    import uvicorn

    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    main()
