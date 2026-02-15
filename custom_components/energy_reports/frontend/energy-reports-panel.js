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
    this._replaceMaterialIcons();
    window.__energyReportsPanel = this;
    window.generateReportComplete = () => this.generateReportComplete();
    window.toggleDevice = (entityId) => this.toggleDevice(entityId);
    window.saveAutoReportSchedule = () => this.saveAutoReportSchedule();
    window.saveCleanupConfig = () => this.saveCleanupConfig();
    window.runCleanupNow = () => this.runCleanupNow();
    window.downloadSpecificReport = (filename) => this.downloadSpecificReport(filename);
    window.deleteReport = (filename) => this.deleteReport(filename);

    this.availableEntities = [];
    this.selectedEntities = [];

    await this.loadDevices();
    await this.loadAutoUpdateConfig();
    await this.loadCleanupConfig();
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

  _replaceMaterialIcons() {
    const iconMap = {
      assessment: "mdi:chart-line",
      settings: "mdi:cog",
      devices: "mdi:devices",
      play_arrow: "mdi:play",
      history: "mdi:history",
      hourglass_empty: "mdi:hourglass",
      description: "mdi:file-document-outline",
      schedule: "mdi:clock-outline",
      folder: "mdi:folder-outline",
      download: "mdi:download",
      delete: "mdi:delete",
    };

    this._root.querySelectorAll("span.material-icons").forEach((node) => {
      const key = node.textContent?.trim();
      const icon = iconMap[key];
      if (!icon) {
        return;
      }
      const ha = document.createElement("ha-icon");
      ha.setAttribute("icon", icon);
      const style = node.getAttribute("style");
      if (style) {
        ha.setAttribute("style", style.replace("font-size", "--mdc-icon-size"));
      }
      node.replaceWith(ha);
    });
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
          "<strong>Unauthorized:</strong> make sure you are logged in to Home Assistant.",
          "error"
        );
      }
      throw err;
    }
  }

  _getAuthTokenSync() {
    if (!this._hass?.auth) {
      return null;
    }
    if (this._hass.auth.accessToken) {
      return this._hass.auth.accessToken;
    }
    if (this._hass.auth.data?.accessToken) {
      return this._hass.auth.data.accessToken;
    }
    return null;
  }

  async generateReportComplete(event) {
    const btn = this._qs("#generateReportBtn") || event?.target;
    if (!btn) {
      this._showStatus("<strong>Error:</strong> Generate button not found.", "error");
      return;
    }
    const originalHTML = btn.dataset.originalHtml || btn.innerHTML;
    if (!btn.dataset.originalHtml) {
      btn.dataset.originalHtml = originalHTML;
    }
    const days = this._qs("#timeRange").value;

    btn.disabled = true;
    btn.querySelectorAll(".spinner").forEach((node) => node.remove());
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
      btn.innerHTML = btn.dataset.originalHtml || originalHTML;
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
      btn.innerHTML = btn.dataset.originalHtml || originalHTML;
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

  async loadCleanupConfig() {
    try {
      const data = await this._callApi("GET", "energy_reports/api/cleanup/config");
      if (data.status === "success") {
        const retentionDays = data.config.retention_days || 0;
        this._qs("#cleanupRetentionDays").value = retentionDays;
      }
    } catch (error) {
      // No-op
    }
  }

  async saveCleanupConfig() {
    const retentionDays = parseInt(this._qs("#cleanupRetentionDays").value, 10);
    const enabled = retentionDays > 0;
    try {
      const data = await this._callApi("POST", "energy_reports/api/cleanup/config", {
        enabled,
        retention_days: retentionDays,
      });
      if (data.status === "success") {
        this._showStatus(
          enabled
            ? "<strong>Success!</strong> Auto-cleanup enabled."
            : "<strong>Success!</strong> Auto-cleanup disabled.",
          "success"
        );
      } else {
        this._showStatus(`<strong>Error:</strong> ${data.message}`, "error");
      }
    } catch (error) {
      this._showStatus("<strong>Error:</strong> Failed to save cleanup configuration", "error");
    }
  }

  async runCleanupNow() {
    try {
      const data = await this._callApi("POST", "energy_reports/api/cleanup/run", {});
      if (data.status === "success") {
        this._showStatus(`<strong>Success!</strong> ${data.message}`, "success");
        await this.loadReports();
      } else {
        this._showStatus(`<strong>Error:</strong> ${data.message}`, "error");
      }
    } catch (error) {
      this._showStatus("<strong>Error:</strong> Cleanup failed", "error");
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
                <ha-icon icon="mdi:file-document-outline" style="--mdc-icon-size: 20px; color: #4CAF50;"></ha-icon>
                <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${report.filename}</span>
              </div>
              <div class="device-id" style="display: flex; gap: 16px; margin-top: 4px;">
                <span><ha-icon icon="mdi:clock-outline" style="--mdc-icon-size: 14px; vertical-align: middle;"></ha-icon> ${report.created}</span>
                <span><ha-icon icon="mdi:folder-outline" style="--mdc-icon-size: 14px; vertical-align: middle;"></ha-icon> ${report.size_kb} KB</span>
              </div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; flex-shrink: 0;">
              <button class="btn" onclick="downloadSpecificReport('${report.filename}')" style="padding: 0; width: 44px; height: 44px; min-width: 44px; display: inline-flex; align-items: center; justify-content: center; background: #03a9f4;">
                <ha-icon icon="mdi:download" style="--mdc-icon-size: 22px; line-height: 0;"></ha-icon>
              </button>
              <button class="btn" onclick="deleteReport('${report.filename}')" style="padding: 0; width: 44px; height: 44px; min-width: 44px; display: inline-flex; align-items: center; justify-content: center; background: #f44336; box-shadow: 0 2px 6px rgba(244, 67, 54, 0.4);">
                <ha-icon icon="mdi:delete" style="--mdc-icon-size: 22px; line-height: 0;"></ha-icon>
              </button>
            </div>
          `;
          container.appendChild(item);
        });
        this._replaceMaterialIcons();
      } else {
        container.innerHTML =
          '<div style="text-align: center; padding: 20px; color: #9b9b9b;">No reports generated yet</div>';
        this._replaceMaterialIcons();
      }
    } catch (error) {
      this._qs("#reportsList").innerHTML =
        '<div style="text-align: center; padding: 20px; color: #e57373;">Failed to load reports</div>';
      this._replaceMaterialIcons();
    }
  }

  async downloadSpecificReport(filename) {
    try {
      if (!this._hass) {
        this._hass = this._resolveParentHass();
      }
      if (!this._hass) {
        throw new Error("Home Assistant not ready");
      }

      const token = this._getAuthTokenSync();
      if (!token) {
        throw new Error("Missing auth token");
      }
      const resp = await fetch(`/api/energy_reports/api/reports/${filename}`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        credentials: "include",
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      }

      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      this._showStatus(`<strong>Error:</strong> Download failed (${error})`, "error");
    }
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
