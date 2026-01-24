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

    const iframe = document.createElement("iframe");
    iframe.src = "/api/energy_reports/ui";

    this._root.append(style, iframe);
  }
}

customElements.define("energy-reports-panel", EnergyReportsPanel);
