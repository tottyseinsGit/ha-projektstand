Projektstatus – Home Assistant Betriebskosten & Zähler (Stand: 2025-09-27 00:00)
0) Kurzfazit
Zähler- und Abrechnungslogik steht für WHG01 (Kaltwasser).
Kern-Entitäten jetzt jahresunabhängig (zukunftssicher), Jahreswerte werden über Aliasse für 2025 an die Gesamtabrechnung durchgereicht.
Preisstrategie Strom: Alle kWh zum Tibber-/EPEX-Preis, ohne Einspeisung. PV-CAPEX nicht als BK; PV-O&M nur bei konkreter Mietvertragsregelung.
Nächstes Ziel: Warmwasser, WMZ und WP für WHG01 genauso fertigstellen; danach WHG02–WHG04 nach gleichem Muster.
1) Architektur & Datenflüsse (Haus gesamt)
Strom
Hauptzähler (Tibber) = grid_import (kWh). Kein grid_export.
PV-Erzeugung (kWh) fließt vollständig als Eigenverbrauch in die Hauslast.
Hauslast = grid_import + pv_generation.
Unterzähler/Abgänge: WHG01–WHG04, EV, Hausstrom, WP (kWh-Totals).
Plausibilisierung: residual = house_total_load − Σ(Unterzähler), Soll |residual| < 2–3 %.
Wasser/Wärme
wmbusmeters → MQTT → HA-Entities via MQTT-Sensor (Totals) + Utility Meter (day/month/year).
2) Benennung & Konventionen
Prinzip
Kern-IDs ohne Jahreszahl (dauerhaft gültig): …_year, …_vormontage_*, …_gesamt.
Jahres-Aliasse 2025 nur für Summendatei (z. B. …_anteil_eur_2025).
Beispiel WHG01 – Wasser kalt
Total (MQTT): sensor.whg01_wasserzaehler_total_m3_kalt
Utility Meter (aktuelles Jahr): sensor.whg01_wasser_kalt_m3_year
Vormontage (aktuelles Jahr): input_number.whg01_wasser_kalt_vormontage_m3
Jahr gesamt (Kern): sensor.whg01_wasser_kalt_m3_gesamt
Abrechnung 2025 (Alias €):
sensor.whg01_wasser_anteil_eur_2025
sensor.whg01_abwasser_anteil_eur_2025
Kalibrierung UTM (falls nötig): Entwicklerwerkzeuge → Aktionen → utility_meter.calibrate → Entity sensor.whg01_wasser_kalt_m3_year → Wert = Nach-Montage-Jahresmenge (z. B. 3.955).
3) Aktueller technischer Stand (WHG01)
3.1 Kaltwasser – fertig
MQTT-Quelle: wmbusmeters/Wasserzaehler_Whg01 → sensor.whg01_wasserzaehler_total_m3_kalt
UTM (Year): sensor.whg01_wasser_kalt_m3_year (state_class: total_increasing)
Vormontage: input_number.whg01_wasser_kalt_vormontage_m3
Jahr gesamt: sensor.whg01_wasser_kalt_m3_gesamt = year + vormontage
€-Alias 2025: whg01_wasser_anteil_eur_2025, whg01_abwasser_anteil_eur_2025
Kontrollwerte (Beispiel): Total ≈ 3.95 m³ (seit Montage), Vormontage = 10.00 m³ → Jahr gesamt ~ 13.95 m³ (UTM ggf. kalibriert).
3.2 Warmwasser – angelegt, noch ohne Hardware
MQTT-Placeholder: wmbusmeters/Wasserzaehler_Whg01_Warm → sensor.whg01_wasserzaehler_total_m3_warm
UTM (Year): sensor.whg01_wasser_warm_m3_year
Vormontage: input_number.whg01_wasser_warm_vormontage_m3
Jahr gesamt: sensor.whg01_wasser_warm_m3_gesamt
€-Alias 2025: whg01_wasser_warm_anteil_eur_2025, whg01_abwasser_warm_anteil_eur_2025
3.3 WMZ (Wärmemenge) – angelegt
MQTT-Quelle: wmbusmeters/sensostar_wmz_94857143 → sensor.whg01_wmz_total_kwh
UTM (Year): sensor.whg01_wmz_kwh_year
Vormontage: input_number.whg01_wmz_vormontage_kwh
Jahr gesamt: sensor.whg01_wmz_kwh_gesamt
€-Alias 2025: whg01_wmz_anteil_eur_2025 (setzt input_number.haus_kosten_waermemenge_arbeitspreis_eur_kwh voraus)
3.4 Strom / WP – angelegt
Quelle: bestehender Unterzähler WP, Entity noch eintragen bei utility_meter.whg01_strom_wp_kwh_year.source
Vormontage: input_number.whg01_strom_wp_vormontage_kwh
Jahr gesamt: sensor.whg01_strom_wp_kwh_gesamt
€-Aliasse 2025:
Variabel: whg01_strom_variabel_anteil_eur_2025 (Tibber-/EPEX-Preis)
Grundpreis: whg01_strom_grundpreis_anteil_eur_2025 (aus input_number.whg01_strom_grundpreis_anteil_eur)
4) Preis- & Rechtsrahmen (Strom)
Arbeitspreis: interne Abrechnung = Tibber-/EPEX-Preis für alle kWh (einfach, gut erklärbar).
PV-CAPEX: nicht über Betriebskosten umlagefähig; Modernisierungsumlage §559 BGB max. 8 %/Jahr (mit Kappungsgrenzen). Aktuell nicht genutzt.
PV-O&M: umlagefähig nur bei konkreter Benennung als „sonstige Betriebskosten“ im Mietvertrag.
Grundpreis Netz: separater Jahresbetrag, Verteilung nach Schlüssel (m²/Parteien/…).
Keine Einspeisung: grid_export = 0 → Hauslast = Netzbezug + PV-Erzeugung.
5) Oberflächen & Kontrolle
Zählerseite (31er-Dateien): Stammdaten (Montage, Eichfrist, Hersteller, RSSI) + Anzeige-Kernwerte (…_gesamt).
Kontroll-Template: zeigt UTM, Vormontage, Gesamt, €-Posten je Medium (bereit; funktioniert ohne Macros).
Strombilanz hausweit (geplant): Tiles für Netzbezug, PV, Hauslast, Σ-Unterzähler, Residual (%), Tag/Monat/Jahr.
6) Git & Betrieb
Einzeiler Sync:
git add -A && git commit -m "sync HA state" ; git push -u origin HEAD:main
Regel für Packages: pro Datei jeden Top-Level-Schlüssel nur einmal (mqtt, utility_meter, input_number, template).
MQTT-Sensoren initial „unbekannt“, bis erste (retained) Nachricht ankommt → Add-on kurz neu starten hilft.
7) Offene Punkte / To-dos (priorisiert)
WHG01 Strom/WP: Quelle (Entity-ID) im UTM eintragen, prüfen, ggf. UTM kalibrieren.
WHG01 Warmwasser: tatsächliches Topic setzen, sobald montiert; testen.
WHG01 WMZ: MQTT-Daten prüfen (Sensostar), ggf. Preishelper befüllen.
Bridges WHG02–WHG04: je Wohnung Kern-IDs + 2025-Aliasse anlegen.
Strombilanz hausweit: Residual-Berechnung + Warnsensor (>3 %).
Mietvertrag-Check: PV-O&M konkret als „sonstige BK“ aufnehmen, falls Umlage gewünscht.
ENTITY_INDEX.md: nachziehen (nur Doku).
8) Troubleshooting-Notizen
Utility-Meter zählt „ab Anlage“: rückwirkende Werte via Aktion utility_meter.calibrate setzen (Wert = Nach-Montage bis jetzt).
MQTT-Driver-Warnung (Engelmann WaterStar M): wmbusmeters meldet „unknown“ → trotzdem werden JSON-Felder dekodiert; Totals kommen an.
Mehrfach-Keys in Packages: führt zum Überschreiben früherer Blöcke → Symptome: „Helper/Entities fehlen“.
Dezimaltrennzeichen: in Aktionen . verwenden (3.955, nicht 3,955).
9) Nächste Schritte (konkret, kurz)
Heute: UTM Kaltwasser kalibrieren (3.955) → prüfen: …_m3_gesamt ≈ 13.955.
Morgen: WHG01 WP-Quelle eintragen und testen; Warmwasser-Topic vorbereiten; WMZ prüfen.
Danach: WHG02–WHG04 im selben Muster durchziehen; Strombilanz hinzufügen.