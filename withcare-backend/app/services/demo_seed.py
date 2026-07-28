"""
Demo seed — populate a fresh account with realistic mock data so a judge (or anyone using the
Judge Login) can explore EVERY feature immediately, without adding anything from scratch.

PERFORMANCE: the production DB is SQLite on a GCS-FUSE volume where every commit fsyncs to Cloud
Storage (~1-2s each, WAL disabled). So this builds ALL rows in memory and writes them in a SINGLE
transaction (one commit) instead of ~100 per-write commits — turning a 2-3 minute seed into a few
seconds. The only network cost left is the Reader embeddings.
"""
import json
import uuid
from datetime import date, datetime, timedelta

from app.db.database import get_db
from app.services.embedding_service import embed_texts
from app.services.reader_service import _chunk
from app.services.vitals_service import METRICS
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _ago(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).isoformat(timespec="minutes")


def _ahead(n: int) -> str:
    return (datetime.now() + timedelta(days=n)).isoformat(timespec="minutes")


def _nid(p):
    return p + uuid.uuid4().hex[:12]


# ── row builders (accumulate into lists; nothing touches the DB until the end) ──────
class _Rows:
    def __init__(self):
        self.kg = []      # kg_nodes
        self.ev = []      # events

    def node(self, uid, pid, typ, name, data):
        self.kg.append((_nid("k-"), uid, pid, typ, name, json.dumps(data)))

    def med(self, uid, pid, name, dose, times, qty, thresh, recipient):
        self.node(uid, pid, "medication", name, {
            "dose": dose, "times": times, "per_dose": 1, "quantity": qty,
            "refill_threshold_days": thresh, "start_date": date.today().isoformat(),
            "recipient": recipient, "email": "", "reminder_ids": [], "event_ids": [], "alerted": False})

    def routine(self, uid, pid, name, category, content, frequency, recipient):
        self.node(uid, pid, "routine", name, {
            "category": category, "content": content, "frequency": frequency, "times": [],
            "recurrence": "", "recipient": recipient, "email": "", "reminder_ids": [], "event_ids": []})

    def appointment(self, uid, pid, name, when, doctor=""):
        self.node(uid, pid, "appointment", name, {"date": when, "doctor": doctor})

    def vital(self, uid, pid, metric, value=None, systolic=None, diastolic=None, at=None):
        label, unit, kind = METRICS[metric]
        at = at or _ago(0)
        if kind == "bp":
            data = {"metric": metric, "systolic": systolic, "diastolic": diastolic, "unit": unit, "at": at, "note": ""}
            disp = f"{int(systolic)}/{int(diastolic)} {unit}"
        else:
            data = {"metric": metric, "value": value, "unit": unit, "at": at, "note": ""}
            disp = f"{value} {unit}".strip()
        self.node(uid, pid, "health_metric", f"{label}: {disp}", data)

    def event(self, uid, pid, domain, etype, subject="", value=None, unit="", status="",
              occurred_at=None, valid_from=None, valid_to=None, meta=None):
        occ = occurred_at or _ago(0)
        self.ev.append((_nid("e-"), uid, pid, domain, subject, etype, value, None, unit, status or "",
                        occ, valid_from or occ, valid_to, "manual", "", json.dumps(meta or {})))


# ── document text (static) ──────────────────────────────────────────────────────────
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

_DOCS = [
    ("Amma health insurance policy", _POLICY, "insurance", "amma_policy.txt"),
    ("Amma lab report (HbA1c & lipids)", _LAB, "report", "amma_lab.txt"),
    ("Doctor visit: Amma at City Care Hospital", _VISIT, "visit", "amma_visit.txt"),
    ("Doctor visit: Appa at Yashoda (Orthopedics)", _VISIT_APPA, "visit", "appa_visit.txt"),
    ("Appa left-knee X-ray report", _XRAY, "report", "appa_xray.txt"),
    ("Priya antenatal scan report", _ANC, "report", "priya_anc.txt"),
]


def seed_demo(user_id: str) -> dict:
    """Populate a fresh user with a full demo dataset in ONE transaction. No-op if it already
    has profiles."""
    db = get_db()
    if db.execute("SELECT COUNT(*) AS n FROM profiles WHERE user_id=?", (user_id,)).fetchone()["n"]:
        db.close()
        return {"seeded": False, "reason": "account already has data"}
    u = user_id
    r = _Rows()

    # ── profiles (self + family + pet); mock @example.com emails so Emergency contacts populate ──
    ids = {}
    def prof(name, **kw):
        pid = "p-" + uuid.uuid4().hex[:12]
        cols, vals = ["id", "user_id", "name"], [pid, u, name]
        for k, v in kw.items():
            cols.append(k); vals.append(v)
        db.execute(f"INSERT INTO profiles({','.join(cols)}) VALUES({','.join(['?'] * len(vals))})", vals)
        ids[name] = pid
        return pid

    charan = prof("Charan", relation="Your own care", is_self=1, age=30, gender="male",
                  weight=74, height=176, email="charan.demo@example.com")
    amma = prof("Amma", relation="Mother", age=68, gender="female", weight=62, height=155,
                conditions="type 2 diabetes, hypertension",
                allergies="dairy (lactose intolerant), penicillin", blood_group="B+",
                email="amma.demo@example.com")
    appa = prof("Appa", relation="Father", age=72, gender="male", weight=78, height=170,
                conditions="arthritis", notes="bad left knee, cannot jump or run",
                blood_group="O+", email="appa.demo@example.com")
    priya = prof("Priya", relation="Wife", age=29, gender="female", weight=63, height=162,
                 blood_group="A+", conditions="pregnancy (2nd trimester)",
                 notes="Expecting their first child; around 24 weeks, due in about 4 months.",
                 email="priya.demo@example.com")
    bruno = prof("Bruno", kind="pet", species="dog", relation="Pet", age=4, weight=18)

    # ── conditions ──
    for cond in ("type 2 diabetes", "hypertension"):
        r.node(u, amma, "condition", cond, {})
    r.node(u, appa, "condition", "arthritis", {})
    r.node(u, priya, "condition", "pregnancy (2nd trimester)", {})

    # ── medications (Amlodipine & Folic acid deliberately low -> refill-soon) ──
    r.med(u, amma, "Metformin", "500mg", ["09:00", "21:00"], 30, 5, "Amma")
    r.med(u, amma, "Amlodipine", "5mg", ["08:00", "20:00"], 4, 5, "Amma")
    r.med(u, appa, "Paracetamol", "500mg", ["09:00"], 20, 5, "Appa")
    r.med(u, priya, "Folic acid", "5mg", ["09:00"], 6, 7, "Priya")
    r.med(u, priya, "Iron + folic acid (IFA)", "", ["21:00"], 30, 7, "Priya")
    r.med(u, priya, "Calcium + Vitamin D3", "500mg", ["10:00", "22:00"], 40, 7, "Priya")

    # ── vitals (Amma sugar up + weight down; Priya weight up; plus HR/SpO2/others) ──
    for i, s in enumerate([130, 142, 155, 170]):
        r.vital(u, amma, "blood_sugar", value=s, at=_ago(21 - 7 * i))
    for i, w in enumerate([68, 66, 64, 62]):
        r.vital(u, amma, "weight", value=w, at=_ago(90 - 30 * i))
    for i, (sy, di) in enumerate([(130, 84), (138, 88), (148, 92)]):
        r.vital(u, amma, "blood_pressure", systolic=sy, diastolic=di, at=_ago(20 - 10 * i))
    for i, hr in enumerate([78, 82, 80]):
        r.vital(u, amma, "heart_rate", value=hr, at=_ago(14 - 6 * i))
    for i, sp in enumerate([97, 97, 96]):
        r.vital(u, amma, "spo2", value=sp, at=_ago(14 - 6 * i))
    for i, w in enumerate([79, 78.5, 78, 78]):
        r.vital(u, appa, "weight", value=w, at=_ago(90 - 30 * i))
    for i, (sy, di) in enumerate([(128, 82), (132, 84), (130, 82)]):
        r.vital(u, appa, "blood_pressure", systolic=sy, diastolic=di, at=_ago(20 - 10 * i))
    for i, w in enumerate([75, 74.5, 74, 74]):
        r.vital(u, charan, "weight", value=w, at=_ago(90 - 30 * i))
    for i, (sy, di) in enumerate([(120, 78), (118, 76), (122, 80)]):
        r.vital(u, charan, "blood_pressure", systolic=sy, diastolic=di, at=_ago(20 - 10 * i))
    for i, hr in enumerate([72, 70, 74]):
        r.vital(u, charan, "heart_rate", value=hr, at=_ago(14 - 6 * i))
    for i, w in enumerate([17.5, 17.8, 18, 18]):
        r.vital(u, bruno, "weight", value=w, at=_ago(90 - 30 * i))
    for i, w in enumerate([58, 60, 61.5, 63]):
        r.vital(u, priya, "weight", value=w, at=_ago(90 - 30 * i))
    for i, (sy, di) in enumerate([(110, 70), (114, 72), (118, 76)]):
        r.vital(u, priya, "blood_pressure", systolic=sy, diastolic=di, at=_ago(20 - 10 * i))

    # ── adherence history (Temporal Memory) ──
    for i, st in enumerate(["taken", "missed", "taken", "taken", "missed", "taken", "taken"]):
        r.event(u, amma, "medication", st, subject="Metformin", status=st, occurred_at=_ago(6 - i))
    for i, st in enumerate(["done", "skipped", "done", "skipped", "done"]):
        r.event(u, appa, "exercise", st, subject="Evening walk", status=st, value=30, unit="min", occurred_at=_ago(4 - i))
    for i, st in enumerate(["taken", "taken", "missed", "taken", "taken", "taken", "taken"]):
        r.event(u, priya, "medication", st, subject="Folic acid", status=st, occurred_at=_ago(6 - i))

    # ── dose-change history (validity intervals): Metformin 250mg -> 500mg ──
    r.event(u, amma, "medication", "changed", subject="Metformin", occurred_at=_ago(120),
            valid_from=_ago(120), valid_to=_ago(45), meta={"dose": "250mg"})
    r.event(u, amma, "medication", "changed", subject="Metformin", occurred_at=_ago(45),
            valid_from=_ago(45), valid_to=None, meta={"dose": "500mg"})

    # ── routines (across every category) ──
    r.routine(u, appa, "Knee-safe workout", "workout",
              "**Mon:** 30-min walk\n**Wed:** chair squats x10, seated leg raises\n"
              "**Fri:** 30-min walk\nNo jumping or running.", "3x per week", "Appa")
    r.routine(u, amma, "Morning & night skincare", "skincare",
              "Cleanser, then moisturizer with SPF 30 (AM) / night cream (PM), and a vitamin C serum.",
              "Twice daily (AM & PM)", "Amma")
    r.routine(u, amma, "Quarterly eye check-up", "checkup",
              "Diabetic retinopathy screening with the ophthalmologist.", "Every 3 months", "Amma")
    r.routine(u, amma, "Stay hydrated", "hydration",
              "8 glasses of water through the day; a glass with each medicine.", "Throughout the day", "Amma")
    r.routine(u, amma, "Daily diabetic foot check", "checkup",
              "Check feet for cuts, blisters or numbness; moisturise, but not between the toes.", "Daily", "Amma")
    r.routine(u, appa, "Knee physiotherapy", "physio",
              "Quad sets, straight-leg raises, and heel slides — 10 reps each, twice a day.", "Twice daily", "Appa")
    r.routine(u, appa, "Wind-down for sleep", "sleep",
              "No screens 30 minutes before bed; lights out by 10:30 PM.", "Nightly", "Appa")
    r.routine(u, charan, "Desk eye breaks (20-20-20)", "eyecare",
              "Every 20 minutes, look 20 feet away for 20 seconds. Blink often.", "Through the workday", "Charan")
    r.routine(u, charan, "Evening gym", "workout",
              "Mon/Wed/Fri strength, Tue/Thu cardio, 45 minutes.", "5x per week", "Charan")
    r.routine(u, bruno, "Walks & feeding", "other",
              "Two 20-minute walks (morning & evening); measured meals twice a day.", "Daily", "Bruno")
    r.routine(u, bruno, "Deworming & flea check", "checkup",
              "Monthly deworming tablet and a tick/flea check.", "Monthly", "Bruno")
    r.routine(u, priya, "Prenatal walk & stretches", "workout",
              "20-minute gentle walk daily, plus pelvic tilts and light stretches. "
              "Avoid lying flat on the back.", "Daily", "Priya")
    r.routine(u, priya, "Pregnancy nutrition", "diet",
              "Iron- and folate-rich meals (leafy greens, dates, lentils), calcium (curd, ragi), "
              "and plenty of water. Avoid raw or undercooked food and unpasteurised dairy.", "Daily", "Priya")

    # ── appointments (upcoming + attended history) ──
    r.appointment(u, amma, "Cardiologist review", _ahead(6), doctor="Dr. Rao")
    r.appointment(u, amma, "Eye check-up", _ago(120))
    r.appointment(u, priya, "Obstetrician check-up (ANC)", _ahead(4), doctor="Dr. Meera")
    r.appointment(u, priya, "Glucose tolerance test (GTT)", _ahead(11))
    r.appointment(u, priya, "Anomaly / growth scan", _ahead(25))
    r.appointment(u, priya, "Dating scan (1st trimester)", _ago(80))
    r.event(u, amma, "appointment", "attended", subject="Eye check-up", occurred_at=_ago(120))
    r.event(u, priya, "appointment", "attended", subject="Dating scan (1st trimester)", occurred_at=_ago(80))

    # ── Reader documents: chunk ALL docs, embed in ONE network call, then insert with the rest ──
    doc_rows, chunk_rows = [], []
    specs, all_chunks = [], []          # specs: (label, kind, fname, text, chunks, offset)
    for label, text, kind, fname in _DOCS:
        chunks = _chunk(text)
        specs.append((label, kind, fname, text, chunks, len(all_chunks)))
        all_chunks.extend(chunks)
    try:
        vecs = embed_texts(all_chunks, task_type="RETRIEVAL_DOCUMENT") if all_chunks else []
    except Exception as e:
        logger.warning(f"demo Reader embed failed (non-fatal): {e}")
        vecs = []
    if vecs:
        for label, kind, fname, text, chunks, off in specs:
            did = "d-" + uuid.uuid4().hex[:12]
            doc_rows.append((did, u, fname, label, "text/plain", kind, len(text), len(chunks), "ready"))
            for j, c in enumerate(chunks):
                chunk_rows.append(("dc-" + uuid.uuid4().hex[:12], did, u, j, c, json.dumps(vecs[off + j])))

    # ── ONE transaction: write everything, commit once ──
    db.executemany("INSERT INTO kg_nodes(id,user_id,profile_id,type,name,data) VALUES(?,?,?,?,?,?)", r.kg)
    db.executemany(
        "INSERT INTO events(id,user_id,profile_id,domain,subject,event_type,value,value2,unit,status,"
        "occurred_at,valid_from,valid_to,source,subject_ref,meta) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", r.ev)
    if doc_rows:
        db.executemany(
            "INSERT INTO documents(id,user_id,filename,label,mime,kind,char_count,chunk_count,status) "
            "VALUES(?,?,?,?,?,?,?,?,?)", doc_rows)
        db.executemany(
            "INSERT INTO doc_chunks(id,document_id,user_id,chunk_index,text,embedding) VALUES(?,?,?,?,?,?)",
            chunk_rows)
    db.commit()
    db.close()

    logger.info(f"demo seeded for {u} (1 commit: {len(r.kg)} nodes, {len(r.ev)} events, {len(doc_rows)} docs)")
    return {"seeded": True, "profiles": 5}
