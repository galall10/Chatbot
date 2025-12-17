# Multi-stage Docker build for production-ready chatbot service

# Stage 1: Base Python image with dependencies
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user
RUN useradd -m -u 1000 chatbot && \
    mkdir -p /app && \
    chown -R chatbot:chatbot /app

WORKDIR /app

# Stage 2: Dependencies
FROM base as dependencies

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Application
FROM dependencies as application

# Copy application code
COPY --chown=chatbot:chatbot src/ ./src/

# Switch to non-root user
USER chatbot

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5.0)" || exit 1

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
