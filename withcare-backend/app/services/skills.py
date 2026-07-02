"""
Modular skills loader.

Each skill is a markdown playbook in `skills/`. The orchestrator loads the lean
`orchestrator.md` every turn; each *reasoning* agent loads its own domain skill only when it
runs (progressive disclosure — the diet skill's tokens are paid only when planning a diet).
Deterministic executors (reminders, facility fetch) don't need a skill.
"""
import os
from functools import lru_cache

_SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "skills")


@lru_cache(maxsize=None)
def load_skill(name: str) -> str:
    path = os.path.join(_SKILLS_DIR, f"{name}.md")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""
