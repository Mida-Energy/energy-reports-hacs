"""
Mida Energy Report Generator - Home Assistant Add-on version
Integrated API with automatic Shelly data collection
"""
from flask import Flask, jsonify, send_file, request
from pathlib import Path
import sys
import logging
import json
from datetime import datetime
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
    # Log request
    logger.info(f">>> REQUEST: {request.method} {request.path}")
    sys.stdout.flush()
    
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

# Force unbuffered output
sys.stdout.flush()
sys.stderr.flush()

# Get paths from environment (set by add-on)
DATA_PATH = Path(os.getenv('DATA_PATH', '/share/energy_reports/data'))
OUTPUT_PATH = Path('/media/energy_reports')
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
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
                        logger.info(f"  ✓ {friendly_name}: {value}")
                    except:
                        value = 0.0
                        logger.warning(f"  ⚠ {friendly_name}: Cannot convert to float, using 0.0")
                    
                    raw_data[friendly_name] = value
                else:
                    logger.error(f"  ✗ Failed to get data from {entity_id}")
            
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
            logger.info(f"✓ Data collected successfully: {len(raw_data)} entities → {len(data_row)-1} standard columns saved to {self.csv_file}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"✗ Error collecting data: {e}", exc_info=True)
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
    """Start background data collection thread"""
    global collection_thread
    
    logger.info("=" * 60)
    logger.info("Initializing background data collection...")
    logger.info("=" * 60)
    
    # Read configuration
    auto_export = os.getenv('AUTO_EXPORT', 'true').lower() == 'true'
    interval_hours = int(os.getenv('EXPORT_INTERVAL', '1'))
    
    logger.info(f"Auto-export enabled: {auto_export}")
    logger.info(f"Export interval: {interval_hours} hours")
    
    # For now, we'll auto-discover Shelly entities
    # In a future version, this could be configurable
    entity_ids = discover_shelly_entities()
    
    if entity_ids and auto_export:
        collector = ShellyDataCollector(entity_ids, interval_seconds=interval_hours * 3600)
        collection_thread = threading.Thread(target=collector.start_collection, daemon=True)
        collection_thread.start()
        logger.info("=" * 60)
        logger.info("✓ Background data collection thread started successfully")
        logger.info("=" * 60)
    else:
        logger.warning("=" * 60)
        if not auto_export:
            logger.warning("⚠ Auto-collection is DISABLED in configuration")
        else:
            logger.warning("⚠ No Shelly entities found - collection cannot start")
        logger.warning("=" * 60)


def discover_shelly_entities():
    """Discover Shelly power/energy entities from Home Assistant"""
    try:
        logger.info("=" * 60)
        logger.info("Discovering Shelly entities from Home Assistant...")
        logger.info("=" * 60)
        
        url = f"{HA_API_URL}/states"
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"✗ Failed to get states from HA API: {response.status_code}")
            return []
        
        all_states = response.json()
        shelly_entities = []
        
        # Look for Shelly energy/power sensors
        for state in all_states:
            entity_id = state.get('entity_id', '')
            if 'shelly' in entity_id.lower() and any(x in entity_id for x in ['power', 'energy']):
                shelly_entities.append(entity_id)
                logger.info(f"  ✓ Found: {entity_id}")
        
        logger.info("=" * 60)
        logger.info(f"✓ Discovery complete: {len(shelly_entities)} Shelly entities found")
        logger.info("=" * 60)
        return shelly_entities
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"✗ Error discovering Shelly entities: {e}")
        logger.error("=" * 60)
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
                    <span class="info-value">""" + str(OUTPUT_PATH) + """</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Auto-Collection</span>
                    <span class="badge """ + ("success" if os.getenv('AUTO_EXPORT', 'true') == 'true' else "") + """">""" + str(os.getenv('AUTO_EXPORT', 'true')) + """</span>
                </div>
            </div>

            <div class="card">
                <div class="card-title">
                    <span class="material-icons">manage_history</span>
                    Actions
                </div>
                <div class="button-grid">
                    <button class="btn" onclick="collectData()">
                        <span class="material-icons">sync</span>
                        Collect Data
                    </button>
                    <button class="btn" onclick="generateReport()">
                        <span class="material-icons">description</span>
                        Generate Report
                    </button>
                    <button class="btn btn-success" onclick="downloadReport()">
                        <span class="material-icons">download</span>
                        Download PDF
                    </button>
                </div>
                <div id="status" class="status"></div>
            </div>
        </div>
        <script>
            function showStatus(message, type) {
                const statusDiv = document.getElementById('status');
                statusDiv.className = 'status ' + type;
                statusDiv.innerHTML = message;
                statusDiv.style.display = 'block';
                setTimeout(() => {
                    if (type !== 'error') {
                        statusDiv.style.display = 'none';
                    }
                }, 10000);
            }
            
            function collectData() {
                const btn = event.target;
                const originalHTML = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = '<span class="material-icons">hourglass_empty</span>Processing...<span class="spinner"></span>';
                showStatus('Collecting data from Shelly devices...', 'info');
                
                fetch('/collect-data', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        btn.disabled = false;
                        btn.innerHTML = originalHTML;
                        if (data.status === 'success') {
                            showStatus('<strong>Success!</strong> Collected data from ' + data.entities_count + ' entities and saved to CSV', 'success');
                        } else {
                            showStatus('<strong>Error:</strong> ' + data.message, 'error');
                        }
                    })
                    .catch(error => {
                        btn.disabled = false;
                        btn.innerHTML = originalHTML;
                        showStatus('<strong>Network Error:</strong> ' + error, 'error');
                    });
            }
            
            function generateReport() {
                const btn = event.target;
                const originalHTML = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = '<span class="material-icons">hourglass_empty</span>Generating...<span class="spinner"></span>';
                showStatus('Generating PDF report... Please wait.', 'info');
                
                fetch('/generate', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        btn.disabled = false;
                        btn.innerHTML = originalHTML;
                        if (data.status === 'success') {
                            showStatus('<strong>Success!</strong> Report generated successfully (' + data.pdf_size_kb + ' KB)<br>' +
                                      '<a href="/download/latest" style="color: #81c784; text-decoration: underline; font-weight: 500;">' +
                                      'Click here to download</a>', 'success');
                        } else {
                            showStatus('<strong>Error:</strong> ' + data.message, 'error');
                        }
                    })
                    .catch(error => {
                        btn.disabled = false;
                        btn.innerHTML = originalHTML;
                        showStatus('<strong>Network Error:</strong> ' + error, 'error');
                    });
            }
            
            function downloadReport() {
                window.location.href = '/download/latest';
            }
        </script>
    </body>
    </html>
    """
    return html


@app.route('/health')
def health():
    """Health check for Home Assistant"""
    logger.info("Health check requested")
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.route('/collect-data', methods=['POST'])
def collect_data():
    """Manually trigger data collection from Shelly devices"""
    sys.stdout.flush()
    sys.stderr.flush()
    logger.info("=" * 60)
    logger.info("MANUAL DATA COLLECTION REQUESTED")
    logger.info("=" * 60)
    sys.stdout.flush()
    
    try:
        # Discover Shelly entities
        logger.info("Starting Shelly entity discovery...")
        entity_ids = discover_shelly_entities()
        
        if not entity_ids:
            logger.error("No Shelly entities found!")
            return jsonify({
                'status': 'error',
                'message': 'No Shelly entities found in Home Assistant'
            }), 404
        
        logger.info(f"Found {len(entity_ids)} entities, starting collection...")
        
        # Collect data immediately
        collector = ShellyDataCollector(entity_ids, interval_seconds=300)
        collector.collect_and_save()
        
        logger.info("=" * 60)
        logger.info("✓ MANUAL COLLECTION COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        
        return jsonify({
            'status': 'success',
            'message': 'Data collected successfully',
            'entities_count': len(entity_ids),
            'entities': entity_ids,
            'csv_file': str(collector.csv_file)
        })
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"✗ ERROR IN MANUAL COLLECTION: {e}", exc_info=True)
        logger.error("=" * 60)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/generate', methods=['POST'])
def generate_report():
    """Generate PDF report from CSV data"""
    sys.stdout.flush()
    sys.stderr.flush()
    logger.info("=" * 60)
    logger.info("PDF REPORT GENERATION REQUESTED")
    logger.info("=" * 60)
    sys.stdout.flush()
    
    try:
        logger.info(f"Checking data folder: {DATA_PATH}")
        
        # Check data folder
        if not DATA_PATH.exists():
            logger.error(f"Data folder not found: {DATA_PATH}")
            return jsonify({
                'status': 'error',
                'message': f'Data folder not found: {DATA_PATH}'
            }), 404
        
        # Check for CSV files
        csv_files = list(DATA_PATH.glob("*.csv"))
        logger.info(f"Found {len(csv_files)} CSV files in {DATA_PATH}")
        
        if not csv_files:
            logger.error("No CSV files found")
            return jsonify({
                'status': 'error',
                'message': 'No CSV files found. Make sure Shelly data is being collected.'
            }), 404
        
        for csv_file in csv_files:
            logger.info(f"  - {csv_file.name}")
        
        # Create analyzer and generate report
        logger.info("Creating ShellyEnergyReport analyzer...")
        analyzer = ShellyEnergyReport(
            data_dir=str(DATA_PATH),
            output_dir=str(OUTPUT_PATH.parent),
            correct_timestamps=True
        )
        
        logger.info("Running analysis and generating PDF...")
        analyzer.run_analysis()
        
        # Check if PDF was created (report generator puts it in /media/generale/)
        pdf_file = OUTPUT_PATH.parent / 'generale' / 'report_generale.pdf'
        logger.info(f"Checking for PDF at: {pdf_file}")
        
        if pdf_file.exists():
            file_size = pdf_file.stat().st_size
            logger.info("=" * 60)
            logger.info(f"✓ PDF GENERATED SUCCESSFULLY: {pdf_file}")
            logger.info(f"  File size: {round(file_size / 1024, 2)} KB")
            logger.info("=" * 60)
            
            return jsonify({
                'status': 'success',
                'message': 'Report generated successfully!',
                'pdf_size_kb': round(file_size / 1024, 2),
                'timestamp': datetime.now().isoformat(),
                'download_url': '/download/latest'
            })
        else:
            logger.error("PDF not found after generation")
            logger.error(f"Expected location: {pdf_file}")
            logger.error(f"Output directory contents: {list(OUTPUT_PATH.parent.iterdir())}")
            return jsonify({
                'status': 'error',
                'message': 'PDF generation failed - file not created'
            }), 500
            
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"✗ ERROR GENERATING REPORT: {e}", exc_info=True)
        logger.error("=" * 60)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/download/latest')
def download_latest():
    """Download the latest PDF report"""
    logger.info("=" * 60)
    logger.info("PDF DOWNLOAD REQUESTED")
    logger.info("=" * 60)
    
    try:
        pdf_file = OUTPUT_PATH.parent / 'generale' / 'report_generale.pdf'
        logger.info(f"Looking for PDF at: {pdf_file}")
        
        if not pdf_file.exists():
            logger.error(f"PDF not found at {pdf_file}")
            logger.error(f"Output directory exists: {OUTPUT_PATH.exists()}")
            if OUTPUT_PATH.exists():
                logger.error(f"Output directory contents: {list(OUTPUT_PATH.iterdir())}")
            return jsonify({
                'status': 'error',
                'message': 'No report found. Generate one first.'
            }), 404
        
        # Get file info
        file_stat = pdf_file.stat()
        file_date = datetime.fromtimestamp(file_stat.st_mtime)
        file_size = file_stat.st_size
        
        logger.info(f"✓ Serving PDF: {pdf_file}")
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
        logger.error(f"✗ ERROR SERVING PDF: {e}", exc_info=True)
        logger.error("=" * 60)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/status')
def get_status():
    """Get status of reports and data"""
    try:
        pdf_file = OUTPUT_PATH / 'report_generale.pdf'
        
        # Count CSV files
        csv_count = len(list(DATA_PATH.glob("*.csv"))) if DATA_PATH.exists() else 0
        
        if not pdf_file.exists():
            return jsonify({
                'status': 'no_report',
                'has_report': False,
                'csv_files_count': csv_count,
                'data_path': str(DATA_PATH)
            })
        
        # Get PDF info
        file_stat = pdf_file.stat()
        file_date = datetime.fromtimestamp(file_stat.st_mtime)
        
        return jsonify({
            'status': 'ready',
            'has_report': True,
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
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("ENERGY REPORTS ADD-ON STARTING")
    logger.info("=" * 60)
    logger.info(f"Data path: {DATA_PATH}")
    logger.info(f"Output path: {OUTPUT_PATH}")
    logger.info(f"Supervisor token available: {bool(SUPERVISOR_TOKEN)}")
    logger.info("=" * 60)
    
    # Start background data collection
    start_background_collection()


# Initialize when running under Gunicorn
if __name__ != '__main__':
    initialize_addon()


if __name__ == '__main__':
    # Running standalone (not under Gunicorn)
    initialize_addon()
    
    # Run server (development mode)
    app.run(host='0.0.0.0', port=5000, debug=False)

