# Packages – Projektregeln (Home Assistant)

**Ziel:** Einheitliche Struktur. Änderungen schnell finden, Komponenten sauber trennen.

## Standard
- Alles thematisch in `/config/packages/` – *pro Gerät/Feature eine Datei* (`ohmpilot.yaml`, `waermepumpe.yaml`, …).
- Keine neuen Einträge mehr in `sensor.yaml`, `template.yaml`, `utility_meter.yaml` (Altbestand bleibt, wird migriert).
- Eigene JS-Cards nur über **Einstellungen → Dashboards → Ressourcen** (Typ *JavaScript-Modul*). Kein `extra_module_url` für eigene JS. Pro Datei **genau 1** Eintrag; Updates via `?v=`.
- Entity-IDs: ASCII `snake_case`, keine Umlaute; Friendly Names deutsch.
- `device_class`/`state_class` korrekt setzen (energy: `total_increasing`, power: `measurement`).

## Struktur
/config
├─ configuration.yaml # minimal, bindet Packages ein
├─ packages/
│ ├─ ohmpilot.yaml # Beispielpaket
│ └─ README.md # dieses Dokument
├─ www/ # /local/
└─ …

## Workflow
1. Neue Funktion ⇒ **neue Datei** in `/config/packages/<thema>.yaml`.
2. Einstellungen → Entwicklerwerkzeuge → YAML → **Konfiguration prüfen**.
3. **Neustart**.
4. Entities in Lovelace verwenden. JS-Card aktualisieren: 1 Ressourceneintrag, ggf. `?v` erhöhen.

## Troubleshooting (Kurz)
- „Custom element doesn’t exist“ → Ressource vorhanden? Nur 1 Eintrag? `?v` erhöhen.
- Utility-Meter zählt nicht → Quell-Sensor hat `device_class: energy`, `state_class: total_increasing`? Recorder nimmt die Entity auf?
- YAML → keine Tabs, saubere Einrückung, UTF-8 ohne BOM.
