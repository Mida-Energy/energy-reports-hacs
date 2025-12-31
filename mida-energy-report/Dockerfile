# Use Alpine base image
FROM python:3.11-alpine

# Set shell
SHELL ["/bin/sh", "-o", "pipefail", "-c"]

# Install requirements for add-on
RUN apk add --no-cache \
    gcc \
    g++ \
    python3-dev \
    musl-dev \
    linux-headers \
    bash \
    jq \
    curl

# Copy requirements and install Python packages
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Install Flask for API
RUN pip3 install --no-cache-dir flask gunicorn

# Copy application files
WORKDIR /app
COPY report_generator/ /app/report_generator/
COPY app_addon.py /app/app.py

# Create entrypoint script
RUN echo '#!/bin/bash' > /entrypoint.sh && \
    echo 'set -e' >> /entrypoint.sh && \
    echo 'CONFIG_PATH=/data/options.json' >> /entrypoint.sh && \
    echo 'export DATA_PATH=$(jq -r ".data_path // \"/config/mida_energy/data\"" $CONFIG_PATH)' >> /entrypoint.sh && \
    echo 'export AUTO_EXPORT=$(jq -r ".auto_export_enabled // true" $CONFIG_PATH)' >> /entrypoint.sh && \
    echo 'export EXPORT_INTERVAL=$(jq -r ".export_interval_hours // 1" $CONFIG_PATH)' >> /entrypoint.sh && \
    echo 'mkdir -p "${DATA_PATH}"' >> /entrypoint.sh && \
    echo 'mkdir -p /app/reports/generale' >> /entrypoint.sh && \
    echo 'echo "Starting Mida Energy Report Generator..."' >> /entrypoint.sh && \
    echo 'echo "Data path: ${DATA_PATH}"' >> /entrypoint.sh && \
    echo 'cd /app' >> /entrypoint.sh && \
    echo 'exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 300 --access-logfile - app:app' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["/entrypoint.sh"]
