FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCFUSION_TASKS_ROOT=/var/docfusion/tasks

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-server.txt /app/requirements-server.txt
RUN pip install --no-cache-dir -r /app/requirements-server.txt

COPY server_toolkit /app/server_toolkit
COPY docker-entrypoint.sh /usr/local/bin/docfusion-server
RUN chmod +x /usr/local/bin/docfusion-server \
    && mkdir -p /var/docfusion/tasks

EXPOSE 8010

ENTRYPOINT ["docfusion-server"]
