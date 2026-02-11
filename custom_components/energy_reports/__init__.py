from __future__ import annotations

from pathlib import Path
import os
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from homeassistant.components import frontend
from homeassistant.components.recorder import history as recorder_history, get_instance
from homeassistant.core import HomeAssistant
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PANEL_ICON, PANEL_TITLE

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: cv.empty_config_schema}, extra=vol.ALLOW_EXTRA)

from .views import (
    EnergyReportsApiView,
    EnergyReportsAutoUpdateConfigView,
    EnergyReportsDownloadLatestView,
    EnergyReportsEntitiesSelectView,
    EnergyReportsEntitiesView,
    EnergyReportsGenerateView,
    EnergyReportsHealthView,
    EnergyReportsIndexView,
    EnergyReportsPanelJsView,
    EnergyReportsReportsItemView,
    EnergyReportsReportsView,
    EnergyReportsRootView,
    EnergyReportsStatusView,
    EnergyReportsUiView,
    _convert_history_to_csv,
    _history_to_json,
    _read_json,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    base_path = Path(hass.config.path("energy_reports"))
    data_path = base_path / "data"
    output_path = base_path / "output"
    pdf_path = base_path / "pdfs"

    for path in (base_path, data_path, output_path, pdf_path):
        path.mkdir(parents=True, exist_ok=True)

    hass.data[DOMAIN] = {
        "base_path": base_path,
        "data_path": data_path,
        "output_path": output_path,
        "pdf_path": pdf_path,
    }

    os.environ["DATA_PATH"] = str(data_path)

    hass.http.register_view(EnergyReportsRootView(hass))
    hass.http.register_view(EnergyReportsIndexView(hass))
    hass.http.register_view(EnergyReportsUiView(hass))
    hass.http.register_view(EnergyReportsPanelJsView(hass))
    hass.http.register_view(EnergyReportsHealthView(hass))
    hass.http.register_view(EnergyReportsEntitiesView(hass))
    hass.http.register_view(EnergyReportsEntitiesSelectView(hass))
    hass.http.register_view(EnergyReportsReportsView(hass))
    hass.http.register_view(EnergyReportsReportsItemView(hass))
    hass.http.register_view(EnergyReportsDownloadLatestView(hass))
    hass.http.register_view(EnergyReportsStatusView(hass))
    hass.http.register_view(EnergyReportsApiView(hass))
    hass.http.register_view(EnergyReportsGenerateView(hass))
    hass.http.register_view(EnergyReportsAutoUpdateConfigView(hass))

    last_run = {"value": None}

    async def _auto_update_worker(_: object) -> None:
        try:
            config_path = data_path / "auto_update_config.json"
            config = await _read_json(
                hass, config_path, {"enabled": False, "interval_hours": 0}
            )
            interval_hours = config.get("interval_hours", 0)
            enabled = config.get("enabled", False)

            if enabled and interval_hours and interval_hours > 0:
                now = dt_util.now()
                if last_run["value"] is None or (now - last_run["value"]) >= timedelta(
                    hours=interval_hours
                ):
                    selected_path = data_path / "selected_entities.json"
                    entity_ids = await _read_json(hass, selected_path, [])
                    if entity_ids:
                        start_time = now - timedelta(days=7)

                        def _get_history_sync():
                            try:
                                return recorder_history.get_significant_states(
                                    hass,
                                    start_time,
                                    now,
                                    entity_ids,
                                    True,
                                    True,
                                    True,
                                    True,
                                )
                            except TypeError:
                                return recorder_history.get_significant_states(
                                    hass, start_time, now, entity_ids
                                )

                        recorder = get_instance(hass)
                        states_map = await recorder.async_add_executor_job(_get_history_sync)
                        history_data = _history_to_json(entity_ids, states_map)
                        csv_file = data_path / "all.csv"
                        await hass.async_add_executor_job(
                            _convert_history_to_csv, history_data, csv_file
                        )

                        def _run_report():
                            from .report_generator.src.main import ShellyEnergyReport

                            analyzer = ShellyEnergyReport(
                                data_dir=str(data_path),
                                output_dir=str(output_path),
                                correct_timestamps=True,
                            )
                            analyzer.run_analysis()

                        await hass.async_add_executor_job(_run_report)
                        last_run["value"] = now
        except Exception as exc:
            _LOGGER.warning("Auto-update worker error: %s", exc)

    unsub = async_track_time_interval(hass, _auto_update_worker, timedelta(minutes=5))
    hass.data[DOMAIN]["auto_update_unsub"] = unsub

    async def _stop(_: object) -> None:
        unsub()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop)

    async def _register_panel_async() -> None:
        try:
            if hasattr(frontend, "async_register_panel"):
                await frontend.async_register_panel(
                    hass,
                    component_name="custom",
                    sidebar_title=PANEL_TITLE,
                    sidebar_icon=PANEL_ICON,
                    frontend_url_path=DOMAIN,
                    config={
                        "_panel_custom": {
                            "name": "energy-reports-panel",
                            "module_url": "/api/energy_reports/panel.js?v=5",
                        }
                    },
                    require_admin=False,
                )
            else:
                frontend.async_register_built_in_panel(
                    hass,
                    component_name="custom",
                    sidebar_title=PANEL_TITLE,
                    sidebar_icon=PANEL_ICON,
                    frontend_url_path=DOMAIN,
                    config={
                        "_panel_custom": {
                            "name": "energy-reports-panel",
                            "module_url": "/api/energy_reports/panel.js?v=5",
                        }
                    },
                    require_admin=False,
                )
        except Exception as exc:
            _LOGGER.warning("Failed to register panel: %s", exc)

    await _register_panel_async()

    return True
