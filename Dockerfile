FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Create data directories (will be used for local storage in dev)
RUN mkdir -p data/uploads

# Environment variables (override at runtime)
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV LOG_FORMAT=json
ENV EXPOSE_ERROR_DETAILS=false
ENV TEMP_DIR=/tmp/call-analytics/tmp
ENV UPLOAD_DIR=/tmp/call-analytics/uploads

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/live')" || exit 1

EXPOSE 7860

# Run with single worker (HF Spaces is stateless)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
