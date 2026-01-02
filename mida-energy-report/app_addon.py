"""
Mida Energy Report Generator - Home Assistant Add-on version
Integrated API with automatic Shelly data collection
"""
from flask import Flask, jsonify, send_file, request
from pathlib import Path
import sys
import logging
import json
from datetime import datetime, timedelta
import os
import requests
import csv
import threading
import time
from io import StringIO

# Add report generator to path
sys.path.insert(0, str(Path(__file__).parent / 'report_generator' / 'src'))

from main import ShellyEnergyReport

app = Flask(__name__)

# Ingress support for Home Assistant
@app.before_request
def handle_ingress():
    """Handle Home Assistant Ingress path prefix and log requests"""
    # Log request (no flush to avoid JSON corruption)
    logger.info(f">>> REQUEST: {request.method} {request.path}")
    
    # Handle Ingress path
    ingress_path = request.headers.get('X-Ingress-Path', '')
    if ingress_path:
        request.environ['SCRIPT_NAME'] = ingress_path

# Configure logging for Gunicorn compatibility
if __name__ != '__main__':
    # Running under Gunicorn
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    logger = app.logger
else:
    # Running standalone
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger(__name__)

# Get paths - always use /share for persistence
DATA_PATH = Path('/share/energy_reports/data')  # Always use /share for data persistence
TEMP_OUTPUT_PATH = Path('/share/energy_reports/output')  # For charts, temp files
PDF_OUTPUT_PATH = Path('/share/energy_reports/pdfs')  # For final PDFs
TEMP_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
PDF_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
DATA_PATH.mkdir(parents=True, exist_ok=True)

# Home Assistant API configuration
SUPERVISOR_TOKEN = os.getenv('SUPERVISOR_TOKEN', '')
HA_API_URL = "http://supervisor/core/api"
HEADERS = {
    "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
    "Content-Type": "application/json"
}

# Data collection thread
collection_thread = None
stop_collection = False


def get_history_from_ha(entity_ids, start_time=None, end_time=None):
    """Get historical data from Home Assistant for specified entities"""
    try:
        # Default to last 7 days if no time range specified
        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(days=7)
        
        # Format timestamps for HA API
        start_str = start_time.strftime('%Y-%m-%dT%H:%M:%S')
        end_str = end_time.strftime('%Y-%m-%dT%H:%M:%S')
        
        logger.info(f"Fetching history from {start_str} to {end_str}")
        logger.info(f"For {len(entity_ids)} entities")
        
        # HA History API endpoint
        url = f"{HA_API_URL}/history/period/{start_str}"
        params = {
            'filter_entity_id': ','.join(entity_ids),
            'end_time': end_str
        }
        
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Failed to get history: {response.status_code}")
            return None
        
        history_data = response.json()
        logger.info(f"Retrieved history data for {len(history_data)} entities")
        
        return history_data
        
    except Exception as e:
        logger.error(f"Error getting history from HA: {e}", exc_info=True)
        return None


def convert_history_to_csv(history_data, output_file):
    """Convert HA history data to CSV format"""
    try:
        logger.info(f"Converting history data to CSV: {output_file}")
        
        all_rows = []
        
        for entity_history in history_data:
            if not entity_history:
                continue
                
            for state in entity_history:
                try:
                    timestamp = datetime.fromisoformat(state['last_changed'].replace('Z', '+00:00'))
                    
                    # Try to get numeric value
                    value = 0.0
                    try:
                        value = float(state['state'])
                    except (ValueError, TypeError):
                        continue
                    
                    entity_id = state['entity_id']
                    friendly_name = state.get('attributes', {}).get('friendly_name', entity_id)
                    
                    all_rows.append({
                        'timestamp': int(timestamp.timestamp()),
                        'entity_id': entity_id,
                        'friendly_name': friendly_name,
                        'value': value
                    })
                except Exception as e:
                    logger.debug(f"Error processing state: {e}")
                    continue
        
        if not all_rows:
            logger.warning("No valid data points found in history")
            return False
        
        # Sort by timestamp
        all_rows.sort(key=lambda x: x['timestamp'])
        
        # Write to CSV with entity_id - NO AGGREGATION, keep per-device data
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', newline='') as f:
            fieldnames = ['timestamp', 'entity_id', 'friendly_name', 'total_act_energy', 'max_act_power', 'avg_voltage', 'avg_current']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in all_rows:
                # Calculate metrics per device
                power = row['value']
                voltage = 230.0  # Default voltage
                current = power / voltage if voltage > 0 else 0
                
                writer.writerow({
                    'timestamp': row['timestamp'],
                    'entity_id': row['entity_id'],
                    'friendly_name': row['friendly_name'],
                    'total_act_energy': power,
                    'max_act_power': power,
                    'avg_voltage': voltage,
                    'avg_current': current
                })
        
        logger.info(f"[SUCCESS] Wrote {len(all_rows)} data points to {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"Error converting history to CSV: {e}", exc_info=True)
        return False


def filter_csv_by_selected_entities(input_csv, output_csv, selected_entity_ids):
    """Filter CSV data to include only selected entities"""
    try:
        logger.info(f"Filtering CSV for {len(selected_entity_ids)} selected entities")
        
        if not input_csv.exists():
            logger.error(f"Input CSV not found: {input_csv}")
            return False
        
        # For now, since we're aggregating all data, we'll just copy the file
        # In future, if we track entity_id in CSV, we can filter here
        import shutil
        shutil.copy2(input_csv, output_csv)
        
        logger.info(f"[SUCCESS] Filtered CSV saved to {output_csv}")
        return True
        
    except Exception as e:
        logger.error(f"Error filtering CSV: {e}", exc_info=True)
        return False


class ShellyDataCollector:
    """Collects data from Shelly devices via Home Assistant API"""
    
    def __init__(self, entity_ids, interval_seconds=300):
        self.entity_ids = entity_ids
        self.interval = interval_seconds
        self.csv_file = DATA_PATH / "all.csv"
        self.running = False
        
    def get_entity_state(self, entity_id):
        """Get entity state from Home Assistant"""
        try:
            url = f"{HA_API_URL}/states/{entity_id}"
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get state for {entity_id}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting state for {entity_id}: {e}")
            return None
    
    def collect_and_save(self):
        """Collect data from all entities and save to CSV"""
        try:
            logger.info("=" * 60)
            logger.info("Starting data collection from Shelly devices...")
            logger.info("=" * 60)
            
            # Collect data from all entities
            raw_data = {}
            
            for entity_id in self.entity_ids:
                logger.info(f"Collecting data from: {entity_id}")
                state_data = self.get_entity_state(entity_id)
                if state_data:
                    # Extract friendly name and value
                    friendly_name = state_data.get('attributes', {}).get('friendly_name', entity_id)
                    value = state_data.get('state', '0')
                    
                    # Try to convert to float
                    try:
                        value = float(value)
                        logger.info(f"  [OK] {friendly_name}: {value}")
                    except:
                        value = 0.0
                        logger.warning(f"  [WARN] {friendly_name}: Cannot convert to float, using 0.0")
                    
                    raw_data[friendly_name] = value
                else:
                    logger.error(f"  [FAIL] Failed to get data from {entity_id}")
            
            # Map Shelly data to standard column names expected by report generator
            # Potenza = Active Power (W), Potenza apparente = Apparent Power (VA)
            # We'll sum both meters and calculate averages
            data_row = {
                'timestamp': int(datetime.now().timestamp()),
                'total_act_energy': 0,  # Will be calculated from power readings
                'max_act_power': 0,
                'avg_voltage': 230.0,  # Default voltage (Shelly EM doesn't provide this)
                'avg_current': 0
            }
            
            # Extract power values (Potenza = Active Power in Watts)
            total_power = 0
            power_count = 0
            for key, value in raw_data.items():
                if 'potenza' in key.lower() and 'apparente' not in key.lower() and 'fattore' not in key.lower():
                    total_power += value
                    power_count += 1
            
            # Set power and estimate current
            data_row['max_act_power'] = total_power
            if data_row['avg_voltage'] > 0:
                data_row['avg_current'] = total_power / data_row['avg_voltage']
            
            # Energy: convert power (W) to energy (Wh) assuming 1-hour interval
            # This will accumulate over time
            data_row['total_act_energy'] = total_power
            
            # Check if file exists to determine if we need headers
            file_exists = self.csv_file.exists()
            
            # Write to CSV
            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=data_row.keys())
                if not file_exists:
                    writer.writeheader()
                    logger.info(f"Created new CSV file: {self.csv_file}")
                writer.writerow(data_row)
            
            logger.info("=" * 60)
            logger.info(f"[SUCCESS] Data collected successfully: {len(raw_data)} entities -> {len(data_row)-1} standard columns saved to {self.csv_file}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"[ERROR] Error collecting data: {e}", exc_info=True)
            logger.error("=" * 60)
    
    def start_collection(self):
        """Start background data collection"""
        self.running = True
        logger.info("=" * 60)
        logger.info("BACKGROUND DATA COLLECTION STARTED")
        logger.info(f"Collection interval: {self.interval} seconds ({self.interval/3600} hours)")
        logger.info(f"Monitoring entities: {self.entity_ids}")
        logger.info(f"CSV output: {self.csv_file}")
        logger.info("=" * 60)
        
        while self.running and not stop_collection:
            self.collect_and_save()
            logger.info(f"Next collection in {self.interval} seconds...")
            time.sleep(self.interval)
        
        logger.info("=" * 60)
        logger.info("Data collection stopped")
        logger.info("=" * 60)


def start_background_collection():
    """Start background data collection thread (only in first worker)"""
    global collection_thread
    
    # Only start collection in the first worker to avoid duplicates
    # Check if we're running under Gunicorn with multiple workers
    if collection_thread is not None:
        logger.info("Background collection already initialized, skipping...")
        return
    
    logger.info("=" * 60)
    logger.info("Initializing background data collection...")
    logger.info("=" * 60)
    
    # Read configuration
    auto_export = os.getenv('AUTO_EXPORT', 'true').lower() == 'true'
    interval_hours = int(os.getenv('EXPORT_INTERVAL', '1'))
    
    logger.info(f"Auto-export enabled: {auto_export}")
    logger.info(f"Export interval: {interval_hours} hours")
    
    # Check for selected entities first
    config_file = DATA_PATH / 'selected_entities.json'
    entity_ids = []
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                entity_ids = json.load(f)
            logger.info(f"Loaded {len(entity_ids)} selected entities from config")
        except Exception as e:
            logger.error(f"Error loading selected entities: {e}")
    
    # If no selection, discover all
    if not entity_ids:
        logger.info("No entity selection found, discovering all Shelly devices...")
        discovered = discover_shelly_entities()
        entity_ids = [e['entity_id'] if isinstance(e, dict) else e for e in discovered]
    
    if entity_ids and auto_export:
        collector = ShellyDataCollector(entity_ids, interval_seconds=interval_hours * 3600)
        collection_thread = threading.Thread(target=collector.start_collection, daemon=True)
        collection_thread.start()
        logger.info("=" * 60)
        logger.info("[SUCCESS] Background data collection thread started successfully")
        logger.info("=" * 60)
    else:
        logger.warning("=" * 60)
        if not auto_export:
            logger.warning("[WARN] Auto-collection is DISABLED in configuration")
        else:
            logger.warning("[WARN] No Shelly entities found - collection cannot start")
        logger.warning("=" * 60)


def discover_shelly_entities():
    """Discover Shelly power/energy entities from Home Assistant"""
    try:
        logger.info("Discovering Shelly entities from Home Assistant...")
        
        url = f"{HA_API_URL}/states"
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Failed to get states from HA API: {response.status_code}")
            return []
        
        all_states = response.json()
        shelly_entities = []
        
        logger.info(f"Total entities in HA: {len(all_states)}")
        
        # Find Shelly power sensors (we'll integrate power to get energy)
        for state in all_states:
            entity_id = state.get('entity_id', '')
            attributes = state.get('attributes', {})
            friendly_name = attributes.get('friendly_name', entity_id)
            device_class = attributes.get('device_class', '')
            unit = attributes.get('unit_of_measurement', '')
            
            if 'shelly' in entity_id.lower() and entity_id.startswith('sensor.'):
                # Include power sensors (W) or energy sensors (kWh)
                # Exclude apparent_power (VA) and power_factor
                if device_class == 'power' or device_class == 'energy' or unit in ['W', 'kW', 'kWh', 'Wh']:
                    logger.info(f"[INFO] Found usable sensor: {entity_id}")
                    logger.info(f"[INFO]   Name: {friendly_name}")
                    logger.info(f"[INFO]   Class: {device_class}")
                    logger.info(f"[INFO]   Unit: {unit}")
                    
                    shelly_entities.append({
                        'entity_id': entity_id,
                        'friendly_name': friendly_name
                    })
        
        logger.info(f"Discovery complete: {len(shelly_entities)} Shelly entities found")
        return shelly_entities
        
    except Exception as e:
        logger.error(f"Error discovering Shelly entities: {e}")
        return []


@app.route('/')
def home():
    """Home page with integrated UI"""
    logger.info("=" * 60)
    logger.info("HOME PAGE ACCESSED")
    logger.info("=" * 60)
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Energy Reports</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500&display=swap" rel="stylesheet">
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Oxygen, Ubuntu, sans-serif;
                background: #111111;
                color: #e1e1e1;
                padding: 20px;
                min-height: 100vh;
            }
            .container { 
                max-width: 1000px; 
                margin: 0 auto;
            }
            .header {
                background: #1c1c1c;
                padding: 24px;
                border-radius: 8px;
                margin-bottom: 24px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            h1 { 
                color: #e1e1e1;
                font-size: 28px;
                font-weight: 400;
                margin-bottom: 8px;
                display: flex;
                align-items: center;
            }
            h1 .material-icons {
                margin-right: 12px;
                font-size: 32px;
                color: #03a9f4;
            }
            .subtitle {
                color: #9b9b9b;
                font-size: 14px;
                font-weight: 300;
            }
            .card { 
                background: #1c1c1c;
                padding: 24px;
                border-radius: 8px;
                margin-bottom: 16px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            .card-title {
                color: #e1e1e1;
                font-size: 16px;
                font-weight: 500;
                margin-bottom: 16px;
                display: flex;
                align-items: center;
            }
            .card-title .material-icons {
                margin-right: 8px;
                font-size: 20px;
                color: #03a9f4;
            }
            .info-item {
                padding: 8px 0;
                border-bottom: 1px solid #2a2a2a;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .info-item:last-child { border-bottom: none; }
            .info-label {
                color: #9b9b9b;
                font-size: 14px;
            }
            .info-value {
                color: #e1e1e1;
                font-size: 14px;
                font-family: monospace;
            }
            .button-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 16px;
                margin-bottom: 16px;
            }
            .btn { 
                background: #03a9f4;
                color: white;
                border: none;
                padding: 16px 24px;
                font-size: 14px;
                font-weight: 500;
                border-radius: 4px;
                cursor: pointer;
                transition: all 0.2s;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 2px 4px rgba(3, 169, 244, 0.3);
            }
            .btn .material-icons {
                margin-right: 8px;
                font-size: 20px;
            }
            .btn:hover { 
                background: #0288d1;
                box-shadow: 0 4px 8px rgba(3, 169, 244, 0.4);
                transform: translateY(-1px);
            }
            .btn:disabled { 
                background: #3a3a3a;
                color: #666;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }
            .btn-success { 
                background: #4caf50;
                box-shadow: 0 2px 4px rgba(76, 175, 80, 0.3);
            }
            .btn-success:hover { 
                background: #388e3c;
                box-shadow: 0 4px 8px rgba(76, 175, 80, 0.4);
            }
            .status { 
                padding: 16px;
                margin: 16px 0;
                border-radius: 4px;
                display: none;
                border-left: 4px solid;
            }
            .status.success { 
                background: rgba(76, 175, 80, 0.1);
                color: #81c784;
                border-color: #4caf50;
            }
            .status.error { 
                background: rgba(244, 67, 54, 0.1);
                color: #e57373;
                border-color: #f44336;
            }
            .status.info { 
                background: rgba(3, 169, 244, 0.1);
                color: #4fc3f7;
                border-color: #03a9f4;
            }
            .spinner { 
                border: 2px solid rgba(255,255,255,0.3);
                border-top: 2px solid white;
                border-radius: 50%;
                width: 16px;
                height: 16px;
                animation: spin 0.8s linear infinite;
                display: inline-block;
                vertical-align: middle;
                margin-left: 8px;
                flex-shrink: 0;
            }
            @keyframes spin { 
                0% { transform: rotate(0deg); } 
                100% { transform: rotate(360deg); } 
            }
            .badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 500;
                background: rgba(3, 169, 244, 0.2);
                color: #03a9f4;
            }
            .badge.success {
                background: rgba(76, 175, 80, 0.2);
                color: #4caf50;
            }
            .device-item {
                padding: 12px;
                border-bottom: 1px solid #2a2a2a;
                display: flex;
                align-items: center;
                cursor: pointer;
                transition: background 0.2s;
            }
            .device-item:hover {
                background: rgba(255, 255, 255, 0.05);
            }
            .device-item:last-child {
                border-bottom: none;
            }
            .device-checkbox {
                width: 20px;
                height: 20px;
                margin-right: 12px;
                cursor: pointer;
                accent-color: #03a9f4;
            }
            .device-info {
                flex: 1;
            }
            .device-name {
                color: #e1e1e1;
                font-size: 14px;
                font-weight: 500;
            }
            .device-id {
                color: #9b9b9b;
                font-size: 12px;
                margin-top: 2px;
                font-family: monospace;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1><span class="material-icons">assessment</span>Energy Reports</h1>
                <p class="subtitle">Generate and manage your energy consumption reports</p>
            </div>
            
            <div class="card">
                <div class="card-title">
                    <span class="material-icons">settings</span>
                    Configuration
                </div>
                <div class="info-item">
                    <span class="info-label">Data Path</span>
                    <span class="info-value">""" + str(DATA_PATH) + """</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Reports Path</span>
                    <span class="info-value">""" + str(PDF_OUTPUT_PATH) + """</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Time Range (days)</span>
                    <select id="timeRange" style="background: #2a2a2a; color: #e1e1e1; border: 1px solid #444; padding: 8px; border-radius: 4px; font-size: 14px;">
                        <option value="1">Last 24 hours</option>
                        <option value="7" selected>Last 7 days</option>
                        <option value="30">Last 30 days</option>
                        <option value="90">Last 90 days</option>
                    </select>
                </div>
            </div>

            <div class="card">
                <div class="card-title">
                    <span class="material-icons">devices</span>
                    Device Selection & Report Generation
                </div>
                <p style="color: #9b9b9b; font-size: 14px; margin-bottom: 16px;">
                    Select devices and generate their energy reports. The system will automatically collect the latest data from Home Assistant and generate PDF reports.
                </p>
                
                <div style="margin-bottom: 16px;">
                    <label style="display: block; color: #9b9b9b; font-size: 13px; margin-bottom: 8px;">
                        <span class="material-icons" style="font-size: 16px; vertical-align: middle;">date_range</span>
                        Data Collection Period
                    </label>
                    <select id="timeRange" style="width: 100%; background: #2a2a2a; color: #e1e1e1; border: 1px solid #444; padding: 10px; border-radius: 4px; font-size: 14px;">
                        <option value="7" selected>Last 7 days</option>
                        <option value="14">Last 14 days</option>
                        <option value="30">Last 30 days</option>
                        <option value="90">Last 90 days</option>
                    </select>
                </div>
                
                <div style="margin-bottom: 16px;">
                    <label style="display: block; color: #9b9b9b; font-size: 13px; margin-bottom: 8px;">Select Devices</label>
                    <div id="deviceList" style="max-height: 300px; overflow-y: auto; border: 1px solid #444; border-radius: 4px; padding: 8px;">
                        <div style="text-align: center; padding: 20px; color: #9b9b9b;">
                            <span class="spinner"></span> Loading devices...
                        </div>
                    </div>
                </div>
                
                <button class="btn" onclick="generateReportComplete()" style="width: 100%; padding: 14px; font-size: 16px; background: #4CAF50;">
                    <span class="material-icons" style="vertical-align: middle; margin-right: 8px;">play_arrow</span>
                    Collect Data & Generate Report
                </button>
                
                <div id="status" class="status" style="margin-top: 12px;"></div>
            </div>

            <div class="card">
                <div class="card-title">
                    <span class="material-icons">schedule</span>
                    Auto-Update Configuration
                </div>
                <p style="color: #9b9b9b; font-size: 14px; margin-bottom: 16px;">
                    Automatically collect data and generate reports at regular intervals.
                </p>
                <div class="info-item" style="border: none; padding: 12px 0;">
                    <label style="display: flex; align-items: center; cursor: pointer;">
                        <input type="checkbox" id="autoUpdateEnabled" onchange="saveAutoUpdateConfig()" style="width: 20px; height: 20px; margin-right: 12px; cursor: pointer;">
                        <span style="font-size: 14px;">Enable automatic updates</span>
                    </label>
                </div>
                <div class="info-item" style="border: none; padding: 12px 0;">
                    <span class="info-label">Update Interval</span>
                    <select id="autoUpdateInterval" onchange="saveAutoUpdateConfig()" style="background: #2a2a2a; color: #e1e1e1; border: 1px solid #444; padding: 8px; border-radius: 4px; font-size: 14px;">
                        <option value="1">Every hour</option>
                        <option value="6">Every 6 hours</option>
                        <option value="12">Every 12 hours</option>
                        <option value="24" selected>Daily</option>
                        <option value="168">Weekly</option>
                    </select>
                </div>
            </div>

            <div class="card">
                <div class="card-title">
                    <span class="material-icons">history</span>
                    Reports History
                </div>
                <p style="color: #9b9b9b; font-size: 14px; margin-bottom: 16px;">
                    View and download previously generated reports.
                </p>
                <div id="reportsList" style="max-height: 400px; overflow-y: auto;">
                    <div style="text-align: center; padding: 20px; color: #9b9b9b;">
                        <span class="spinner"></span> Loading reports...
                    </div>
                </div>
            </div>
        </div>
        <script>
            let availableEntities = [];
            let selectedEntities = [];
            
            // Load devices on page load
            loadDevices();
            loadAutoUpdateConfig();
            loadReports();
            
            function showStatus(message, type) {
                const statusDiv = document.getElementById('status');
                statusDiv.className = 'status ' + type;
                statusDiv.innerHTML = message;
                statusDiv.style.display = 'block';
                
                // Only auto-hide success messages, keep info and error messages visible
                if (type === 'success') {
                    setTimeout(() => {
                        statusDiv.style.display = 'none';
                    }, 5000);
                }
            }
            
            function generateReportComplete() {
                const btn = event.target;
                const originalHTML = btn.innerHTML;
                const days = document.getElementById('timeRange').value;
                
                btn.disabled = true;
                btn.innerHTML = '<span class="material-icons" style="margin-right: 8px;">hourglass_empty</span><span>Processing...</span><span class="spinner"></span>';
                
                // Clear any previous status message
                document.getElementById('status').style.display = 'none';
                
                // Step 1: Collect data
                showStatus(`<strong>Step 1/2:</strong> Fetching data from Home Assistant (last ${days} days)...`, 'info');
                
                fetch('collect-data', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ days: parseInt(days) })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        // Step 2: Generate report
                        showStatus('<strong>Step 2/2:</strong> Generating PDF report... Please wait.', 'info');
                        
                        return fetch('generate', { method: 'POST' })
                            .then(response => response.json())
                            .then(genData => {
                                btn.disabled = false;
                                btn.innerHTML = originalHTML;
                                document.getElementById('status').style.display = 'none';
                                
                                if (genData.status === 'success') {
                                    showStatus('<strong>Success!</strong> Report generated successfully (' + genData.pdf_size_kb + ' KB). Check Reports History below.', 'success');
                                    loadReports();
                                } else {
                                    showStatus('<strong>Error:</strong> ' + genData.message, 'error');
                                }
                            });
                    } else {
                        btn.disabled = false;
                        btn.innerHTML = originalHTML;
                        document.getElementById('status').style.display = 'none';
                        showStatus('<strong>Error:</strong> ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    btn.disabled = false;
                    btn.innerHTML = originalHTML;
                    document.getElementById('status').style.display = 'none';
                    showStatus('<strong>Network Error:</strong> ' + error, 'error');
                });
            }
            
            function generateReportComplete() {
                const btn = event.target;
                const originalHTML = btn.innerHTML;
                const days = document.getElementById('timeRange').value;
                
                btn.disabled = true;
                btn.innerHTML = '<span class="material-icons" style="margin-right: 8px;">hourglass_empty</span><span>Processing...</span><span class="spinner"></span>';
                
                // Clear any previous status message
                document.getElementById('status').style.display = 'none';
                
                // Step 1: Collect data
                showStatus(`<strong>Step 1/2:</strong> Fetching data from Home Assistant (last ${days} days)...`, 'info');
                
                fetch('collect-data', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ days: parseInt(days) })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        // Step 2: Generate report
                        showStatus('<strong>Step 2/2:</strong> Generating PDF report... Please wait.', 'info');
                        
                        return fetch('generate', { method: 'POST' })
                            .then(response => response.json())
                            .then(genData => {
                                btn.disabled = false;
                                btn.innerHTML = originalHTML;
                                document.getElementById('status').style.display = 'none';
                                
                                if (genData.status === 'success') {
                                    showStatus('<strong>Success!</strong> Report generated successfully (' + genData.pdf_size_kb + ' KB). Check Reports History below.', 'success');
                                    loadReports();
                                } else {
                                    showStatus('<strong>Error:</strong> ' + genData.message, 'error');
                                }
                            });
                    } else {
                        btn.disabled = false;
                        btn.innerHTML = originalHTML;
                        document.getElementById('status').style.display = 'none';
                        showStatus('<strong>Error:</strong> ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    btn.disabled = false;
                    btn.innerHTML = originalHTML;
                    document.getElementById('status').style.display = 'none';
                    showStatus('<strong>Network Error:</strong> ' + error, 'error');
                });
            }
            
            function loadDevices() {
                fetch('api/entities')
                    .then(response => {
                        console.log('Response status:', response.status);
                        console.log('Response headers:', response.headers);
                        
                        // Check HTTP status before parsing
                        if (!response.ok) {
                            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                        }
                        
                        return response.text();
                    })
                    .then(text => {
                        console.log('Raw response:', text);
                        const data = JSON.parse(text);
                        if (data.status === 'success') {
                            availableEntities = data.entities;
                            selectedEntities = data.selected || [];
                            renderDeviceList();
                        } else {
                            document.getElementById('deviceList').innerHTML = 
                                '<div style="text-align: center; padding: 20px; color: #e57373;">Error: ' + (data.message || 'Unknown error') + '</div>';
                        }
                    })
                    .catch(error => {
                        console.error('Failed to load devices:', error);
                        document.getElementById('deviceList').innerHTML = 
                            '<div style="text-align: center; padding: 20px; color: #e57373;">Failed to load devices: ' + error.message + '</div>';
                    });
            }
            
            function renderDeviceList() {
                const container = document.getElementById('deviceList');
                if (availableEntities.length === 0) {
                    container.innerHTML = '<div style="text-align: center; padding: 20px; color: #9b9b9b;">No Shelly devices found</div>';
                    return;
                }
                
                container.innerHTML = '';
                availableEntities.forEach(entity => {
                    const isSelected = selectedEntities.includes(entity.entity_id);
                    const item = document.createElement('div');
                    item.className = 'device-item';
                    item.onclick = () => toggleDevice(entity.entity_id);
                    
                    item.innerHTML = `
                        <input type="checkbox" class="device-checkbox" ${isSelected ? 'checked' : ''} 
                               onclick="event.stopPropagation(); toggleDevice('${entity.entity_id}')">
                        <div class="device-info">
                            <div class="device-name">${entity.friendly_name}</div>
                            <div class="device-id">${entity.entity_id}</div>
                        </div>
                    `;
                    container.appendChild(item);
                });
            }
            
            function toggleDevice(entityId) {
                const index = selectedEntities.indexOf(entityId);
                if (index > -1) {
                    selectedEntities.splice(index, 1);
                } else {
                    selectedEntities.push(entityId);
                }
                renderDeviceList();
                
                // Auto-save selection
                saveDeviceSelection();
            }
            
            function saveDeviceSelection() {
                // Allow empty selection (will be validated on collect/generate)
                fetch('api/entities/select', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ entity_ids: selectedEntities })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        showStatus('<strong>Success!</strong> Saved ' + selectedEntities.length + ' devices for report generation.', 'success');
                    } else {
                        showStatus('<strong>Error:</strong> ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    showStatus('<strong>Error:</strong> Failed to save selection', 'error');
                });
            }
            
            function loadAutoUpdateConfig() {
                fetch('api/auto-update/config')
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            document.getElementById('autoUpdateEnabled').checked = data.config.enabled;
                            document.getElementById('autoUpdateInterval').value = data.config.interval_hours;
                        }
                    })
                    .catch(error => console.error('Failed to load auto-update config:', error));
            }
            
            function saveAutoUpdateConfig() {
                const enabled = document.getElementById('autoUpdateEnabled').checked;
                const interval = parseInt(document.getElementById('autoUpdateInterval').value);
                
                fetch('api/auto-update/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: enabled, interval_hours: interval })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        showStatus('<strong>Success!</strong> Auto-update configuration saved.', 'success');
                    } else {
                        showStatus('<strong>Error:</strong> ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    showStatus('<strong>Error:</strong> Failed to save configuration', 'error');
                });
            }
            
            function loadReports() {
                fetch('api/reports')
                    .then(response => response.json())
                    .then(data => {
                        const container = document.getElementById('reportsList');
                        
                        if (data.status === 'success' && data.reports.length > 0) {
                            container.innerHTML = '';
                            
                            data.reports.forEach(report => {
                                const item = document.createElement('div');
                                item.className = 'device-item';
                                item.style.cursor = 'default';
                                item.style.display = 'flex';
                                item.style.alignItems = 'center';
                                item.style.justifyContent = 'space-between';
                                
                                item.innerHTML = `
                                    <div class="device-info" style="flex: 1; min-width: 0;">
                                        <div class="device-name" style="display: flex; align-items: center; gap: 8px;">
                                            <span class="material-icons" style="font-size: 20px; color: #4CAF50;">description</span>
                                            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${report.filename}</span>
                                        </div>
                                        <div class="device-id" style="display: flex; gap: 16px; margin-top: 4px;">
                                            <span><span class="material-icons" style="font-size: 14px; vertical-align: middle;">schedule</span> ${report.created}</span>
                                            <span><span class="material-icons" style="font-size: 14px; vertical-align: middle;">folder</span> ${report.size_kb} KB</span>
                                        </div>
                                    </div>
                                    <div style="display: flex; gap: 8px; align-items: center; flex-shrink: 0;">
                                        <button class="btn" onclick="downloadSpecificReport('${report.filename}')" style="padding: 10px; min-width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;">
                                            <span class="material-icons" style="font-size: 20px;">download</span>
                                        </button>
                                        <button class="btn" onclick="deleteReport('${report.filename}')" style="padding: 10px; min-width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; background: #e57373;">
                                            <span class="material-icons" style="font-size: 20px;">delete</span>
                                        </button>
                                    </div>
                                `;
                                container.appendChild(item);
                            });
                        } else {
                            container.innerHTML = '<div style="text-align: center; padding: 20px; color: #9b9b9b;">No reports generated yet</div>';
                        }
                    })
                    .catch(error => {
                        console.error('Failed to load reports:', error);
                        document.getElementById('reportsList').innerHTML = 
                            '<div style="text-align: center; padding: 20px; color: #e57373;">Failed to load reports</div>';
                    });
            }
            
            function downloadSpecificReport(filename) {
                window.location.href = 'api/reports/' + filename;
            }
            
            function deleteReport(filename) {
                if (!confirm(`Are you sure you want to delete ${filename}?`)) {
                    return;
                }
                
                fetch('api/reports/' + filename, { method: 'DELETE' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            showStatus('<strong>Success!</strong> Report deleted successfully.', 'success');
                            loadReports(); // Reload the list
                        } else {
                            showStatus('<strong>Error:</strong> ' + data.message, 'error');
                        }
                    })
                    .catch(error => {
                        showStatus('<strong>Error:</strong> Failed to delete report', 'error');
                    });
            }
        </script>
    </body>
    </html>
    """
    return html


@app.route('/api/reports', methods=['GET'])
def get_reports():
    """Get list of all available PDF reports"""
    logger.info("API: GET /api/reports")
    try:
        reports = []
        
        # Search in PDF output directory only
        if PDF_OUTPUT_PATH.exists():
            for pdf_file in PDF_OUTPUT_PATH.glob('*.pdf'):
                stat_info = pdf_file.stat()
                reports.append({
                    'filename': pdf_file.name,
                    'path': str(pdf_file),
                    'size': stat_info.st_size,
                    'size_kb': round(stat_info.st_size / 1024, 2),
                    'created': datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': stat_info.st_mtime
                })
        
        # Sort by timestamp (newest first)
        reports.sort(key=lambda x: x['timestamp'], reverse=True)
        
        logger.info(f"Found {len(reports)} reports")
        return jsonify({
            'status': 'success',
            'reports': reports
        })
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/reports/<filename>', methods=['GET'])
def download_report(filename):
    """Download a specific report by filename"""
    logger.info(f"API: GET /api/reports/{filename}")
    try:
        pdf_file = PDF_OUTPUT_PATH / filename
        
        if not pdf_file.exists():
            return jsonify({
                'status': 'error',
                'message': 'Report not found'
            }), 404
        
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Error downloading report: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/reports/<filename>', methods=['DELETE'])
def delete_report(filename):
    """Delete a specific report by filename"""
    logger.info(f"API: DELETE /api/reports/{filename}")
    try:
        pdf_file = PDF_OUTPUT_PATH / filename
        
        if not pdf_file.exists():
            return jsonify({
                'status': 'error',
                'message': 'Report not found'
            }), 404
        
        pdf_file.unlink()
        logger.info(f"Deleted report: {filename}")
        
        return jsonify({
            'status': 'success',
            'message': f'Report {filename} deleted successfully'
        })
    except Exception as e:
        logger.error(f"Error deleting report: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/health')
def health():
    """Health check for Home Assistant"""
    logger.info("Health check requested")
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.route('/api/entities', methods=['GET'])
def get_entities():
    """Get list of available Shelly entities"""
    logger.info("API: GET /api/entities")
    try:
        entities = discover_shelly_entities()
        
        # Load selected entities from file
        config_file = DATA_PATH / 'selected_entities.json'
        selected = []
        if config_file.exists():
            with open(config_file, 'r') as f:
                selected = json.load(f)
        
        logger.info(f"Returning {len(entities)} entities, {len(selected)} selected")
        
        # Build response and return immediately
        response_data = {
            'status': 'success',
            'entities': entities,
            'selected': selected
        }
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in get_entities: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/entities/select', methods=['POST'])
def select_entities():
    """Save selected entities"""
    try:
        data = request.get_json()
        selected_ids = data.get('entity_ids', [])
        
        # Save to file
        config_file = DATA_PATH / 'selected_entities.json'
        with open(config_file, 'w') as f:
            json.dump(selected_ids, f)
        
        logger.info(f"Saved {len(selected_ids)} selected entities")
        
        return jsonify({
            'status': 'success',
            'message': f'Saved {len(selected_ids)} entities',
            'selected': selected_ids
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/auto-update/config', methods=['GET'])
def get_auto_update_config():
    """Get auto-update configuration"""
    try:
        config_file = DATA_PATH / 'auto_update_config.json'
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            config = {'enabled': False, 'interval_hours': 24}
        
        return jsonify({
            'status': 'success',
            'config': config
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/auto-update/config', methods=['POST'])
def save_auto_update_config():
    """Save auto-update configuration"""
    try:
        data = request.get_json()
        config = {
            'enabled': data.get('enabled', False),
            'interval_hours': data.get('interval_hours', 24)
        }
        
        config_file = DATA_PATH / 'auto_update_config.json'
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        logger.info(f"Auto-update config saved: {config}")
        
        return jsonify({
            'status': 'success',
            'message': 'Auto-update configuration saved',
            'config': config
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/collect-data', methods=['POST'])
def collect_data():
    """Manually trigger data collection from Home Assistant history"""
    logger.info("=" * 60)
    logger.info("MANUAL DATA COLLECTION REQUESTED")
    logger.info("=" * 60)
    
    try:
        # Load selected entities from file
        config_file = DATA_PATH / 'selected_entities.json'
        if not config_file.exists():
            return jsonify({
                'status': 'error',
                'message': 'Please select at least one device before collecting data'
            }), 400
        
        with open(config_file, 'r') as f:
            entity_ids = json.load(f)
        
        if not entity_ids:
            return jsonify({
                'status': 'error',
                'message': 'Please select at least one device before collecting data'
            }), 400
        
        logger.info(f"Using {len(entity_ids)} selected entities, fetching history...")
        
        # Get time range from request or default to last 7 days
        data = request.get_json() or {}
        days = data.get('days', 7)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        history_data = get_history_from_ha(entity_ids, start_time, end_time)
        
        if not history_data:
            return jsonify({
                'status': 'error',
                'message': 'Failed to retrieve history data from Home Assistant'
            }), 500
        
        # Convert to CSV format
        csv_file = DATA_PATH / 'all.csv'
        success = convert_history_to_csv(history_data, csv_file)
        
        if not success:
            return jsonify({
                'status': 'error',
                'message': 'Failed to convert history data to CSV'
            }), 500
        
        logger.info("=" * 60)
        logger.info("[SUCCESS] MANUAL COLLECTION COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        
        return jsonify({
            'status': 'success',
            'message': 'Data collected successfully from Home Assistant history',
            'entities_count': len(entity_ids),
            'entities': entity_ids,
            'csv_file': str(csv_file)
        })
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"[ERROR] ERROR IN MANUAL COLLECTION: {e}", exc_info=True)
        logger.error("=" * 60)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/generate', methods=['POST'])
def generate_report():
    """Generate PDF report from CSV data"""
    logger.info("=" * 60)
    logger.info("PDF REPORT GENERATION REQUESTED")
    logger.info("=" * 60)
    
    try:
        logger.info(f"Checking data folder: {DATA_PATH}")
        
        # Check data folder
        if not DATA_PATH.exists():
            logger.error(f"Data folder not found: {DATA_PATH}")
            return jsonify({
                'status': 'error',
                'message': f'Data folder not found: {DATA_PATH}'
            }), 404
        
        # Check for main CSV file
        main_csv = DATA_PATH / 'all.csv'
        if not main_csv.exists():
            logger.error("No CSV data found")
            return jsonify({
                'status': 'error',
                'message': 'No CSV data found. Collect data first.'
            }), 404
        
        # Load selected entities for filtering
        config_file = DATA_PATH / 'selected_entities.json'
        selected_entities = []
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    selected_entities = json.load(f)
                logger.info(f"Loaded {len(selected_entities)} selected entities for report filtering")
            except Exception as e:
                logger.warning(f"Could not load selected entities: {e}")
        
        # If entities are selected, filter the CSV data for report
        report_data_dir = DATA_PATH
        if selected_entities:
            logger.info("Filtering data for selected entities...")
            filtered_csv = DATA_PATH / 'filtered_report.csv'
            success = filter_csv_by_selected_entities(main_csv, filtered_csv, selected_entities)
            if success:
                # Create temp directory for filtered data
                report_data_dir = DATA_PATH / 'filtered'
                report_data_dir.mkdir(exist_ok=True)
                # Copy filtered CSV to temp directory
                import shutil
                shutil.copy2(filtered_csv, report_data_dir / 'all.csv')
        
        # Create analyzer and generate report
        logger.info("Creating ShellyEnergyReport analyzer...")
        analyzer = ShellyEnergyReport(
            data_dir=str(report_data_dir),
            output_dir=str(TEMP_OUTPUT_PATH),
            correct_timestamps=True
        )
        
        logger.info("Running analysis and generating PDF...")
        analyzer.run_analysis()
        
        # Check for generated PDFs in PDF_OUTPUT_PATH
        all_pdfs = list(PDF_OUTPUT_PATH.glob('report_*.pdf'))
        
        # Filter for just-generated PDFs (last 10 seconds)
        import time
        current_time = time.time()
        device_pdfs = [pdf for pdf in all_pdfs if (current_time - pdf.stat().st_mtime) < 10]
        
        if device_pdfs:
            total_size = sum(pdf.stat().st_size for pdf in device_pdfs)
            
            logger.info("=" * 60)
            logger.info(f"[SUCCESS] PDF REPORTS GENERATED: {len(device_pdfs)} devices")
            logger.info(f"  Total size: {round(total_size / 1024, 2)} KB")
            logger.info("=" * 60)
            
            # Cleanup temp filtered directory
            if selected_entities:
                shutil.rmtree(report_data_dir, ignore_errors=True)
            
            return jsonify({
                'status': 'success',
                'message': f'{len(device_pdfs)} device reports generated successfully!',
                'pdf_count': len(device_pdfs),
                'pdf_size_kb': round(total_size / 1024, 2),
                'timestamp': datetime.now().isoformat(),
                'device_reports': [pdf.name for pdf in device_pdfs]
            })
        
        # No PDFs found
        logger.error("PDF not found after generation")
        logger.error(f"PDF output directory: {PDF_OUTPUT_PATH}")
        logger.error(f"Directory contents: {list(PDF_OUTPUT_PATH.iterdir()) if PDF_OUTPUT_PATH.exists() else 'Not found'}")
        return jsonify({
            'status': 'error',
            'message': 'PDF generation failed - file not created'
        }), 500
            
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"[ERROR] ERROR GENERATING REPORT: {e}", exc_info=True)
        logger.error("=" * 60)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/download/latest')
def download_latest():
    """Download the latest PDF report(s) generated in the last 30 seconds"""
    logger.info("=" * 60)
    logger.info("PDF DOWNLOAD REQUESTED")
    logger.info("=" * 60)
    
    try:
        # Get all report PDFs
        all_pdfs = list(PDF_OUTPUT_PATH.glob('report_*.pdf'))
        
        # Filter for recently generated PDFs (last 30 seconds)
        import time
        current_time = time.time()
        recent_pdfs = [pdf for pdf in all_pdfs if (current_time - pdf.stat().st_mtime) < 30]
        
        if len(recent_pdfs) > 1:
            # Multiple reports - create zip
            import zipfile
            from io import BytesIO
            
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for pdf_path in recent_pdfs:
                    zip_file.write(pdf_path, pdf_path.name)
            
            zip_buffer.seek(0)
            logger.info(f"Created zip with {len(recent_pdfs)} reports")
            
            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name=f'energy_reports_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
            )
        
        elif len(recent_pdfs) == 1:
            # Single report
            pdf_file = recent_pdfs[0]
            logger.info(f"Sending single report: {pdf_file.name}")
            return send_file(
                pdf_file,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=pdf_file.name
            )
        
        # No recent reports found
        logger.error(f"No recent PDFs found in {PDF_OUTPUT_PATH}")
        logger.error(f"Total PDFs in directory: {len(all_pdfs)}")
        if PDF_OUTPUT_PATH.exists():
            logger.error(f"PDF output directory contents: {[p.name for p in all_pdfs[:5]]}")
        return jsonify({
            'status': 'error',
            'message': 'No recent report found. Generate one first.'
            }), 404
        
        # Get file info
        file_stat = pdf_file.stat()
        file_date = datetime.fromtimestamp(file_stat.st_mtime)
        file_size = file_stat.st_size
        
        logger.info(f"[SUCCESS] Serving PDF: {pdf_file}")
        logger.info(f"  Size: {round(file_size / 1024, 2)} KB")
        logger.info(f"  Modified: {file_date}")
        logger.info("=" * 60)
        
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'energy_report_{file_date.strftime("%Y%m%d")}.pdf'
        )
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"[ERROR] ERROR SERVING PDF: {e}", exc_info=True)
        logger.error("=" * 60)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/status')
def get_status():
    """Get status of reports and data"""
    try:
        # Check for device-specific reports
        device_pdfs = list(PDF_OUTPUT_PATH.glob('report_*.pdf')) if PDF_OUTPUT_PATH.exists() else []
        
        # Fallback to general report
        general_pdf = PDF_OUTPUT_PATH / 'report_generale.pdf'
        
        # Count CSV files
        csv_count = len(list(DATA_PATH.glob("*.csv"))) if DATA_PATH.exists() else 0
        
        has_reports = len(device_pdfs) > 0 or general_pdf.exists()
        
        if not has_reports:
            return jsonify({
                'status': 'no_report',
                'has_report': False,
                'csv_files_count': csv_count,
                'data_path': str(DATA_PATH)
            })
        
        # Get latest report info
        if device_pdfs:
            latest_pdf = max(device_pdfs, key=lambda p: p.stat().st_mtime)
            file_stat = latest_pdf.stat()
            report_count = len(device_pdfs)
        else:
            latest_pdf = general_pdf
            file_stat = latest_pdf.stat()
            report_count = 1
        
        file_date = datetime.fromtimestamp(file_stat.st_mtime)
        
        return jsonify({
            'status': 'ready',
            'has_report': True,
            'report_count': report_count,
            'last_generated': file_date.isoformat(),
            'last_generated_human': file_date.strftime('%d/%m/%Y %H:%M:%S'),
            'pdf_size_kb': round(file_stat.st_size / 1024, 2),
            'csv_files_count': csv_count,
            'data_path': str(DATA_PATH),
            'download_url': '/download/latest'
        })
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# Initialize on module load (for Gunicorn)
def initialize_addon():
    """Initialize addon when module is loaded"""
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    TEMP_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    PDF_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("ENERGY REPORTS ADD-ON STARTING")
    logger.info("=" * 60)
    logger.info(f"Data path: {DATA_PATH}")
    logger.info(f"Temp output path: {TEMP_OUTPUT_PATH}")
    logger.info(f"PDF output path: {PDF_OUTPUT_PATH}")
    logger.info(f"Supervisor token available: {bool(SUPERVISOR_TOKEN)}")
    logger.info("=" * 60)
    
    # Background collection disabled - using Home Assistant history API instead
    logger.info("Background collection disabled - data will be fetched from HA history on demand")


# Initialize when running under Gunicorn
if __name__ != '__main__':
    initialize_addon()


if __name__ == '__main__':
    # Running standalone (not under Gunicorn)
    initialize_addon()
    
    # Run server (development mode)
    app.run(host='0.0.0.0', port=5000, debug=False)

