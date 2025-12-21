# HVAC Comfort Start — Adaptive Preheat
# Version: Beta 9
# Status: Stable beta (validated on modulating furnace)
# Notes:
# - Uses cycle-based learning and asymmetric offset correction
# - Designed to prefer slight earliness over lateness

import sys
import json
from datetime import datetime, timedelta

MODULE_PATH = "/config/pyscript_modules"
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
    
CYCLE = {"start_ts": None, "start_t": None}

import furnace_config_io

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

async def _load_cfg():
    """Load config via native module in the executor."""
    try:
        cfg = await hass.async_add_executor_job(furnace_config_io.load_config)
    except Exception as e:
        log.error(f"furnace_preheat: error loading config file: {e}")
        cfg = {}

    return {
        "climate": cfg.get("climate", "climate.daikin"),
        "indoor": cfg.get("indoor_temp", "sensor.indoor_temperature"),
        "outdoor": cfg.get("outdoor_temp", "sensor.main_room_outdoor_air_temperature"),

        "forecast_low": cfg.get("forecast_low", "sensor.nws_overnight_low_temperature"),
        "occupied": cfg.get("occupied_binary", "binary_sensor.family_home"),
        "vacation": cfg.get("vacation", "input_boolean.vacation"),

        "comfort": cfg.get("comfort_time", "input_datetime.comfort_time"),
        "preheat": cfg.get("preheat_start", "input_datetime.preheat_start"),

        "target": float(cfg.get("target_temp", 74)),
        "active_hours": cfg.get("active_hours", ["03:00:00", "23:00:00"]),

        "forecast_hours": int(cfg.get("forecast_hours_ahead", 8)),
        "min_lead": cfg.get("min_lead", "input_number.preheat_min_lead"),
        "max_lead": cfg.get("max_lead", "input_number.preheat_max_lead"),
        "unocc_cap": cfg.get("unocc_cap", "input_number.preheat_unoccupied_cap"),
    }


#
# Model storage in input_text.furnace_model_json
#

DEFAULT_MODEL = {"version": 2, "k": 1.0, "alpha": 0.15, "offset_min": 0.0}
SAMPLE = {"last_t": None, "last_ts": None}


def _get_model():
    raw = _entity("input_text.furnace_model_json", None)
    if not raw:
        return DEFAULT_MODEL.copy()
    try:
        model = json.loads(raw)
        return {
            "version": 2,
            "k": float(model.get("k", 1.0)),
            "alpha": float(model.get("alpha", 0.15)),
            "offset_min": float(model.get("offset_min", 0.0)),
        }
    except Exception:
        return DEFAULT_MODEL.copy()


def _save_model(model):
    try:
        payload = json.dumps(
            {
                "version": 2,
                "k": float(model["k"]),
                "alpha": float(model.get("alpha", 0.15)),
                "offset_min": float(model.get("offset_min", 0.0)),
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

@state_trigger("input_boolean.preheat_active == 'on'")
async def furnace_preheat_capture_start():
    cfg = await _load_cfg()
    CYCLE["start_ts"] = datetime.now()
    CYCLE["start_t"] = _entity_f(cfg["indoor"])
    log.info(
        "furnace_preheat: captured preheat start at %s indoor=%.2fF"
        % (CYCLE["start_ts"].strftime("%H:%M:%S"), CYCLE["start_t"])
    )

@time_trigger("startup")
def init_model():
    # Seed model if it's invalid JSON
    cur = _entity("input_text.furnace_model_json")
    if cur in (None, "unknown", "unavailable", ""):
        _save_model(DEFAULT_MODEL)
        return

    try:
        _ = _get_model()
    except Exception:
        _save_model(DEFAULT_MODEL)


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
async def furnace_preheat_evaluate_arrival():
    cfg = await _load_cfg()
    model = _get_model()

    indoor = _entity_f(cfg["indoor"])
    target = float(cfg["target"])

    k_model = float(model.get("k", 1.0))
    offset = float(model.get("offset_min", 0.0))

    error_T = target - indoor  # + => late, - => early

    # Guard: only trust cycle-based math near comfort time
    comfort_s = _entity(cfg["comfort"]) or "06:00:00"
    hh, mm, ss = [int(x) for x in comfort_s.split(":")]
    now = datetime.now()
    comfort_dt = now.replace(hour=hh, minute=mm, second=ss, microsecond=0)

    window_min = 5.0
    near_comfort = abs((now - comfort_dt).total_seconds()) <= window_min * 60.0

    # Determine cycle-effective k (only near comfort time)
    k_cycle = None
    if near_comfort and CYCLE["start_ts"] is not None and CYCLE["start_t"] is not None:
        minutes = max(
            1.0,
            (now - CYCLE["start_ts"]).total_seconds() / 60.0
        )
        gained = indoor - float(CYCLE["start_t"])
        if gained >= 0.5:
            k_cycle = minutes / gained

    # Use the slower (more conservative) k
    k_used = k_model
    if k_cycle is not None:
        k_used = max(k_model, k_cycle)

    # If we're essentially on target, do nothing
    if abs(error_T) < 0.3:
        log.info(
            "furnace_preheat: arrival ok indoor=%.1fF target=%.1fF k_model=%.2f k_cycle=%s offset=%.1f"
            % (
                indoor,
                target,
                k_model,
                f"{k_cycle:.2f}" if k_cycle else "n/a",
                offset,
            )
        )
        return

    # Minutes early/late based on k_used
    error_min = error_T * k_used
    error_min = max(-120.0, min(120.0, error_min))

    # Asymmetric offset correction
    alpha_late = 0.6    # correct lateness quickly
    alpha_early = 0.1   # back off earliness slowly
    alpha_off = alpha_late if error_T > 0 else alpha_early

    new_offset = (1 - alpha_off) * offset + alpha_off * error_min
    new_offset = max(0.0, min(180.0, new_offset))

    # Update k from cycle measurement (asymmetric)
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
        "furnace_preheat: arrival eval indoor=%.1fF target=%.1fF error_T=%.2fF "
        "k_model=%.2f k_cycle=%s k_used=%.2f error_min=%.1fm offset_old=%.1f offset_new=%.1f"
        % (
            indoor,
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
# Learning loop
#

@time_trigger("cron(* * * * *)")  # every minute
async def learn_from_slope():
    cfg = await _load_cfg()

    # Learn only while actually preheating (avoid daytime maintenance ramps)
    if not _entity_onoff("input_boolean.preheat_active", default_off=True):
        SAMPLE["last_t"] = None
        SAMPLE["last_ts"] = None
        return

    # Use climate state for mode (no attribute calls needed)
    hvac_mode = (_entity(cfg["climate"], "") or "").lower()
    if hvac_mode not in ("heat", "heat_cool"):
        SAMPLE["last_t"] = None
        SAMPLE["last_ts"] = None
        return

    indoor = _entity_f(cfg["indoor"])
    target = float(cfg["target"])

    # Ignore the slow tail around target; wider band for modulating units
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
    k_cur = float(model.get("k", 1.0))

    # Asymmetric EWMA:
    # - If k needs to INCREASE (we were late), adjust quickly   (alpha_up)
    # - If k wants to DECREASE, adjust very slowly              (alpha_down)
    alpha_up = 0.30
    alpha_down = 0.05
    alpha = alpha_up if k_obs > k_cur else alpha_down

    k_new = (1 - alpha) * k_cur + alpha * k_obs

    # Guard rails
    k_min = 2.0    # don’t allow unrealistically fast heating (<2 min/°F)
    k_max = 60.0   # don’t allow extreme values from weird spikes
    k_new = max(k_min, min(k_max, k_new))

    model["k"] = k_new
    _save_model(model)


#
# Recompute preheat schedule
#

@service
@time_trigger("cron(*/15 2-7 * * *)") # recompute every 15 minutes between 2 and 8
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
    comfort_dt = (
        comfort_today
        if comfort_today > now
        else _mk_on(now + timedelta(days=1), comfort)
    )

    # --- model parameters ---
    model = _get_model()
    k = float(model.get("k", 1.0))
    offset_min = float(model.get("offset_min", 0.0))

    # --- current conditions ---
    current = _entity_f(cfg["indoor"])
    target = float(cfg["target"])
    outdoor = _entity_f(cfg["outdoor"])

    delta = max(0.0, target - current)
    bias = 1.0

    # Forecast-based bias adjustment
    if cfg["forecast_low"]:
        f_low = _entity_f(cfg["forecast_low"], outdoor)
        drop = max(0.0, outdoor - f_low)
        if drop >= 5:
            bias += 0.10
        if drop >= 10:
            bias += 0.20

    # Base lead from model
    lead_min = k * delta * bias

    # Apply arrival-time offset from evaluation service
    lead_min += offset_min

    # Occupancy cap for unoccupied home
    occupied = _entity_onoff(cfg["occupied"], default_off=False)
    if not occupied:
        cap = float(_entity(cfg["unocc_cap"]) or 0)
        if cap > 0:
            lead_min = min(lead_min, cap)

    # Clamp to configured min/max bounds
    min_lead = float(_entity(cfg["min_lead"]) or 0)
    max_lead = float(_entity(cfg["max_lead"]) or 240)
    lead_min = max(min_lead, min(max_lead, lead_min))

    # Compute start datetime from comfort datetime
    start_dt = comfort_dt - timedelta(minutes=lead_min)

    # Optional clamp to active_hours window
    try:
        start_s, end_s = cfg["active_hours"]
        win_start = _mk_on(start_dt, start_s)
        win_end = _mk_on(start_dt, end_s)

        if win_end <= win_start:
            # Handle windows that cross midnight
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

    # Write new preheat start time
    service.call(
        "input_datetime",
        "set_datetime",
        entity_id=cfg["preheat"],
        time=start_dt.strftime("%H:%M:%S"),
    )

    log.info(
        "furnace_preheat: delta=%.1fF k=%.2f bias=%.2f offset=%.1fm occ=%s lead=%.0fm "
        "start=%s comfort=%s"
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

    # Only log when this is the configured climate entity
    if var_name != climate_eid:
        return

    attrs = state.getattr(climate_eid) or {}
    act = attrs.get("hvac_action")
    log.debug(f"furnace_preheat: hvac_action={act}")
