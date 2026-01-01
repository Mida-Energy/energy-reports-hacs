# Energy Reports - Home Assistant Add-on

Generate professional PDF energy reports from your Shelly EM data directly in Home Assistant!

## What it does

- **Auto-discovers Shelly devices** and collects data automatically
- **Generates PDF reports** with charts, statistics, and insights  
- **One-click download** from Home Assistant dashboard
- **Professional reports** with daily and historical analysis
- **Background data collection** with configurable intervals

---

## Installation

### Step 1: Add Repository to Home Assistant

1. Go to **Settings** → **Add-ons** → **Add-on Store**
2. Click **⋮** (top right) → **Repositories**
3. Add: `https://github.com/Mida-Energy/energy-reports`
4. Click **Add** → **Close**

### Step 2: Install the Add-on

1. Find **"Energy Reports"** in the store
2. Click **Install**
3. Wait for installation to complete

### Step 3: Configure

1. Go to the **Configuration** tab
2. Set your preferences:
   ```yaml
   data_path: /config/mida_energy/data
   auto_export_enabled: true
   export_interval_hours: 1
   ```
3. Click **Save**

### Step 4: Start the Add-on

1. Go to **Info** tab
2. Click **Start**
3. Enable **"Start on boot"** (recommended)
4. The addon will appear in the **sidebar** of Home Assistant!

---

## Usage

### Access the Integrated UI

Once installed, **Energy Reports** appears directly in your **Home Assistant sidebar**!

Just click on **"Energy Reports"** in the left menu - no need to configure anything else.

> **Note:** The addon integrates automatically via Home Assistant Ingress, so it's secure and doesn't expose additional ports.

### Alternative: External Access

If you prefer external access (not recommended):
```
http://homeassistant.local:5000
```

### Generate Your First Report

1. Make sure your **Shelly EM is integrated** in Home Assistant
2. Click **"Generate Report"** button
3. Wait 30-60 seconds
4. Click **"Download PDF"**
5. Done!

---

## Features

- Automatic Shelly EM data collection  
- Professional PDF reports with charts  
- Daily and general reports  
- Energy consumption statistics  
- Power usage analysis  
- Hourly breakdown  
- Recommendations and insights  
- Works on all architectures (ARM, x86)  

---

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `data_path` | Where CSV data is stored | `/config/mida_energy/data` |
| `auto_export_enabled` | Enable automatic export | `true` |
| `export_interval_hours` | Export frequency (1-24) | `1` |

---

## Testing

### Test API Health

```bash
curl http://homeassistant.local:5000/health
```

### Test Report Generation

```bash
curl -X POST http://homeassistant.local:5000/generate
```

### Download PDF

```bash
curl -o report.pdf http://homeassistant.local:5000/download/latest
```

---

## File Structure

```
homeassistant-addon/
├── config.json          # Add-on configuration
├── Dockerfile           # Container build
├── build.json          # Build configuration
├── build.yaml          # Build metadata
├── run.sh              # Startup script
├── app_addon.py        # Flask API server
├── README.md           # Add-on documentation
├── requirements.txt    # Python dependencies
└── report_generator/   # Report generation code
```

---

## Troubleshooting

### Add-on won't start

**Check logs:**
```
Add-on page → Log tab
```

**Common issues:**
- Make sure Shelly integration is working
- Verify data path exists
- Check system has enough memory

### No CSV files found

**Solution:**
- Verify Shelly EM is integrated in Home Assistant
- Check **Developer Tools** → **States** for `sensor.shelly_*`
- Ensure sensors have data

### PDF generation fails

**Solution:**
- Check logs for errors
- Verify CSV files exist in `/config/mida_energy/data/`
- Try generating with fewer CSV files first

---

## Next Steps

1. Install add-on
2. Configure settings  
3. Start add-on
4. Add dashboard card
5. Generate your first report!

---

## Tips

- **First time?** Let it collect data for a few hours before generating
- **Reports too big?** Limit the date range in CSV files
- **Want daily reports?** Keep auto-export enabled
- **Sharing reports?** PDFs are saved in `/share/mida_energy_reports/`

---

## License

Your project, your rules!

## Credits

Built for the Home Assistant community.
