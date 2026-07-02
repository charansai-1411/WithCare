"""
Run from withcare-backend directory:
    python scripts/ingest_schemes.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from google.cloud import firestore
from app.config import settings


def ingest_schemes():
    db = firestore.Client(project=settings.gcp_project_id, database=settings.firestore_database)
    schemes_dir = Path(__file__).parent.parent / "app" / "data" / "schemes"

    if not schemes_dir.exists():
        print(f"ERROR: schemes directory not found at {schemes_dir}")
        return

    files = list(schemes_dir.glob("*.json"))
    if not files:
        print("ERROR: No JSON files found in schemes directory")
        return

    print(f"Found {len(files)} scheme files. Ingesting...")
    for json_file in files:
        data = json.loads(json_file.read_text(encoding="utf-8"))
        doc_id = data["id"]
        db.collection("schemes").document(doc_id).set(data)
        print(f"  ✓ Ingested: {doc_id} — {data['name']}")

    print(f"\nDone. {len(files)} schemes ingested into Firestore.")


if __name__ == "__main__":
    ingest_schemes()
