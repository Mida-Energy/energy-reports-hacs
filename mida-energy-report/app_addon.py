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
            data_row = {
                'timestamp': datetime.now().isoformat()
            }
            
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
                    
                    data_row[friendly_name] = value
                else:
                    logger.error(f"  ✗ Failed to get data from {entity_id}")
            
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
            logger.info(f"✓ Data collected successfully: {len(data_row)-1} entities saved to {self.csv_file}")
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
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; background: #f5f5f5; }
            .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; margin-bottom: 30px; }
            .btn { background: #03a9f4; color: white; border: none; padding: 15px 30px; font-size: 16px; 
                   border-radius: 5px; cursor: pointer; margin: 10px 5px; transition: all 0.3s; }
            .btn:hover { background: #0288d1; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(3,169,244,0.4); }
            .btn:disabled { background: #ccc; cursor: not-allowed; transform: none; }
            .btn-download { background: #4caf50; }
            .btn-download:hover { background: #45a049; }
            .status { padding: 15px; margin: 20px 0; border-radius: 5px; display: none; }
            .status.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .status.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .status.info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
            .spinner { border: 3px solid #f3f3f3; border-top: 3px solid #03a9f4; border-radius: 50%; 
                       width: 20px; height: 20px; animation: spin 1s linear infinite; display: inline-block; 
                       vertical-align: middle; margin-left: 10px; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            .info-box { background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Energy Reports</h1>
            <div class="info-box">
                <strong>Data Path:</strong> """ + str(DATA_PATH) + """<br>
                <strong>Reports Path:</strong> """ + str(OUTPUT_PATH) + """<br>
                <strong>Auto-Collection:</strong> """ + str(os.getenv('AUTO_EXPORT', 'true')) + """
            </div>
            <button class="btn" onclick="collectData()">📊 Raccogli Dati Shelly Ora</button>
            <button class="btn" onclick="generateReport()">🔄 Genera Report PDF</button>
            <button class="btn btn-download" onclick="downloadReport()">📥 Scarica Ultimo Report</button>
            <div id="status" class="status"></div>
        </div>
        <script>
            function showStatus(message, type) {
                const statusDiv = document.getElementById('status');
                statusDiv.className = 'status ' + type;
                statusDiv.innerHTML = message;
                statusDiv.style.display = 'block';
            }collectData() {
                const btn = event.target;
                btn.disabled = true;
                btn.innerHTML = '⏳ Raccolta dati...<span class="spinner"></span>';
                showStatus('Raccolta dati dai dispositivi Shelly in corso...', 'info');
                
                fetch('/collect-data', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        btn.disabled = false;
                        btn.innerHTML = '📊 Raccogli Dati Shelly Ora';
                        if (data.status === 'success') {
                            showStatus('✅ Dati raccolti: ' + data.entities_count + ' entità, salvate in CSV', 'success');
                        } else {
                            showStatus('❌ Errore: ' + data.message, 'error');
                        }
                    })
                    .catch(error => {
                        btn.disabled = false;
                        btn.innerHTML = '📊 Raccogli Dati Shelly Ora';
                        showStatus('❌ Errore di rete: ' + error, 'error');
                    });
            }
            
            function 
            
            function generateReport() {
                const btn = event.target;
                btn.disabled = true;
                btn.innerHTML = '⏳ Generazione in corso...<span class="spinner"></span>';
                showStatus('Generazione del report in corso... Attendere prego.', 'info');
                
                fetch('/generate', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        btn.disabled = false;
                        btn.innerHTML = '🔄 Genera Report PDF';
                        if (data.status === 'success') {
                            showStatus('✅ Report generato con successo! Dimensione: ' + data.pdf_size_kb + ' KB<br>' +
                                      '<a href="/download/latest" style="color: #fff; background: #4caf50; padding: 10px 20px; ' +
                                      'text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 10px;">' +
                                      '📥 Clicca qui per scaricare sul tuo PC</a>', 'success');
                        } else {
                            showStatus('❌ Errore: ' + data.message, 'error');
                        }
                    })
                    .catch(error => {
                        btn.disabled = false;
                        btn.innerHTML = '🔄 Genera Report PDF';
                        showStatus('❌ Errore di rete: ' + error, 'error');
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
    logger.info("=" * 60)
    logger.info("MANUAL DATA COLLECTION REQUESTED")
    logger.info("=" * 60)
    
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
        
        # Check if PDF was created
        pdf_file = OUTPUT_PATH / 'report_generale.pdf'
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
        pdf_file = OUTPUT_PATH / 'report_generale.pdf'
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

