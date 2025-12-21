# HVAC Comfort Start — Adaptive Preheat

**Status:** Stable Beta (Beta 9)  
**Platform:** Home Assistant (Pyscript-based)  
**Target Systems:** Gas / modulating furnaces and similar HVAC systems

HVAC Comfort Start is an adaptive preheat controller for Home Assistant that learns how long your HVAC system actually needs to reach a desired comfort temperature and automatically schedules preheating so the target temperature is reached *at* the configured comfort time.

This project is designed for real-world systems where fixed schedules and static offsets consistently arrive too early or too late.

---

## Key Capabilities

- Adaptive learning of heating performance based on real cycles
- Accurate comfort-time arrival (not just “start early and hope”)
- Stable control that avoids day-to-day oscillation
- Persistent model state across restarts
- Designed to prefer slight earliness over lateness
- Validated on a real modulating furnace

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

## Current Beta Status (Beta 9)

This release represents a **stable and validated control loop**:

- Persistent late arrival has been eliminated.
- Learning converges reliably across days.
- Control logic is robust against restarts and manual intervention.
- Recompute runs frequently overnight to avoid stale assumptions.
- Cycle-based learning is guarded to prevent invalid data injection.

Feature enhancements are intentionally deferred until the Release Candidate phase.

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

## Versioning

This project follows a pragmatic versioning approach:

- **Beta**: Core logic stabilized and validated
- **Release Candidate (RC)**: Feature-complete with conservative defaults
- **Stable**: Minimal configuration, documented behavior

Current version: **Beta 9**

