# Living Runbooks - Docker Configuration
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
COPY slack/requirements.txt /app/slack/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r slack/requirements.txt

# Optional: Install AI dependencies
RUN pip install --no-cache-dir \
    anthropic>=0.18.0 \
    openai>=1.12.0 \
    sentence-transformers>=2.3.1 \
    gitpython>=3.1.42 \
    fastapi>=0.109.0 \
    uvicorn>=0.27.0 \
    websockets>=12.0 || true

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/runbooks /app/logs /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_ENV=production

# Expose ports
# 8000 - FastAPI
# 3000 - Flask Slack webhook
EXPOSE 8000 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command - run FastAPI server
CMD ["python", "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
