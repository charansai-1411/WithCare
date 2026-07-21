"""
Manual vitals logging — a caregiver records readings (blood sugar, BP, weight, …) for a person
and gets them back as a time series for trend charts. Stored as knowledge-graph `health_metric`
nodes (unique="never", so every reading is its own node), so they also enrich the person's memory.
"""
from datetime import datetime

from app.services.memory_service import write_fact, find_nodes, delete_node
from app.utils.logger import get_logger

logger = get_logger(__name__)

# metric key -> (label, default unit, kind). kind "bp" carries systolic/diastolic.
METRICS = {
    "blood_sugar":    ("Blood sugar", "mg/dL", "single"),
    "blood_pressure": ("Blood pressure", "mmHg", "bp"),
    "weight":         ("Weight", "kg", "single"),
    "heart_rate":     ("Heart rate", "bpm", "single"),
    "spo2":           ("SpO2", "%", "single"),
    "temperature":    ("Temperature", "F", "single"),
}


def log_vital(user_id, profile_id, metric, value=None, systolic=None, diastolic=None,
              unit=None, note="", at=None):
    label, default_unit, kind = METRICS.get(metric, (metric, "", "single"))
    unit = unit or default_unit
    at = at or datetime.now().isoformat(timespec="minutes")
    if kind == "bp":
        disp = f"{int(systolic)}/{int(diastolic)} {unit}"
        data = {"metric": metric, "systolic": systolic, "diastolic": diastolic,
                "unit": unit, "at": at, "note": note}
    else:
        disp = f"{value} {unit}".strip()
        data = {"metric": metric, "value": value, "unit": unit, "at": at, "note": note}
    nid = write_fact(user_id, profile_id, "health_metric", f"{label}: {disp}",
                     data=data, predicate="recorded", unique="never")
    return {"id": nid, "name": f"{label}: {disp}", **data}


def list_vitals(user_id, profile_id=None, metric=None):
    """All readings for a person (optionally one metric), oldest -> newest for trend charts."""
    out = []
    for n in find_nodes(user_id, "health_metric", profile_id):
        d = n.get("data") or {}
        if not d.get("metric"):
            continue  # skip any legacy/agent-written health fact without a metric
        if metric and d.get("metric") != metric:
            continue
        out.append({"id": n["id"], "name": n["name"], **d})
    out.sort(key=lambda r: r.get("at") or "")
    return out


def delete_vital(user_id, vital_id):
    return bool(delete_node(user_id, vital_id))
