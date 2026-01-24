# Energy Reports - Home Assistant (HACS)

Genera report PDF professionali dai tuoi Shelly direttamente in Home Assistant, con una UI integrata nella sidebar.

## Requisiti

- Home Assistant Core/Supervised/OS
- HACS installato
- Integrazione Shelly già configurata

## Installazione tramite HACS

1. HACS → **Integrations**
2. Menu in alto a destra → **Custom repositories**
3. Aggiungi questo repo con categoria **Integration**
4. Cerca **Energy Reports** e installa
5. Riavvia Home Assistant

> Dopo il riavvio, comparirà la voce **Energy Reports** nella sidebar.

## Uso

1. Apri **Energy Reports** dalla sidebar
2. Seleziona i dispositivi
3. **Collect Data** (recupera lo storico da HA)
4. **Generate Report** per creare i PDF
5. Scarica o elimina i report dalla sezione **Reports History**

## Dove vengono salvati i file

- Dati CSV: `/config/energy_reports/data`
- Output temporanei: `/config/energy_reports/output`
- PDF finali: `/config/energy_reports/pdfs`

## Note importanti

- Questa versione è una **custom integration HACS** (non add-on).
- Non usa Supervisor né Ingress: la UI è servita internamente da Home Assistant.
- Ogni istanza HA genera i propri report in modo indipendente (perfetto per più istanze).
- Se la voce in sidebar non compare, puoi aggiungere un pannello manuale:
  ```yaml
  panel_iframe:
    energy_reports:
      title: Energy Reports
      icon: mdi:chart-line
      url: /api/energy_reports/
  ```

## Troubleshooting

### Non vedo la voce in sidebar

- Verifica di aver riavviato HA dopo l’installazione.
- Controlla i log per errori dell’integrazione.

### Nessun PDF generato

- Verifica che ci siano dati storici per i sensori selezionati.
- Controlla in `/config/energy_reports/data` che esista `all.csv`.

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
