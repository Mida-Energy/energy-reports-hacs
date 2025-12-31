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

# Create entrypoint script with full permissions
COPY --chmod=0777 <<EOF /entrypoint.sh
#!/bin/bash
set -e
CONFIG_PATH=/data/options.json
export DATA_PATH=\$(jq -r ".data_path // \"/config/mida_energy/data\"" \$CONFIG_PATH)
export AUTO_EXPORT=\$(jq -r ".auto_export_enabled // true" \$CONFIG_PATH)
export EXPORT_INTERVAL=\$(jq -r ".export_interval_hours // 1" \$CONFIG_PATH)
mkdir -p "\${DATA_PATH}"
mkdir -p /app/reports/generale
echo "Starting Mida Energy Report Generator..."
echo "Data path: \${DATA_PATH}"
cd /app
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 300 --access-logfile - app:app
EOF

RUN chmod -R 777 /entrypoint.sh /app

EXPOSE 5000

CMD ["/bin/bash", "/entrypoint.sh"]
