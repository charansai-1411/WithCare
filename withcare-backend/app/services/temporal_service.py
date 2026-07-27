"""
Temporal Memory — append-only, time-aware history across every care domain.

Where the Knowledge Graph stores the CURRENT state of a person (latest dose, next appointment),
Temporal Memory stores what HAPPENED and how it CHANGED: dose-adherence day by day, vital trends,
exercise/diet history, appointment history, and dose changes as validity intervals
(valid_from / valid_to, NULL = still in effect).

Design: see docs/TEMPORAL_MEMORY.md. All trend / adherence / prediction math is done HERE in code
(deterministic, free) — the LLM only narrates the already-computed numbers.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta

from app.db.database import get_db
from app.services import vitals_service
from app.services.memory_service import find_nodes
from app.utils.logger import get_logger

logger = get_logger(__name__)

_PERIOD_DAYS = {"day": 1, "week": 7, "month": 30, "quarter": 90, "year": 365, "all": 3650}

# Guidance bands (navigational thresholds, NOT clinical advice) for attention flags.
_BANDS = {
    "blood_sugar": ("high", 180.0),      # fasting > 180 mg/dL -> worth a look
    "blood_pressure": ("high", 140.0),   # systolic > 140 mmHg
    "spo2": ("low", 92.0),               # SpO2 < 92%
    "heart_rate": ("high", 100.0),
}


# ── time helpers ─────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _period_start(since: str | None) -> str:
    """Resolve 'week' | 'month' | 'year' | ISO-date into a concrete start timestamp."""
    if not since:
        since = "week"
    since = str(since).strip().lower()
    if since in _PERIOD_DAYS:
        return (datetime.now() - timedelta(days=_PERIOD_DAYS[since])).isoformat(timespec="seconds")
    # try to parse an explicit date/datetime
    try:
        return datetime.fromisoformat(since).isoformat(timespec="seconds")
    except Exception:
        return (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")


def _slope(xs: list[float], ys: list[float]) -> float:
    """Least-squares slope of y over x (per unit x). 0 if degenerate."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def _direction(first: float, last: float) -> str:
    if first == 0:
        return "rising" if last > 0 else "stable"
    change = (last - first) / abs(first)
    if change > 0.05:
        return "rising"
    if change < -0.05:
        return "falling"
    return "stable"


# ── writes ───────────────────────────────────────────────────────────────────────
def record_event(user_id, profile_id, domain, event_type, subject="", value=None, value2=None,
                 unit="", status="", occurred_at=None, valid_from=None, valid_to=None,
                 source="manual", subject_ref="", meta=None) -> dict:
    """Append one event to Temporal Memory."""
    eid = "e-" + uuid.uuid4().hex[:12]
    occurred_at = occurred_at or _now()
    db = get_db()
    db.execute(
        "INSERT INTO events(id,user_id,profile_id,domain,subject,event_type,value,value2,unit,"
        "status,occurred_at,valid_from,valid_to,source,subject_ref,meta) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (eid, user_id, profile_id, domain, subject or "", event_type,
         value, value2, unit or "", status or "", occurred_at,
         valid_from or occurred_at, valid_to, source, subject_ref or "",
         json.dumps(meta or {})),
    )
    db.commit()
    db.close()
    return {"id": eid, "domain": domain, "subject": subject, "event_type": event_type,
            "value": value, "occurred_at": occurred_at}


def log_adherence(user_id, profile_id, domain, subject, status, occurred_at=None, value=None,
                  unit="", source="manual", meta=None) -> dict:
    """Log a dose/exercise/diet outcome: status in taken|missed|skipped|done.
    domain in medication|exercise|diet. The status IS the event_type."""
    status = (status or "").lower().strip()
    if status not in ("taken", "missed", "skipped", "done"):
        status = "done"
    return record_event(user_id, profile_id, domain, status, subject=subject, value=value,
                        unit=unit, status=status, occurred_at=occurred_at, source=source, meta=meta)


def record_med_change(user_id, profile_id, subject, dose="", schedule="", occurred_at=None,
                      source="manual", subject_ref="", meta=None) -> dict:
    """Version a medication regimen with a VALIDITY INTERVAL: close the previous open interval
    for this medicine (valid_to = now) and open a new one (valid_to = NULL = current)."""
    occurred_at = occurred_at or _now()
    db = get_db()
    # close any currently-open interval for this subject
    db.execute(
        "UPDATE events SET valid_to=? WHERE user_id=? AND profile_id IS ? AND subject=? "
        "AND domain='medication' AND event_type='changed' AND valid_to IS NULL",
        (occurred_at, user_id, profile_id, subject),
    )
    db.commit()
    db.close()
    m = {"dose": dose, "schedule": schedule}
    m.update(meta or {})
    return record_event(user_id, profile_id, "medication", "changed", subject=subject,
                        occurred_at=occurred_at, valid_from=occurred_at, valid_to=None,
                        source=source, subject_ref=subject_ref, meta=m)


# ── reads ────────────────────────────────────────────────────────────────────────
def _rows(user_id, profile_id, domain=None, subject=None, start=None, end=None,
          event_types=None) -> list[dict]:
    sql = "SELECT * FROM events WHERE user_id=?"
    params: list = [user_id]
    if profile_id:
        sql += " AND profile_id=?"; params.append(profile_id)
    if domain:
        sql += " AND domain=?"; params.append(domain)
    if subject:
        sql += " AND subject=?"; params.append(subject)
    if start:
        sql += " AND occurred_at>=?"; params.append(start)
    if end:
        sql += " AND occurred_at<=?"; params.append(end)
    if event_types:
        sql += " AND event_type IN (%s)" % ",".join("?" * len(event_types))
        params.extend(event_types)
    sql += " ORDER BY occurred_at ASC"
    db = get_db()
    rows = [dict(r) for r in db.execute(sql, params).fetchall()]
    db.close()
    for r in rows:
        try:
            r["meta"] = json.loads(r.get("meta") or "{}")
        except Exception:
            r["meta"] = {}
    return rows


def events_between(user_id, profile_id, domain=None, since="week", until=None, subject=None):
    return _rows(user_id, profile_id, domain=domain, subject=subject,
                 start=_period_start(since), end=until)


def timeline(user_id, profile_id, since="week", domain=None):
    """A flat, human-readable history for a window (newest first)."""
    rows = events_between(user_id, profile_id, domain=domain, since=since)
    rows.reverse()
    out = []
    for r in rows:
        when = (r["occurred_at"] or "")[:10]
        label = r["subject"] or r["domain"]
        detail = r["event_type"]
        if r.get("value") is not None:
            detail += f" {r['value']}{(' ' + r['unit']) if r['unit'] else ''}"
        if r["meta"].get("dose"):
            detail += f" ({r['meta']['dose']})"
        out.append({"date": when, "domain": r["domain"], "subject": label, "detail": detail})
    return out


def dose_at(user_id, profile_id, subject, when=None) -> dict | None:
    """The medication regimen in effect at `when` (validity-interval lookup)."""
    when = when or _now()
    db = get_db()
    row = db.execute(
        "SELECT * FROM events WHERE user_id=? AND profile_id IS ? AND subject=? AND domain='medication' "
        "AND event_type='changed' AND valid_from<=? AND (valid_to IS NULL OR valid_to>?) "
        "ORDER BY valid_from DESC LIMIT 1",
        (user_id, profile_id, subject, when, when),
    ).fetchone()
    db.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["meta"] = json.loads(d.get("meta") or "{}")
    except Exception:
        d["meta"] = {}
    return d


# ── trend / adherence ──────────────────────────────────────────────────────────────
def trend(user_id, profile_id, metric, since="month") -> dict:
    """First/last/delta/slope/direction for a numeric metric. Vitals come from the existing
    append-only health_metric store; other numeric domains come from events.

    If the requested window holds fewer than 2 readings (e.g. weight logged monthly, asked over
    'week'), it AUTO-WIDENS to the full history so a real trend is still returned rather than a
    misleading 'steady'."""
    start = _period_start(since)
    all_series = []  # (occurred_at, value) across ALL history
    if metric in vitals_service.METRICS:
        for v in vitals_service.list_vitals(user_id, profile_id, metric):
            at = v.get("at") or ""
            val = v.get("systolic") if v.get("metric") == "blood_pressure" else v.get("value")
            if at and val is not None:
                all_series.append((at, float(val)))
    else:
        for r in _rows(user_id, profile_id, subject=metric):
            if r.get("value") is not None:
                all_series.append((r["occurred_at"], float(r["value"])))
    all_series.sort()
    series = [p for p in all_series if p[0] >= start]
    widened = False
    # < 3 in-window points is too few for a meaningful trend (e.g. weight logged monthly asked
    # over a month = 2 points) — fall back to the full history so we show the real trajectory.
    if len(series) < 3 and len(all_series) >= 2:
        series, widened = all_series, True
    if not series:
        return {"metric": metric, "n": 0, "found": False}
    ys = [v for _, v in series]
    xs = list(range(len(ys)))
    first, last = ys[0], ys[-1]
    unit = vitals_service.METRICS.get(metric, (metric, "", ""))[1]
    return {
        "metric": metric, "found": True, "n": len(ys),
        "first": first, "last": last, "delta": round(last - first, 2),
        "min": min(ys), "max": max(ys), "avg": round(sum(ys) / len(ys), 1),
        "slope_per_reading": round(_slope(xs, ys), 3),
        "direction": _direction(first, last), "unit": unit, "widened": widened,
        "from_date": series[0][0][:10], "to_date": series[-1][0][:10],
        "series": [{"at": a[:10], "value": v} for a, v in series],
    }


def adherence_report(user_id, profile_id, domain="medication", subject=None, since="week") -> dict:
    """taken / total, % and the missed dates for a med or exercise over the window."""
    rows = events_between(user_id, profile_id, domain=domain, since=since, subject=subject)
    done_types = {"taken", "done"}
    miss_types = {"missed", "skipped"}
    per_subject: dict[str, dict] = {}
    for r in rows:
        if r["event_type"] not in done_types | miss_types:
            continue
        s = r["subject"] or domain
        d = per_subject.setdefault(s, {"done": 0, "missed": 0, "missed_dates": [], "done_dates": []})
        if r["event_type"] in done_types:
            d["done"] += 1; d["done_dates"].append(r["occurred_at"][:10])
        else:
            d["missed"] += 1; d["missed_dates"].append(r["occurred_at"][:10])
    for s, d in per_subject.items():
        total = d["done"] + d["missed"]
        d["total"] = total
        d["rate"] = round(100 * d["done"] / total) if total else None
    overall_done = sum(d["done"] for d in per_subject.values())
    overall_total = sum(d["total"] for d in per_subject.values())
    return {
        "domain": domain, "since": since,
        "overall": {"done": overall_done, "total": overall_total,
                    "rate": round(100 * overall_done / overall_total) if overall_total else None},
        "by_subject": per_subject,
    }


# ── next upcoming ──────────────────────────────────────────────────────────────────
def _appt_date(node: dict) -> str | None:
    d = node.get("data") or {}
    for k in ("date", "datetime", "start", "when", "start_datetime", "start_iso"):
        v = d.get(k)
        if v:
            return str(v)
    return None


def next_event(user_id, profile_id, of="appointment") -> dict:
    """The next upcoming appointment / medicine dose / check-up."""
    now = _now()
    if of in ("appointment", "checkup"):
        cands = []
        for n in find_nodes(user_id, "appointment", profile_id):
            dt = _appt_date(n)
            if dt and dt >= now[:len(dt)]:
                if of == "checkup" and not any(
                    w in (n["name"] + json.dumps(n.get("data") or {})).lower()
                    for w in ("check", "checkup", "check-up", "screening", "review", "follow")):
                    continue
                cands.append((dt, n["name"], (n.get("data") or {})))
        # also future 'booked' events
        for r in _rows(user_id, profile_id, domain="appointment", start=now):
            cands.append((r["occurred_at"], r["subject"] or "Appointment", r["meta"]))
        cands.sort()
        if cands:
            dt, name, data = cands[0]
            return {"of": of, "found": True, "when": dt[:16], "what": name,
                    "doctor": (data or {}).get("doctor", "")}
        return {"of": of, "found": False}
    if of in ("medication", "medicine", "dose"):
        best = None
        for n in find_nodes(user_id, "medication", profile_id):
            for t in (n.get("data") or {}).get("times") or []:
                nxt = _next_daily(t)
                if nxt and (best is None or nxt < best[0]):
                    best = (nxt, n["name"], t)
        if best:
            return {"of": "medication", "found": True, "when": best[0][:16],
                    "what": best[1], "time": best[2]}
        return {"of": "medication", "found": False}
    return {"of": of, "found": False}


def _next_daily(hhmm: str) -> str | None:
    """Next occurrence of a daily HH:MM as an ISO datetime (today if still ahead, else tomorrow)."""
    try:
        h, m = [int(x) for x in str(hhmm).split(":")[:2]]
    except Exception:
        return None
    now = datetime.now()
    cand = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if cand <= now:
        cand += timedelta(days=1)
    return cand.isoformat(timespec="minutes")


# ── prediction / attention (heuristic + statistical) ───────────────────────────────
def attention_flags(user_id, profile_id) -> list[dict]:
    """Navigational 'worth a look' flags — never clinical. Each: {level, kind, message}."""
    flags = []
    # vital trends + band crossings
    for metric in vitals_service.METRICS:
        t = trend(user_id, profile_id, metric, since="month")
        if not t.get("found") or t["n"] < 2:
            continue
        band = _BANDS.get(metric)
        label = vitals_service.METRICS[metric][0]
        if band:
            side, thresh = band
            crossed = (t["last"] > thresh) if side == "high" else (t["last"] < thresh)
            if crossed:
                flags.append({"level": "high", "kind": f"{metric}_band",
                              "message": f"{label} is {t['last']}{t['unit']} — {'above' if side=='high' else 'below'} "
                                         f"the {thresh}{t['unit']} guidance line. Worth discussing with the doctor."})
        if t["direction"] == "rising" and metric in ("blood_sugar", "blood_pressure", "weight"):
            flags.append({"level": "watch", "kind": f"{metric}_trend",
                          "message": f"{label} has risen from {t['first']} to {t['last']}{t['unit']} "
                                     f"over the last month — an upward trend to keep an eye on."})
        if metric == "weight" and t["first"]:
            pct = (t["last"] - t["first"]) / abs(t["first"]) * 100
            if abs(pct) >= 5:
                flags.append({"level": "watch", "kind": "weight_change",
                              "message": f"Weight changed {round(pct)}% in a month ({t['first']}→{t['last']}kg)."})
    # medication adherence
    adh = adherence_report(user_id, profile_id, "medication", since="week")
    r = adh["overall"]["rate"]
    if r is not None and r < 70:
        flags.append({"level": "high", "kind": "med_adherence",
                      "message": f"Only {r}% of medicine doses were taken this week — several were missed."})
    return flags


# ── summaries / digest ─────────────────────────────────────────────────────────────
def summary(user_id, profile_id, period="week") -> dict:
    """A cross-domain health summary for the window: vital trends, adherence, appointments, flags."""
    trends = {}
    for metric in vitals_service.METRICS:
        t = trend(user_id, profile_id, metric, since=period)
        if t.get("found") and t["n"] >= 1:
            trends[metric] = {k: t[k] for k in ("first", "last", "delta", "direction", "avg", "unit", "n")}
    med = adherence_report(user_id, profile_id, "medication", since=period)
    exercise = adherence_report(user_id, profile_id, "exercise", since=period)
    appts = [e for e in timeline(user_id, profile_id, since=period, domain="appointment")]
    return {
        "period": period, "trends": trends,
        "medication_adherence": med["overall"], "medication_by_drug": med["by_subject"],
        "exercise_adherence": exercise["overall"],
        "appointments": appts, "attention": attention_flags(user_id, profile_id),
    }


def digest(user_id, profile_id) -> str:
    """A one-line temporal digest for the agent's memory block, so even a plain answer is
    time-aware before any tool call. '' if there's no history yet."""
    bits = []
    for metric in ("blood_sugar", "blood_pressure", "weight"):
        t = trend(user_id, profile_id, metric, since="month")
        if t.get("found") and t["n"] >= 2 and t["direction"] != "stable":
            arrow = "up" if t["direction"] == "rising" else "down"
            bits.append(f"{vitals_service.METRICS[metric][0]} trending {arrow} "
                        f"({t['first']}->{t['last']}{t['unit']}, 1mo)")
    adh = adherence_report(user_id, profile_id, "medication", since="week")
    if adh["overall"]["rate"] is not None:
        bits.append(f"med adherence {adh['overall']['rate']}% this week")
    return "; ".join(bits)
