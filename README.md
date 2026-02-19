# HVAC Comfort Start --- Adaptive Preheat

**Status:** Release Candidate 1 (RC1-004) --- stable\
**Platform:** Home Assistant (Pyscript-based)\
**Compatibility:** Thermostat-agnostic (`climate` entity based)

HVAC Comfort Start is an adaptive preheat controller for Home Assistant
that learns how long your HVAC system actually needs to reach a desired
comfort temperature and automatically schedules preheating so the target
temperature is reached *at* the configured comfort time.

This project is optimized for real-world systems where static schedules
and fixed offsets consistently arrive too early or too late.

------------------------------------------------------------------------

## Key Capabilities

-   Adaptive learning of heating performance based on real cycles
-   Accurate comfort-time arrival (not just "start early and hope")
-   Stable control that avoids day-to-day oscillation
-   Persistent model state across restarts
-   Designed to prefer slight earliness over lateness
-   Validated on a real modulating furnace

------------------------------------------------------------------------

## How It Works

The system separates the problem into three layers:

### 1. Planning (Recompute)

Periodically calculates required preheat start time based on:

-   Current indoor temperature
-   Target temperature
-   Learned heating rate (`k`)
-   Learned systematic offset (`offset_min`)
-   Optional forecast bias

------------------------------------------------------------------------

### 2. Execution

-   A Home Assistant automation starts preheating at the computed time.
-   `input_boolean.preheat_active` marks the active preheat window.

------------------------------------------------------------------------

### 3. Learning (Arrival Evaluation)

Arrival is detected when indoor temperature first reaches the configured
threshold (target − tolerance).

Learning is bounded to:

preheat start → first arrival

This prevents post-arrival modulation from contaminating learning.

At comfort time, the system evaluates timing accuracy and updates:

-   Effective heating rate (`k`)
-   Systematic timing bias (`offset_min`)

------------------------------------------------------------------------

## Model Concepts

### k (minutes per degree)

Learned effective heating rate derived from full-cycle performance.

### offset_min

Learned systematic bias (minutes) compensating for factors not captured
by k alone (envelope loss, sensor lag, distribution delay, etc.).

### Asymmetric Learning

-   Late arrivals corrected quickly.
-   Early arrivals corrected slowly.
-   Slight earliness preferred over lateness for stability.

------------------------------------------------------------------------

## Version

Current version: **RC1-004**

