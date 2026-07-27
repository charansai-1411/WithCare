"""
Temporal Memory API — append-only, time-aware history across care domains.
  POST /api/temporal/adherence       { profile_id, domain, subject, status, occurred_at?, value? }
  POST /api/temporal/event           { profile_id, domain, event_type, subject?, value?, ... }
  POST /api/temporal/med-change      { profile_id, subject, dose, schedule?, occurred_at? }
  POST /api/temporal/timeline        { profile_id, since?, domain? }
  POST /api/temporal/trend           { profile_id, metric, since? }
  POST /api/temporal/adherence-report{ profile_id, domain?, subject?, since? }
  POST /api/temporal/summary         { profile_id, period? }        (week|month)
  POST /api/temporal/next            { profile_id, of }             (appointment|medication|checkup)
  POST /api/temporal/attention       { profile_id }
"""
from fastapi import APIRouter, Header, HTTPException

from app.services import temporal_service as T

router = APIRouter(prefix="/api/temporal", tags=["Temporal Memory"])


def _pid(body: dict) -> str | None:
    return body.get("profile_id") or None


@router.post("/adherence")
def log_adherence(body: dict, x_user_id: str = Header(...)):
    subject = (body.get("subject") or "").strip()
    if not subject:
        raise HTTPException(status_code=400, detail="subject is required.")
    return T.log_adherence(
        x_user_id, _pid(body), (body.get("domain") or "medication"), subject,
        (body.get("status") or "done"), occurred_at=body.get("occurred_at"),
        value=body.get("value"), unit=(body.get("unit") or ""),
        source=(body.get("source") or "manual"), meta=body.get("meta"),
    )


@router.post("/event")
def record_event(body: dict, x_user_id: str = Header(...)):
    if not body.get("domain") or not body.get("event_type"):
        raise HTTPException(status_code=400, detail="domain and event_type are required.")
    return T.record_event(
        x_user_id, _pid(body), body["domain"], body["event_type"],
        subject=(body.get("subject") or ""), value=body.get("value"), value2=body.get("value2"),
        unit=(body.get("unit") or ""), status=(body.get("status") or ""),
        occurred_at=body.get("occurred_at"), valid_from=body.get("valid_from"),
        valid_to=body.get("valid_to"), source=(body.get("source") or "manual"),
        subject_ref=(body.get("subject_ref") or ""), meta=body.get("meta"),
    )


@router.post("/med-change")
def med_change(body: dict, x_user_id: str = Header(...)):
    subject = (body.get("subject") or "").strip()
    if not subject:
        raise HTTPException(status_code=400, detail="subject is required.")
    return T.record_med_change(
        x_user_id, _pid(body), subject, dose=(body.get("dose") or ""),
        schedule=(body.get("schedule") or ""), occurred_at=body.get("occurred_at"),
        source=(body.get("source") or "manual"), subject_ref=(body.get("subject_ref") or ""),
        meta=body.get("meta"),
    )


@router.post("/timeline")
def timeline(body: dict, x_user_id: str = Header(...)):
    return T.timeline(x_user_id, _pid(body), since=(body.get("since") or "week"),
                      domain=body.get("domain"))


@router.post("/trend")
def trend(body: dict, x_user_id: str = Header(...)):
    metric = (body.get("metric") or "").strip()
    if not metric:
        raise HTTPException(status_code=400, detail="metric is required.")
    return T.trend(x_user_id, _pid(body), metric, since=(body.get("since") or "month"))


@router.post("/adherence-report")
def adherence_report(body: dict, x_user_id: str = Header(...)):
    return T.adherence_report(x_user_id, _pid(body), domain=(body.get("domain") or "medication"),
                              subject=body.get("subject"), since=(body.get("since") or "week"))


@router.post("/summary")
def summary(body: dict, x_user_id: str = Header(...)):
    return T.summary(x_user_id, _pid(body), period=(body.get("period") or "week"))


@router.post("/next")
def next_event(body: dict, x_user_id: str = Header(...)):
    return T.next_event(x_user_id, _pid(body), of=(body.get("of") or "appointment"))


@router.post("/attention")
def attention(body: dict, x_user_id: str = Header(...)):
    return {"flags": T.attention_flags(x_user_id, _pid(body))}
