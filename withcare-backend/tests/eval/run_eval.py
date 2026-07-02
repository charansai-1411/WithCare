"""
WithCare eval / regression runner.

Runs tests/eval/cases.yaml against the live /chat API and checks each turn's behavior.
This is the parity target for the agentic refactor and the permanent regression net.

Usage (backend must be running on 127.0.0.1:8001):
    python -m tests.eval.run_eval
    python -m tests.eval.run_eval --only coverage_scope_refine   # single case
"""
import argparse
import os
import sys
import uuid

import httpx
import yaml

BASE = os.environ.get("WITHCARE_API", "http://127.0.0.1:8001")
CASES = os.path.join(os.path.dirname(__file__), "cases.yaml")

GREEN, RED, DIM, BOLD, RST = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


def setup_fixtures(client: httpx.Client, profiles_spec: dict) -> tuple[str, dict]:
    """Create a fresh user + the fixture profiles; return (user_id, {name: family_member})."""
    u = client.post(f"{BASE}/api/auth/dev", json={"name": "EvalUser"}).json()
    uid = u["id"]
    h = {"x-user-id": uid}
    client.get(f"{BASE}/api/profiles", headers=h)  # seed self
    members = {}
    for key, spec in (profiles_spec or {}).items():
        created = client.post(f"{BASE}/api/profiles", headers=h, json=spec).json()
        members[key] = {
            "id": created["id"],
            "name": spec["name"],
            "relation": spec.get("relation", ""),
            "kind": spec.get("kind", "person"),
            "species": spec.get("species", ""),
            "age": spec.get("age"),
            "gender": spec.get("gender", ""),
            "conditions": spec.get("conditions", ""),
        }
    return uid, members


def classify(resp: httpx.Response) -> dict:
    """Normalize a /chat response into {kind, text, agents}."""
    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = {"error": resp.text}
        return {"kind": "error", "text": str(body.get("error", body)), "agents": set()}
    body = resp.json()
    if isinstance(body, dict) and body.get("ordered_steps") is not None:
        steps = body["ordered_steps"]
        agents = {s.get("agent") for s in steps if s.get("agent")}
        # Searchable text = the message PLUS the card content (plans/results live in the cards).
        text = body.get("message", "") + " " + " ".join(
            f"{s.get('action','')} {s.get('detail','')}" for s in steps)
        return {"kind": "plan", "text": text, "agents": agents, "steps": len(steps)}
    if isinstance(body, dict) and body.get("clarify") is not None:
        return {"kind": "clarify", "text": body["clarify"], "agents": set(), "steps": 0}
    return {"kind": "other", "text": str(body), "agents": set(), "steps": 0}


def check(expect: dict, r: dict) -> list[str]:
    """Return a list of failure messages ([] == pass)."""
    fails = []
    text = (r["text"] or "").lower()
    want_type = expect.get("type", "any")
    if want_type != "any" and r["kind"] != want_type:
        fails.append(f"type: want {want_type}, got {r['kind']} ({r['text'][:60]!r})")
    for a in expect.get("agents_all", []):
        if a not in r["agents"]:
            fails.append(f"agents_all: missing {a} (got {sorted(r['agents'])})")
    if expect.get("agents_any"):
        if not (set(expect["agents_any"]) & r["agents"]):
            fails.append(f"agents_any: none of {expect['agents_any']} (got {sorted(r['agents'])})")
    for a in expect.get("agents_none", []):
        if a in r["agents"]:
            fails.append(f"agents_none: {a} present but shouldn't be")
    if expect.get("contains_any"):
        if not any(s.lower() in text for s in expect["contains_any"]):
            fails.append(f"contains_any: none of {expect['contains_any']}")
    for s in expect.get("contains_all", []):
        if s.lower() not in text:
            fails.append(f"contains_all: missing {s!r}")
    for s in expect.get("not_contains", []):
        if s.lower() in text:
            fails.append(f"not_contains: found {s!r}")
    if expect.get("min_steps") is not None and r.get("steps", 0) < expect["min_steps"]:
        fails.append(f"min_steps: want >= {expect['min_steps']}, got {r.get('steps', 0)}")
    return fails


def run_case(client, case, uid, members) -> list[str]:
    member = members.get(case.get("profile"))
    family = [member] if member else []
    sid = "eval-" + uuid.uuid4().hex[:10]
    history = []
    fails = []
    for i, turn in enumerate(case["turns"], 1):
        payload = {
            "message": turn["say"], "session_id": sid, "user_id": uid,
            "location": case.get("location", ""), "for_member": member["name"] if member else "self",
            "family_profile": family, "history": history,
        }
        resp = client.post(f"{BASE}/chat", json=payload, timeout=180)
        r = classify(resp)
        for f in check(turn.get("expect", {}), r):
            fails.append(f"turn {i} ({turn['say'][:40]!r}): {f}")
        history.append({"role": "user", "content": turn["say"]})
        history.append({"role": "assistant", "content": r["text"]})
    return fails


def run_case_retry(client, case, uid, members, attempts: int):
    """LLM behavior is probabilistic; a case that is *achievable* should pass. Retry up to
    `attempts` times and pass on the first clean run. Consistently-broken cases still fail."""
    last = []
    for i in range(1, attempts + 1):
        last = run_case(client, case, uid, members)
        if not last:
            return [], i
    return last, attempts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="run a single case id")
    ap.add_argument("--attempts", type=int, default=1,
                    help="max attempts per case (raise to 2-3 only when investigating flakiness — costs LLM calls)")
    args = ap.parse_args()

    with open(CASES, encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    with httpx.Client() as client:
        try:
            client.get(f"{BASE}/health", timeout=5)
        except Exception:
            print(f"{RED}Backend not reachable at {BASE}. Start it first.{RST}")
            sys.exit(2)
        uid, members = setup_fixtures(client, spec.get("profiles", {}))

        cases = spec["cases"]
        if args.only:
            cases = [c for c in cases if c["id"] == args.only]

        passed = 0          # regular cases that pass
        regular = 0         # regular case count
        xfail_failing = 0   # known targets still failing (expected)
        xpass = []          # known targets that now PASS (celebrate)
        flaky = []
        for case in cases:
            attempts = 1 if case.get("xfail") else args.attempts
            fails, used = run_case_retry(client, case, uid, members, attempts)
            is_xfail = bool(case.get("xfail"))
            if is_xfail:
                if fails:
                    xfail_failing += 1
                    print(f"{DIM}⋯ {case['id']} (target){RST}  {DIM}{case.get('desc','')}{RST}")
                else:
                    xpass.append(case["id"])
                    print(f"{BOLD}{GREEN}★ {case['id']} (target now PASSES!){RST}")
                continue
            regular += 1
            if fails:
                print(f"{RED}✗ {case['id']}{RST}  {DIM}{case.get('desc','')}{RST}")
                for f in fails:
                    print(f"    {RED}{f}{RST}")
            else:
                passed += 1
                tag = f"{RED} (flaky: passed on attempt {used}/{attempts}){RST}" if used > 1 else ""
                if used > 1:
                    flaky.append(case["id"])
                print(f"{GREEN}✓ {case['id']}{RST}  {DIM}{case.get('desc','')}{RST}{tag}")

        color = GREEN if passed == regular else RED
        print(f"\n{BOLD}{color}{passed}/{regular} passed{RST}  "
              f"{DIM}({xfail_failing} targets still open"
              + (f", {len(xpass)} newly passing: {', '.join(xpass)}" if xpass else "")
              + (f"; {len(flaky)} flaky: {', '.join(flaky)}" if flaky else "") + f"){RST}")
        sys.exit(0 if passed == regular else 1)


if __name__ == "__main__":
    main()
