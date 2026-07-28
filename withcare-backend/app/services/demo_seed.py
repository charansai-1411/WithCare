"""
Demo seed — populate a fresh account with realistic mock data so a judge (or anyone using the
Judge Login) can explore EVERY feature immediately, without adding anything from scratch.

Everything here is static (no LLM calls) except the Reader documents, which need embeddings.
Safe to call once per new user; it no-ops if the account already has profiles.
"""
import uuid
from datetime import date, datetime, timedelta

from app.db.database import get_db
from app.services import reader_service, temporal_service as tm, vitals_service
from app.services.memory_service import sync_profile_to_kg, write_fact
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _ago(n_days: int) -> str:
    return (datetime.now() - timedelta(days=n_days)).isoformat(timespec="minutes")


def _ahead(n_days: int) -> str:
    return (datetime.now() + timedelta(days=n_days)).isoformat(timespec="minutes")


def _profile(db, uid, name, **kw) -> str:
    pid = "p-" + uuid.uuid4().hex[:12]
    cols, vals = ["id", "user_id", "name"], [pid, uid, name]
    for k, v in kw.items():
        cols.append(k)
        vals.append(v)
    db.execute(f"INSERT INTO profiles({','.join(cols)}) VALUES({','.join(['?'] * len(vals))})", vals)
    return pid


def _med(uid, pid, name, dose, times, qty, thresh, recipient):
    data = {"dose": dose, "times": times, "per_dose": 1, "quantity": qty,
            "refill_threshold_days": thresh, "start_date": date.today().isoformat(),
            "recipient": recipient, "email": "", "reminder_ids": [], "event_ids": [], "alerted": False}
    write_fact(uid, pid, "medication", name, data=data, predicate="takes", unique="name")


def _routine(uid, pid, name, category, content, frequency, recipient):
    data = {"category": category, "content": content, "frequency": frequency, "times": [],
            "recurrence": "", "recipient": recipient, "email": "", "reminder_ids": [], "event_ids": []}
    write_fact(uid, pid, "routine", name, data=data, predicate="follows_routine", unique="name")


_POLICY = """STAR HEALTH — FAMILY HEALTH OPTIMA POLICY (summary)
Policyholder: Amma   Policy No: WC-DEMO-4521   Type: Family Floater
Sum Insured: Rs 5,00,000 per year.
Room rent limit: up to Rs 5,000 per day (single private AC room).
ICU limit: up to Rs 10,000 per day.
Co-payment: 10% for insured members above 60 years of age.
Pre-existing diseases including diabetes and hypertension: covered after a 36-month waiting period.
Waiting period: 30 days for any illness; 24 months for specified ailments (cataract, hernia).
Maternity: NOT covered under this plan.
Day-care procedures: covered (over 400 listed procedures).
Cashless treatment: available at network hospitals including Apollo, Yashoda and KIMS in Hyderabad.
Ambulance cover: Rs 2,000 per hospitalization.
Annual health check-up: covered once per policy year for each adult member.
"""

_VISIT = """DOCTOR VISIT RECORD
Patient: Amma   Date: last week   Hospital: City Care Hospital   Doctor: Dr. Rao
Summary: Reviewed blood sugar and blood pressure. Sugar is trending high. Advised to continue
Metformin 500mg twice daily after food, and to start Amlodipine 5mg for blood pressure.
Diet: reduce salt, avoid pickles and deep-fried food, prefer millets over white rice.
Activity: a 30-minute walk every evening.
Tests advised: HbA1c and a lipid profile before the next visit.
Follow-up: Cardiologist review in one week.
"""


def seed_demo(user_id: str) -> dict:
    """Populate a fresh user with a full demo dataset. No-op if it already has profiles."""
    db = get_db()
    if db.execute("SELECT COUNT(*) AS n FROM profiles WHERE user_id=?", (user_id,)).fetchone()["n"]:
        db.close()
        return {"seeded": False, "reason": "account already has data"}

    # ── care profiles: self + a real family + a pet ──
    _profile(db, user_id, "Charan", relation="Your own care", is_self=1, age=30, gender="male")
    amma = _profile(db, user_id, "Amma", relation="Mother", age=68, gender="female", weight=62,
                    height=155, conditions="type 2 diabetes, hypertension",
                    allergies="dairy (lactose intolerant), penicillin", blood_group="B+")
    appa = _profile(db, user_id, "Appa", relation="Father", age=72, gender="male", weight=78,
                    height=170, conditions="arthritis", notes="bad left knee, cannot jump or run",
                    blood_group="O+")
    priya = _profile(db, user_id, "Priya", relation="Wife", age=29, gender="female", blood_group="A+")
    _profile(db, user_id, "Bruno", kind="pet", species="dog", relation="Pet", age=4)
    db.commit()
    db.close()

    # conditions -> KG nodes (so the graph + injected memory reflect them)
    sync_profile_to_kg(user_id, {"id": amma, "conditions": "type 2 diabetes, hypertension"})
    sync_profile_to_kg(user_id, {"id": appa, "conditions": "arthritis"})

    # ── medications (Amlodipine is low on stock -> refill-soon alert) ──
    _med(user_id, amma, "Metformin", "500mg", ["09:00", "21:00"], 30, 5, "Amma")   # ~15 days left
    _med(user_id, amma, "Amlodipine", "5mg", ["08:00", "20:00"], 4, 5, "Amma")     # ~2 days -> refill soon
    _med(user_id, appa, "Paracetamol", "500mg", ["09:00"], 20, 5, "Appa")

    # ── vitals: rising sugar, falling weight, rising BP -> rich temporal trends ──
    for i, s in enumerate([130, 142, 155, 170]):
        vitals_service.log_vital(user_id, amma, "blood_sugar", value=s, at=_ago(21 - 7 * i))
    for i, w in enumerate([68, 66, 64, 62]):
        vitals_service.log_vital(user_id, amma, "weight", value=w, at=_ago(90 - 30 * i))
    for i, (sy, di) in enumerate([(130, 84), (138, 88), (148, 92)]):
        vitals_service.log_vital(user_id, amma, "blood_pressure", systolic=sy, diastolic=di, at=_ago(20 - 10 * i))

    # ── adherence history (Temporal Memory) ──
    for i, st in enumerate(["taken", "missed", "taken", "taken", "missed", "taken", "taken"]):
        tm.log_adherence(user_id, amma, "medication", "Metformin", st, occurred_at=_ago(6 - i))
    for i, st in enumerate(["done", "skipped", "done", "skipped", "done"]):
        tm.log_adherence(user_id, appa, "exercise", "Evening walk", st, occurred_at=_ago(4 - i),
                         value=30, unit="min")

    # ── dose-change history (validity intervals): Metformin was 250mg, now 500mg ──
    tm.record_med_change(user_id, amma, "Metformin", dose="250mg", occurred_at=_ago(120))
    tm.record_med_change(user_id, amma, "Metformin", dose="500mg", occurred_at=_ago(45))

    # ── routines ──
    _routine(user_id, appa, "Knee-safe workout", "workout",
             "**Mon:** 30-min walk\n**Wed:** chair squats x10, seated leg raises\n"
             "**Fri:** 30-min walk\nNo jumping or running.", "3x per week", "Appa")
    _routine(user_id, amma, "Morning & night skincare", "skincare",
             "Cleanser, then moisturizer with SPF 30 (AM) / night cream (PM), and a vitamin C serum.",
             "Twice daily (AM & PM)", "Amma")
    _routine(user_id, amma, "Quarterly eye check-up", "checkup",
             "Diabetic retinopathy screening with the ophthalmologist.", "Every 3 months", "Amma")

    # ── appointments: an upcoming one + attended history ──
    write_fact(user_id, amma, "appointment", "Cardiologist review",
               data={"date": _ahead(6), "doctor": "Dr. Rao"}, predicate="booked", unique="never")
    write_fact(user_id, amma, "appointment", "Eye check-up",
               data={"date": _ago(120)}, predicate="attended", unique="never")
    write_fact(user_id, priya, "appointment", "Annual health check-up",
               data={"date": _ahead(12)}, predicate="booked", unique="never")
    # mirror the past appointment into Temporal Memory so history_timeline shows it
    tm.record_event(user_id, amma, "appointment", "attended", subject="Eye check-up", occurred_at=_ago(120))

    # ── Reader documents (RAG): an insurance policy + a doctor-visit record ──
    try:
        reader_service.ingest_text(user_id, "Amma health insurance policy", _POLICY,
                                   kind="insurance", filename="amma_policy.txt")
        reader_service.ingest_text(user_id, "Doctor visit: Amma at City Care Hospital", _VISIT,
                                   kind="visit", filename="amma_visit.txt")
    except Exception as e:
        logger.warning(f"demo Reader seed failed (non-fatal): {e}")

    logger.info(f"demo seeded for {user_id}")
    return {"seeded": True, "profiles": 5}
