# Use Home Assistant base image
ARG BUILD_FROM
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install requirements for add-on
RUN apk add --no-cache \
    python3 \
    py3-pip \
    gcc \
    g++ \
    python3-dev \
    musl-dev \
    linux-headers

# Copy requirements and install Python packages
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

# Install Flask for API
RUN pip3 install --no-cache-dir --break-system-packages flask gunicorn

# Copy application files
WORKDIR /
COPY report_generator/ /app/report_generator/
COPY app_addon.py /app/app.py

# Create startup script
RUN echo '#!/usr/bin/with-contenv bashio' > /run.sh && \
    echo 'bashio::log.info "Starting Mida Energy Report Generator..."' >> /run.sh && \
    echo 'DATA_PATH=$(bashio::config "data_path")' >> /run.sh && \
    echo 'AUTO_EXPORT=$(bashio::config "auto_export_enabled")' >> /run.sh && \
    echo 'EXPORT_INTERVAL=$(bashio::config "export_interval_hours")' >> /run.sh && \
    echo 'mkdir -p "${DATA_PATH}"' >> /run.sh && \
    echo 'mkdir -p /app/reports/generale' >> /run.sh && \
    echo 'export DATA_PATH="${DATA_PATH}"' >> /run.sh && \
    echo 'export AUTO_EXPORT="${AUTO_EXPORT}"' >> /run.sh && \
    echo 'export EXPORT_INTERVAL="${EXPORT_INTERVAL}"' >> /run.sh && \
    echo 'bashio::log.info "Starting API server on port 5000..."' >> /run.sh && \
    echo 'cd /app' >> /run.sh && \
    echo 'exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 300 --access-logfile - app:app' >> /run.sh && \
    chmod +x /run.sh

# Set working directory
WORKDIR /app

CMD ["/run.sh"]
