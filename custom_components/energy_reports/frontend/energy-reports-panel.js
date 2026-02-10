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
      throw new Error("Home Assistant non pronto");
    }

    let token = null;
    try {
      token = await this._hass.auth.getAccessToken();
    } catch (err) {
      token = null;
    }

    const options = {
      method,
      headers: {},
      credentials: "include",
    };

    if (token) {
      options.headers.Authorization = `Bearer ${token}`;
    }

    if (data !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(data);
    }

    const resp = await fetch(`/api/${path}`, options);
    const text = await resp.text();

    if (!resp.ok) {
      if (resp.status === 401 || resp.status === 403) {
        this._showStatus(
          "<strong>Non autorizzato:</strong> assicurati di essere loggato in Home Assistant.",
          "error"
        );
      }
      const message = text ? text.slice(0, 200) : resp.statusText;
      throw new Error(message || "Non autorizzato");
    }

    return text ? JSON.parse(text) : {};
  }

  async generateReportComplete() {
    const btn = this._qs("#generateReportBtn");
    const originalHTML = btn.innerHTML;
    const days = this._qs("#timeRange").value;

    btn.disabled = true;
    btn.innerHTML = `${originalHTML} <span class="spinner"></span>`;
    this._showStatus(
      `<strong>Step 1/2:</strong> Recupero dati da Home Assistant (ultimi ${days} giorni)...`,
      "info"
    );

    try {
      await this._callApi("POST", "energy_reports/collect-data", { days: parseInt(days, 10) });
      this._showStatus(
        "<strong>Step 2/2:</strong> Generazione report PDF... Attendi.",
        "info"
      );
      const genData = await this._callApi("POST", "energy_reports/generate", {});
      btn.disabled = false;
      btn.innerHTML = originalHTML;
      this._qs("#status").style.display = "none";

      if (genData.status === "success") {
        this._showStatus(
          `<strong>Successo!</strong> Report generato (${genData.pdf_size_kb} KB). Vedi la cronologia report qui sotto.`,
          "success"
        );
        await this.loadReports();
      } else {
        this._showStatus(`<strong>Errore:</strong> ${genData.message}`, "error");
      }
    } catch (error) {
      btn.disabled = false;
      btn.innerHTML = originalHTML;
      this._qs("#status").style.display = "none";
      this._showStatus(`<strong>Errore di rete:</strong> ${error}`, "error");
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
        this._qs("#deviceList").innerHTML = `<div style="text-align: center; padding: 20px; color: #e57373;">Errore: ${
          data.message || "Errore sconosciuto"
        }</div>`;
      }
    } catch (error) {
      this._qs("#deviceList").innerHTML = `<div style="text-align: center; padding: 20px; color: #e57373;">Impossibile caricare i dispositivi: ${error.message}</div>`;
    }
  }

  renderDeviceList() {
    const container = this._qs("#deviceList");
    if (this.availableEntities.length === 0) {
      container.innerHTML =
        '<div style="text-align: center; padding: 20px; color: #9b9b9b;">Nessun dispositivo Shelly trovato</div>';
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
          `<strong>Successo!</strong> Salvati ${this.selectedEntities.length} dispositivi per la generazione report.`,
          "success"
        );
      } else {
        this._showStatus(`<strong>Errore:</strong> ${data.message}`, "error");
      }
    } catch (error) {
      this._showStatus("<strong>Errore:</strong> Salvataggio selezione fallito", "error");
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
            ? "<strong>Successo!</strong> Generazione automatica programmata."
            : "<strong>Successo!</strong> Generazione automatica disattivata.",
          "success"
        );
      } else {
        this._showStatus(`<strong>Errore:</strong> ${data.message}`, "error");
      }
    } catch (error) {
      this._showStatus("<strong>Errore:</strong> Salvataggio configurazione fallito", "error");
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
          '<div style="text-align: center; padding: 20px; color: #9b9b9b;">Nessun report generato</div>';
      }
    } catch (error) {
      this._qs("#reportsList").innerHTML =
        '<div style="text-align: center; padding: 20px; color: #e57373;">Impossibile caricare i report</div>';
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
        this._showStatus("<strong>Successo!</strong> Report eliminato.", "success");
        await this.loadReports();
      } else {
        this._showStatus(`<strong>Errore:</strong> ${data.message}`, "error");
      }
    } catch (error) {
      this._showStatus("<strong>Errore:</strong> Eliminazione report fallita", "error");
    }
  }
}

customElements.define("energy-reports-panel", EnergyReportsPanel);
