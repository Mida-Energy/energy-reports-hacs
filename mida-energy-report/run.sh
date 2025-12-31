#!/bin/bash
set -e
# ==============================================================================
# Start Mida Energy Report Generator Add-on
# ==============================================================================

echo "[INFO] Starting Mida Energy Report Generator..."

# Read configuration from add-on options (fallback to defaults if not set)
DATA_PATH="${DATA_PATH:-/config/mida_energy/data}"
AUTO_EXPORT="${AUTO_EXPORT:-true}"
EXPORT_INTERVAL="${EXPORT_INTERVAL:-1}"

echo "[INFO] Data path: ${DATA_PATH}"
echo "[INFO] Auto export: ${AUTO_EXPORT}"
echo "[INFO] Export interval: ${EXPORT_INTERVAL} hours"

# Create data directory if it doesn't exist
mkdir -p "${DATA_PATH}"
mkdir -p /app/reports/generale

# Set environment variables for the app
export DATA_PATH="${DATA_PATH}"
export AUTO_EXPORT="${AUTO_EXPORT}"
export EXPORT_INTERVAL="${EXPORT_INTERVAL}"

echo "[INFO] Starting API server on port 5000..."

# Start the Flask API server
cd /app
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 300 --access-logfile - app:app
