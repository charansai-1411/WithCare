"""
Vitals API — manually log a person's readings and read them back for trend charts.
  GET    /api/vitals?profile_id=&metric=   list readings (oldest -> newest)
  POST   /api/vitals                        log a reading
  DELETE /api/vitals/{id}                   remove a reading
"""
from fastapi import APIRouter, Header, HTTPException

from app.services import vitals_service as vit

router = APIRouter(prefix="/api/vitals", tags=["Vitals"])


@router.get("")
def list_vitals(x_user_id: str = Header(...), profile_id: str | None = None, metric: str | None = None):
    return vit.list_vitals(x_user_id, profile_id or None, metric or None)


@router.post("")
def log_vital(body: dict, x_user_id: str = Header(...)):
    metric = (body.get("metric") or "").strip()
    if metric not in vit.METRICS:
        raise HTTPException(status_code=400, detail="Unknown metric.")
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    kind = vit.METRICS[metric][2]
    if kind == "bp":
        sys_, dia = num(body.get("systolic")), num(body.get("diastolic"))
        if sys_ is None or dia is None:
            raise HTTPException(status_code=400, detail="Enter both systolic and diastolic.")
        return vit.log_vital(x_user_id, body.get("profile_id") or None, metric,
                             systolic=sys_, diastolic=dia, unit=(body.get("unit") or "").strip() or None,
                             note=(body.get("note") or "").strip())
    val = num(body.get("value"))
    if val is None:
        raise HTTPException(status_code=400, detail="Enter a value.")
    return vit.log_vital(x_user_id, body.get("profile_id") or None, metric, value=val,
                         unit=(body.get("unit") or "").strip() or None, note=(body.get("note") or "").strip())


@router.delete("/{vital_id}")
def delete_vital(vital_id: str, x_user_id: str = Header(...)):
    if not vit.delete_vital(x_user_id, vital_id):
        raise HTTPException(status_code=404, detail="Reading not found.")
    return {"ok": True}
