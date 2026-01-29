# HVAC Comfort Start — Adaptive Preheat
# Version: RC1-004 (builds on Beta 9 baseline)
# Status: RC candidate patch for arrival-based learning stop
#
# Key RC1-004 changes:
# - Adds ARRIVAL latch (first-hit) recorded by service furnace_preheat_mark_arrival()
# - evaluate_arrival() prefers time-based arrival error (minutes vs comfort time)
# - k_cycle (cycle-effective) uses start->arrival window when ARRIVAL is present
# - Keeps Beta 9 asymmetric correction and guarded learning behavior

import sys
import json
import re
from datetime import datetime, timedelta

MODULE_PATH = "/config/pyscript_modules"
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

import furnace_config_io

# Captured at the moment preheat becomes active (used for cycle-based k)
CYCLE = {"start_ts": None, "start_t": None}

# RC1-004: ARRIVAL latch captured at first threshold hit (idempotent)
ARRIVAL = {"ts": None, "t": None, "reason": None}

#
# Basic state helpers
#

def _entity(eid, default=None):
    """Get state as string, with unknown/unavailable handling."""
    try:
        v = state.get(eid)
        if v in (None, "unknown", "unavailable"):
            return default
        return v
    except Exception:
        return default


def _entity_f(eid, default=0.0):
    """Get state as float."""
    try:
        v = state.get(eid)
        if v in (None, "unknown", "unavailable"):
            return default
        return float(v)
    except Exception:
        return default


def _entity_onoff(eid, default_off=True):
    """
    Interpret an entity as on/off.

    default_off=True means: if unknown/unavailable, treat as OFF.
    default_off=False means: if unknown/unavailable, treat as ON.
    """
    v = _entity(eid, None)
    if v is None:
        return not default_off
    return str(v).lower() == "on"


#
# Config loading (from JSON file via executor)
#

_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def _clean_entity_id(val, default):
    """Return a usable entity_id string or default."""
    try:
        if val is None:
            return default
        s = str(val).strip()
        if not s:
            return default
        if s.lower() in ("none", "null", "unknown", "unavailable"):
            return default
        return s
    except Exception:
        return default


def _resolve_active_hours(cfg):
    default = ["03:00:00", "23:00:00"]
    raw = cfg.get("active_hours", default)

    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        log.warning("furnace_preheat: invalid active_hours (expected 2-item list); using default %s", default)
        return default

    start, end = raw[0], raw[1]
    if not (isinstance(start, str) and isinstance(end, str) and _TIME_RE.match(start) and _TIME_RE.match(end)):
        log.warning("furnace_preheat: invalid active_hours values %s; using default %s", raw, default)
        return default

    return [start, end]


def _resolve_forecast_hours(cfg):
    default = 8
    raw = cfg.get("forecast_hours_ahead", default)
    try:
        val = int(raw)
    except Exception:
        log.warning("furnace_preheat: invalid forecast_hours_ahead=%r; using default %d", raw, default)
        return default

    # Clamp to sane bounds for RC1
    val = max(1, min(val, 48))
    return val


def _resolve_target_temp(cfg):
    """Resolve target temperature with RC1 precedence:
       1) Helper (authoritative)
       2) Legacy JSON (numeric only)
       3) Hard default
    """
    helper = "input_number.hvac_comfort_start_target_temp"

    # 1) Preferred: helper
    try:
        v = state.get(helper)
        if v not in (None, "unknown", "unavailable", ""):
            return float(v), "helper"
    except Exception:
        pass

    # 2) Legacy JSON fallback (numeric only)
    legacy = cfg.get("target_temp")
    if isinstance(legacy, (int, float)):
        return float(legacy), "legacy_config"

    # 3) Absolute fallback
    return 74.0, "default"


async def _load_cfg():
    """Load config via native module in the executor and return a normalized dict.

    RC1 notes:
    - Target temperature is resolved primarily from the helper
      input_number.hvac_comfort_start_target_temp (single source of truth).
    - furnace_preheat_config.json target_temp is legacy and used only if numeric.
    """
    defaults = {
        "climate": "climate.daikin",
        "indoor": "sensor.indoor_temperature",
        "outdoor": "sensor.main_room_outdoor_air_temperature",
        "forecast_low": "sensor.nws_overnight_low_temperature",
        "occupied": "binary_sensor.family_home",
        "vacation": "input_boolean.vacation",
        "comfort": "input_datetime.comfort_time",
        "preheat": "input_datetime.preheat_start",
        "min_lead": "input_number.preheat_min_lead",
        "max_lead": "input_number.preheat_max_lead",
        "unocc_cap": "input_number.preheat_unoccupied_cap",
    }

    try:
        cfg = await hass.async_add_executor_job(furnace_config_io.load_config)
    except Exception as e:
        log.error(f"furnace_preheat: error loading config file: {e}")
        cfg = {}

    target, target_source = _resolve_target_temp(cfg)
    log.debug(
        "furnace_preheat: resolved target temperature = %.1fF (source=%s)",
        target,
        target_source,
    )

    return {
        "climate": _clean_entity_id(cfg.get("climate"), defaults["climate"]),
        "indoor": _clean_entity_id(cfg.get("indoor_temp"), defaults["indoor"]),
        "outdoor": _clean_entity_id(cfg.get("outdoor_temp"), defaults["outdoor"]),

        "forecast_low": _clean_entity_id(cfg.get("forecast_low"), defaults["forecast_low"]),
        "occupied": _clean_entity_id(cfg.get("occupied_binary"), defaults["occupied"]),
        "vacation": _clean_entity_id(cfg.get("vacation"), defaults["vacation"]),

        "comfort": _clean_entity_id(cfg.get("comfort_time"), defaults["comfort"]),
        "preheat": _clean_entity_id(cfg.get("preheat_start"), defaults["preheat"]),

        "target": target,
        "active_hours": _resolve_active_hours(cfg),

        "forecast_hours": _resolve_forecast_hours(cfg),
        "min_lead": _clean_entity_id(cfg.get("min_lead"), defaults["min_lead"]),
        "max_lead": _clean_entity_id(cfg.get("max_lead"), defaults["max_lead"]),
        "unocc_cap": _clean_entity_id(cfg.get("unocc_cap"), defaults["unocc_cap"]),
    }


#
# Model storage in input_text.furnace_model_json
#

DEFAULT_MODEL = {"version": 2, "k": 12.0, "alpha": 0.15, "offset_min": 0.0}
SAMPLE = {"last_t": None, "last_ts": None}


def _get_model():
    raw = _entity("input_text.furnace_model_json", None)
    if not raw:
        return DEFAULT_MODEL.copy()
    try:
        model = json.loads(raw)
        return {
            "version": 2,
            "k": float(model.get("k", DEFAULT_MODEL["k"])),
            "alpha": float(model.get("alpha", DEFAULT_MODEL["alpha"])),
            "offset_min": float(model.get("offset_min", DEFAULT_MODEL["offset_min"])),
        }
    except Exception:
        return DEFAULT_MODEL.copy()


def _save_model(model):
    try:
        payload = json.dumps(
            {
                "version": 2,
                "k": float(model["k"]),
                "alpha": float(model.get("alpha", DEFAULT_MODEL["alpha"])),
                "offset_min": float(model.get("offset_min", DEFAULT_MODEL["offset_min"])),
            }
        )
        service.call(
            "input_text",
            "set_value",
            entity_id="input_text.furnace_model_json",
            value=payload,
        )
    except Exception as e:
        log.error(f"furnace_preheat: save failed: {e}")


@time_trigger("startup")
def init_model():
    cur = _entity("input_text.furnace_model_json")
    if cur in (None, "unknown", "unavailable", ""):
        _save_model(DEFAULT_MODEL)
        return
    try:
        _ = _get_model()
    except Exception:
        _save_model(DEFAULT_MODEL)


#
# Cycle capture: record the moment preheat becomes active
# Also clear ARRIVAL latch for the new cycle.
#

@state_trigger("input_boolean.preheat_active == 'on'")
async def furnace_preheat_capture_start():
    cfg = await _load_cfg()
    CYCLE["start_ts"] = datetime.now()
    CYCLE["start_t"] = _entity_f(cfg["indoor"])

    # RC1-004: reset arrival latch for new session
    ARRIVAL["ts"] = None
    ARRIVAL["t"] = None
    ARRIVAL["reason"] = None

    log.info(
        "furnace_preheat: captured preheat start at %s indoor=%.2fF"
        % (CYCLE["start_ts"].strftime("%H:%M:%S"), CYCLE["start_t"])
    )


#
# Services
#

@service
def furnace_preheat_dump_model():
    log.info(f"furnace_preheat: model = {_get_model()}")


@service
def furnace_preheat_reset_model():
    _save_model(DEFAULT_MODEL)


@service
async def furnace_preheat_dump_config():
    cfg = await _load_cfg()
    log.info(f"furnace_preheat: effective cfg = {cfg}")


@service
async def furnace_preheat_mark_arrival(arrival_tolerance: float = 0.3, reason: str = "threshold"):
    """
    RC1-004: Latch ARRIVAL exactly once per preheat session.

    Intended to be called by an automation that triggers on indoor temp reaching:
        indoor >= target - arrival_tolerance
    """
    # Idempotent
    if ARRIVAL["ts"] is not None:
        return

    cfg = await _load_cfg()
    indoor = _entity_f(cfg["indoor"])
    target = float(cfg["target"])

    tol = float(arrival_tolerance) if arrival_tolerance is not None else 0.3

    # Safety: only latch if threshold is actually met right now
    if indoor < (target - tol):
        log.debug(
            "furnace_preheat: mark_arrival ignored (below threshold). indoor=%.2f target=%.2f tol=%.2f"
            % (indoor, target, tol)
        )
        return

    ARRIVAL["ts"] = datetime.now()
    ARRIVAL["t"] = indoor
    ARRIVAL["reason"] = str(reason) if reason is not None else "threshold"

    log.info(
        "furnace_preheat: arrival latched at %s indoor=%.2fF target=%.2fF tol=%.2f (%s)"
        % (ARRIVAL["ts"].strftime("%H:%M:%S"), indoor, target, tol, ARRIVAL["reason"])
    )


@service
async def furnace_preheat_evaluate_arrival():
    """
    Called at comfort time by automation.

    RC1-004 behavior:
    - If ARRIVAL latch exists, compute arrival time error in minutes vs comfort time,
      and update offset_min from that time error (late fast, early slow).
    - Update k from cycle k_cycle using start->arrival window when ARRIVAL exists
      (prevents post-arrival modulation from contaminating k).
    - If ARRIVAL is missing (never hit target), fall back to Beta 9 behavior
      using temperature error at comfort time mapped to minutes via k_used.
    """
    cfg = await _load_cfg()
    model = _get_model()

    indoor_now = _entity_f(cfg["indoor"])
    target = float(cfg["target"])

    k_model = float(model.get("k", DEFAULT_MODEL["k"]))
    offset = float(model.get("offset_min", 0.0))

    # Comfort datetime (today or tomorrow) aligned with "now"
    comfort_s = _entity(cfg["comfort"]) or "06:00:00"
    hh, mm, ss = [int(x) for x in comfort_s.split(":")]
    now = datetime.now()
    comfort_dt = now.replace(hour=hh, minute=mm, second=ss, microsecond=0)

    # If comfort time earlier than now by more than a few minutes, interpret as "today's comfort already passed"
    # (evaluate_arrival is typically called right at comfort time; this is just defensive.)
    if comfort_dt < (now - timedelta(minutes=10)):
        comfort_dt = comfort_dt + timedelta(days=1)

    # Choose evaluation endpoint:
    # - If ARRIVAL latched, use arrival timestamp and arrival temp
    # - Otherwise, use now (comfort time) and current indoor temp
    end_ts = ARRIVAL["ts"] if ARRIVAL["ts"] is not None else now
    end_t = float(ARRIVAL["t"]) if ARRIVAL["t"] is not None else indoor_now

    # Compute cycle-effective k using start->end window (end is arrival when available)
    k_cycle = None
    if CYCLE["start_ts"] is not None and CYCLE["start_t"] is not None:
        minutes = max(1.0, (end_ts - CYCLE["start_ts"]).total_seconds() / 60.0)
        start_t = float(CYCLE["start_t"])
        gained = end_t - start_t

        # High-demand gate (avoid modulated/partial-load contaminating k)
        delta_start = max(0.0, target - start_t)
        if delta_start >= 2.0 and minutes >= 15.0 and gained >= 0.5:
            k_cycle = minutes / gained

    # Conservative k for error-to-minutes mapping (fallback path)
    k_used = k_model
    if k_cycle is not None:
        k_used = max(k_model, k_cycle)

    # --- RC1-004 primary path: time-based arrival error if ARRIVAL exists ---
    if ARRIVAL["ts"] is not None:
        # arrival_offset_min: negative = early, positive = late
        arrival_offset_min = (ARRIVAL["ts"] - comfort_dt).total_seconds() / 60.0
        arrival_offset_min = max(-180.0, min(180.0, arrival_offset_min))

        # Asymmetric offset correction: late fast, early slow; clamp >= 0 to prefer slight earliness (Beta 9 behavior)
        alpha_late = 0.60
        alpha_early = 0.10
        alpha_off = alpha_late if arrival_offset_min > 0 else alpha_early

        new_offset = (1 - alpha_off) * offset + alpha_off * arrival_offset_min
        new_offset = max(0.0, min(180.0, new_offset))

        # Update k from cycle measurement (asymmetric: increase faster, decrease slower)
        if k_cycle is not None:
            alpha_up = 0.40
            alpha_down = 0.08
            alpha_k = alpha_up if k_cycle > k_model else alpha_down

            k_new = (1 - alpha_k) * k_model + alpha_k * k_cycle
            k_new = max(2.0, min(60.0, k_new))
            model["k"] = k_new

        model["offset_min"] = new_offset
        _save_model(model)

        log.info(
            "furnace_preheat: arrival eval (time-based) arrival_ts=%s comfort=%s "
            "arrival_offset_min=%.1f offset_old=%.1f offset_new=%.1f "
            "k_model=%.2f k_cycle=%s k_used=%.2f"
            % (
                ARRIVAL["ts"].strftime("%H:%M:%S"),
                comfort_dt.strftime("%H:%M:%S"),
                arrival_offset_min,
                offset,
                new_offset,
                k_model,
                f"{k_cycle:.2f}" if k_cycle else "n/a",
                k_used,
            )
        )
        return

    # --- Fallback path: temperature error at comfort time (Beta 9) ---
    error_T = target - indoor_now  # + => late, - => early (temperature-based)

    # If we're within 0.3°, treat as on-time
    if abs(error_T) < 0.3:
        log.info(
            "furnace_preheat: arrival ok (temp-based) indoor=%.1fF target=%.1fF k_model=%.2f k_cycle=%s offset=%.1f"
            % (indoor_now, target, k_model, f"{k_cycle:.2f}" if k_cycle else "n/a", offset)
        )
        return

    # Convert temperature error to minutes (bounded)
    error_min = error_T * k_used
    error_min = max(-120.0, min(120.0, error_min))

    alpha_late = 0.60
    alpha_early = 0.10
    alpha_off = alpha_late if error_T > 0 else alpha_early

    new_offset = (1 - alpha_off) * offset + alpha_off * error_min
    new_offset = max(0.0, min(180.0, new_offset))

    if k_cycle is not None:
        alpha_up = 0.40
        alpha_down = 0.08
        alpha_k = alpha_up if k_cycle > k_model else alpha_down

        k_new = (1 - alpha_k) * k_model + alpha_k * k_cycle
        k_new = max(2.0, min(60.0, k_new))
        model["k"] = k_new

    model["offset_min"] = new_offset
    _save_model(model)

    log.info(
        "furnace_preheat: arrival eval (temp-based) indoor=%.1fF target=%.1fF error_T=%.2fF "
        "k_model=%.2f k_cycle=%s k_used=%.2f error_min=%.1fm offset_old=%.1f offset_new=%.1f"
        % (
            indoor_now,
            target,
            error_T,
            k_model,
            f"{k_cycle:.2f}" if k_cycle else "n/a",
            k_used,
            error_min,
            offset,
            new_offset,
        )
    )


#
# Learning loop (slope-based) — optional safety net
# One-sided: may only INCREASE k (never make system "faster")
#

@time_trigger("cron(* * * * *)")  # every minute
async def learn_from_slope():
    cfg = await _load_cfg()

    # Learn only while actually preheating (avoid daytime maintenance ramps)
    if not _entity_onoff("input_boolean.preheat_active", default_off=True):
        SAMPLE["last_t"] = None
        SAMPLE["last_ts"] = None
        return

    # RC1-004: if ARRIVAL is latched, stop slope learning for the remainder of the session
    if ARRIVAL["ts"] is not None:
        SAMPLE["last_t"] = None
        SAMPLE["last_ts"] = None
        return

    # Use climate state for mode
    hvac_mode = (_entity(cfg["climate"], "") or "").lower()
    if hvac_mode not in ("heat", "heat_cool"):
        SAMPLE["last_t"] = None
        SAMPLE["last_ts"] = None
        return

    indoor = _entity_f(cfg["indoor"])
    target = float(cfg["target"])

    # Ignore the slow tail around target
    if indoor >= (target - 1.0):
        SAMPLE["last_t"] = None
        SAMPLE["last_ts"] = None
        return

    now = datetime.now()
    if SAMPLE["last_t"] is None:
        SAMPLE["last_t"] = indoor
        SAMPLE["last_ts"] = now
        return

    dt_min = max(0.1, (now - SAMPLE["last_ts"]).total_seconds() / 60.0)
    dT = indoor - SAMPLE["last_t"]
    SAMPLE["last_t"] = indoor
    SAMPLE["last_ts"] = now

    slope = dT / dt_min  # °F per min

    # Keep only plausible, positive ramps
    if slope <= 0.02 or slope >= 2.0:
        return

    k_obs = 1.0 / slope  # minutes per degree
    model = _get_model()
    k_cur = float(model.get("k", DEFAULT_MODEL["k"]))

    # EWMA (biased to accept increases faster than decreases)
    alpha_up = 0.30
    alpha_down = 0.05
    alpha = alpha_up if k_obs > k_cur else alpha_down

    k_new = (1 - alpha) * k_cur + alpha * k_obs
    k_new = max(2.0, min(60.0, k_new))

    # One-sided clamp: never allow slope learning to make k smaller/faster
    k_new = max(k_cur, k_new)

    if k_new > k_cur * 1.01:
        model["k"] = k_new
        _save_model(model)


#
# Recompute preheat schedule
#

@service
@time_trigger("cron(0 21 * * *)")      # 21:00 daily
@time_trigger("cron(30 23 * * *)")     # 23:30 daily
@time_trigger("cron(*/15 2-7 * * *)")  # every 15 minutes from 02:00–07:59
async def furnace_preheat_recompute():
    cfg = await _load_cfg()

    if _entity_onoff(cfg["vacation"]):
        log.info("furnace_preheat: vacation mode active; skipping schedule")
        return

    comfort = _entity(cfg["comfort"]) or "06:00:00"

    def _mk_on(base: datetime, hhmmss: str):
        hh, mm, ss = [int(x) for x in hhmmss.split(":")]
        return base.replace(hour=hh, minute=mm, second=ss, microsecond=0)

    now = datetime.now()
    comfort_today = _mk_on(now, comfort)
    comfort_dt = comfort_today if comfort_today > now else _mk_on(now + timedelta(days=1), comfort)

    # --- Freeze guard: avoid moving preheat_start once we are close to it ---
    existing_start_s = _entity(cfg["preheat"])
    if existing_start_s:
        try:
            hh, mm, ss = [int(x) for x in existing_start_s.split(":")]
            existing_start_dt = comfort_dt.replace(hour=hh, minute=mm, second=ss, microsecond=0)

            # If the stored start appears after comfort, interpret it as "today"
            if existing_start_dt > comfort_dt:
                existing_start_dt -= timedelta(days=1)

            freeze_window_min = 15
            if datetime.now() >= (existing_start_dt - timedelta(minutes=freeze_window_min)):
                log.info(
                    "furnace_preheat: recompute skipped (freeze window). existing_start=%s"
                    % existing_start_dt.strftime("%H:%M:%S")
                )
                return
        except Exception as e:
            log.debug(f"furnace_preheat: freeze guard skipped: {e}")

    model = _get_model()
    k = float(model.get("k", DEFAULT_MODEL["k"]))
    offset_min = float(model.get("offset_min", 0.0))

    current = _entity_f(cfg["indoor"])
    target = float(cfg["target"])
    outdoor = _entity_f(cfg["outdoor"])

    delta = max(0.0, target - current)
    bias = 1.0

    if cfg["forecast_low"]:
        f_low = _entity_f(cfg["forecast_low"], outdoor)
        drop = max(0.0, outdoor - f_low)
        if drop >= 5:
            bias += 0.10
        if drop >= 10:
            bias += 0.20

    lead_min = (k * delta * bias) + offset_min

    occupied = _entity_onoff(cfg["occupied"], default_off=False)
    if not occupied:
        cap = float(_entity(cfg["unocc_cap"]) or 0)
        if cap > 0:
            lead_min = min(lead_min, cap)

    min_lead = float(_entity(cfg["min_lead"]) or 0)
    max_lead = float(_entity(cfg["max_lead"]) or 240)
    lead_min = max(min_lead, min(max_lead, lead_min))

    start_dt = comfort_dt - timedelta(minutes=lead_min)

    # Optional clamp to active_hours window
    try:
        start_s, end_s = cfg["active_hours"]
        win_start = _mk_on(start_dt, start_s)
        win_end = _mk_on(start_dt, end_s)

        if win_end <= win_start:
            # Window crosses midnight
            if start_dt < win_start:
                win_start -= timedelta(days=1)
            else:
                win_end += timedelta(days=1)

        if start_dt < win_start:
            start_dt = win_start
        if start_dt > win_end:
            start_dt = win_end
    except Exception as e:
        log.debug(f"furnace_preheat: window clamp skipped: {e}")

    service.call(
        "input_datetime",
        "set_datetime",
        entity_id=cfg["preheat"],
        time=start_dt.strftime("%H:%M:%S"),
    )

    log.info(
        "furnace_preheat: delta=%.1fF k=%.2f bias=%.2f offset=%.1fm occ=%s lead=%.0fm start=%s comfort=%s"
        % (
            delta,
            k,
            bias,
            offset_min,
            occupied,
            lead_min,
            start_dt.strftime("%H:%M:%S"),
            comfort_dt.strftime("%H:%M:%S"),
        )
    )


#
# Debug logging of hvac_action
#

@state_trigger("var_name.startswith('climate.')")
async def furnace_preheat_log_action_changes(value=None, var_name=None, old_value=None):
    cfg = await _load_cfg()
    climate_eid = cfg["climate"]

    if var_name != climate_eid:
        return

    attrs = state.getattr(climate_eid) or {}
    act = attrs.get("hvac_action")
    log.debug(f"furnace_preheat: hvac_action={act}")
