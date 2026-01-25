from __future__ import annotations

from datetime import datetime, timedelta
import csv
import json
from pathlib import Path
from typing import Any
import shutil

from aiohttp import web
from homeassistant.components.recorder import history as recorder_history
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .report_generator.src.main import ShellyEnergyReport


def _get_paths(hass: HomeAssistant) -> dict[str, Path]:
    return hass.data[DOMAIN]


def _read_json_sync(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


async def _read_json(hass: HomeAssistant, path: Path, default: Any) -> Any:
    return await hass.async_add_executor_job(_read_json_sync, path, default)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle)


def _convert_history_to_csv(history_data: list[list[dict[str, Any]]], output_file: Path) -> bool:
    try:
        all_rows: list[dict[str, Any]] = []
        for entity_history in history_data:
            if not entity_history:
                continue
            for state in entity_history:
                try:
                    timestamp = datetime.fromisoformat(state["last_changed"].replace("Z", "+00:00"))
                    try:
                        value = float(state["state"])
                    except (ValueError, TypeError):
                        continue

                    entity_id = state["entity_id"]
                    friendly_name = state.get("attributes", {}).get("friendly_name", entity_id)

                    all_rows.append(
                        {
                            "timestamp": int(timestamp.timestamp()),
                            "entity_id": entity_id,
                            "friendly_name": friendly_name,
                            "value": value,
                        }
                    )
                except Exception:
                    continue

        if not all_rows:
            return False

        all_rows.sort(key=lambda x: x["timestamp"])

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", newline="", encoding="utf-8") as handle:
            fieldnames = [
                "timestamp",
                "entity_id",
                "friendly_name",
                "total_act_energy",
                "max_act_power",
                "avg_voltage",
                "avg_current",
            ]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in all_rows:
                power = row["value"]
                voltage = 230.0
                current = power / voltage if voltage > 0 else 0
                writer.writerow(
                    {
                        "timestamp": row["timestamp"],
                        "entity_id": row["entity_id"],
                        "friendly_name": row["friendly_name"],
                        "total_act_energy": power,
                        "max_act_power": power,
                        "avg_voltage": voltage,
                        "avg_current": current,
                    }
                )

        return True
    except Exception:
        return False


def _discover_shelly_entities(hass: HomeAssistant) -> list[dict[str, str]]:
    entities = []
    for state in hass.states.async_all():
        entity_id = state.entity_id
        attrs = state.attributes or {}
        friendly_name = attrs.get("friendly_name", entity_id)
        device_class = attrs.get("device_class", "")
        unit = attrs.get("unit_of_measurement", "")

        if "shelly" in entity_id.lower() and entity_id.startswith("sensor."):
            if device_class in ("power", "energy") or unit in ("W", "kW", "kWh", "Wh"):
                entities.append({"entity_id": entity_id, "friendly_name": friendly_name})

    return entities


def _history_to_json(entity_ids: list[str], states_map: dict[str, list[Any]]) -> list[list[dict[str, Any]]]:
    history_data: list[list[dict[str, Any]]] = []
    for entity_id in entity_ids:
        history_states = states_map.get(entity_id, [])
        entity_list = []
        for state in history_states:
            entity_list.append(
                {
                    "entity_id": state.entity_id,
                    "state": state.state,
                    "attributes": dict(state.attributes),
                    "last_changed": state.last_changed.isoformat(),
                }
            )
        history_data.append(entity_list)
    return history_data


class EnergyReportsRootView(HomeAssistantView):
    url = "/api/energy_reports"
    name = "api:energy_reports:root"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        raise web.HTTPFound("/api/energy_reports/")


class EnergyReportsIndexView(HomeAssistantView):
    url = "/api/energy_reports/"
    name = "api:energy_reports:index"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        html_path = Path(__file__).parent / "frontend" / "index.html"
        html = await self.hass.async_add_executor_job(
            html_path.read_text, "utf-8"
        )
        paths = _get_paths(self.hass)
        html = html.replace("{{DATA_PATH}}", str(paths["data_path"]))
        html = html.replace("{{PDF_PATH}}", str(paths["pdf_path"]))
        token = request.query.get("token", "")
        html = html.replace("{{AUTH_TOKEN}}", token)
        return web.Response(text=html, content_type="text/html")


class EnergyReportsPanelJsView(HomeAssistantView):
    url = "/api/energy_reports/panel.js"
    name = "api:energy_reports:panel_js"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        js_path = Path(__file__).parent / "frontend" / "energy-reports-panel.js"
        js = js_path.read_text(encoding="utf-8")
        return web.Response(text=js, content_type="application/javascript")


class EnergyReportsHealthView(HomeAssistantView):
    url = "/api/energy_reports/health"
    name = "api:energy_reports:health"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "healthy", "timestamp": datetime.now().isoformat()})


class EnergyReportsEntitiesView(HomeAssistantView):
    url = "/api/energy_reports/api/entities"
    name = "api:energy_reports:entities"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        paths = _get_paths(self.hass)
        selected_path = paths["data_path"] / "selected_entities.json"
        selected = await _read_json(self.hass, selected_path, [])

        entities = _discover_shelly_entities(self.hass)
        return web.json_response(
            {"status": "success", "entities": entities, "selected": selected}
        )


class EnergyReportsEntitiesSelectView(HomeAssistantView):
    url = "/api/energy_reports/api/entities/select"
    name = "api:energy_reports:entities_select"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        paths = _get_paths(self.hass)
        data = await request.json()
        selected_ids = data.get("entity_ids", [])
        await self.hass.async_add_executor_job(
            _write_json, paths["data_path"] / "selected_entities.json", selected_ids
        )
        return web.json_response(
            {"status": "success", "message": f"Saved {len(selected_ids)} entities", "selected": selected_ids}
        )


class EnergyReportsReportsView(HomeAssistantView):
    url = "/api/energy_reports/api/reports"
    name = "api:energy_reports:reports"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        paths = _get_paths(self.hass)
        pdf_path = paths["pdf_path"]
        reports = []
        if pdf_path.exists():
            for pdf_file in pdf_path.glob("*.pdf"):
                stat_info = pdf_file.stat()
                reports.append(
                    {
                        "filename": pdf_file.name,
                        "path": str(pdf_file),
                        "size": stat_info.st_size,
                        "size_kb": round(stat_info.st_size / 1024, 2),
                        "created": datetime.fromtimestamp(stat_info.st_mtime).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "timestamp": stat_info.st_mtime,
                    }
                )
        reports.sort(key=lambda x: x["timestamp"], reverse=True)
        return web.json_response({"status": "success", "reports": reports})


class EnergyReportsReportsItemView(HomeAssistantView):
    url = "/api/energy_reports/api/reports/{filename}"
    name = "api:energy_reports:reports_item"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        paths = _get_paths(self.hass)
        filename = request.match_info["filename"]
        pdf_file = paths["pdf_path"] / filename
        if not pdf_file.exists():
            return web.json_response({"status": "error", "message": "Report not found"}, status=404)

        return web.FileResponse(path=pdf_file, headers={"Content-Type": "application/pdf"})

    async def delete(self, request: web.Request) -> web.Response:
        paths = _get_paths(self.hass)
        filename = request.match_info["filename"]
        pdf_file = paths["pdf_path"] / filename
        if not pdf_file.exists():
            return web.json_response({"status": "error", "message": "Report not found"}, status=404)

        pdf_file.unlink()
        return web.json_response({"status": "success", "message": f"Report {filename} deleted successfully"})


class EnergyReportsAutoUpdateConfigView(HomeAssistantView):
    url = "/api/energy_reports/api/auto-update/config"
    name = "api:energy_reports:auto_update_config"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        paths = _get_paths(self.hass)
        config_path = paths["data_path"] / "auto_update_config.json"
        config = await _read_json(self.hass, config_path, {"enabled": False, "interval_hours": 0})
        return web.json_response({"status": "success", "config": config})

    async def post(self, request: web.Request) -> web.Response:
        paths = _get_paths(self.hass)
        data = await request.json()
        config = {
            "enabled": data.get("enabled", False),
            "interval_hours": data.get("interval_hours", 24),
        }
        await self.hass.async_add_executor_job(
            _write_json, paths["data_path"] / "auto_update_config.json", config
        )
        return web.json_response(
            {"status": "success", "message": "Auto-update configuration saved", "config": config}
        )


class EnergyReportsDownloadLatestView(HomeAssistantView):
    url = "/api/energy_reports/download/latest"
    name = "api:energy_reports:download_latest"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        paths = _get_paths(self.hass)
        pdf_path = paths["pdf_path"]
        if not pdf_path.exists():
            return web.json_response({"status": "error", "message": "No reports found"}, status=404)

        pdfs = list(pdf_path.glob("*.pdf"))
        if not pdfs:
            return web.json_response({"status": "error", "message": "No reports found"}, status=404)

        latest_pdf = max(pdfs, key=lambda p: p.stat().st_mtime)
        return web.FileResponse(path=latest_pdf, headers={"Content-Type": "application/pdf"})


class EnergyReportsStatusView(HomeAssistantView):
    url = "/api/energy_reports/status"
    name = "api:energy_reports:status"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        paths = _get_paths(self.hass)
        pdf_path = paths["pdf_path"]
        data_path = paths["data_path"]
        device_pdfs = list(pdf_path.glob("report_*.pdf")) if pdf_path.exists() else []
        general_pdf = pdf_path / "report_generale.pdf"
        csv_count = len(list(data_path.glob("*.csv"))) if data_path.exists() else 0

        has_reports = len(device_pdfs) > 0 or general_pdf.exists()
        if not has_reports:
            return web.json_response(
                {
                    "status": "no_report",
                    "has_report": False,
                    "csv_files_count": csv_count,
                    "data_path": str(data_path),
                }
            )

        if device_pdfs:
            latest_pdf = max(device_pdfs, key=lambda p: p.stat().st_mtime)
            file_stat = latest_pdf.stat()
            report_count = len(device_pdfs)
        else:
            latest_pdf = general_pdf
            file_stat = latest_pdf.stat()
            report_count = 1

        file_date = datetime.fromtimestamp(file_stat.st_mtime)
        return web.json_response(
            {
                "status": "ready",
                "has_report": True,
                "report_count": report_count,
                "last_generated": file_date.isoformat(),
                "last_generated_human": file_date.strftime("%d/%m/%Y %H:%M:%S"),
                "pdf_size_kb": round(file_stat.st_size / 1024, 2),
                "csv_files_count": csv_count,
                "data_path": str(data_path),
                "download_url": "/api/energy_reports/download/latest",
            }
        )


class EnergyReportsApiView(HomeAssistantView):
    url = "/api/energy_reports/collect-data"
    name = "api:energy_reports:collect_data"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        paths = _get_paths(self.hass)
        selected_path = paths["data_path"] / "selected_entities.json"
        entity_ids = await _read_json(self.hass, selected_path, [])

        if not entity_ids:
            return web.json_response(
                {"status": "error", "message": "Please select at least one device before collecting data"},
                status=400,
            )

        data = await request.json()
        days = data.get("days", 7)
        end_time = dt_util.now()
        start_time = end_time - timedelta(days=days)

        if "recorder" not in self.hass.config.components:
            return web.json_response(
                {"status": "error", "message": "Recorder integration is not loaded"},
                status=500,
            )

        def _get_history_sync() -> dict[str, list[Any]]:
            try:
                return recorder_history.get_significant_states(
                    self.hass,
                    start_time,
                    end_time,
                    entity_ids=entity_ids,
                    include_start_time_state=True,
                    significant_changes_only=True,
                    minimal_response=True,
                )
            except TypeError:
                return recorder_history.get_significant_states(
                    self.hass, start_time, end_time, entity_ids
                )

        try:
            states_map = await self.hass.async_add_executor_job(_get_history_sync)
        except Exception as exc:
            return web.json_response(
                {"status": "error", "message": f"History fetch failed: {exc}"},
                status=500,
            )

        history_data = _history_to_json(entity_ids, states_map)

        csv_file = paths["data_path"] / "all.csv"
        success = await self.hass.async_add_executor_job(
            _convert_history_to_csv, history_data, csv_file
        )

        if not success:
            return web.json_response(
                {"status": "error", "message": "Failed to convert history data to CSV"},
                status=500,
            )

        return web.json_response(
            {
                "status": "success",
                "message": "Data collected successfully from Home Assistant history",
                "entities_count": len(entity_ids),
                "entities": entity_ids,
                "csv_file": str(csv_file),
            }
        )


class EnergyReportsGenerateView(HomeAssistantView):
    url = "/api/energy_reports/generate"
    name = "api:energy_reports:generate"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        paths = _get_paths(self.hass)
        data_path = paths["data_path"]
        output_path = paths["output_path"]
        pdf_path = paths["pdf_path"]

        main_csv = data_path / "all.csv"
        if not main_csv.exists():
            return web.json_response(
                {"status": "error", "message": "No CSV data found. Collect data first."},
                status=404,
            )

        def _run_report() -> None:
            analyzer = ShellyEnergyReport(
                data_dir=str(data_path),
                output_dir=str(output_path),
                correct_timestamps=True,
            )
            analyzer.run_analysis()

        await self.hass.async_add_executor_job(_run_report)

        general_pdf = output_path / "generale" / "report_generale.pdf"
        if general_pdf.exists():
            target = pdf_path / "report_generale.pdf"
            try:
                shutil.copy2(general_pdf, target)
            except Exception:
                pass

        device_pdfs = list(pdf_path.glob("report_*.pdf"))
        if not device_pdfs:
            return web.json_response(
                {"status": "error", "message": "PDF generation failed - file not created"},
                status=500,
            )

        total_size = sum(pdf.stat().st_size for pdf in device_pdfs)
        return web.json_response(
            {
                "status": "success",
                "message": f"{len(device_pdfs)} device reports generated successfully!",
                "pdf_count": len(device_pdfs),
                "pdf_size_kb": round(total_size / 1024, 2),
                "timestamp": datetime.now().isoformat(),
                "device_reports": [pdf.name for pdf in device_pdfs],
            }
        )
