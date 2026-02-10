class EnergyReportsPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
  }

  connectedCallback() {
    if (this._root) {
      return;
    }
    this._root = this.attachShadow({ mode: "open" });
    if (!this._hass) {
      this._hass = this._resolveParentHass();
    }
    this._init();
  }

  _resolveParentHass() {
    try {
      const root = window.parent?.document?.querySelector("home-assistant");
      return root ? root.hass : null;
    } catch (err) {
      return null;
    }
  }

  async _init() {
    const template = await this._loadTemplate();
    this._root.innerHTML = template;
    window.__energyReportsPanel = this;
    window.generateReportComplete = () => this.generateReportComplete();
    window.toggleDevice = (entityId) => this.toggleDevice(entityId);
    window.saveAutoReportSchedule = () => this.saveAutoReportSchedule();
    window.downloadSpecificReport = (filename) => this.downloadSpecificReport(filename);
    window.deleteReport = (filename) => this.deleteReport(filename);

    this.availableEntities = [];
    this.selectedEntities = [];

    await this.loadDevices();
    await this.loadAutoUpdateConfig();
    await this.loadReports();
  }

  async _loadTemplate() {
    const resp = await fetch("/api/energy_reports/ui", { credentials: "include" });
    const text = await resp.text();
    const doc = new DOMParser().parseFromString(text, "text/html");
    const links = Array.from(doc.querySelectorAll('link[rel="stylesheet"]'))
      .map((link) => link.outerHTML)
      .join("");
    const style = doc.querySelector("style")?.outerHTML || "";
    const body = doc.body?.innerHTML || "";
    return `
      ${links}
      ${style}
      ${body}
    `;
  }

  _qs(selector) {
    return this._root.querySelector(selector);
  }

  _showStatus(message, type) {
    const status = this._qs("#status");
    status.innerHTML = message;
    status.className = `status ${type}`;
    status.style.display = "block";
  }

  async _callApi(method, path, data) {
    if (!this._hass) {
      this._hass = this._resolveParentHass();
    }
    if (!this._hass) {
      throw new Error("Home Assistant not ready");
    }
    try {
      return await this._hass.callApi(method, path, data);
    } catch (err) {
      if (err?.status === 401 || err?.status === 403) {
        this._showStatus(
          "<strong>Non autorizzato:</strong> assicurati di essere loggato in Home Assistant.",
          "error"
        );
      }
      throw err;
    }
  }

  async generateReportComplete() {
    const btn = this._qs("#generateReportBtn");
    const originalHTML = btn.innerHTML;
    const days = this._qs("#timeRange").value;

    btn.disabled = true;
    btn.innerHTML = `${originalHTML} <span class="spinner"></span>`;
    this._showStatus(
      `<strong>Step 1/2:</strong> Fetching data from Home Assistant (last ${days} days)...`,
      "info"
    );

    try {
      await this._callApi("POST", "energy_reports/collect-data", { days: parseInt(days, 10) });
      this._showStatus(
        "<strong>Step 2/2:</strong> Generating PDF report... Please wait.",
        "info"
      );
      const genData = await this._callApi("POST", "energy_reports/generate", {});
      btn.disabled = false;
      btn.innerHTML = originalHTML;
      this._qs("#status").style.display = "none";

      if (genData.status === "success") {
        this._showStatus(
          `<strong>Success!</strong> Report generated successfully (${genData.pdf_size_kb} KB). Check Reports History below.`,
          "success"
        );
        await this.loadReports();
      } else {
        this._showStatus(`<strong>Error:</strong> ${genData.message}`, "error");
      }
    } catch (error) {
      btn.disabled = false;
      btn.innerHTML = originalHTML;
      this._qs("#status").style.display = "none";
      this._showStatus(`<strong>Network Error:</strong> ${error}`, "error");
    }
  }

  async loadDevices() {
    try {
      const data = await this._callApi("GET", "energy_reports/api/entities");
      if (data.status === "success") {
        this.availableEntities = data.entities;
        this.selectedEntities = data.selected || [];
        this.renderDeviceList();
      } else {
        this._qs("#deviceList").innerHTML = `<div style="text-align: center; padding: 20px; color: #e57373;">Error: ${
          data.message || "Unknown error"
        }</div>`;
      }
    } catch (error) {
      this._qs("#deviceList").innerHTML = `<div style="text-align: center; padding: 20px; color: #e57373;">Failed to load devices: ${error.message}</div>`;
    }
  }

  renderDeviceList() {
    const container = this._qs("#deviceList");
    if (this.availableEntities.length === 0) {
      container.innerHTML =
        '<div style="text-align: center; padding: 20px; color: #9b9b9b;">No Shelly devices found</div>';
      return;
    }

    container.innerHTML = "";
    this.availableEntities.forEach((entity) => {
      const isSelected = this.selectedEntities.includes(entity.entity_id);
      const item = document.createElement("div");
      item.className = "device-item";
      item.onclick = () => this.toggleDevice(entity.entity_id);

      item.innerHTML = `
        <input type="checkbox" class="device-checkbox" ${isSelected ? "checked" : ""} 
               onclick="event.stopPropagation(); toggleDevice('${entity.entity_id}')">
        <div class="device-info">
          <div class="device-name">${entity.friendly_name}</div>
          <div class="device-id">${entity.entity_id}</div>
        </div>
      `;
      container.appendChild(item);
    });
  }

  toggleDevice(entityId) {
    const index = this.selectedEntities.indexOf(entityId);
    if (index > -1) {
      this.selectedEntities.splice(index, 1);
    } else {
      this.selectedEntities.push(entityId);
    }
    this.renderDeviceList();
    this.saveDeviceSelection();
  }

  async saveDeviceSelection() {
    try {
      const data = await this._callApi("POST", "energy_reports/api/entities/select", {
        entity_ids: this.selectedEntities,
      });
      if (data.status === "success") {
        this._showStatus(
          `<strong>Success!</strong> Saved ${this.selectedEntities.length} devices for report generation.`,
          "success"
        );
      } else {
        this._showStatus(`<strong>Error:</strong> ${data.message}`, "error");
      }
    } catch (error) {
      this._showStatus("<strong>Error:</strong> Failed to save selection", "error");
    }
  }

  async loadAutoUpdateConfig() {
    try {
      const data = await this._callApi("GET", "energy_reports/api/auto-update/config");
      if (data.status === "success") {
        const intervalHours = data.config.interval_hours || 0;
        this._qs("#autoReportSchedule").value = intervalHours;
      }
    } catch (error) {
      // No-op: keep default value
    }
  }

  async saveAutoReportSchedule() {
    const intervalHours = parseInt(this._qs("#autoReportSchedule").value, 10);
    const enabled = intervalHours > 0;
    try {
      const data = await this._callApi("POST", "energy_reports/api/auto-update/config", {
        enabled,
        interval_hours: intervalHours,
      });
      if (data.status === "success") {
        this._showStatus(
          enabled
            ? "<strong>Success!</strong> Automatic report generation scheduled."
            : "<strong>Success!</strong> Automatic report generation disabled.",
          "success"
        );
      } else {
        this._showStatus(`<strong>Error:</strong> ${data.message}`, "error");
      }
    } catch (error) {
      this._showStatus("<strong>Error:</strong> Failed to save configuration", "error");
    }
  }

  async loadReports() {
    try {
      const data = await this._callApi("GET", "energy_reports/api/reports");
      const container = this._qs("#reportsList");
      if (data.status === "success" && data.reports.length > 0) {
        container.innerHTML = "";
        data.reports.forEach((report) => {
          const item = document.createElement("div");
          item.className = "device-item";
          item.style.cursor = "default";
          item.style.display = "flex";
          item.style.alignItems = "center";
          item.style.justifyContent = "space-between";

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
              <button class="btn" onclick="downloadSpecificReport('${report.filename}')" style="padding: 0; width: 44px; height: 44px; min-width: 44px; display: inline-flex; align-items: center; justify-content: center; background: #03a9f4;">
                <span class="material-icons" style="font-size: 22px; line-height: 0;">download</span>
              </button>
              <button class="btn" onclick="deleteReport('${report.filename}')" style="padding: 0; width: 44px; height: 44px; min-width: 44px; display: inline-flex; align-items: center; justify-content: center; background: #f44336; box-shadow: 0 2px 6px rgba(244, 67, 54, 0.4);">
                <span class="material-icons" style="font-size: 22px; line-height: 0;">delete</span>
              </button>
            </div>
          `;
          container.appendChild(item);
        });
      } else {
        container.innerHTML =
          '<div style="text-align: center; padding: 20px; color: #9b9b9b;">No reports generated yet</div>';
      }
    } catch (error) {
      this._qs("#reportsList").innerHTML =
        '<div style="text-align: center; padding: 20px; color: #e57373;">Failed to load reports</div>';
    }
  }

  downloadSpecificReport(filename) {
    window.location.href = `/api/energy_reports/api/reports/${filename}`;
  }

  async deleteReport(filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) {
      return;
    }
    try {
      const data = await this._callApi("DELETE", `energy_reports/api/reports/${filename}`);
      if (data.status === "success") {
        this._showStatus("<strong>Success!</strong> Report deleted successfully.", "success");
        await this.loadReports();
      } else {
        this._showStatus(`<strong>Error:</strong> ${data.message}`, "error");
      }
    } catch (error) {
      this._showStatus("<strong>Error:</strong> Failed to delete report", "error");
    }
  }
}

customElements.define("energy-reports-panel", EnergyReportsPanel);
