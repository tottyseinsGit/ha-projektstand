# Projektstand – Allgemeiner Hausstrom (Betriebskosten 2025)

## Zielbild
- **Strikte Trennung** der Positionen:
  - **Fix**: Grundkosten (Jahresgrundgebühr) – *für Abrechnung aktuell nachrangig*
  - **Variabel**: Verbrauchskosten  
    - **Live ab Go-Live**: €/h = kWh_h × EPEX-Preis (Fallback: Arbeitspreis-Helper)  
    - **Nachtrag 1.1.→Go-Live**: Tage × (kWh/Tag) × (€/kWh)

---

## Verwendete Eingaben (Helper)
- **Go-Live-Datum:** `input_datetime.whg04_strom_montage`  → *z. B. 2025-09-25*
- **Arbeitspreis €/kWh:** `input_number.haus_kosten_strom_arbeitspreis_eur_kwh`  → *z. B. 0.2998*
- **kWh/Tag (Schätzung):** `input_number.haus_allgemeinstrom_baseline_kwh_pro_tag_2025`  → *z. B. 20*
- **(Fix) Jahresgrundgebühr:** `input_number.haus_betriebskosten_strom_grundgebuehr_2025`
- **(optional) Startwert kWh:** `number.zaehler_haus_allgemein_haus_zahler_startwert_kanal_1_kwh`

## Messquellen
- **Gesamtzähler (S0, kWh):** `sensor.zaehler_xiao_c6_s0_kanal_1_energie_gesamt_kwh`
- **EPEX-Preis (€/kWh):**
  - Netto: `sensor.epex_spot_data_net_price`
  - Brutto: `sensor.epex_spot_data_price`

## Utility-Meter (kWh aus Gesamtzähler)
- `sensor.haus_allgemein_energy_hour_kwh`
- `sensor.haus_allgemein_energy_day_kwh`
- `sensor.haus_allgemein_energy_month_kwh`
- `sensor.haus_allgemein_energy_year_kwh`  
*(Quelle jeweils: `sensor.zaehler_xiao_c6_s0_kanal_1_energie_gesamt_kwh`)*

---

## Abgeleitete Entitäten (Variabel)

### Live ab Go-Live
- **€/h (EPEX, mit Fallback auf Arbeitspreis):**  
  `sensor.haus_allgemeinstrom_var_stunde_eur`  
  - nutzt Preis: **EPEX netto → EPEX brutto → `input_number.haus_kosten_strom_arbeitspreis_eur_kwh`**
  - Attribs: `kwh_stunde`, `preis_eur_kwh`, `preisquelle`

### Nachtrag 1.1.→Go-Live (pauschal)
- **Tage:** `sensor.haus_allgemeinstrom_nachtrag_tage_2025`  
  `= max(0, datum(Go-Live) – 2025-01-01)`
- **kWh:** `sensor.haus_allgemeinstrom_var_nachtrag_kwh_2025_jan1_golive`  
  `= Tage × (kWh/Tag)`
- **€:** `sensor.haus_allgemeinstrom_var_nachtrag_eur_2025_jan1_golive`  
  `= kWh × (€/kWh aus input_number.haus_kosten_strom_arbeitspreis_eur_kwh)`

> **Aktueller Sollwert (mit deinen Zahlen):**  
> Go-Live **25.09.2025** → **267 Tage**, kWh/Tag **20**, Preis **0.2998 €/kWh**  
> **Nachtrag kWh = 5 340** • **Nachtrag € ≈ 1 600,93**

### (Optional) Startwert-Methode
- `sensor.haus_allgemeinstrom_var_nachtrag_kwh_2025`  
- `sensor.haus_allgemeinstrom_var_nachtrag_eur_2025`  
> Idee: `(Gesamt – Startwert) – Jahres-kWh seit HA` (untere Schranke 0); × Arbeitspreis.

---

## Bekannte Stolpersteine & Status
- **Doppelte Definitionen**: Wenn eine Entität in **zwei YAML-Dateien** vorkommt, lädt HA u. U. die **ältere** (falsche Preisquelle ⇒ `preis_eur_kwh = 0`).  
  **Workaround umgesetzt:** alternative Datei mit **v2-IDs**:  
  `/config/packages/40_kosten_2025_haus_nachtrag_v2.yaml`  
  - `…nachtrag_tage_2025_v2`  
  - `…nachtrag_kwh_2025_jan1_golive_v2`  
  - `…nachtrag_eur_2025_jan1_golive_v2`
- **Index immer pflegen:** `ENTITY_INDEX.md` nach Änderungen neu erzeugen, committen, pushen.

---

## Anzeige (Tablet) – Minimal
**Eingaben zeigen:**  
- Go-Live (`input_datetime.whg04_strom_montage`)  
- kWh/Tag (`input_number.haus_allgemeinstrom_baseline_kwh_pro_tag_2025`)  
- €/kWh (`input_number.haus_kosten_strom_arbeitspreis_eur_kwh`)

**Ergebnisse zeigen:**  
- Nachtrag **kWh** (`…_nachtrag_kwh_2025_jan1_golive` *oder* `…_v2`)  
- Nachtrag **€** (`…_nachtrag_eur_2025_jan1_golive` *oder* `…_v2`)  
- Live **€/h** (`sensor.haus_allgemeinstrom_var_stunde_eur`)

---

## Nächste Schritte (Backlog)
1. **EPEX-Summen (€)** bauen (aus `…_var_stunde_eur`) → Tag/Monat/Jahr + „bis heute“.  
2. **Preis-Helper vereinheitlichen** im gesamten Repo (nur noch `input_number.haus_kosten_strom_arbeitspreis_eur_kwh`).  
3. **Doppelte Entitäten entfernen** (alte IDs), wenn v2-Varianten geprüft sind.  
4. **Optionale Summe kWh 2025 inkl. Nachtrag** (ein eigener Sensor, falls gewünscht).  
5. **ENTITY_INDEX.md** nach jedem Schritt neu generieren und pushen.

---

## Repo-/Dateipfade (Stand)
- Hauptpakete: **`/homeassistant/packages`** (Repo) → entspricht HA-`/config/packages` zur Laufzeit.
- Hausstrom-Dateien:
  - `40_kosten_2025_haus.yaml` (Hauptlogik, Preis-Helper umgestellt)  
  - `40_kosten_2025_haus_nachtrag_v2.yaml` (Konfliktfreie v2-Nachtrag-IDs)
