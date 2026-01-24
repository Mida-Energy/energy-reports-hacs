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

RUN chmod -R 777 /app

EXPOSE 5000

ENV PYTHONUNBUFFERED=1

CMD ["/bin/bash", "-c", "CONFIG_PATH=/data/options.json; if [ -f \"${CONFIG_PATH}\" ]; then export DATA_PATH=$(jq -r '.data_path // \"/data/energy_reports/data\"' \"${CONFIG_PATH}\"); export AUTO_EXPORT=$(jq -r '.auto_export_enabled // true' \"${CONFIG_PATH}\"); export EXPORT_INTERVAL=$(jq -r '.export_interval_hours // 1' \"${CONFIG_PATH}\"); else export DATA_PATH=${DATA_PATH:-/data/energy_reports/data}; export AUTO_EXPORT=${AUTO_EXPORT:-true}; export EXPORT_INTERVAL=${EXPORT_INTERVAL:-1}; fi; mkdir -p \"${DATA_PATH}\" || true; mkdir -p /app/reports/generale; echo 'Starting Energy Reports...'; echo \"Data path: ${DATA_PATH}\"; cd /app; exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 300 --access-logfile - --error-logfile - --log-level info --capture-output app:app"]
