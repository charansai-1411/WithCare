# WithCare — Agent Memory

This file defines the **structure of the agent's long-term memory**: what WithCare remembers
about the people in a user's care, and the rules it follows to keep that memory accurate.

The agent **writes and updates this memory on its own** as conversations happen — the user never
has to fill it in. At runtime the live memory lives in the knowledge graph
(`kg_nodes` / `kg_edges` / `kg_summaries`, see `app/services/memory_service.py`); this document is
the human-readable **schema and contract** for it. One memory record exists **per care profile**
(each person or pet the user manages), not one global blob.

---

## What a profile's memory looks like

Each profile's memory is rendered into a compact block that is injected into every LLM turn
(`get_profile_memory`). It is built from these sections:

```
<Name> (<relation|pet species>, <age> <gender>, <weight>kg, <height>cm)
Conditions: <comma-separated chronic conditions>
Notes: <free-text context worth remembering>
Medications: <up to a few current medicines>
Appointments: <recent / upcoming bookings>
Hospitals: <facilities they've used or been referred to>
Govt schemes: <schemes explored or enrolled>
Insurance: <private policies explored or held>
Workout plan: <label of the current plan, if any>
Diet plan: <label of the current plan, if any>
Reminders: <active recurring/one-time reminders>
Tasks: <open tasks>
Health: <tracked metrics — e.g. HbA1c, BP, weight trend>
Recent: <1–3 sentence rolling summary of the latest activity>
```

## Memory record types

Every remembered fact is one typed node linked to the profile. Allowed types (keep to these):

| Type            | Holds                                              | Written by / when |
|-----------------|----------------------------------------------------|-------------------|
| `condition`     | A chronic condition (diabetes, hypertension…)      | Profile edit, or when stated in chat |
| `medication`    | A current medicine                                 | When mentioned or read from a prescription |
| `appointment`   | A booked/proposed appointment                      | On scheduling |
| `hospital`      | A facility used or referred to                     | On facility search / booking |
| `scheme`        | A government scheme explored or enrolled           | On coverage search |
| `insurance`     | A private policy explored or held                  | On coverage search / document read |
| `workout_plan`  | The current workout plan text (one per profile)    | On plan generation (supersedes old) |
| `diet_plan`     | The current diet plan text (one per profile)       | On plan generation (supersedes old) |
| `reminder`      | An active reminder                                 | On reminder set |
| `task`          | An open task                                        | On task create |
| `health_metric` | A tracked value (HbA1c, BP, weight…)               | When a value is shared or read from a report |

## Rules the agent follows when updating memory

1. **Write facts, not chatter.** Store durable, reusable facts (a condition, a plan, a policy,
   an appointment) — never small talk, the user's phrasing, or one-off questions.
2. **One fact per record.** Each node holds a single fact with a short `name` and optional
   structured `data`.
3. **Update, don't duplicate.** If a fact of the same `(profile, type, name)` already exists,
   update it. Plans are unique per type — a new plan **replaces** the old one (adaptivity as
   health changes).
4. **Never re-ask what memory already holds.** Read the profile's memory first; only ask the user
   for something genuinely missing.
5. **Correct on new evidence.** If the user or a document contradicts a stored fact, overwrite the
   stale fact; delete facts that turn out to be wrong.
6. **Right profile.** Attach every fact to the profile it's about (resolve "mother"/"Bruno"/a name
   to the correct profile), never to the wrong person.
7. **Keep `Recent` fresh.** Roll the short activity summary forward each meaningful turn so the
   agent has quick context without scanning every node.
8. **Privacy.** Memory is per-user and never shared across accounts; it can be viewed and cleared
   from **Settings → Privacy & Data → Memory**.

## Safety boundary

Memory records **what is** (conditions, values, coverage) — never a diagnosis, severity judgment,
or treatment plan. Clinical interpretation is out of scope for both the memory and the agent.
