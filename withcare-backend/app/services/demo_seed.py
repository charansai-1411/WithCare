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

_ANC = """ANTENATAL ULTRASOUND REPORT
Patient: Priya   Gestational age: 22 weeks 3 days   Referred by: Dr. Meera
Findings: Single live intrauterine pregnancy. Fetal heart rate 148 bpm, regular.
Growth: consistent with dates; estimated fetal weight appropriate for gestational age.
Placenta: fundal, not low-lying. Amniotic fluid: adequate.
Advice: continue iron, folic acid and calcium supplements. Anomaly scan findings were normal.
Next: routine antenatal review in 4 weeks; glucose tolerance test at 24-28 weeks.
"""

_VISIT_APPA = """DOCTOR VISIT RECORD
Patient: Appa   Date: two weeks ago   Hospital: Yashoda Hospital   Doctor: Dr. Iyer (Orthopedics)
Summary: Left knee osteoarthritis reviewed. Advised to avoid jumping and running, continue
physiotherapy, and take Paracetamol 500mg only as needed for pain.
Activity: low-impact only - walking, chair squats, seated leg raises.
Tests advised: repeat knee X-ray in 6 months.
Follow-up: review in 3 months, or sooner if pain worsens.
"""

_LAB = """LABORATORY REPORT
Patient: Amma   Lab: SRL Diagnostics   Collected: last week
HbA1c: 8.2 % (target < 7.0) - high.
Fasting blood sugar: 168 mg/dL (normal 70-100) - high.
Post-prandial blood sugar: 232 mg/dL.
Total cholesterol: 214 mg/dL. LDL: 138 mg/dL. HDL: 42 mg/dL. Triglycerides: 180 mg/dL.
Serum creatinine: 0.9 mg/dL (normal). Blood pressure at visit: 148/92 mmHg.
Impression: sub-optimal glycaemic control; borderline lipids. Correlate clinically.
"""

_XRAY = """RADIOLOGY REPORT - LEFT KNEE X-RAY
Patient: Appa   Modality: X-ray, left knee (AP & lateral)   Referred by: Dr. Iyer
Findings: Reduced medial joint space with marginal osteophytes. Mild subchondral sclerosis.
No fracture or dislocation. Soft tissues unremarkable.
Impression: moderate osteoarthritis of the left knee (Grade 2-3).
Advice: joint-protection measures, physiotherapy, weight management.
"""


def seed_demo(user_id: str) -> dict:
    """Populate a fresh user with a full demo dataset. No-op if it already has profiles."""
    db = get_db()
    if db.execute("SELECT COUNT(*) AS n FROM profiles WHERE user_id=?", (user_id,)).fetchone()["n"]:
        db.close()
        return {"seeded": False, "reason": "account already has data"}

    # ── care profiles: self + a real family + a pet ──
    # (mock @example.com emails so the Emergency "contacts" list populates; example.com never
    #  delivers, and real SOS sending still needs the caregiver's own Gmail connected.)
    charan = _profile(db, user_id, "Charan", relation="Your own care", is_self=1, age=30,
                      gender="male", weight=74, height=176, email="charan.demo@example.com")
    amma = _profile(db, user_id, "Amma", relation="Mother", age=68, gender="female", weight=62,
                    height=155, conditions="type 2 diabetes, hypertension",
                    allergies="dairy (lactose intolerant), penicillin", blood_group="B+",
                    email="amma.demo@example.com")
    appa = _profile(db, user_id, "Appa", relation="Father", age=72, gender="male", weight=78,
                    height=170, conditions="arthritis", notes="bad left knee, cannot jump or run",
                    blood_group="O+", email="appa.demo@example.com")
    priya = _profile(db, user_id, "Priya", relation="Wife", age=29, gender="female", weight=63,
                     height=162, blood_group="A+", conditions="pregnancy (2nd trimester)",
                     notes="Expecting their first child; around 24 weeks, due in about 4 months.",
                     email="priya.demo@example.com")
    bruno = _profile(db, user_id, "Bruno", kind="pet", species="dog", relation="Pet", age=4, weight=18)
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
    for i, hr in enumerate([78, 82, 80]):
        vitals_service.log_vital(user_id, amma, "heart_rate", value=hr, at=_ago(14 - 6 * i))
    for i, sp in enumerate([97, 97, 96]):
        vitals_service.log_vital(user_id, amma, "spo2", value=sp, at=_ago(14 - 6 * i))
    # Appa: stable weight, mildly high BP, heart rate
    for i, w in enumerate([79, 78.5, 78, 78]):
        vitals_service.log_vital(user_id, appa, "weight", value=w, at=_ago(90 - 30 * i))
    for i, (sy, di) in enumerate([(128, 82), (132, 84), (130, 82)]):
        vitals_service.log_vital(user_id, appa, "blood_pressure", systolic=sy, diastolic=di, at=_ago(20 - 10 * i))
    # Charan (self, the default view): a healthy adult baseline so the Health page isn't empty
    for i, w in enumerate([75, 74.5, 74, 74]):
        vitals_service.log_vital(user_id, charan, "weight", value=w, at=_ago(90 - 30 * i))
    for i, (sy, di) in enumerate([(120, 78), (118, 76), (122, 80)]):
        vitals_service.log_vital(user_id, charan, "blood_pressure", systolic=sy, diastolic=di, at=_ago(20 - 10 * i))
    for i, hr in enumerate([72, 70, 74]):
        vitals_service.log_vital(user_id, charan, "heart_rate", value=hr, at=_ago(14 - 6 * i))
    # Bruno: pet weight tracking
    for i, w in enumerate([17.5, 17.8, 18, 18]):
        vitals_service.log_vital(user_id, bruno, "weight", value=w, at=_ago(90 - 30 * i))

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
    _routine(user_id, amma, "Stay hydrated", "hydration",
             "8 glasses of water through the day; a glass with each medicine.", "Throughout the day", "Amma")
    _routine(user_id, amma, "Daily diabetic foot check", "checkup",
             "Check feet for cuts, blisters or numbness; moisturise, but not between the toes.", "Daily", "Amma")
    _routine(user_id, appa, "Knee physiotherapy", "physio",
             "Quad sets, straight-leg raises, and heel slides — 10 reps each, twice a day.", "Twice daily", "Appa")
    _routine(user_id, appa, "Wind-down for sleep", "sleep",
             "No screens 30 minutes before bed; lights out by 10:30 PM.", "Nightly", "Appa")
    _routine(user_id, charan, "Desk eye breaks (20-20-20)", "eyecare",
             "Every 20 minutes, look 20 feet away for 20 seconds. Blink often.", "Through the workday", "Charan")
    _routine(user_id, charan, "Evening gym", "workout",
             "Mon/Wed/Fri strength, Tue/Thu cardio, 45 minutes.", "5x per week", "Charan")
    _routine(user_id, bruno, "Walks & feeding", "other",
             "Two 20-minute walks (morning & evening); measured meals twice a day.", "Daily", "Bruno")
    _routine(user_id, bruno, "Deworming & flea check", "checkup",
             "Monthly deworming tablet and a tick/flea check.", "Monthly", "Bruno")

    # ── appointments: an upcoming one + attended history ──
    write_fact(user_id, amma, "appointment", "Cardiologist review",
               data={"date": _ahead(6), "doctor": "Dr. Rao"}, predicate="booked", unique="never")
    write_fact(user_id, amma, "appointment", "Eye check-up",
               data={"date": _ago(120)}, predicate="attended", unique="never")
    # mirror the past appointment into Temporal Memory so history_timeline shows it
    tm.record_event(user_id, amma, "appointment", "attended", subject="Eye check-up", occurred_at=_ago(120))

    # ── Priya: pregnancy / antenatal care (a second, very different care scenario) ──
    sync_profile_to_kg(user_id, {"id": priya, "conditions": "pregnancy (2nd trimester)"})
    # prenatal supplements (folic acid running low -> refill-soon)
    _med(user_id, priya, "Folic acid", "5mg", ["09:00"], 6, 7, "Priya")            # refill soon
    _med(user_id, priya, "Iron + folic acid (IFA)", "", ["21:00"], 30, 7, "Priya")
    _med(user_id, priya, "Calcium + Vitamin D3", "500mg", ["10:00", "22:00"], 40, 7, "Priya")
    # weight GAIN (opposite of Amma) + gentle BP monitoring for pre-eclampsia watch
    for i, w in enumerate([58, 60, 61.5, 63]):
        vitals_service.log_vital(user_id, priya, "weight", value=w, at=_ago(90 - 30 * i))
    for i, (sy, di) in enumerate([(110, 70), (114, 72), (118, 76)]):
        vitals_service.log_vital(user_id, priya, "blood_pressure", systolic=sy, diastolic=di, at=_ago(20 - 10 * i))
    # supplement adherence (6/7 this week)
    for i, st in enumerate(["taken", "taken", "missed", "taken", "taken", "taken", "taken"]):
        tm.log_adherence(user_id, priya, "medication", "Folic acid", st, occurred_at=_ago(6 - i))
    # prenatal routines
    _routine(user_id, priya, "Prenatal walk & stretches", "workout",
             "20-minute gentle walk daily, plus pelvic tilts and light stretches. "
             "Avoid lying flat on the back.", "Daily", "Priya")
    _routine(user_id, priya, "Pregnancy nutrition", "diet",
             "Iron- and folate-rich meals (leafy greens, dates, lentils), calcium (curd, ragi), "
             "and plenty of water. Avoid raw or undercooked food and unpasteurised dairy.", "Daily", "Priya")
    # antenatal appointments: upcoming ANC + GTT + growth scan, and an attended dating scan
    write_fact(user_id, priya, "appointment", "Obstetrician check-up (ANC)",
               data={"date": _ahead(4), "doctor": "Dr. Meera"}, predicate="booked", unique="never")
    write_fact(user_id, priya, "appointment", "Glucose tolerance test (GTT)",
               data={"date": _ahead(11)}, predicate="booked", unique="never")
    write_fact(user_id, priya, "appointment", "Anomaly / growth scan",
               data={"date": _ahead(25)}, predicate="booked", unique="never")
    write_fact(user_id, priya, "appointment", "Dating scan (1st trimester)",
               data={"date": _ago(80)}, predicate="attended", unique="never")
    tm.record_event(user_id, priya, "appointment", "attended", subject="Dating scan (1st trimester)",
                    occurred_at=_ago(80))

    # ── Reader documents (RAG): insurance, lab & scan reports, and recorded doctor visits ──
    # (the two kind="visit" docs also populate the Record Doctor Visit "Past visits" list)
    for label, text, kind, fname in (
        ("Amma health insurance policy", _POLICY, "insurance", "amma_policy.txt"),
        ("Amma lab report (HbA1c & lipids)", _LAB, "report", "amma_lab.txt"),
        ("Doctor visit: Amma at City Care Hospital", _VISIT, "visit", "amma_visit.txt"),
        ("Doctor visit: Appa at Yashoda (Orthopedics)", _VISIT_APPA, "visit", "appa_visit.txt"),
        ("Appa left-knee X-ray report", _XRAY, "report", "appa_xray.txt"),
        ("Priya antenatal scan report", _ANC, "report", "priya_anc.txt"),
    ):
        try:
            reader_service.ingest_text(user_id, label, text, kind=kind, filename=fname)
        except Exception as e:
            logger.warning(f"demo Reader seed failed for {label!r} (non-fatal): {e}")

    logger.info(f"demo seeded for {user_id}")
    return {"seeded": True, "profiles": 5}
