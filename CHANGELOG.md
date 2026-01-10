# Changelog

## HVAC Comfort Start — Release Candidate 1 (RC1)

### Status
Feature complete. Control logic frozen. Entering maintenance mode.

### RC1-001 — Helper Standardization
- Externalized all user-tunable parameters into Home Assistant helpers
- Established a single authoritative target temperature helper
- Consolidated helper definitions into a dedicated package file
- Eliminated duplicated configuration inputs

### RC1-002 — Blueprint Cleanup
- Removed duplicate target temperature inputs from automations
- Standardized blueprint behavior around shared helpers
- Improved separation between planning, execution, and learning automations
- Reduced user configuration error surface

### RC1-003 — Pyscript Configuration Hardening
- Target temperature resolution now prioritizes helper values
- Legacy JSON configuration treated as numeric fallback only
- Hardened config parsing to prevent `"None"` string coercion
- Improved runtime diagnostics via effective configuration dump

### Notes
- RC1 is built directly on the Beta 9 control model
- No changes were made to the core learning or planning algorithms
- Behavior and convergence characteristics are intentionally preserved


## HVAC Comfort Start — Beta 9

### Status
Stable beta release. Core control logic validated in a real production environment.

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
- Recompute is not yet triggered by thermostat setback events
- Temperature unit assumptions are implicit (°F-centric thresholds)
- Logging verbosity is fixed
- No user-facing UI beyond helpers

### Upgrade Notes
- Beta 9 is intended as a **baseline checkpoint**.
- Future work should build on this version without modifying core control logic.
- Existing helpers and model JSON may be reused without reset.

---

## Previous Betas
Earlier beta iterations were experimental and are superseded by RC1.

