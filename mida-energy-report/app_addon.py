"""
Mida Energy Report Generator - Home Assistant Add-on version
Integrated API with automatic Shelly data collection
"""
from flask import Flask, jsonify, send_file, request
from pathlib import Path
import sys
import logging
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

# Configure logging
logging.basicConfig(level=logging.INFO)
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
            # Collect data from all entities
            data_row = {
                'timestamp': datetime.now().isoformat()
            }
            
            for entity_id in self.entity_ids:
                state_data = self.get_entity_state(entity_id)
                if state_data:
                    # Extract friendly name and value
                    friendly_name = state_data.get('attributes', {}).get('friendly_name', entity_id)
                    value = state_data.get('state', '0')
                    
                    # Try to convert to float
                    try:
                        value = float(value)
                    except:
                        value = 0.0
                    
                    data_row[friendly_name] = value
            
            # Check if file exists to determine if we need headers
            file_exists = self.csv_file.exists()
            
            # Write to CSV
            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=data_row.keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerow(data_row)
            
            logger.info(f"Data collected and saved: {len(data_row)-1} entities")
            
        except Exception as e:
            logger.error(f"Error collecting data: {e}", exc_info=True)
    
    def start_collection(self):
        """Start background data collection"""
        self.running = True
        logger.info(f"Starting data collection every {self.interval} seconds for entities: {self.entity_ids}")
        
        while self.running and not stop_collection:
            self.collect_and_save()
            time.sleep(self.interval)
        
        logger.info("Data collection stopped")


def start_background_collection():
    """Start background data collection thread"""
    global collection_thread
    
    # Read configuration
    auto_export = os.getenv('AUTO_EXPORT', 'true').lower() == 'true'
    interval_hours = int(os.getenv('EXPORT_INTERVAL', '1'))
    
    # For now, we'll auto-discover Shelly entities
    # In a future version, this could be configurable
    entity_ids = discover_shelly_entities()
    
    if entity_ids and auto_export:
        collector = ShellyDataCollector(entity_ids, interval_seconds=interval_hours * 3600)
        collection_thread = threading.Thread(target=collector.start_collection, daemon=True)
        collection_thread.start()
        logger.info("Background data collection started")
    else:
        logger.info("Auto-collection disabled or no Shelly entities found")


def discover_shelly_entities():
    """Discover Shelly power/energy entities from Home Assistant"""
    try:
        url = f"{HA_API_URL}/states"
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Failed to get states: {response.status_code}")
            return []
        
        all_states = response.json()
        shelly_entities = []
        
        # Look for Shelly energy/power sensors
        for state in all_states:
            entity_id = state.get('entity_id', '')
            if 'shelly' in entity_id.lower() and any(x in entity_id for x in ['power', 'energy']):
                shelly_entities.append(entity_id)
        
        logger.info(f"Discovered {len(shelly_entities)} Shelly entities: {shelly_entities}")
        return shelly_entities
        
    except Exception as e:
        logger.error(f"Error discovering Shelly entities: {e}")
        return []


@app.route('/')
def home():
    """Home page with integrated UI"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mida Energy Report Generator</title>
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
            <h1>📊 Mida Energy Report Generator</h1>
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
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.route('/collect-data', methods=['POST'])
def collect_data():
    """Manually trigger data collection from Shelly devices"""
    try:
        # Discover Shelly entities
        entity_ids = discover_shelly_entities()
        
        if not entity_ids:
            return jsonify({
                'status': 'error',
                'message': 'No Shelly entities found in Home Assistant'
            }), 404
        
        # Collect data immediately
        collector = ShellyDataCollector(entity_ids, interval_seconds=300)
        collector.collect_and_save()
        
        return jsonify({
            'status': 'success',
            'message': 'Data collected successfully',
            'entities_count': len(entity_ids),
            'entities': entity_ids,
            'csv_file': str(collector.csv_file)
        })
        
    except Exception as e:
        logger.error(f"Error collecting data: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/generate', methods=['POST'])
def generate_report():
    """Generate PDF report from CSV data"""
    try:
        logger.info("=== Starting PDF report generation ===")
        
        # Check data folder
        if not DATA_PATH.exists():
            logger.error(f"Data folder not found: {DATA_PATH}")
            return jsonify({
                'status': 'error',
                'message': f'Data folder not found: {DATA_PATH}'
            }), 404
        
        # Check for CSV files
        csv_files = list(DATA_PATH.glob("*.csv"))
        if not csv_files:
            logger.error("No CSV files found")
            return jsonify({
                'status': 'error',
                'message': 'No CSV files found. Make sure Shelly data is being collected.'
            }), 404
        
        logger.info(f"Found {len(csv_files)} CSV files")
        
        # Create analyzer and generate report
        analyzer = ShellyEnergyReport(
            data_dir=str(DATA_PATH),
            output_dir=str(OUTPUT_PATH.parent),
            correct_timestamps=True
        )
        
        logger.info("Running analysis and generating PDF...")
        analyzer.run_analysis()
        
        # Check if PDF was created
        pdf_file = OUTPUT_PATH / 'report_generale.pdf'
        if pdf_file.exists():
            logger.info(f"PDF generated successfully: {pdf_file}")
            return jsonify({
                'status': 'success',
                'message': 'Report generated successfully!',
                'pdf_size_kb': round(pdf_file.stat().st_size / 1024, 2),
                'timestamp': datetime.now().isoformat(),
                'download_url': '/download/latest'
            })
        else:
            logger.error("PDF not found after generation")
            return jsonify({
                'status': 'error',
                'message': 'PDF generation failed'
            }), 500
            
    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/download/latest')
def download_latest():
    """Download the latest PDF report"""
    try:
        pdf_file = OUTPUT_PATH / 'report_generale.pdf'
        
        if not pdf_file.exists():
            return jsonify({
                'status': 'error',
                'message': 'No report found. Generate one first.'
            }), 404
        
        # Get file info
        file_stat = pdf_file.stat()
        file_date = datetime.fromtimestamp(file_stat.st_mtime)
        
        logger.info(f"Serving PDF: {pdf_file}")
        
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'energy_report_{file_date.strftime("%Y%m%d")}.pdf'
        )
        
    except Exception as e:
        logger.error(f"Error serving PDF: {e}")
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


if __name__ == '__main__':
    # Ensure directories exist
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    
    logger.info("Starting Mida Energy Report API (Add-on mode)...")
    logger.info(f"Data path: {DATA_PATH}")
    logger.info(f"Output path: {OUTPUT_PATH}")
    logger.info(f"Supervisor token available: {bool(SUPERVISOR_TOKEN)}")
    
    # Start background data collection
    start_background_collection()
    
    # Run server (production mode for add-on)
    app.run(host='0.0.0.0', port=5000, debug=False)

