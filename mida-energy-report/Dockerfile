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

# Copy s6 service files - be specific to avoid overwriting base image files
COPY rootfs/etc/services.d/mida-report /etc/services.d/mida-report

# Make s6 scripts executable
RUN chmod +x /etc/services.d/mida-report/run \
    && chmod +x /etc/services.d/mida-report/finish

# Set working directory
WORKDIR /app
