# Energy Reports - Home Assistant (HACS)

Generate professional PDF reports from your Shelly sensors directly in Home Assistant, with an embedded sidebar UI.

## Requirements

- Home Assistant Core/Supervised/OS
- HACS installed
- Shelly integration already configured

## Installation via HACS

1. HACS → **Integrations**
2. Top-right menu → **Custom repositories**
3. Add this repo with category **Integration**
4. Search for **Energy Reports** and install
5. Restart Home Assistant

> After restart, **Energy Reports** appears in the sidebar.

## Usage

1. Open **Energy Reports** from the sidebar
2. Select devices
3. **Collect Data** (fetches history from HA)
4. **Generate Report** to create PDFs
5. Download or delete reports from **Reports History**

## File locations

- CSV data: `/config/energy_reports/data`
- Temporary output: `/config/energy_reports/output`
- Final PDFs: `/config/energy_reports/pdfs`

## Important notes

- This is a **HACS custom integration** (not an add-on).
- No Supervisor/Ingress: the UI is served internally by Home Assistant.
- Each HA instance generates its own reports (ideal for multiple instances).
- If the sidebar item does not appear, add a manual panel:
  ```yaml
  panel_iframe:
    energy_reports:
      title: Energy Reports
      icon: mdi:chart-line
      url: /api/energy_reports/
  ```

## Troubleshooting

### Sidebar entry is missing

- Make sure you restarted HA after installation.
- Check logs for integration errors.

### No PDF generated

- Verify there is history data for the selected sensors.
- Check that `/config/energy_reports/data/all.csv` exists.

---

## File structure (HACS)

```
custom_components/
└── energy_reports/
    ├── __init__.py
    ├── const.py
    ├── manifest.json
    ├── views.py
    ├── frontend/
    │   └── index.html
    └── report_generator/
        └── src/
            └── main.py
```
