"""
Placeholder for medicine ingestion (Wave 2 / P1).
Jan Aushadhi catalogue ingestion will be added here.

Run from withcare-backend directory:
    python scripts/ingest_medicines.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def ingest_medicines():
    print("Medicine ingestion is a P1 feature — not yet implemented.")
    print("Jan Aushadhi catalogue will be ingested here in Wave 3+.")


if __name__ == "__main__":
    ingest_medicines()
