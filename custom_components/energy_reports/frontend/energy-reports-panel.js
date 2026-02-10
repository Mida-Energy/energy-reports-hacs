class EnergyReportsPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
  }

  connectedCallback() {
    if (this._root) {
      return;
    }
    this._root = this.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = `
      :host {
        display: block;
        height: 100%;
      }
      iframe {
        border: 0;
        width: 100%;
        height: 100vh;
        background: transparent;
      }
    `;

    this._iframe = document.createElement("iframe");
    this._iframe.src = "/api/energy_reports/";

    this._root.append(style, this._iframe);
  }
}

customElements.define("energy-reports-panel", EnergyReportsPanel);
