# Multi-stage build for optimized production image
FROM python:3.10-slim AS builder

# Install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

# Production stage
FROM python:3.10-slim

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY *.py ./

RUN mkdir -p /app/models && chown -R appuser:appuser /app

USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:5000/health', timeout=5); assert r.status_code == 200" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "4", "--log-level", "info"]
