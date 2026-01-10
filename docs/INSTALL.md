# HVAC Comfort Start — Installation Guide (Beta 9)

This guide walks through installing **HVAC Comfort Start — Adaptive Preheat** into an existing Home Assistant system using Pyscript.

The system is designed to be **hands-off once installed**, but initial setup requires basic familiarity with Home Assistant configuration files.

---

## Prerequisites

- Home Assistant Core or OS
- **Pyscript integration installed and enabled**
- A working thermostat entity (`climate.*`)
- Indoor temperature sensor
- Outdoor temperature sensor (optional but recommended)
- Comfort time defined via `input_datetime`

---

## Getting the Files

You can obtain the project files in one of two ways.

### Option A — Download ZIP (simplest)

1. Open the GitHub repository page.
2. Click **Code → Download ZIP**.
3. Extract the ZIP on your computer.
4. Use the extracted folders when copying files in the steps below.

This option does **not** require Git.

---

### Option B — Clone the repository (recommended for advanced users)

If you are comfortable with Git, cloning makes future updates easier.

```bash
git clone https://github.com/dbullendsl/hvac-comfort-start.git
```

This will create a local `hvac-comfort-start/` directory containing all required files.

Use this directory when copying files into Home Assistant in the steps below.

---

## Files and Locations

| Repo path | Home Assistant path |
|---|---|
| `blueprints/Furnace Automations/*.yaml` | `/config/blueprints/automation/Furnace Automations/` |
| `packages/furnace_preheat_helpers.yaml` | `/config/packages/furnace_preheat_helpers.yaml` |
| `pyscript/furnace_preheat.py` | `/config/pyscript/furnace_preheat.py` |
| `pyscript_modules/furnace_config_io.py` | `/config/pyscript_modules/furnace_config_io.py` |

---

## Step 1 — Copy Files into Home Assistant

1. Copy the Pyscript module:
   - From: `pyscript/furnace_preheat.py`
   - To: `/config/pyscript/furnace_preheat.py`

2. Copy the Pyscript helper module:
   - From: `pyscript_modules/furnace_config_io.py`
   - To: `/config/pyscript_modules/furnace_config_io.py`

3. Copy all blueprint files:
   - From: `blueprints/Furnace Automations/*.yaml`
   - To: `/config/blueprints/automation/Furnace Automations/`

4. Copy the helpers package:
   - From: `packages/furnace_preheat_helpers.yaml`
   - To: `/config/packages/furnace_preheat_helpers.yaml`

---

## Step 2 — Enable the Helpers Package

Ensure your `configuration.yaml` includes packages:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Restart Home Assistant if this is newly added.

The helpers defined in `furnace_preheat_helpers.yaml` will now appear in Home Assistant.

---

## Step 3 — Reload Pyscript

1. Go to **Developer Tools → YAML**
2. Click **Reload Pyscript**

Check the log for errors. A clean reload should produce no exceptions.

---

## Step 4 — Import and Configure the Blueprint

1. Go to **Settings → Automations & Scenes → Blueprints**
2. Import the blueprint(s) from:
   ```
   blueprints/Furnace Automations/
   ```
3. Create a new automation from the blueprint.
4. Select:
   - Your thermostat entity
   - Comfort time helper
   - Target temperature

This automation is responsible for **starting preheat** and **evaluating arrival**.

---

## Step 5 — Verify Operation

Overnight, you should see logs similar to:

- Recompute planning (between 02:00–07:00)
- Preheat start captured
- Arrival evaluation at comfort time

Example log entries:

```
furnace_preheat: captured preheat start at 04:15:00 indoor=68.3F
furnace_preheat: arrival eval indoor=74.1F target=74.0F ...
```

---

## Notes

- This project does **not** require `/config/pyscript/data/` in Beta 9.
- Learning is intentionally conservative to support **modulating HVAC systems**.
- Minor day-to-day variation is normal during seasonal transitions.

---

## Troubleshooting

- If preheat does not start, verify:
  - `input_boolean.preheat_active`
  - `input_datetime.preheat_start`
  - The automation created from the blueprint
- If Pyscript fails to reload, check indentation and log output.

---

## Version

- **HVAC Comfort Start — Beta 9**
- Stable beta release
- Designed for hands-off operation once installed
