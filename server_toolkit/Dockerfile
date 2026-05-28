FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCFUSION_TASKS_ROOT=/var/docfusion/tasks

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice \
        pandoc \
        curl \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-server.txt /app/requirements-server.txt
RUN pip install --no-cache-dir -r /app/requirements-server.txt

COPY server_toolkit /app/server_toolkit
COPY docker-entrypoint.sh /usr/local/bin/docfusion-server
RUN chmod +x /usr/local/bin/docfusion-server \
    && mkdir -p /var/docfusion/tasks

EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://127.0.0.1:8010/healthz || exit 1

ENTRYPOINT ["docfusion-server"]
