# Changelog

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
Earlier beta iterations were experimental and are superseded by Beta 9.

