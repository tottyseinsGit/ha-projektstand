# Projektstatus – Home Assistant Betriebskostenabrechnung  
*(Stand: 05.10.2025, Europe/Berlin – erstellt 05.10.2025, 17:00 UTC+02:00)*

> **Ziel:** Jahresneutrale Betriebskostenabrechnung je Wohnung (WHG01–WHG04) **plus Hausgesamt**, per Button erzeugte **PDF**, **ohne** jährliche Codeänderungen. Das Abrechnungsjahr wird über den Helper `input_number.abrechnungsjahr` gesetzt.

---

## Inhaltsverzeichnis

1. [Architektur-Überblick](#1-architektur-überblick)  
2. [Grundsatz-Entscheidung (Naming & Jahreslogik)](#2-grundsatz-entscheidung-naming--jahreslogik)  
3. [Relevante HA-Dateien (Auszug)](#3-relevante-ha-dateien-auszug)  
4. [Export-Server (Ubuntu) – aktueller Stand](#4-export-server-ubuntu--aktueller-stand)  
5. [PDF-Vorlage (Server) – `bk_whg01.html`](#5-pdf-vorlage-server--bk_whg01html)  
6. [„Happy Path“ – Schritt-für-Schritt PDF-Erzeugung](#6-happy-path--schritt-für-schritt-pdf-erzeugung)  
7. [Aktuell verifizierte Datenpunkte](#7-aktuell-verifizierte-datenpunkte)  
8. [Troubleshooting (Kurz & knackig)](#8-troubleshooting-kurz--knackig)  
9. [Offene ToDos (geordnet, „einmal richtig“)](#9-offene-todos-geordnet-einmal-richtig)  
10. [Validierung: Preflight-Checkliste vor dem Export](#10-validierung-preflight-checkliste-vor-dem-export)  
11. [Cheatsheet: Befehle & Beispiele](#11-cheatsheet-befehle--beispiele)  
12. [Anhang A: Pfade & URLs auf einen Blick](#12-anhang-a-pfade--urls-auf-einen-blick)  
13. [Anhang B: Entity-Naming-Matrix (WHG01)](#13-anhang-b-entity-naming-matrix-whg01)  
14. [Changelog](#14-changelog)

---

## 1) Architektur-Überblick

- **Home Assistant (HA)**
  - **Frontend / Supervisor:** `http://192.168.178.60:8123`
  - **VM (Proxmox):** `192.168.178.94`
  - **Statischer Web-Pfad:** `/config/www` → im Browser als `/local/...`
  - **Export-Ziel für PDFs:** `/config/www/exports`  
    (teilweise zusätzlich eingebunden als `/share/ha_www/www/exports`; im Browser **immer** `http://192.168.178.60:8123/local/exports/...`)

- **Export-Server (Ubuntu)**
  - **Host/IP:** `192.168.178.5`
  - **App-Verzeichnis:** `/opt/bk-export`
  - **Server-App:** `/opt/bk-export/app.py` (Flask + Gunicorn)
  - **Vorlage (serverseitig, Jinja):** `/opt/bk-export/templates/bk_whg01.html`
  - **PDF-Engine:** `wkhtmltopdf` (0.12.6)
  - **Systemd-Dienst:** `bk-export.service` (läuft als Benutzer `torsten`)
  - **Schreibt PDFs/HTML nach:** `/share/ha_www/www/exports`  
    (entspricht in HA: `/config/www/exports`)

- **Kommunikationsfluss**
  1. HA berechnet/aggregiert **jahresneutrale** Beträge in Sensoren (z. B. `sensor.whg01_wasser_anteil_eur`).
  2. HA ruft per **REST GET** die Export-Route auf:  
     `http://192.168.178.5:5000/export?...` und übergibt Beträge + Meta.
  3. Export-Server rendert `bk_whg01.html` → erzeugt **versionierte PDF** + `latest`-Alias.
  4. HA-Benachrichtigung enthält **absoluten** Link:  
     `http://192.168.178.60:8123/local/exports/bk_<jahr>_latest.pdf?v=<ts>`

---

## 2) Grundsatz-Entscheidung (Naming & Jahreslogik)

- **Entscheidung: _Option B (jahresneutral)_**
  - HA-Templates/Sensoren arbeiten **ohne Jahres-Suffix** (z. B. `sensor.whg01_wasser_anteil_eur`).
  - Das **aktuelle Abrechnungsjahr** kommt aus `input_number.abrechnungsjahr`.
  - Die serverseitige PDF-Vorlage erwartet **unsuffixed** Felder (alias‑freundlich).  
    → Kein jährliches Umbenennen der Sensoren/Keys mehr nötig.

> **Aufräumen:** Historische/duplizierte Sensoren (`*_2`, `*_2025_2`) **entfernen/deaktivieren**, damit alle Referenzen eindeutig sind.

---

## 3) Relevante HA-Dateien (Auszug)

- `/config/packages/31_zaehler_whg01.yaml`  
  - MQTT-Zähler **Kaltwasser** (`sensor.whg01_wasser_total_m3`)  
  - Vormontage-Helper: `input_number.whg01_wasser_kalt_vormontage_m3`  
  - Abgeleitet: `sensor.whg01_wasser_kalt_m3_gesamt` (**OK**)  
  - **Letzter Monat**-History-Sensor ergänzt & korrigiert (zeigt jetzt korrekt).

- `/config/packages/42_abrechnung_whg01_bridge.yaml`  
  - Brücke/Vormontage + Aufsummierung je Wohnung (Kalt/Warm Wasser).

- `/config/packages/42_abrechnung_whg01_wasser.yaml`  
  - Berechnung **Wasser-Anteile** auf Basis `sensor.whg01_wasser_kalt_m3_gesamt`, optional Warm, und `sensor.haus_kosten_wasser_eur_m3_eff`.

- `/config/packages/42_abrechnung.yaml`  
  - Summiert **WHG01-Kosten gesamt** (erwartet jahresneutral benannte `*_anteil_eur`‑Sensoren **ohne** Suffix).

- `/config/packages/10_stammdaten_haus.yaml`  
  - Verteilerschlüssel (Fläche/Personen), Haus-Kosten/Meta.

- `/config/packages/20_mieter_whg01.yaml`  
  - Mieter/WHG-Stammdaten (Vorname, Nachname, Fläche, Personen, etc.).

- `/config/packages/99_bk_export.yaml`  
  - **rest_command** zu `192.168.178.5:5000/export` (GET) mit allen Kostenfeldern.  
  - **script.export_betriebskosten_pdf_now** + Button + Benachrichtigung (mit **absolutem** HA-Link auf `/local/exports/...` inkl. Cache‑Buster).

---

## 4) Export-Server (Ubuntu) – aktueller Stand

- **wkhtmltopdf:** installiert (0.12.6)
- **Gunicorn-Dienst:** `bk-export.service` aktiv auf Port **5000**  
  (Alt-Prozess `/root/bkexport/server.py` wurde entfernt; verursachte „Test-PDF“ + Port-Konflikte).
- **Schreibrechte:** Export-Ordner auf **torsten:torsten** gestellt, Rechte angepasst.

**Typische Fehlerbilder & Lösungen**  
- *Graue Seite*: PDF war HTML (Fallback). Meist fehlende `wkhtmltopdf`-Nutzung → gefixt.  
- *500 Internal Server Error*: `PermissionError` beim Schreiben nach `/share/…/exports` → Rechte gefixt.  
- *„Test-PDF“ weiterhin*: kam vom **alten** Exporter → Prozess beseitigt.

> **Hinweis:** Wenn die Unit-Datei geändert wurde, danach  
> `sudo systemctl daemon-reload` ausführen, dann `sudo systemctl restart bk-export`.

---

## 5) PDF-Vorlage (Server) – `bk_whg01.html`

- Erwartet (unsuffixed) **Query-Parameter**:  
  `wasser_anteil_eur`, `abwasser_anteil_eur`, `strom_variabel_anteil_eur`,  
  `strom_grundpreis_anteil_eur`, `grundsteuer_anteil_eur`, `versicherung_anteil_eur`,  
  `muell_anteil_eur`, `niederschlagswasser_anteil_eur`, `wartung_heizung_anteil_eur`,  
  `abrechnungsservice_anteil_eur`, `betriebskosten_summe_eur`, plus Meta (`wohnung`, `abrechnungsjahr`, `created_at`, …).
- Darstellung: A4, Tabelle **Kostenübersicht**, **Gesamtsumme**.

---

## 6) „Happy Path“ – Schritt-für-Schritt PDF-Erzeugung

1. In HA: `input_number.abrechnungsjahr` auf z. B. **2025** setzen.  
2. Prüfen, dass **alle Anteil-Sensoren** für WHG01 befüllt sind (Wasser, Abwasser, Strom **variabel + Grundpreis**, Grundsteuer, Versicherung, Müll, Niederschlag, Wartung Heizung, optional Abrechnungsservice) **ohne Suffix**.  
3. In HA den Button **„Export Betriebskosten PDF“** klicken. HA sendet GET an `http://192.168.178.5:5000/export?...`.  
4. Benachrichtigung zeigt Link:  
   `http://192.168.178.60:8123/local/exports/bk_<jahr>_latest.pdf?v=<timestamp>`  
5. PDF zeigt die **realen Beträge** aus Schritt 2.

---

## 7) Aktuell verifizierte Datenpunkte (Beispiele)

- `sensor.whg01_wasser_total_m3` = **5.359**  
- `input_number.whg01_wasser_kalt_vormontage_m3` = **0.026**  
- `sensor.whg01_wasser_kalt_m3_gesamt` = **5.385** (**OK**)  
- `sensor.whg01_wasser_warm_m3_gesamt` = **0.0** (Warmzähler fehlt)  
- `input_number.abrechnungsjahr` = **2025**  
- **Wasserpreis (effektiv)**: `sensor.haus_kosten_wasser_eur_m3_eff` = **1.52 € / m³**  
- **Diagnose-Test**: ergab z. B. **8.61 €** Wasseranteil (plausibel).

---

## 8) Troubleshooting (Kurz & knackig)

- **„PDF zeigt nur ‚Test-PDF‘“**  
  → Prüfen, dass **kein** Alt-Prozess läuft:  
  `sudo ss -lntp | grep ':5000'`  
  Erwartet: nur **gunicorn** aus `/opt/bk-export/venv/...`.  
  Falls `/root/bkexport/server.py` sichtbar → Prozess **killen**, Autostart **deaktivieren**.

- **Graue Seite statt PDF**  
  → `wkhtmltopdf` prüfen (`wkhtmltopdf -V`) und Service-Logs:  
  `sudo journalctl -u bk-export -n 50 --no-pager`  
  Außerdem: `file /share/ha_www/www/exports/bk_<jahr>_latest.pdf` → muss „PDF document“ sein.

- **500 Internal Server Error**  
  → Fast immer **Rechteproblem** im Export-Ordner:  
  ```bash
  sudo chown -R torsten:torsten /share/ha_www/www/exports
  find /share/ha_www/www/exports -type d -exec chmod 755 {} \;
  find /share/ha_www/www/exports -type f -exec chmod 644 {} \;
  ```

- **PDF-Link in HA öffnet Startseite**  
  → Link **muss absolut** sein und auf die HA-IP zeigen:  
  `http://192.168.178.60:8123/local/exports/...` (nicht `192.168.178.5`).

- **Leere/unknown Sensoren**  
  → Doppelte IDs entfernen (`*_2`, `*_2025_2`), Naming vereinheitlichen (unsuffixed).  
  → Templates neu laden / HA **neu starten**.

---

## 9) Offene ToDos (geordnet, „einmal richtig“)

1. **Sensoren konsolidieren (WHG01)**  
   - Doppelte/alte Sensoren (`*_2`, `*_2025_2`) **deaktivieren/entfernen**.  
   - Für **alle** Kostenpositionen sicherstellen, dass **unsuffixed** `sensor.whg01_*_anteil_eur` existieren und befüllt sind:  
     - Wasser, Abwasser, Strom (variabel + Grundpreis), Grundsteuer, Versicherung, Müll, Niederschlagswasser, Wartung Heizung, optional Abrechnungsservice.  
   - **Summe**: `sensor.whg01_betriebskosten_summe_eur` (Summe aus Positionen) prüfen.

2. **Verteilerschlüssel**  
   - `input_select.haus_verteilerschluessel` (`flaeche` / `personen`) verlässlich auswerten → Anteilfaktoren je Wohnung berechnen und in den `*_anteil_eur`‑Templates verwenden.

3. **Strom-Zähler & -Kosten**  
   - `sensor.whg01_strom_kwh_gesamt_auto` (o. ä.) stabil speisen.  
   - `sensor.haus_kosten_strom_eur_kwh_eff` + **Grundpreis-Verteilung** je Wohnung klären.

4. **Warmwasserzähler** *(optional)*  
   - Sobald vorhanden: `sensor.whg01_wasser_warm_m3_gesamt` in Wasser-/Abwasser‑Logik einbeziehen.

5. **Mieter/Meta anzeigen** *(optional)*  
   - In Server‑Template: Vorname/Nachname, Tel, E‑Mail, Ein-/Auszug, Wohnfläche, Personen (via GET‑KV oder später DB).

6. **Hausgesamt-PDF & WHG02–WHG04**  
   - Gleiche Struktur, Präfixe/Summen anpassen.  
   - Button pro Wohnung **plus** Hausgesamt.

---

## 10) Validierung: Preflight-Checkliste vor dem Export

- [ ] `input_number.abrechnungsjahr` auf gewünschtes Jahr gesetzt  
- [ ] Alle `sensor.whg01_*_anteil_eur` vorhanden und **nicht** `unknown/unavailable`  
- [ ] `sensor.whg01_betriebskosten_summe_eur` entspricht Summe der Positionen  
- [ ] Export‑Server erreichbar: `curl -sS http://192.168.178.5:5000/health` *(falls vorhanden)*  
- [ ] `wkhtmltopdf -V` liefert 0.12.6  
- [ ] Ordner-Berechtigungen `/share/ha_www/www/exports` passend (`torsten:torsten`, 755/644)  
- [ ] Kein Alt‑Prozess auf Port 5000 (`ss -lntp | grep ':5000'`)

---

## 11) Cheatsheet: Befehle & Beispiele

**Dienst-Status & Logs**
```bash
sudo systemctl status bk-export --no-pager
sudo journalctl -u bk-export -n 50 --no-pager
# Nach Unit-Änderungen:
sudo systemctl daemon-reload && sudo systemctl restart bk-export
```

**Port-Belegung prüfen (soll nur gunicorn sein)**
```bash
sudo ss -lntp | grep ':5000'
```

**Test-Export (Zahlen sichtbar, zum Gegenprüfen)**
```bash
curl -sS "http://192.168.178.5:5000/export?wohnung=WHG01&abrechnungsjahr=2025&wasser_anteil_eur=12.34&abwasser_anteil_eur=5.67&strom_variabel_anteil_eur=0&strom_grundpreis_anteil_eur=0&grundsteuer_anteil_eur=0&versicherung_anteil_eur=0&muell_anteil_eur=0&niederschlagswasser_anteil_eur=0&wartung_heizung_anteil_eur=0&abrechnungsservice_anteil_eur=0&betriebskosten_summe_eur=18.01"
```

**Datei-Typ prüfen (muss „PDF document“ sein)**
```bash
file /share/ha_www/www/exports/bk_2025_latest.pdf
```

**Absoluter Link in HA-Benachrichtigung**
```text
http://192.168.178.60:8123/local/exports/bk_<jahr>_latest.pdf?v=<timestamp>
```

---

## 12) Anhang A: Pfade & URLs auf einen Blick

| Kontext            | Pfad/URL |
|--------------------|---------|
| HA Frontend        | `http://192.168.178.60:8123` |
| HA statisches Root | `/config/www` → Browser: `/local/...` |
| HA Export-Ordner   | `/config/www/exports` |
| Export-Server Host | `http://192.168.178.5:5000` |
| Exporter App       | `/opt/bk-export/app.py` |
| Systemd Unit       | `bk-export.service` |
| Jinja Vorlage      | `/opt/bk-export/templates/bk_whg01.html` |
| Share-Mount        | `/share/ha_www/www/exports` (entspricht HA `/config/www/exports`)|

---

## 13) Anhang B: Entity-Naming-Matrix (WHG01)

| Zweck | Entity (jahresneutral) |
|------|-------------------------|
| Kaltwasser Stand gesamt | `sensor.whg01_wasser_kalt_m3_gesamt` |
| Warmwasser Stand gesamt *(optional)* | `sensor.whg01_wasser_warm_m3_gesamt` |
| Wasser-Anteil € | `sensor.whg01_wasser_anteil_eur` |
| Abwasser-Anteil € | `sensor.whg01_abwasser_anteil_eur` |
| Strom variabel € | `sensor.whg01_strom_variabel_anteil_eur` |
| Strom Grundpreis € | `sensor.whg01_strom_grundpreis_anteil_eur` |
| Grundsteuer € | `sensor.whg01_grundsteuer_anteil_eur` |
| Versicherung € | `sensor.whg01_versicherung_anteil_eur` |
| Müll € | `sensor.whg01_muell_anteil_eur` |
| Niederschlagswasser € | `sensor.whg01_niederschlagswasser_anteil_eur` |
| Wartung Heizung € | `sensor.whg01_wartung_heizung_anteil_eur` |
| Abrechnungsservice € *(optional)* | `sensor.whg01_abrechnungsservice_anteil_eur` |
| **Summe** | `sensor.whg01_betriebskosten_summe_eur` |

> **Hinweis:** Bitte alte/duplizierte Varianten (`*_2`, `*_2025_2`) entfernen.

---

## 14) Changelog

- **05.10.2025**  
  - Architektur, Naming und Export-Flow **konsolidiert**.  
  - Alt-Prozesse/Port-Konflikte dokumentiert; Rechte-Thematik behoben.  
  - **Preflight-Checkliste** ergänzt, **Anhang** (Pfade, Entities) hinzugefügt.  
  - Klarstellung: HA-Benachrichtigungslink **immer absolut** auf 192.168.178.60.

---

**Kurz-Fazit:**  
Die wesentlichen Bausteine sind funktionsfähig (jahresneutraler Datenpfad, Export-Server, PDF-Erzeugung). Nächste Hebel mit größtem Effekt: *Sensorenkonsolidierung WHG01*, belastbare *Stromkostenermittlung* (variabel+Grundpreis), und *Verteilerschlüssel*-Durchstich. Danach zügig auf *Hausgesamt* + *WHG02–WHG04* ausrollen.
