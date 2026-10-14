# HVAC Comfort Start — Architecture

**Version:** Release Candidate 1 (RC1-005)  
**Platform:** Home Assistant + Pyscript  
**Compatibility:** Thermostat-agnostic (`climate` entity based)

## Design Goal

Reach the selected comfort temperature near the configured comfort time while learning from real heating behavior and avoiding contamination from post-arrival modulation, scheduling clamps, manual overrides, or stale planning state.

## Layers

```
+-------------------+
| Planning          |
| Recompute         |
+-------------------+
          |
          v
+-------------------+
| Execution         |
| Blueprints        |
+-------------------+
          |
          v
+-------------------+
| Learning          |
| Arrival Eval      |
+-------------------+
```

## 1. Planning Layer

The Pyscript controller calculates `preheat_start` from:

- indoor temperature
- outdoor temperature
- comfort target
- learned `k`
- learned `offset_min`
- optional forecast bias
- occupancy
- min/max lead helpers
- unoccupied lead cap
- `active_hours`

### Recompute cadence

RC1-005 schedules the Pyscript recompute service every 15 minutes. The service itself decides whether planning is currently allowed by checking `active_hours`.

This replaces the RC1-004 hard-coded overnight cron window.

### Event-aware planning

A separate blueprint requests immediate recompute when:

- the comfort target changes
- comfort time changes
- the configured climate entity changes HVAC mode

The 15-minute trigger remains the fallback.

### Post-comfort guard

After today's comfort time has passed, planning for the next cycle does not open until that next cycle's `active_hours` start.

### Missed-start recovery

If recompute determines that the correct start time has already passed, and comfort time is still ahead, Pyscript emits:

`hvac_comfort_start_start_due`

The Start blueprint listens for both the normal time trigger and this catch-up event. All normal Start conditions still apply.

The freeze guard also recognizes an already-stored start that has passed and requests catch-up rather than silently suppressing the cycle.

## 2. Execution Layer

Four automation blueprints make up the normal RC1-005 execution layer:

1. **Start at Computed Preheat Time**
2. **Stop Learning at Arrival**
3. **Resume/Verify at Comfort Time**
4. **Recompute on Planning Input Changes**

### Start protections

The Start blueprint requires:

- vacation OFF
- HVAC mode compatible with heating
- occupied OR an enabled unoccupied lead cap
- indoor temperature still below target minus tolerance

The last condition prevents a stale or minimum-lead start from creating a pointless preheat session on a warm morning.

### Manual OFF

A manually OFF thermostat is treated as a hard override. Start and Resume/Verify do not turn it back on.

## 3. Arrival Layer

Arrival occurs at:

**target − tolerance**

The arrival-stop blueprint:

- detects the first threshold crossing
- calls `pyscript.furnace_preheat_mark_arrival`
- clears the active preheat state

Arrival is latched once and is idempotent.

For Celsius sensors, the blueprint converts the configured °F-equivalent tolerance to native °C before evaluating the threshold.

## 4. Learning Layer

The normal learning window is:

**preheat start → first arrival**

The model contains:

- `k`: effective minutes per °F
- `offset_min`: learned systematic timing bias

### Celsius boundary

RC1-005 keeps the model in °F internally so existing RC1-004 model files remain valid.

Temperature entities are normalized to °F only inside Pyscript. Home Assistant blueprints continue to operate in each entity's native displayed unit.

### Clamp-aware learning

A cycle is marked clamped if scheduling was constrained by:

- minimum lead
- maximum lead
- unoccupied lead cap
- active-hours start/end

Clamped cycles are observation-only. They do not modify `k` or `offset_min`, because the observed timing no longer represents a free model decision.

Clamp state is carried from planning to cycle start. After a Pyscript restart, the controller can infer common clamps from the stored `preheat_start` and configured limits.

### Manual-OFF learning guard

If the configured thermostat is OFF at evaluation time, learning is skipped. A deliberately cold room must not be interpreted as a failed preheat cycle.

## 5. Resume/Verify

At comfort time:

- if the thermostat is OFF, HVAC actions are skipped
- if target is already met, the configured resume mode is restored
- if target is below threshold and enforcement is enabled, heat is driven to target or timeout
- arrival evaluation is finalized
- the selected `preheat_active` helper is cleared

The tolerance is °F-equivalent and converted automatically for Celsius indoor sensors.

## Stability Principles

RC1-005 preserves the RC1-004 model philosophy:

- first-hit arrival boundary
- late correction faster than early correction
- slight earliness preferred over repeated lateness
- full-cycle learning favored over transient modulation behavior
- no learning from constrained or manually overridden cycles

## Release State

RC1-005 has passed accelerated sandbox regression testing across normal operation, planning edge cases, temperature-unit handling, manual overrides, and restart scenarios.

The intended next milestone is `rc1-final` after release packaging and final documentation review.
