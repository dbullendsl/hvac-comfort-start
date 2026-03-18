<p align="center">
  <img src="assets/banner-light.png#gh-light-mode-only" alt="HVAC Comfort Start banner for light mode">
  <img src="assets/banner-dark.png#gh-dark-mode-only" alt="HVAC Comfort Start banner for dark mode">
</p>

<p align="center">
  <strong>Predictive Preheat Control for Home Assistant</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-RC1-blue" alt="Status RC1">
  <img src="https://img.shields.io/badge/Home%20Assistant-Custom-41BDF5" alt="Home Assistant Custom">
  <img src="https://img.shields.io/github/v/tag/dbullendsl/hvac-comfort-start?label=release" alt="Release">
  <img src="https://img.shields.io/github/stars/dbullendsl/hvac-comfort-start?style=flat" alt="GitHub stars">
</p>

**Status:** RC1-004 (Release Candidate 1) — Stable  
**Platform:** Home Assistant (Pyscript-based)  
**Compatibility:** Thermostat-agnostic (`climate` entity based)

HVAC Comfort Start is an adaptive preheat controller for Home Assistant
that learns how long your HVAC system actually needs to reach a desired
comfort temperature and automatically schedules preheating so the target
temperature is reached *at* the configured comfort time.

---

## Key Capabilities

- Adaptive learning of heating performance based on real cycles
- Accurate comfort-time arrival (not just "start early and hope")
- Stable control that avoids day-to-day oscillation
- Persistent model state across restarts
- Designed to prefer slight earliness over lateness
- Validated on real-world modulating HVAC systems

---

## How It Works

The system separates the problem into three layers:

---

### 1. Planning (Recompute)

Periodically calculates required preheat start time based on:

- Current indoor temperature
- Target temperature
- Learned heating rate (`k`)
- Learned systematic offset (`offset_min`)
- Optional forecast bias

---

### 2. Execution

- A Home Assistant automation starts preheating at the computed time.
- `input_boolean.preheat_active` marks the active preheat window.

---

### 3. Learning (Arrival Evaluation)

Arrival is detected when indoor temperature first reaches the configured
threshold (target − tolerance).

Learning is strictly bounded to:

**preheat start → first arrival (target − tolerance)**

Arrival defines the end of the heating phase and terminates learning for
that cycle. This prevents post-arrival modulation or holding behavior
from influencing the model.

Arrival is latched once per cycle and treated as idempotent, ensuring
that repeated threshold crossings or automation retriggers do not affect
learning stability.

An arrival-stop automation detects the first threshold crossing,
marks arrival, and clears the active preheat state. This enforces a
hard boundary between the heating phase and post-arrival behavior.

At comfort time, the system evaluates timing accuracy and updates the
model. This acts as a finalization step and ensures learning completes
even if arrival was not detected during the preheat cycle.

## How It Works

<p align="center">
  <img src="assets/preheat-flow.png" alt="HVAC Comfort Start Preheat Flow" width="500">
</p>

---

## Model Concepts

### k (minutes per degree)

Learned effective heating rate derived from full-cycle performance.

### offset_min

Learned systematic bias (minutes) compensating for factors not captured
by k alone (envelope loss, sensor lag, distribution delay, etc.).

### Asymmetric Learning

- Late arrivals corrected quickly
- Early arrivals corrected slowly
- Slight earliness preferred over lateness for stability

---

## Why Arrival-Based Learning Matters

In many systems, learning continues after the target temperature is
reached. On modulating HVAC systems, this introduces bias because the
system reduces output and enters a holding phase.

HVAC Comfort Start stops learning at the moment of arrival, ensuring the
model reflects only the true heating phase. This produces more stable
and accurate preheat timing over time.

---

## Version

Current version: **RC1-004**

---

## Notes

Internal module and function names may still reference "furnace" for
backward compatibility, but the system is fully HVAC-agnostic.

---

### AI Disclosure

Core system design, control strategy, and learning behavior were authored directly. AI was utilized as a development tool for code optimization and documentation structuring.