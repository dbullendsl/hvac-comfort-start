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

---

**Status:** RC1-005 — release-candidate build  
**Platform:** Home Assistant + Pyscript  
**Compatibility:** Thermostat-agnostic (`climate` entity based)

HVAC Comfort Start is an adaptive preheat controller for Home Assistant. It learns how long a home and heating system actually need to recover from setback, then schedules heating so the selected comfort temperature is reached near the configured comfort time.

RC1-005 expands the stable RC1-004 release with Fahrenheit / Celsius support, more flexible planning, improved learning accuracy, stronger safety handling, and easier configuration.

## When This Is Most Useful

HVAC Comfort Start is especially useful in homes that use meaningful temperature setbacks, particularly in colder climates where overnight recovery can take hours rather than minutes.

Without adaptive preheating, setback schedules create a tradeoff:

- Start heating too early → reduced setback savings
- Start heating too late → uncomfortable mornings

Comfort Start learns the recovery behavior instead of relying on a fixed early-start offset.

## Key Capabilities

- Adaptive learning from real heating cycles
- Predictive preheat scheduling to reach comfort temperature near the desired time
- Fahrenheit / Celsius temperature support
- Flexible planning and automatic recalculation when important settings change
- Improved learning accuracy by ignoring constrained or non-representative cycles
- Stronger safety handling for manual HVAC OFF and near-comfort conditions
- Thermostat-agnostic Home Assistant integration

## How It Works

### 1. Planning

Pyscript periodically recomputes the required preheat start from:

- Current indoor temperature
- Outdoor temperature
- Target temperature
- Learned heating rate `k`
- Learned timing offset `offset_min`
- Optional forecast bias
- Occupancy
- Min/max lead limits
- Configured `active_hours`

A 15-minute recompute is the fallback cadence. RC1-005 also includes a small blueprint that requests an immediate recompute when key planning inputs change.

### 2. Execution

The Start blueprint normally fires at `input_datetime.preheat_start`.

If recompute discovers that the calculated start is already in the past, Pyscript emits a scoped `hvac_comfort_start_start_due` event. The same Start blueprint handles that catch-up event, so vacation, occupancy, thermostat-mode, and near-comfort safeguards remain centralized.

### 3. Arrival and Learning

Arrival is detected at:

**target − tolerance**

Learning is bounded to:

**preheat start → first arrival**

The arrival-stop blueprint latches arrival once, then clears the active preheat state. At comfort time, Resume/Verify finalizes the cycle and updates the model.

Cycles whose start time was constrained by min lead, max lead, `active_hours`, or the unoccupied lead cap are treated as **observation-only**. They do not alter `k` or `offset_min`, because their timing was constrained by policy rather than the model alone.

## Model Concepts

### k

Effective heating rate in **minutes per °F**.

RC1-005 keeps the internal model in °F even on Celsius systems so existing learned model values remain valid. Temperature entities are normalized at the Pyscript boundary.

### offset_min

Learned timing bias in minutes for effects not fully captured by `k`.

### Asymmetric Correction

- Late arrivals are corrected relatively quickly
- Early arrivals are corrected slowly
- Slight earliness is preferred over repeated lateness

## Celsius Support

RC1-005 supports Celsius temperature sensors and target helpers. Pyscript converts temperatures to internal °F for model calculations, while the blueprints compare and command temperatures in Home Assistant's native unit.

**Important:** the supplied helper package currently defines the target helper with Fahrenheit-oriented limits and `°F`. On a Celsius installation, the target helper must instead use Celsius values and the same native unit as the indoor sensor / climate entity. See `docs/INSTALL.md`.

## Manual HVAC OFF

A manually OFF thermostat is a hard override.

When the configured climate entity is OFF:

- Preheat will not start
- Missed-start catch-up will not start heating
- Comfort-time Resume/Verify will not re-enable heating
- Arrival evaluation will not learn from the cold room

## FAQ

### Can comfort time vary by day?

Yes. Use any Home Assistant schedule or automation to update `input_datetime.comfort_time`. RC1-005 detects the change and recalculates the required preheat start. Comfort Start does not need its own weekday/weekend scheduler.

### Can the target temperature vary by day?

Yes. A Home Assistant schedule or automation can update `input_number.hvac_comfort_start_target_temp`. Comfort Start will use the new target for subsequent planning.

### Does Comfort Start work with Celsius?

Yes. RC1-005 supports both Fahrenheit and Celsius temperature entities. The internal learned model remains in minutes per °F for backward compatibility, while temperature values are converted automatically at the Pyscript boundary.

### What happens if the thermostat is set to Auto, Cool, or Off?

Any mode other than Heat tells HVAC Comfort Start to stand down. Comfort Start will not start heating or change the HVAC operating mode. Selecting Auto returns control to the thermostat, while Cool or Off likewise prevents an HCS heating cycle from starting.

### What if the house is already near the target temperature?

The Start automation checks indoor temperature before starting preheat. If the home is already within the configured tolerance of the target, the preheat cycle is skipped.

### Does it require a specific weather integration?

No. Comfort Start can use compatible Home Assistant outdoor-temperature and forecast-low entities. It is not tied to a specific weather provider.

### What happens if the calculated start time has already passed?

RC1-005 can request an immediate catch-up start, while still applying the normal vacation, occupancy, thermostat-mode, and near-comfort safeguards.

### Can it work when nobody is home?

Yes. The unoccupied lead cap controls how much preheating is allowed when the occupancy sensor reports nobody home. Set the cap to match your preference.

### Can HVAC Comfort Start be installed through HACS?

Not yet. RC1-005 / RC1-final uses a multi-file Home Assistant setup that includes Pyscript, blueprints, helpers, and configuration files, so installation is currently handled from the GitHub repository. A more streamlined HACS-compatible package is being considered as a separate future effort after the current release is finalized and proven in production.

### Does HVAC Comfort Start support multiple HVAC systems or zones?

Not yet. RC1-005 / RC1-final is designed around one heating system, one indoor temperature source, and one comfort schedule.

Multi-system and multi-zone support is a future development area. A future version could allow separate learned models, targets, schedules, and preheat calculations for each zone or HVAC system while keeping the same overall control approach.

### Does HVAC Comfort Start base its calculations on long-term historical data?

No. HVAC Comfort Start does not analyze months of Home Assistant history or require a large historical dataset before it can work.

Instead, it learns incrementally from completed preheat cycles. After each valid cycle, it updates a small persistent model of how long the home actually takes to warm. Recent experience is blended with what the system has already learned, so the model gradually adapts over time.

That approach is useful because home heating behavior is not perfectly linear. Outdoor temperature is only one influence; wind, sun versus cloud cover, internal heat gains, building thermal mass, and other changing conditions can all affect how quickly a house warms. Rather than trying to model every variable explicitly, HVAC Comfort Start learns from the actual result of each heating cycle.

The learned model persists across restarts, and cycles affected by scheduling clamps or manual HVAC OFF are excluded so they do not distort learning.

## Repository Layout

- `blueprints/Furnace Automation/` — Start, Arrival Stop, Resume/Verify, and event-aware Recompute blueprints
- `packages/` — helper package
- `pyscript/` — main adaptive controller
- `pyscript_modules/` — configuration I/O support
- `docs/` — installation and architecture notes

## Version

Current development/release-candidate version: **RC1-005**

The intended next release milestone is `rc1-final` after final repository and installation review.

## Notes

Some internal module, file, and service names still reference “furnace” for backward compatibility. The public behavior is HVAC-oriented and works with a compatible Home Assistant `climate` entity.

### AI Disclosure

HVAC Comfort Start is a one-person development project. AI was used as a development assistant for code review, troubleshooting, implementation support, test design, simulation work, and documentation.

The project was developed iteratively over many hours of hands-on testing, including accelerated overnight simulation, targeted regression testing, and validation on the author's production Home Assistant system. The simulator substantially shortened the development cycle by allowing complete heating scenarios and edge cases to be exercised repeatedly without waiting for suitable weather or overnight conditions.

The project requirements, control strategy, acceptance criteria, testing decisions, and final implementation choices were directed and validated by the author. AI accelerated the engineering process; it did not replace the testing or judgment required to determine whether the system actually worked.

## Support the Project

HVAC Comfort Start is free and open source. If you find it useful and would like to support continued development:

[![Buy me a coffee](https://img.shields.io/badge/Buy_me_a_coffee-Support_HCS-FFDD00?style=for-the-badge&labelColor=FFDD00&color=FFDD00)](https://buymeacoffee.com/p0OYWxFbzt)
