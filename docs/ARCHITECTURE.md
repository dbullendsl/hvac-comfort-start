# HVAC Comfort Start — Architecture

**Version:** Release Candidate 1 (RC1)  
**Status:** Feature complete; maintenance mode  
**Platform:** Home Assistant + Pyscript  
**Compatibility:** Thermostat-agnostic (`climate` entity based)

This document describes the internal architecture of the HVAC Comfort Start system and the design principles behind its adaptive preheat control logic.

---

## Design Goals

HVAC Comfort Start was designed to solve a specific and common problem:

> Reach the desired comfort temperature **at** the configured comfort time — not early, not late — across varying outdoor conditions and HVAC behavior.

Key goals:

- Eliminate fixed offsets and guesswork
- Learn from real heating cycles
- Remain stable across days (no oscillation)
- Survive restarts and configuration changes
- Prefer slight earliness over lateness
- Remain thermostat-agnostic at the Home Assistant layer

---

## Thermostat & HVAC Compatibility

HVAC Comfort Start is **thermostat-agnostic**.

It works with any Home Assistant–integrated thermostat that exposes a standard `climate` entity and supports:

- `climate.set_temperature`
- `climate.set_hvac_mode` (at minimum `heat`; optionally `heat_cool`)
- a readable indoor temperature (either via the climate entity or a separate sensor)

Because all control occurs at the Home Assistant abstraction layer, the underlying HVAC system may be:

- gas / propane / oil furnaces (including modulating systems)
- electric baseboard or radiant panels
- hydronic radiant systems
- heat pumps (heating path supported in RC1)

---

## High-Level Architecture

The system is divided into three independent but coordinated layers:

```
+-------------------+
| Planning          |
| (Recompute)       |
+-------------------+
          |
          v
+-------------------+
| Execution         |
| (Automations)     |
+-------------------+
          |
          v
+-------------------+
| Learning          |
| (Arrival Eval)    |
+-------------------+
```

Each layer has a single responsibility and minimal coupling to the others.

---

## 1. Planning Layer — Recompute

**Purpose:**  
Determine *when* preheating must start in order to reach comfort temperature at comfort time.

**Key Inputs:**
- Current indoor temperature
- Target temperature (from helper)
- Learned heating rate (`k`)
- Learned systematic bias (`offset_min`)
- Optional forecast-based bias
- Occupancy state
- Min/max lead constraints

**Core Equation (conceptual):**

```
lead_minutes = (k × temperature_delta × bias) + offset_min
```

**Characteristics:**
- Runs every 15 minutes during the overnight window
- Continuously corrects for overnight temperature drift
- Does not modify learning state
- Does not execute HVAC actions directly

**Output:**
- Writes `input_datetime.preheat_start`

---

## 2. Execution Layer — Automation

**Purpose:**  
Start and stop preheating at the correct times using Home Assistant automations.

**Responsibilities:**
- Start heating when current time ≥ `preheat_start`
- Set `input_boolean.preheat_active` during active preheat
- Restore normal HVAC mode after comfort time
- Trigger learning evaluation at comfort time

**Important Design Choice:**  
Execution logic is intentionally *outside* the Pyscript controller to:
- Allow UI-driven customization
- Avoid timing races
- Keep control logic deterministic

---

## 3. Learning Layer — Arrival Evaluation

**Purpose:**  
Learn how well the plan worked and adjust the model accordingly.

**Triggered:**  
- Exactly at comfort time via automation

**What It Measures:**
- Actual indoor temperature vs target
- Elapsed time since preheat start
- Effective full-cycle heating rate (`k_cycle`) when gating conditions are met

**What It Updates:**
- `k` — minutes per degree (learned heating rate)
- `offset_min` — systematic bias in minutes

---

## Learning Model

### `k` — Effective Heating Rate
- Units: minutes per degree (°F or °C)
- Represents *full-cycle* performance
- Learned conservatively:
  - Faster increases
  - Slower decreases

This avoids optimistic assumptions based on short-term slope.

### `offset_min` — Systematic Bias
- Units: minutes
- Compensates for factors not captured by `k`:
  - Envelope losses
  - Sensor lag
  - Control hysteresis
  - Environmental variability

**Asymmetric Update Strategy:**
- Late arrival → corrected aggressively
- Early arrival → corrected slowly
- Offset never allowed to go negative

This prevents oscillation and prioritizes comfort.

---

## Stability Guards

Several safeguards ensure reliable operation:

### Near-Comfort Guard
Cycle-based learning (`k_cycle`) is only trusted within a tight window around comfort time.  
This prevents manual calls or late executions from corrupting the model.

### Active Preheat Guard
Learning and optional slope sampling only occur while `input_boolean.preheat_active` is asserted, preventing daytime maintenance ramps from polluting the model.

### Bias-Safe Clamping
- `k` constrained to realistic bounds
- `offset_min` constrained to non-negative values

---

## Persistent State

The learning model is stored in:

```
input_text.furnace_model_json
```

This allows:
- Restart persistence
- Manual inspection or seeding
- No filesystem dependency for model state

Runtime-only artifacts (if any) live under:

```
pyscript/data/
```

and are not version-controlled.

---

## Why This Architecture Works

This architecture succeeds because:

- Planning, execution, and learning are decoupled
- Learning uses **full-cycle reality**, not theory
- Corrections are asymmetric to prevent oscillation
- Frequent replanning avoids stale assumptions
- Guardrails prevent bad data from poisoning the model

The result is a controller that converges reliably under real-world conditions.

---

## RC1 Status

RC1 represents a **feature-complete release** derived from the proven Beta 9 control baseline:

- Persistent late arrival eliminated
- Oscillation eliminated
- Model converges within days, not weeks
- Verified on a real modulating HVAC system

RC1 focuses on configuration hardening, helper standardization, and documentation. Core control behavior is intentionally unchanged from Beta 9.

---

## Maintenance Mode

RC1 is intended for long-term personal use. Future enhancements (if ever resumed) would focus on packaging, multi-zone support, or UI improvements rather than changes to core control logic.

---

## Summary

HVAC Comfort Start is not a schedule tweak or heuristic.  
It is a small, adaptive control system built on real feedback, frozen in a stable and well-documented form in RC1.
