# HVAC Comfort Start — Adaptive Preheat
# Version: RC1-004 (builds on Beta 9 baseline)
#
# DEV DIAGNOSTICS (LOCAL-ONLY, NO GIT):
# - Toggle: input_boolean.hvac_dev_diagnostics
# - Writes CSV to:
#     /config/log_tracking/dev_capture.csv   (capture_start boundary conditions)
#     /config/log_tracking/dev_eval.csv      (evaluate_arrival diagnostics)
#
# IMPORTANT PYSCRIPT NOTES:
# - Avoid generator expressions, comprehensions, ternary expressions, and some advanced AST forms.
# - Keep helpers defined BEFORE any startup triggers/services use them.

import sys
import json
import re
import os
from datetime import datetime, timedelta

MODULE_PATH = "/config/pyscript_modules"
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

import furnace_config_io  # noqa: E402

# -----------------------------
# Basic state helpers (MUST be defined early)
# -----------------------------

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
        # unknown/unavailable -> treat as OFF (default_off=True) or ON (default_off=False)
        return not default_off
    return str(v).lower() == "on"

# -----------------------------
# DEV diagnostics (CSV output) — Pyscript-safe
# -----------------------------

DIAG_TOGGLE = "input_boolean.hvac_dev_diagnostics"
DIAG_DIR = "/config/log_tracking"
EVAL_CSV = os.path.join(DIAG_DIR, "dev_eval.csv")
CAPTURE_CSV = os.path.join(DIAG_DIR, "dev_capture.csv")

def _diag_enabled():
    v = _entity(DIAG_TOGGLE, "off")
    return str(v).lower() == "on"


def _csv_cell(v):
    """Minimal CSV escaping (no generators/comprehensions)."""
    if v is None:
        return ""
    s = str(v)

    needs_quote = False
    for ch in [",", '"', "\n", "\r"]:
        if ch in s:
            needs_quote = True
            break

    if needs_quote:
        s = s.replace('"', '""')
        s = '"' + s + '"'
    return s

import diag_csv_writer

async def _csv_append(path, header, line, newfile):
    await task.executor(diag_csv_writer.append_csv, path, header, line, newfile)

async def diag_capture_start(ts, outside, forecast_low, inside, target, setback):
    if not _diag_enabled():
        return

    header = "ts,outside,forecast_low,inside,target,setback"

    cells = [ts, outside, forecast_low, inside, target, setback]
    parts = []
    for c in cells:
        parts.append(_csv_cell(c))
    line = ",".join(parts)

    newfile = not os.path.exists(CAPTURE_CSV)
    await _csv_append(CAPTURE_CSV, header, line, newfile)


async def diag_eval(ts, kind, arrival_ts, comfort, arrival_offset_min,
                   offset_old, offset_new, k_model, k_cycle, k_used):
    if not _diag_enabled():
        return

    header = "ts,kind,arrival_ts,comfort,arrival_offset_min,offset_old,offset_new,k_model,k_cycle,k_used"

    cells = [
        ts, kind, arrival_ts, comfort,
        arrival_offset_min, offset_old, offset_new,
        k_model, k_cycle, k_used
    ]
    parts = []
    for c in cells:
        parts.append(_csv_cell(c))
    line = ",".join(parts)

    newfile = not os.path.exists(EVAL_CSV)
    await _csv_append(EVAL_CSV, header, line, newfile)

# -----------------------------
# Captured latches
# -----------------------------

# Captured at the moment preheat becomes active (used for cycle-based k)
CYCLE = {"start_ts": None, "start_t": None}

# RC1-004: ARRIVAL latch captured at first threshold hit (idempotent)
ARRIVAL = {"ts": None, "t": None, "reason": None}


# -----------------------------
# Config loading
# -----------------------------

_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def _clean_entity_id(val, default):
    """Return a usable entity_id string or default."""
    try:
        if val is None:
            return default
        s = str(val).strip()
        if not s:
            return default
        low = s.lower()
        if low in ("none", "null", "unknown", "unavailable"):
            return default
        return s
    except Exception:
        return default


def _resolve_active_hours(cfg):
    default = ["03:00:00", "23:00:00"]
    raw = cfg.get("active_hours", default)

    if (not isinstance(raw, (list, tuple))) or len(raw) != 2:
        log.warning("furnace_preheat: invalid active_hours (expected 2-item list); using default %s", default)
        return default

    start = raw[0]
    end = raw[1]
    if (not isinstance(start, str)) or (not isinstance(end, str)) or (_TIME_RE.match(start) is None) or (_TIME_RE.match(end) is None):
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
    if val < 1:
        val = 1
    if val > 48:
        val = 48
    return val


def _resolve_target_temp(cfg):
    """RC1 precedence: helper -> legacy JSON numeric -> hard default."""
    helper = "input_number.hvac_comfort_start_target_temp"

    try:
        v = state.get(helper)
        if v not in (None, "unknown", "unavailable", ""):
            return float(v), "helper"
    except Exception:
        pass

    legacy = cfg.get("target_temp")
    if isinstance(legacy, (int, float)):
        return float(legacy), "legacy_config"

    return 74.0, "default"


async def _load_cfg():
    defaults = {
        "climate": "climate.daikin",
        "indoor": "sensor.indoor_temperature",
        "outdoor": "sensor.main_room_outdoor_air_temperature",
        # Your actual helper
        "forecast_low": "input_number.nws_overnight_low",
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
        log.error("furnace_preheat: error loading config file: %s", e)
        cfg = {}

    target, target_source = _resolve_target_temp(cfg)
    log.debug("furnace_preheat: resolved target temperature = %.1fF (source=%s)", target, target_source)

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


# -----------------------------
# Model storage in input_text.furnace_model_json
# -----------------------------

DEFAULT_MODEL = {"version": 2, "k": 12.0, "alpha": 0.15, "offset_min": 0.0}
SAMPLE = {"last_t": None, "last_ts": None}


def _get_model():
    raw = _entity("input_text.furnace_model_json", None)
    if not raw:
        return DEFAULT_MODEL.copy()
    try:
        model = json.loads(raw)
        out = {}
        out["version"] = 2
        out["k"] = float(model.get("k", DEFAULT_MODEL["k"]))
        out["alpha"] = float(model.get("alpha", DEFAULT_MODEL["alpha"]))
        out["offset_min"] = float(model.get("offset_min", DEFAULT_MODEL["offset_min"]))
        return out
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
        service.call("input_text", "set_value", entity_id="input_text.furnace_model_json", value=payload)
    except Exception as e:
        log.error("furnace_preheat: save failed: %s", e)


@time_trigger("startup")
def init_model():
    cur = _entity("input_text.furnace_model_json", None)
    if cur in (None, "unknown", "unavailable", ""):
        _save_model(DEFAULT_MODEL)
        return
    try:
        _ = _get_model()
    except Exception:
        _save_model(DEFAULT_MODEL)


# -----------------------------
# Cycle capture (rising edge only)
# -----------------------------

@state_trigger("input_boolean.preheat_active")
async def furnace_preheat_capture_start(value=None, old_value=None):
    # Rising edge: off -> on only
    if value != "on":
        return
    if old_value == "on":
        return

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

    # DEV telemetry capture (boundary conditions)
    try:
        ts = CYCLE["start_ts"].isoformat()

        outside = _entity_f(cfg["outdoor"], 0.0)
        f_low = _entity_f(cfg["forecast_low"], outside)

        if CYCLE["start_t"] is not None:
            inside = float(CYCLE["start_t"])
        else:
            inside = _entity_f(cfg["indoor"], 0.0)

        target = float(cfg["target"])
        setback = target - inside

        await diag_capture_start(ts, outside, f_low, inside, target, setback)
    except Exception as e:
        log.error("furnace_preheat: diag_capture_start FAILED: %s", e)


# -----------------------------
# Services
# -----------------------------

@service
def furnace_preheat_dump_model():
    log.info("furnace_preheat: model = %s", _get_model())


@service
def furnace_preheat_reset_model():
    _save_model(DEFAULT_MODEL)


@service
async def furnace_preheat_dump_config():
    cfg = await _load_cfg()
    log.info("furnace_preheat: effective cfg = %s", cfg)


@service
async def furnace_preheat_mark_arrival(arrival_tolerance: float = 0.3, reason: str = "threshold"):
    # Idempotent
    if ARRIVAL["ts"] is not None:
        return

    cfg = await _load_cfg()
    indoor = _entity_f(cfg["indoor"])
    target = float(cfg["target"])

    tol = 0.3
    if arrival_tolerance is not None:
        try:
            tol = float(arrival_tolerance)
        except Exception:
            tol = 0.3

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
    cfg = await _load_cfg()
    model = _get_model()

    indoor_now = _entity_f(cfg["indoor"])
    target = float(cfg["target"])

    k_model = float(model.get("k", DEFAULT_MODEL["k"]))
    offset = float(model.get("offset_min", 0.0))

    comfort_s = _entity(cfg["comfort"], None)
    if comfort_s is None:
        comfort_s = "06:00:00"
    parts = comfort_s.split(":")
    hh = int(parts[0])
    mm = int(parts[1])
    ss = int(parts[2])
    now = datetime.now()
    comfort_dt = now.replace(hour=hh, minute=mm, second=ss, microsecond=0)

    if comfort_dt < (now - timedelta(minutes=10)):
        comfort_dt = comfort_dt + timedelta(days=1)

    # Endpoint: ARRIVAL if latched else comfort-time (now)
    if ARRIVAL["ts"] is not None:
        end_ts = ARRIVAL["ts"]
    else:
        end_ts = now

    if ARRIVAL["t"] is not None:
        end_t = float(ARRIVAL["t"])
    else:
        end_t = indoor_now

    # Compute cycle-effective k using start->end window
    k_cycle = None
    if (CYCLE["start_ts"] is not None) and (CYCLE["start_t"] is not None):
        minutes = (end_ts - CYCLE["start_ts"]).total_seconds() / 60.0
        if minutes < 1.0:
            minutes = 1.0

        start_t = float(CYCLE["start_t"])
        gained = end_t - start_t

        delta_start = target - start_t
        if delta_start < 0.0:
            delta_start = 0.0

        if (delta_start >= 2.0) and (minutes >= 15.0) and (gained >= 0.5):
            k_cycle = minutes / gained

    # Conservative k used for mapping in fallback
    k_used = k_model
    if k_cycle is not None:
        if k_cycle > k_used:
            k_used = k_cycle

    # --- Primary path: time-based arrival error if ARRIVAL exists ---
    if ARRIVAL["ts"] is not None:
        arrival_offset_min = (ARRIVAL["ts"] - comfort_dt).total_seconds() / 60.0
        if arrival_offset_min < -180.0:
            arrival_offset_min = -180.0
        if arrival_offset_min > 180.0:
            arrival_offset_min = 180.0

        alpha_late = 0.60
        alpha_early = 0.10
        if arrival_offset_min > 0:
            alpha_off = alpha_late
        else:
            alpha_off = alpha_early

        new_offset = (1 - alpha_off) * offset + alpha_off * arrival_offset_min
        if new_offset < 0.0:
            new_offset = 0.0
        if new_offset > 180.0:
            new_offset = 180.0

        if k_cycle is not None:
            alpha_up = 0.40
            alpha_down = 0.08
            if k_cycle > k_model:
                alpha_k = alpha_up
            else:
                alpha_k = alpha_down

            k_new = (1 - alpha_k) * k_model + alpha_k * k_cycle
            if k_new < 2.0:
                k_new = 2.0
            if k_new > 60.0:
                k_new = 60.0
            model["k"] = k_new

        model["offset_min"] = new_offset
        _save_model(model)

        # DEV telemetry
        try:
            if k_cycle is not None:
                k_cycle_out = round(k_cycle, 3)
            else:
                k_cycle_out = ""
            await diag_eval(
                ts=datetime.now().isoformat(),
                kind="time-based",
                arrival_ts=ARRIVAL["ts"].strftime("%H:%M:%S"),
                comfort=comfort_dt.strftime("%H:%M:%S"),
                arrival_offset_min=round(arrival_offset_min, 3),
                offset_old=round(offset, 3),
                offset_new=round(new_offset, 3),
                k_model=round(k_model, 3),
                k_cycle=k_cycle_out,
                k_used=round(k_used, 3),
            )
        except Exception as e:
            log.error("furnace_preheat: await diag_eval FAILED: %s", e)

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
                ("%0.2f" % k_cycle) if k_cycle is not None else "n/a",
                k_used,
            )
        )
        return

    # --- Fallback path: temperature error at comfort time (Beta 9 style) ---
    error_T = target - indoor_now

    if abs(error_T) < 0.3:
        log.info(
            "furnace_preheat: arrival ok (temp-based) indoor=%.1fF target=%.1fF k_model=%.2f k_cycle=%s offset=%.1f"
            % (indoor_now, target, k_model, ("%0.2f" % k_cycle) if k_cycle is not None else "n/a", offset)
        )
        return

    error_min = error_T * k_used
    if error_min < -120.0:
        error_min = -120.0
    if error_min > 120.0:
        error_min = 120.0

    alpha_late = 0.60
    alpha_early = 0.10
    if error_T > 0:
        alpha_off = alpha_late
    else:
        alpha_off = alpha_early

    new_offset = (1 - alpha_off) * offset + alpha_off * error_min
    if new_offset < 0.0:
        new_offset = 0.0
    if new_offset > 180.0:
        new_offset = 180.0

    if k_cycle is not None:
        alpha_up = 0.40
        alpha_down = 0.08
        if k_cycle > k_model:
            alpha_k = alpha_up
        else:
            alpha_k = alpha_down

        k_new = (1 - alpha_k) * k_model + alpha_k * k_cycle
        if k_new < 2.0:
            k_new = 2.0
        if k_new > 60.0:
            k_new = 60.0
        model["k"] = k_new

    model["offset_min"] = new_offset
    _save_model(model)

    # DEV telemetry for fallback
    try:
        if k_cycle is not None:
            k_cycle_out = round(k_cycle, 3)
        else:
            k_cycle_out = ""
        await diag_eval(
            ts=datetime.now().isoformat(),
            kind="temp-based",
            arrival_ts=now.strftime("%H:%M:%S"),
            comfort=comfort_dt.strftime("%H:%M:%S"),
            arrival_offset_min=round(error_min, 3),
            offset_old=round(offset, 3),
            offset_new=round(new_offset, 3),
            k_model=round(k_model, 3),
            k_cycle=k_cycle_out,
            k_used=round(k_used, 3),
        )
    except Exception as e:
        log.error("furnace_preheat: await diag_eval(temp) FAILED: %s", e)

    log.info(
        "furnace_preheat: arrival eval (temp-based) indoor=%.1fF target=%.1fF error_T=%.2fF "
        "k_model=%.2f k_cycle=%s k_used=%.2f error_min=%.1fm offset_old=%.1f offset_new=%.1f"
        % (
            indoor_now,
            target,
            error_T,
            k_model,
            ("%0.2f" % k_cycle) if k_cycle is not None else "n/a",
            k_used,
            error_min,
            offset,
            new_offset,
        )
    )


# -----------------------------
# Learning loop (slope-based) — optional safety net
# -----------------------------

@time_trigger("cron(* * * * *)")  # every minute
async def learn_from_slope():
    cfg = await _load_cfg()

    if not _entity_onoff("input_boolean.preheat_active", default_off=True):
        SAMPLE["last_t"] = None
        SAMPLE["last_ts"] = None
        return

    # RC1-004: if ARRIVAL is latched, stop slope learning for the remainder of the session
    if ARRIVAL["ts"] is not None:
        SAMPLE["last_t"] = None
        SAMPLE["last_ts"] = None
        return

    hvac_mode = str(_entity(cfg["climate"], "") or "").lower()
    if (hvac_mode != "heat") and (hvac_mode != "heat_cool"):
        SAMPLE["last_t"] = None
        SAMPLE["last_ts"] = None
        return

    indoor = _entity_f(cfg["indoor"])
    target = float(cfg["target"])

    if indoor >= (target - 1.0):
        SAMPLE["last_t"] = None
        SAMPLE["last_ts"] = None
        return

    now = datetime.now()
    if SAMPLE["last_t"] is None:
        SAMPLE["last_t"] = indoor
        SAMPLE["last_ts"] = now
        return

    dt_min = (now - SAMPLE["last_ts"]).total_seconds() / 60.0
    if dt_min < 0.1:
        dt_min = 0.1

    dT = indoor - SAMPLE["last_t"]
    SAMPLE["last_t"] = indoor
    SAMPLE["last_ts"] = now

    slope = dT / dt_min  # °F per min
    if (slope <= 0.02) or (slope >= 2.0):
        return

    k_obs = 1.0 / slope  # minutes per degree
    model = _get_model()
    k_cur = float(model.get("k", DEFAULT_MODEL["k"]))

    alpha_up = 0.30
    alpha_down = 0.05
    if k_obs > k_cur:
        alpha_k = alpha_up
    else:
        alpha_k = alpha_down

    k_new = (1 - alpha_k) * k_cur + alpha_k * k_obs
    if k_new < 2.0:
        k_new = 2.0
    if k_new > 60.0:
        k_new = 60.0

    # One-sided clamp: never allow slope learning to make k smaller/faster
    if k_new < k_cur:
        k_new = k_cur

    if k_new > (k_cur * 1.01):
        model["k"] = k_new
        _save_model(model)


# -----------------------------
# Recompute preheat schedule
# -----------------------------

@service
@time_trigger("cron(0 21 * * *)")      # 21:00 daily
@time_trigger("cron(30 23 * * *)")     # 23:30 daily
@time_trigger("cron(*/15 2-7 * * *)")  # every 15 minutes from 02:00–07:59
async def furnace_preheat_recompute():
    cfg = await _load_cfg()

    if _entity_onoff(cfg["vacation"]):
        log.info("furnace_preheat: vacation mode active; skipping schedule")
        return

    comfort = _entity(cfg["comfort"], None)
    if comfort is None:
        comfort = "06:00:00"

    def _mk_on(base_dt, hhmmss):
        parts = hhmmss.split(":")
        hh = int(parts[0])
        mm = int(parts[1])
        ss = int(parts[2])
        return base_dt.replace(hour=hh, minute=mm, second=ss, microsecond=0)
    now = datetime.now()
    comfort_today = _mk_on(now, comfort)
    if comfort_today > now:
        comfort_dt = comfort_today
    else:
        comfort_dt = _mk_on(now + timedelta(days=1), comfort)

    # Freeze guard
    existing_start_s = _entity(cfg["preheat"], None)
    if existing_start_s:
        try:
            parts = existing_start_s.split(":")
            hh = int(parts[0])
            mm = int(parts[1])
            ss = int(parts[2])
            existing_start_dt = comfort_dt.replace(hour=hh, minute=mm, second=ss, microsecond=0)

            if existing_start_dt > comfort_dt:
                existing_start_dt = existing_start_dt - timedelta(days=1)

            freeze_window_min = 15
            if datetime.now() >= (existing_start_dt - timedelta(minutes=freeze_window_min)):
                log.info(
                    "furnace_preheat: recompute skipped (freeze window). existing_start=%s"
                    % existing_start_dt.strftime("%H:%M:%S")
                )
                return
        except Exception as e:
            log.debug("furnace_preheat: freeze guard skipped: %s", e)

    model = _get_model()
    k = float(model.get("k", DEFAULT_MODEL["k"]))
    offset_min = float(model.get("offset_min", 0.0))

    current = _entity_f(cfg["indoor"])
    target = float(cfg["target"])
    outdoor = _entity_f(cfg["outdoor"])

    delta = target - current
    if delta < 0.0:
        delta = 0.0

    bias = 1.0

    # Forecast bias uses your helper entity
    f_low = _entity_f(cfg["forecast_low"], outdoor)
    drop = outdoor - f_low
    if drop < 0.0:
        drop = 0.0
    if drop >= 5.0:
        bias = bias + 0.10
    if drop >= 10.0:
        bias = bias + 0.20

    lead_min = (k * delta * bias) + offset_min

    occupied = _entity_onoff(cfg["occupied"], default_off=False)
    if not occupied:
        cap_raw = _entity(cfg["unocc_cap"], None)
        cap = 0.0
        if cap_raw is not None:
            try:
                cap = float(cap_raw)
            except Exception:
                cap = 0.0
        if cap > 0.0 and lead_min > cap:
            lead_min = cap

    min_lead_raw = _entity(cfg["min_lead"], None)
    max_lead_raw = _entity(cfg["max_lead"], None)

    min_lead = 0.0
    max_lead = 240.0
    try:
        if min_lead_raw is not None:
            min_lead = float(min_lead_raw)
    except Exception:
        min_lead = 0.0
    try:
        if max_lead_raw is not None:
            max_lead = float(max_lead_raw)
    except Exception:
        max_lead = 240.0

    if lead_min < min_lead:
        lead_min = min_lead
    if lead_min > max_lead:
        lead_min = max_lead

    start_dt = comfort_dt - timedelta(minutes=lead_min)

    # Optional clamp to active_hours window
    try:
        start_s = cfg["active_hours"][0]
        end_s = cfg["active_hours"][1]

        win_start = _mk_on(start_dt, start_s)
        win_end = _mk_on(start_dt, end_s)

        if win_end <= win_start:
            # Window crosses midnight
            if start_dt < win_start:
                win_start = win_start - timedelta(days=1)
            else:
                win_end = win_end + timedelta(days=1)

        if start_dt < win_start:
            start_dt = win_start
        if start_dt > win_end:
            start_dt = win_end
    except Exception as e:
        log.debug("furnace_preheat: window clamp skipped: %s", e)

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


# -----------------------------
# Debug logging of hvac_action
# -----------------------------

@state_trigger("var_name.startswith('climate.')")
async def furnace_preheat_log_action_changes(value=None, var_name=None, old_value=None):
    cfg = await _load_cfg()
    climate_eid = cfg["climate"]

    if var_name != climate_eid:
        return

    attrs = state.getattr(climate_eid) or {}
    act = attrs.get("hvac_action")
    log.debug("furnace_preheat: hvac_action=%s", act)