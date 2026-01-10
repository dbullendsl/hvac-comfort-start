# HVAC Comfort Start — Adaptive Preheat

**Status:** Release Candidate 1 (RC1) — feature complete, maintenance mode  
**Platform:** Home Assistant (Pyscript-based)  
**Compatibility:** Thermostat-agnostic (`climate` entity based)

HVAC Comfort Start is an adaptive preheat controller for Home Assistant that learns how long your HVAC system actually needs to reach a desired comfort temperature and automatically schedules preheating so the target temperature is reached *at* the configured comfort time.

This project is optimized for real-world systems where static schedules and fixed offsets consistently arrive too early or too late.

---

## Key Capabilities

- Adaptive learning of heating performance based on real cycles
- Accurate comfort-time arrival (not just “start early and hope”)
- Stable control that avoids day-to-day oscillation
- Persistent model state across restarts
- Designed to prefer slight earliness over lateness
- Validated on a real modulating furnace

---

## Thermostat & System Compatibility

HVAC Comfort Start is **thermostat-agnostic**.

It works with **any Home Assistant–integrated thermostat** that exposes a standard `climate` entity and supports:

- `hvac_mode` control (e.g., `heat`, `heat_cool`)
- a controllable target temperature
- a readable indoor temperature sensor

### Supported HVAC System Types

Because control is abstracted at the Home Assistant level, HVAC Comfort Start can be used with:

- Gas furnaces (single-stage, multi-stage, or modulating)
- Electric baseboard heating
- Radiant floor or panel systems
- Heat pumps (air-source or ground-source)
- Hybrid systems managed by a single HA `climate` entity

The algorithm does **not** assume:
- fuel type
- heat source
- staging behavior
- thermostat brand

All learning is derived from **observed temperature response**, not equipment metadata.

---

## How It Works (High Level)

The system separates the problem into three parts:

1. **Planning (Recompute)**
   - Periodically calculates the required preheat start time based on:
     - current indoor temperature
     - target temperature
     - learned heating rate
     - forecast bias (optional)
     - learned systematic offset

2. **Execution**
   - A Home Assistant automation starts preheating at the computed time.
   - A helper (`input_boolean.preheat_active`) marks the active preheat window.

3. **Learning (Arrival Evaluation)**
   - At the comfort time, the system evaluates:
     - how close the actual temperature is to the target
     - how long the full heating cycle took
   - The model is updated using:
     - cycle-based effective heating rate
     - asymmetric correction to avoid oscillation

---

## Model Concepts

- **k (minutes per degree)**  
  Learned effective heating rate, based on full-cycle performance rather than instantaneous slope.

- **offset_min**  
  Learned systematic bias (in minutes) to compensate for effects not captured by k alone (envelope losses, sensor lag, etc.).

- **Asymmetric Learning**
  - Late arrivals are corrected quickly.
  - Early arrivals are corrected slowly.
  - Offset is never driven negative to prevent oscillation.

---

## Release Candidate 1 (RC1) Status

RC1 represents a **feature-complete and stable implementation** intended for long-term personal use and conservative maintenance.

Key RC1 characteristics:

- All user-facing tuning is externalized via helpers
- Target temperature is defined once and shared consistently
- Control logic is robust against restarts and partial state
- Configuration parsing is hardened against invalid or missing values
- Core learning and control behavior is frozen

Future development, if any, is expected to be incremental rather than architectural.

---

## What This Beta Does *Not* Yet Include

Planned for a future Release Candidate:

- Triggered recompute on thermostat setback detection
- Automatic stop of recompute after comfort time
- Temperature unit abstraction (°F / °C)
- User-configurable debug logging
- Optional advanced tuning parameters

---

## Requirements

- Home Assistant
- Pyscript integration
- A controllable `climate` entity
- Indoor temperature sensor
- Helper entities (input_datetime, input_number, input_boolean, input_text)

Exact helper definitions are documented in the repository.

---

## Disclaimer

This project directly controls HVAC behavior.  
Use at your own risk and validate behavior carefully in your environment before relying on it for critical comfort or safety needs.

---

## Maintenance Mode

As of RC1, this project is considered **feature complete** for its intended use case.

- No major new features are planned
- Breaking changes are not expected
- Updates may occur to maintain compatibility with Home Assistant or Pyscript

The project remains public primarily for reference and reuse by others with similar requirements.

---

## Versioning

This project follows a pragmatic versioning approach:

- **Beta**: Core logic stabilized and validated
- **Release Candidate (RC)**: Feature-complete with conservative defaults
- **Stable**: Minimal configuration, documented behavior

Current version: **Beta 9**

