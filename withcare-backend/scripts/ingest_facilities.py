"""
Run from withcare-backend directory:
    python scripts/ingest_facilities.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from google.cloud import firestore
from app.config import settings


def ingest_facilities():
    db = firestore.Client(project=settings.gcp_project_id, database=settings.firestore_database)
    facilities_dir = Path(__file__).parent.parent / "app" / "data" / "facilities"

    if not facilities_dir.exists():
        print(f"ERROR: facilities directory not found at {facilities_dir}")
        return

    files = list(facilities_dir.glob("*.json"))
    if not files:
        print("ERROR: No JSON files found in facilities directory")
        return

    print(f"Found {len(files)} facility files. Ingesting...")
    for json_file in files:
        data = json.loads(json_file.read_text(encoding="utf-8"))
        doc_id = data["id"]
        db.collection("facilities").document(doc_id).set(data)
        print(f"  ✓ Ingested: {doc_id} — {data['name']}")

    print(f"\nDone. {len(files)} facilities ingested into Firestore.")


if __name__ == "__main__":
    ingest_facilities()
