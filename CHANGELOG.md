# Changelog

## HVAC Comfort Start — Release Candidate 1 (RC1)

### Status
Feature complete. Stable. Learning window finalized.

---
### RC1-004 - Respect manual HVAC OFF state in start and resume automations

Fix: Manual thermostat OFF is now respected

If the thermostat is manually set to OFF:
- Preheat will not start
- Comfort-time resume will not re-enable heating
- Learning and state cleanup still occur

This prevents unintended HVAC activation when the system is intentionally disabled.

### RC1-004 — Arrival-Bounded Learning Window (First-Hit Freeze)

- Introduced an explicit arrival stop mechanism to freeze learning when the comfort
  temperature is first reached during an active preheat cycle.
- Learning window is now strictly bounded to:

  **preheat start → first arrival at (target − tolerance)**

- Arrival is latched once per cycle and treated as idempotent.
- Prevents post-arrival modulation / holding behavior from contaminating cycle learning (`k`).
- Comfort-time evaluation now acts as a finalizer / fallback only if arrival was not reached.

#### Impact

- Prevents runaway early start times
- Aligns learning objective with user intent: *reach target at comfort time*
- Improves model stability on modulating HVAC systems
- Preserves underlying model structure while improving robustness

---

### RC1-003 — Pyscript Configuration Hardening

- Target temperature resolution now prioritizes helper values
- Legacy JSON configuration treated as numeric fallback only
- Hardened config parsing to prevent `"None"` string coercion
- Improved runtime diagnostics via effective configuration dump

---

### RC1-002 — Blueprint Cleanup

- Removed duplicate target temperature inputs from automations
- Standardized blueprint behavior around shared helpers
- Improved separation between planning, execution, and learning automations
- Reduced user configuration error surface

---

### RC1-001 — Helper Standardization

- Externalized all user-tunable parameters into Home Assistant helpers
- Established a single authoritative target temperature helper
- Consolidated helper definitions into a dedicated package file
- Eliminated duplicated configuration inputs

---

### Naming Changes (RC1)

- Blueprint and automation names updated from **Furnace** to **HVAC** to reflect
  broader applicability (modulating systems, non-furnace heating, future cooling support)
- Internal file names and pyscript identifiers remain unchanged
- Naming change only; no functional impact

---

## HVAC Comfort Start — Beta 9

### Status
Stable beta release. Core control logic validated in production.

### Added

- Cycle-based effective heating rate learning (`k_cycle`)
- Near-comfort-time guard to prevent invalid learning input
- Asymmetric offset correction to eliminate oscillation
- Bias-safe offset clamping (prefer early over late)
- Frequent overnight recompute to avoid stale delta assumptions
- Robust separation of learning, planning, and execution

### Fixed

- Persistent 30–45 minute late arrival at comfort time
- Overly optimistic slope-based learning
- Model corruption from out-of-window evaluations
- Day-to-day oscillation caused by symmetric correction
- Restart sensitivity and partial-state loss

### Changed

- Learning now prioritizes full-cycle behavior over instantaneous slope
- Offset learning is asymmetric (fast late correction, slow early correction)
- Recompute cadence increased during overnight window

### Known Limitations

- Recompute not triggered by thermostat setback events
- Temperature unit assumptions are °F-centric
- Logging verbosity is fixed
- No user-facing UI beyond helpers

### Upgrade Notes

- Beta 9 serves as the architectural baseline for RC1
- Existing helpers and model JSON may be reused without reset

---

## Previous Betas

Earlier beta iterations were experimental and are superseded by RC1-004.