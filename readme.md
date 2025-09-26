# GridCharge Setup – Stand 2025-08-29

**System**: Home Assistant • EPEX-Spot • Forecast.Solar • Victron MultiPlus-II 3000/48 (3‑phasig) • Fronius am **AC‑OUT** • Batterie 66 kWh NMC (SoC 15–90 %).

## Strategie (Kurzfassung)

* **PV vor Netz**: Erst Verbraucher, dann Akku mit PV. Netz‑Laden nur bei Bedarf.
* **Preis‑Schwelle** je Tag: `Schwelle = (Tages‑Peak × 0,90) − 0,0783 €/kWh`
  (η≈0,90 Rundreise; Verschleiß ≈ **0,0783 €/kWh** für 66 kWh / 12 400 € / 3000 Zyklen @ 80 % DoD.)
* **PV‑Peak blockiert Netz‑Laden** (Headroom für PV).
* **Defizit‑Entscheidung**: Wenn **PV (Rest heute) + Akku >15 %** < **Tagesverbrauch** ⇒ Netz‑Laden **nur** bei Preis ≤ Schwelle und Headroom bis SoC‑Max.

## Relevante Entitäten (anpassen, falls deine Namen abweichen)

* **EPEX Preis**: `sensor.epex_spot_data_net_price`, **Peak heute**: `sensor.epex_spot_data_highest_price`
* **EPEX Services**: `epex_spot.get_lowest_price_interval`, `epex_spot.get_highest_price_interval`
* **Forecast.Solar** (PV‑Prognose): z. B. `sensor.energy_production_remaining_today`
  (oder `sensor.forecast_solar_energy_production_remaining_today`)
* **PV‑Peak Zeitfenster (Forecast.Solar)**: `sensor.power_highest_peak_time_today_*` / `_tomorrow_*` (3/4/5/6/17h)
* **Akku SoC**: `sensor.victron_battery_soc`
* **Ladefreigabe‑Flag**: `input_boolean.strom_gridcharge_request`

---

## YAML #1 — *gridcharge\_minimal.yaml*

**Zweck:** Toggle **EIN/AUS**, wenn aktueller Preis ≤ Schwelle.

```yaml
# /config/packages/gridcharge_minimal.yaml
# Toggle EIN/AUS wenn Preis <= Schwelle
# Schwelle = (heutiger Peak * 0.90) - 0.0783 €/kWh

input_boolean:
  strom_gridcharge_enable:
    name: "GridCharge – aktiv"
    icon: mdi:battery-charging
    initial: true
  strom_gridcharge_request:
    name: "GridCharge – Ladefreigabe (Request)"
    icon: mdi:battery-arrow-down

template:
  - sensor:
      # Schwelle aus EPEX-Peak heute
      - name: "grid_threshold_eur_kwh"
        unique_id: grid_threshold_eur_kwh
        unit_of_measurement: "€/kWh"
        device_class: monetary
        state: >
          {% set peak = states('sensor.epex_spot_data_highest_price') | float(0) %}
          {{ (peak * 0.90 - 0.0783) | round(4) }}
        attributes:
          peak_today: "{{ states('sensor.epex_spot_data_highest_price') }}"
          eta: 0.90
          wear: 0.0783

  - binary_sensor:
      # „Günstig jetzt?“ → Preis <= Schwelle
      - name: "grid_price_profitable_now"
        unique_id: grid_price_profitable_now
        state: >
          {% set price = states('sensor.epex_spot_data_net_price') | float(999) %}
          {% set thr   = states('sensor.grid_threshold_eur_kwh') | float(0) %}
          {{ price <= thr and thr > 0 }}
        attributes:
          price_now: "{{ states('sensor.epex_spot_data_net_price') }}"
          threshold: "{{ states('sensor.grid_threshold_eur_kwh') }}"

automation:
  # Toggle Request je nach „günstig jetzt?“
  - id: gridcharge_toggle_on_price
    alias: "GridCharge – Toggle nach Preis"
    mode: restart
    trigger:
      - platform: state
        entity_id:
          - binary_sensor.grid_price_profitable_now
          - sensor.epex_spot_data_net_price
          - sensor.epex_spot_data_highest_price
      - platform: time_pattern
        minutes: "/5"
    condition:
      - condition: state
        entity_id: input_boolean.strom_gridcharge_enable
        state: "on"
    action:
      - choose:
          - conditions: "{{ is_state('binary_sensor.grid_price_profitable_now','on') }}"
            sequence:
              - service: input_boolean.turn_on
                target: { entity_id: input_boolean.strom_gridcharge_request }
          - conditions: "{{ is_state('binary_sensor.grid_price_profitable_now','off') }}"
            sequence:
              - service: input_boolean.turn_off
                target: { entity_id: input_boolean.strom_gridcharge_request }
```

---

## YAML #2 — *gridcharge\_pv\_priority.yaml* (mit **Forecast.Solar**)

**Zweck:** PV hat Vorrang; Netz‑Laden nur bei **Defizit** und **Preis ≤ Schwelle**.

```yaml
# PV-Priorität + EPEX-Preislogik mit Forecast.Solar
# Akku: 66 kWh, SoC_min 15 %, SoC_max 90 %, eta_roundtrip=0.90, wear=0.0783 €/kWh

input_boolean:
  strom_gridcharge_enable:
    name: "GridCharge – aktiv"
    icon: mdi:battery-charging
    initial: true
  strom_gridcharge_request:
    name: "GridCharge – Ladefreigabe (Request)"
    icon: mdi:battery-arrow-down

# Ø-Tagesverbrauch aus deinen 7 Tagen (375 kWh / 7 = 53.6 kWh)
input_number:
  avg_daily_consumption_kwh:
    name: "Ø Verbrauch heute [kWh]"
    min: 0
    max: 200
    step: 0.1
    unit_of_measurement: "kWh"
    mode: box
    initial: 53.6

template:
  - sensor:
      # 1) PV-Prognose "Remaining today" aus Forecast.Solar
      - name: "pv_forecast_remaining_today_kwh"
        unique_id: pv_forecast_remaining_today_kwh
        unit_of_measurement: "kWh"
        state: >
          {% set candidates = [
            'sensor.energy_production_remaining_today',
            'sensor.forecast_solar_energy_production_remaining_today'
          ] %}
          {% set val = None %}
          {% for e in candidates %}
            {% if states(e) not in ['unknown','unavailable',''] %}
              {% set val = states(e) | float(0) %}
            {% endif %}
          {% endfor %}
          {{ val if val is not none else 0 }}

      # 2) Schwelle aus heutigem Peakpreis (EPEX)
      - name: "grid_threshold_eur_kwh"
        unique_id: grid_threshold_eur_kwh
        unit_of_measurement: "€/kWh"
        device_class: monetary
        state: >
          {% set peak = states('sensor.epex_spot_data_highest_price') | float(0) %}
          {{ (peak * 0.90 - 0.0783) | round(4) }}

      # 3) Akku-Energie jetzt / Headroom
      - name: "battery_energy_now_kwh"
        unique_id: battery_energy_now_kwh
        unit_of_measurement: "kWh"
        state_class: measurement
        state: >
          {% set soc = states('sensor.victron_battery_soc') | float(0) %}
          {{ (66 * soc/100) | round(2) }}

      - name: "battery_energy_at_min_kwh"
        unique_id: battery_energy_at_min_kwh
        unit_of_measurement: "kWh"
        state: "{{ (66 * 0.15) | round(2) }}"  # 9.90 kWh @ 15 %

      - name: "battery_energy_above_min_kwh"
        unique_id: battery_energy_above_min_kwh
        unit_of_measurement: "kWh"
        state: >
          {% set e = states('sensor.battery_energy_now_kwh') | float(0) %}
          {% set emin = states('sensor.battery_energy_at_min_kwh') | float(0) %}
          {{ [e - emin, 0] | max | round(2) }}

      - name: "battery_headroom_to_max_kwh"
        unique_id: battery_headroom_to_max_kwh
        unit_of_measurement: "kWh"
        state: >
          {% set soc = states('sensor.victron_battery_soc') | float(0) %}
          {% set soc_max = 90 %}
          {{ (66 * (soc_max - soc)/100) | round(2) }}

      # 4) Tages-Defizit: was fehlt trotz PV & Akku>15 %
      - name: "grid_deficit_today_kwh"
        unique_id: grid_deficit_today_kwh
        unit_of_measurement: "kWh"
        state: >
          {% set load = states('input_number.avg_daily_consumption_kwh') | float(0) %}
          {% set pv   = states('sensor.pv_forecast_remaining_today_kwh') | float(0) %}
          {% set batt = states('sensor.battery_energy_above_min_kwh') | float(0) %}
          {{ [load - pv - batt, 0] | max | round(2) }}

  - binary_sensor:
      # PV reicht (inkl. Akku>15 %) -> kein Netzladen nötig
      - name: "pv_covers_today"
        unique_id: pv_covers_today
        state: >
          {{ (states('sensor.grid_deficit_today_kwh') | float(0)) == 0 }}

      # Preis aktuell rentabel?
      - name: "grid_price_profitable_now"
        unique_id: grid_price_profitable_now
        state: >
          {% set price = states('sensor.epex_spot_data_net_price') | float(999) %}
          {% set thr   = states('sensor.grid_threshold_eur_kwh') | float(0) %}
          {{ price <= thr and thr > 0 }}

      # Gesamtschalter: jetzt laden?
      - name: "gridcharge_should_charge_now"
        unique_id: gridcharge_should_charge_now
        state: >
          {{ is_state('input_boolean.strom_gridcharge_enable','on')
             and is_state('binary_sensor.pv_covers_today','off')
             and is_state('binary_sensor.grid_price_profitable_now','on')
             and (states('sensor.battery_headroom_to_max_kwh') | float(0)) > 0 }}

automation:
  - id: gridcharge_toggle_with_pv_priority
    alias: "GridCharge – PV-Prio + Preis (EIN/AUS)"
    mode: restart
    trigger:
      - platform: state
        entity_id:
          - binary_sensor.gridcharge_should_charge_now
          - sensor.epex_spot_data_net_price
          - sensor.epex_spot_data_highest_price
          - sensor.pv_forecast_remaining_today_kwh
          - input_number.avg_daily_consumption_kwh
          - sensor.victron_battery_soc
      - platform: time_pattern
        minutes: "/10"
    action:
      - choose:
          - conditions: "{{ is_state('binary_sensor.gridcharge_should_charge_now','on') }}"
            sequence:
              - service: input_boolean.turn_on
                target: { entity_id: input_boolean.strom_gridcharge_request }
        default:
          - service: input_boolean.turn_off
            target: { entity_id: input_boolean.strom_gridcharge_request }
```

---

## YAML #3 — *gridcharge\_pv\_priority.yaml* (mit **PV‑Peak‑Blocker**)

**Zweck:** Wie #2, zusätzlich **kein** Netz‑Laden während PV‑Kernfenster; inkl. Aufteilung *Daylight/Core/Shoulders* über Forecast.Solar‑Peak‑Sensoren.

```yaml
# PV-Priorität + EPEX-Preislogik + PV-Peak-Blocker (Forecast.Solar)
# Akku: 66 kWh, SoC_min 15 %, SoC_max 90 %, eta_roundtrip=0.90, wear=0.0783 €/kWh

input_boolean:
  strom_gridcharge_enable:
    name: "GridCharge – aktiv"
    icon: mdi:battery-charging
    initial: true
  strom_gridcharge_request:
    name: "GridCharge – Ladefreigabe (Request)"
    icon: mdi:battery-arrow-down

# Ø-Tagesverbrauch aus 7 Tagen: 375 kWh / 7 = 53.6 kWh
input_number:
  avg_daily_consumption_kwh:
    name: "Ø Verbrauch heute [kWh]"
    min: 0
    max: 200
    step: 0.1
    unit_of_measurement: "kWh"
    mode: box
    initial: 53.6

template:
  - sensor:
      # PV-Prognose "Remaining today" (Forecast.Solar)
      - name: "pv_forecast_remaining_today_kwh"
        unique_id: pv_forecast_remaining_today_kwh
        unit_of_measurement: "kWh"
        state: >
          {% set candidates = [
            'sensor.energy_production_remaining_today',
            'sensor.forecast_solar_energy_production_remaining_today'
          ] %}
          {% for e in candidates %}
            {% if states(e) not in ['unknown','unavailable','', None] %}
              {{ states(e) | float(0) }}
              {% break %}
            {% endif %}
          {% endfor %}
          {% if loop is defined and loop.index0 == 0 %}0{% endif %}

      # Schwelle aus heutigem EPEX-Peak
      - name: "grid_threshold_eur_kwh"
        unique_id: grid_threshold_eur_kwh
        unit_of_measurement: "€/kWh"
        device_class: monetary
        state: >
          {% set peak = states('sensor.epex_spot_data_highest_price') | float(0) %}
          {{ (peak * 0.90 - 0.0783) | round(4) }}

      # Akku-Energien
      - name: "battery_energy_now_kwh"
        unique_id: battery_energy_now_kwh
        unit_of_measurement: "kWh"
        state_class: measurement
        state: >
          {% set soc = states('sensor.victron_battery_soc') | float(0) %}
          {{ (66 * soc/100) | round(2) }}
      - name: "battery_energy_at_min_kwh"
        unique_id: battery_energy_at_min_kwh
        unit_of_measurement: "kWh"
        state: "{{ (66 * 0.15) | round(2) }}"
      - name: "battery_energy_above_min_kwh"
        unique_id: battery_energy_above_min_kwh
        unit_of_measurement: "kWh"
        state: >
          {% set e = states('sensor.battery_energy_now_kwh') | float(0) %}
          {% set emin = states('sensor.battery_energy_at_min_kwh') | float(0) %}
          {{ [e - emin, 0] | max | round(2) }}
      - name: "battery_headroom_to_max_kwh"
        unique_id: battery_headroom_to_max_kwh
        unit_of_measurement: "kWh"
        state: >
          {% set soc = states('sensor.victron_battery_soc') | float(0) %}
          {% set soc_max = 90 %}
          {{ (66 * (soc_max - soc)/100) | round(2) }}

      # --- PV-PEAK-FENSTER HEUTE ---
      - name: "pv_peak_today_start"
        unique_id: pv_peak_today_start
        state: >
          {% set opts = [
            {'id':'sensor.power_highest_peak_time_today_3','h':3},
            {'id':'sensor.power_highest_peak_time_today_4','h':4},
            {'id':'sensor.power_highest_peak_time_today_5','h':5},
            {'id':'sensor.power_highest_peak_time_today_6','h':6},
            {'id':'sensor.power_highest_peak_time_today_17','h':17}
          ] %}
          {% set found = namespace(ts='') %}
          {% for o in opts %}
            {% set v = states(o.id) %}
            {% if v not in ['unknown','unavailable','', None] %}
              {% set found.ts = v %}
              {% break %}
            {% endif %}
          {% endfor %}
          {{ (as_datetime(found.ts).strftime('%H:%M:%S')) if found.ts else 'unknown' }}
        attributes:
          hours: >
            {% set opts = [
              {'id':'sensor.power_highest_peak_time_today_3','h':3},
              {'id':'sensor.power_highest_peak_time_today_4','h':4},
              {'id':'sensor.power_highest_peak_time_today_5','h':5},
              {'id':'sensor.power_highest_peak_time_today_6','h':6},
              {'id':'sensor.power_highest_peak_time_today_17','h':17}
            ] %}
            {% for o in opts %}
              {% if states(o.id) not in ['unknown','unavailable','', None] %}
                {{ o.h }}
                {% break %}
              {% endif %}
            {% endfor %}
      - name: "pv_peak_today_end"
        unique_id: pv_peak_today_end
        state: >
          {% set opts = [
            {'id':'sensor.power_highest_peak_time_today_3','h':3},
            {'id':'sensor.power_highest_peak_time_today_4','h':4},
            {'id':'sensor.power_highest_peak_time_today_5','h':5},
            {'id':'sensor.power_highest_peak_time_today_6','h':6},
            {'id':'sensor.power_highest_peak_time_today_17','h':17}
          ] %}
          {% set ts = none %}{% set h = 0 %}
          {% for o in opts %}
            {% set v = states(o.id) %}
            {% if v not in ['unknown','unavailable','', None] %}
              {% set ts = as_datetime(v) %}{% set h = o.h %}{% break %}
            {% endif %}
          {% endfor %}
          {{ (ts + timedelta(hours=h)).strftime('%H:%M:%S') if ts else 'unknown' }}

      # --- PV-PEAK-FENSTER MORGEN (optional, Info) ---
      - name: "pv_peak_tomorrow_start"
        unique_id: pv_peak_tomorrow_start
        state: >
          {% set opts = [
            {'id':'sensor.power_highest_peak_time_tomorrow_3','h':3},
            {'id':'sensor.power_highest_peak_time_tomorrow_4','h':4},
            {'id':'sensor.power_highest_peak_time_tomorrow_5','h':5},
            {'id':'sensor.power_highest_peak_time_tomorrow_6','h':6},
            {'id':'sensor.power_highest_peak_time_tomorrow_17','h':17}
          ] %}
          {% set found = namespace(ts='') %}
          {% for o in opts %}
            {% set v = states(o.id) %}
            {% if v not in ['unknown','unavailable','', None] %}
              {% set found.ts = v %}
              {% break %}
            {% endif %}
          {% endfor %}
          {{ (as_datetime(found.ts).strftime('%Y-%m-%d %H:%M:%S')) if found.ts else 'unknown' }}
        attributes:
          hours: >
            {% set opts = [
              {'id':'sensor.power_highest_peak_time_tomorrow_3','h':3},
              {'id':'sensor.power_highest_peak_time_tomorrow_4','h':4},
              {'id':'sensor.power_highest_peak_time_tomorrow_5','h':5},
              {'id':'sensor.power_highest_peak_time_tomorrow_6','h':6},
              {'id':'sensor.power_highest_peak_time_tomorrow_17','h':17}
            ] %}
            {% for o in opts %}
              {% if states(o.id) not in ['unknown','unavailable','', None] %}
                {{ o.h }}
                {% break %}
              {% endif %}
            {% endfor %}
      - name: "pv_peak_tomorrow_end"
        unique_id: pv_peak_tomorrow_end
        state: >
          {% set opts = [
            {'id':'sensor.power_highest_peak_time_tomorrow_3','h':3},
            {'id':'sensor.power_highest_peak_time_tomorrow_4','h':4},
            {'id':'sensor.power_highest_peak_time_tomorrow_5','h':5},
            {'id':'sensor.power_highest_peak_time_tomorrow_6','h':6},
            {'id':'sensor.power_highest_peak_time_tomorrow_17','h':17}
          ] %}
          {% set ts = none %}{% set h = 0 %}
          {% for o in opts %}
            {% set v = states(o.id) %}
            {% if v not in ['unknown','unavailable','', None] %}
              {% set ts = as_datetime(v) %}{% set h = o.h %}{% break %}
            {% endif %}
          {% endfor %}
          {{ (ts + timedelta(hours=h)).strftime('%Y-%m-%d %H:%M:%S') if ts else 'unknown' }}

  - binary_sensor:
      # Deckt PV (Rest) + Akku>15 % den Tagesbedarf?
      - name: "pv_covers_today"
        unique_id: pv_covers_today
        state: >
          {% set load = states('input_number.avg_daily_consumption_kwh') | float(0) %}
          {% set pv   = states('sensor.pv_forecast_remaining_today_kwh') | float(0) %}
          {% set batt = states('sensor.battery_energy_above_min_kwh') | float(0) %}
          {{ (pv + batt) >= load }}

      # Preis aktuell rentabel?
      - name: "grid_price_profitable_now"
        unique_id: grid_price_profitable_now
        state: >
          {% set price = states('sensor.epex_spot_data_net_price') | float(999) %}
          {% set thr   = states('sensor.grid_threshold_eur_kwh') | float(0) %}
          {{ price <= thr and thr > 0 }}

      # Sind wir im PV-Kern (heute)?
      - name: "pv_peak_now"
        unique_id: pv_peak_now
        state: >
          {% set s = states('sensor.pv_peak_today_start') %}
          {% set e = states('sensor.pv_peak_today_end') %}
          {% set ok = (s not in ['unknown','unavailable']) and (e not in ['unknown','unavailable']) %}
          {% if ok %}
            {% set nowt = now().time().strftime('%H:%M:%S') %}
            {{ s <= nowt <= e }}
          {% else %}false{% endif %}

      # Gesamtschalter: JETZT laden?
      - name: "gridcharge_should_charge_now"
        unique_id: gridcharge_should_charge_now
        state: >
          {{ is_state('input_boolean.strom_gridcharge_enable','on')
             and is_state('binary_sensor.pv_covers_today','off')
             and is_state('binary_sensor.grid_price_profitable_now','on')
             and is_state('binary_sensor.pv_peak_now','off')
             and (states('sensor.battery_headroom_to_max_kwh') | float(0)) > 0 }}

automation:
  - id: gridcharge_toggle_with_pv_priority
    alias: "GridCharge – PV-Prio + Preis (EIN/AUS)"
    mode: restart
    trigger:
      - platform: state
        entity_id:
          - binary_sensor.gridcharge_should_charge_now
          - sensor.epex_spot_data_net_price
          - sensor.epex_spot_data_highest_price
          - sensor.pv_forecast_remaining_today_kwh
          - sensor.victron_battery_soc
          - sensor.pv_peak_today_start
          - sensor.pv_peak_today_end
      - platform: time_pattern
        minutes: "/10"
    action:
      - choose:
          - conditions: "{{ is_state('binary_sensor.gridcharge_should_charge_now','on') }}"
            sequence:
              - service: input_boolean.turn_on
                target: { entity_id: input_boolean.strom_gridcharge_request }
        default:
          - service: input_boolean.turn_off
            target: { entity_id: input_boolean.strom_gridcharge_request }
```

---

## Notizen

* **Victron (AC‑OUT Fronius)**: PV versorgt Verbraucher zuerst; Überschuss lädt Akku automatisch.
* **Allow Grid Charge**/AC‑Ladestrom kannst du direkt an `input_boolean.strom_gridcharge_request` koppeln (separate Automation).
* **ApexCharts‑Karte** ist separat vorhanden (EPEX‑Kurve + Schwellenlinie + SoC).

---

**Hinweis zum „Merken“:** Du kannst künftig einfach schreiben: `mdsave: <Text>` – ich hänge’s an dein Profil. Für dieses Dokument hast du hier die komplette MD‑Version an einem Ort.
