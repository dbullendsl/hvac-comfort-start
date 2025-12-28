# Installation

**Project:** HVAC Comfort Start — Adaptive Preheat  
**Version:** Beta 9  
**Platform:** Home Assistant + Pyscript

This guide installs the project into an existing Home Assistant instance.

---

## Prerequisites

- Home Assistant running normally
- Pyscript installed and working
- A working `climate.*` entity for your HVAC system
- An indoor temperature sensor entity (or use the thermostat’s temperature sensor)

You will need file access to Home Assistant (`Samba`, `VS Code add-on`, or SSH).

---

## Files and Locations

This repository maps to Home Assistant’s config folders like this:

| Repo path | Home Assistant path |
|---|---|
| `blueprints/Furnace Automation` | 'blueprints/automation/Furnace Automation` |
| `packages/furnace_preheat_helpers.yaml` | `/config/packages/furnace_preheat_helpers.yaml |
| `pyscript/furnace_preheat.py` | `/config/pyscript/furnace_preheat.py` |
| `pyscript_modules/furnace_config_io.py` | `/config/pyscript_modules/furnace_config_io.py` |

---

## Step 1 — Copy Files into Home Assistant

1. Copy `pyscript/furnace_preheat.py` to:
   - `/config/pyscript/furnace_preheat.py`

2. Copy `pyscript_modules/furnace_config_io.py` to:
   - `/config/pyscript_modules/furnace_config_io.py`

3. Copy 'blueprints/Furnace Automations/*.yaml to:
    - /config/blueprints/automation/Furnace Automations`

4. Copy 'packages/*.yaml to:
    - /config/packages`

---

## Step 2 — Create Required Helpers

Open `helpers/helpers.yaml` from this repo and apply it in Home Assistant using one of the following approaches:

### (Recommended): YAML package
- Put the file under your packages folder, for example:
  - `/config/packages/furnace_preheat_helpers.yaml`
- Ensure packages are enabled in configuration.

After adding helpers:
- Restart Home Assistant (or reload YAML where applicable).

---

## Step 3 — Import Blueprint

### Option A: Import from UI (recommended)
- Settings → Automations & Scenes → Blueprints
- Import blueprint file from this repo (`blueprints/...yaml`)

### Option B: Copy file directly
Copy blueprint YAML into:
- `/config/blueprints/automation/`

Then reload blueprints in Home Assistant.

---

## Step 4 — Create Automations

This project typically uses two automations:

1. **Start at Computed Preheat Time**
   - At `input_datetime.preheat_start`
   - Set HVAC mode / setpoint to heating target
   - Turn `input_boolean.preheat_active` ON

2. **Comfort Time Resume / Arrival Evaluation**
   - At `input_datetime.comfort_time`
   - Restore normal HVAC mode / schedule
   - Turn `input_boolean.preheat_active` OFF
   - Call:
     - `pyscript.furnace_preheat_evaluate_arrival`
     - then `pyscript.furnace_preheat_recompute`

If you use the included blueprint for comfort time handling, configure it with your climate entity and target temperature.

---

## Step 5 — Reload Pyscript

After copying the code:
- Reload Pyscript (or restart Home Assistant)
- Confirm Pyscript logs show no syntax errors.

---

## Verification Checklist

1. Run the service:
   - `pyscript.furnace_preheat_dump_config`
   - Confirm entities and target look correct.

2. Run:
   - `pyscript.furnace_preheat_recompute`
   - Confirm `input_datetime.preheat_start` updates.

3. At comfort time, confirm you get a log line like:
   - `furnace_preheat: arrival eval ... offset_old=... offset_new=...`

---

## Notes

- Beta 9 is tuned to prefer slight earliness over lateness.
- Do not manually run arrival evaluation outside the comfort-time window.

---

## Uninstall

To remove the project:
- Delete:
  - `/config/pyscript/furnace_preheat.py`
  - `/config/pyscript_modules/furnace_config_io.py`
- Remove the helpers you added
- Delete/disable the associated automations
- (Optional) clear model state:
  - `input_text.furnace_model_json`

