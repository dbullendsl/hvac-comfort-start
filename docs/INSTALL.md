# HVAC Comfort Start — Installation Guide (RC1-005)

This guide installs HVAC Comfort Start into Home Assistant using Pyscript and four automation blueprints.

## Prerequisites

- Home Assistant Core or Home Assistant OS
- Pyscript integration installed
- A working heating-capable `climate` entity
- Indoor temperature sensor
- Outdoor temperature sensor
- Comfort time helper
- Occupancy and vacation entities if those protections are used

## Files and Locations

| Repository Path | Home Assistant Path |
|---|---|
| `blueprints/Furnace Automation/*.yaml` | `/config/blueprints/automation/Furnace Automation/` |
| `packages/furnace_preheat_helpers.yaml` | `/config/packages/furnace_preheat_helpers.yaml` |
| `pyscript/furnace_preheat.py` | `/config/pyscript/furnace_preheat.py` |
| `pyscript/data/furnace_preheat_config.example.json` | `/config/pyscript/data/furnace_preheat_config.json` |
| `pyscript_modules/furnace_config_io.py` | `/config/pyscript_modules/furnace_config_io.py` |

## Step 1 — Copy Files

Copy the repository files into the corresponding Home Assistant directories.

## Step 2 — Enable Packages

Ensure packages are enabled in Home Assistant:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Restart Home Assistant if required after adding the package include.

## Step 3 — Review the Pyscript Config

Copy `pyscript/data/furnace_preheat_config.example.json` to `/config/pyscript/data/furnace_preheat_config.json`, then edit the copied file for your installation.

Important fields:

- `climate`
- `indoor_temp`
- `outdoor_temp`
- `forecast_low`
- `occupied_binary`
- `vacation`
- `comfort_time`
- `preheat_start`
- `target_temp_helper`
- `active_hours`

Example:

```json
{
  "climate": "climate.your_thermostat",
  "indoor_temp": "sensor.your_indoor_temperature",
  "outdoor_temp": "sensor.your_outdoor_temperature",
  "forecast_low": "sensor.your_forecast_low",
  "occupied_binary": "binary_sensor.your_occupancy",
  "vacation": "input_boolean.vacation",
  "comfort_time": "input_datetime.comfort_time",
  "preheat_start": "input_datetime.preheat_start",
  "target_temp_helper": "input_number.hvac_comfort_start_target_temp",
  "target_temp": null,
  "active_hours": ["01:00:00", "23:00:00"],
  "forecast_hours_ahead": 8
}
```

### active_hours

`active_hours` is the planning window. RC1-005 no longer has a hard-coded 02:00–07:59 recompute window.

The supplied example uses 01:00–23:00. Choose a window that allows the earliest legitimate start for your schedule.

Midnight-spanning windows are supported.

## Step 4 — Reload Pyscript

Reload Pyscript after copying or changing the controller/config files.

## Step 5 — Create Automations from the Four Blueprints

Create one automation from each included blueprint:

1. **HVAC Comfort Start — Start at Computed Preheat Time**
2. **HVAC Comfort Start — Stop Learning at Arrival**
3. **HVAC Comfort Start — Resume/Verify at Comfort Time**
4. **HVAC Comfort Start — Recompute on Planning Input Changes**

Use selectors to choose the same climate, target, indoor-temperature, comfort-time, preheat-active, occupancy, vacation, and lead-cap helpers used by your installation.

The event-aware recompute blueprint should point to the same climate entity, comfort-time helper, target helper, and preheat-active helper.

## Step 6 — Verify Helpers

The supplied package creates:

- `input_datetime.preheat_start`
- `input_datetime.comfort_time`
- `input_number.preheat_min_lead`
- `input_number.preheat_max_lead`
- `input_number.preheat_unoccupied_cap`
- `input_number.hvac_comfort_start_target_temp`
- `input_text.furnace_model_json`
- `input_boolean.preheat_active`

## Fahrenheit and Celsius

RC1-005 Pyscript supports both Fahrenheit and Celsius temperature entities. The learned model remains minutes per °F internally.

The Home Assistant blueprints operate in native entity units, so the **target helper must use the same temperature scale as the indoor sensor and climate entity**.

### Fahrenheit

The supplied package is currently Fahrenheit-oriented:

```yaml
hvac_comfort_start_target_temp:
  min: 50
  max: 80
  step: 0.5
  unit_of_measurement: "°F"
  icon: mdi:thermometer
```

### Celsius

For a Celsius installation, define the same helper entity ID with Celsius-appropriate limits and values, for example:

```yaml
hvac_comfort_start_target_temp:
  name: HVAC Comfort Target Temperature
  min: 10
  max: 30
  step: 0.5
  unit_of_measurement: "°C"
  icon: mdi:thermometer
```

Do not convert the learned model JSON manually. RC1-005 performs the temperature conversion at runtime.

## Step 7 — Verify Operation

Confirm:

- recompute writes a plausible `preheat_start`
- changing target or comfort time causes an immediate recompute
- heating starts at the computed time
- a missed start catches up immediately while comfort time is still ahead
- arrival is detected at target minus tolerance
- `preheat_active` clears at arrival
- Resume/Verify runs at comfort time
- a manually OFF thermostat remains OFF

## Learning and Clamps

If a cycle is constrained by min lead, max lead, active-hours boundaries, or the unoccupied lead cap, RC1-005 will not learn `k` or `offset_min` from that cycle.

This is intentional: a constrained start does not represent an unconstrained model prediction.

## Notes

Internal file and service names may still reference “furnace” for backward compatibility. The controller itself is HVAC-agnostic.
