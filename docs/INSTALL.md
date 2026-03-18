# HVAC Comfort Start — Installation Guide (RC1-004)

This guide walks through installing **HVAC Comfort Start — Adaptive Preheat** into Home Assistant using Pyscript.

---

## Prerequisites

- Home Assistant Core or OS
- Pyscript integration installed
- A working `climate` entity
- Indoor temperature sensor
- Comfort time helper (`input_datetime`)

---

## Files and Locations

| Repository Path                                   | Home Assistant Path                                      |
|--------------------------------------------------|----------------------------------------------------------|
| `blueprints/Furnace Automations/*.yaml`          | `/config/blueprints/automation/Furnace Automations/`    |
| `packages/furnace_preheat_helpers.yaml`          | `/config/packages/furnace_preheat_helpers.yaml`          |
| `pyscript/furnace_preheat.py`                    | `/config/pyscript/furnace_preheat.py`                    |
| `pyscript_modules/furnace_config_io.py`          | `/config/pyscript_modules/furnace_config_io.py`          |

---

## Step 1 — Copy Files

Copy all files into the corresponding Home Assistant directories.

---

## Step 2 — Enable Packages

Ensure `configuration.yaml` includes:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Restart Home Assistant if needed.

---

## Step 3 — Reload Pyscript

Go to Developer Tools → YAML → Reload Pyscript.

---

## Step 4 — Import Blueprints

- Import the included blueprints  
- Create automations for:
  - Start Preheat  
  - Arrival Stop  
  - Comfort Time Evaluation  

---

## Step 5 — Verify Operation

Confirm the following behavior:

- Preheat start time is calculated and written  
- Preheat begins at the scheduled time  
- Arrival is detected at **(target − tolerance)**  
- `input_boolean.preheat_active` is cleared at arrival  
- Evaluation runs at comfort time  

---

## Understanding Arrival-Based Behavior (RC1-004)

During a preheat cycle, the system will stop active preheating when indoor temperature first reaches:

(target − tolerance)

At that moment:

- Arrival is recorded  
- `input_boolean.preheat_active` is cleared  
- Learning for that cycle is finalized  

If arrival is not reached:

- Evaluation occurs at comfort time as a fallback  

Learning is effectively bounded to the active heating phase, ending at arrival rather than at comfort time. This prevents post-arrival modulation or holding behavior from influencing the model.

This behavior is essential for accurate operation on modulating HVAC systems, ensuring learning reflects only the true heating phase.

---

## Notes

- Internal names may still reference "furnace"
- System is HVAC-agnostic
