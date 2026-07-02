"""
Dependency Executor.

Runs READY frames as parallel chains. A FIND_FACILITY -> SCHEDULE chain runs the
facility search, injects the chosen hospital into the SCHEDULE frame, and then STOPS at
confirmation — it never books inside the chain. The calendar write happens only when the
confirmation gate re-invokes the executor with confirmed_task_id set to that frame.
"""
import asyncio
from datetime import datetime
from typing import Optional

from app.models.task_models import Fact, TaskFrame, TaskIntent, TaskResult, TaskStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DependencyExecutor:
    def __init__(self, scheme_agent, facility_agent, action_agent):
        self.scheme_agent = scheme_agent
        self.facility_agent = facility_agent
        self.action_agent = action_agent

    async def run_all(
        self,
        ready_frames: list[TaskFrame],
        all_frames: dict[str, TaskFrame],
        base_ctx: dict,
        confirmed_task_id: Optional[str] = None,
    ) -> list[TaskResult]:
        # Confirmation path: execute exactly the confirmed frame, bypassing chain logic
        # (it carries depends_on, which _build_chains intentionally skips).
        if confirmed_task_id:
            frame = all_frames.get(confirmed_task_id)
            if not frame:
                return []
            return [await self._execute_one(frame, all_frames, base_ctx, None, confirmed_task_id)]

        chains = self._build_chains(ready_frames, all_frames)
        per_chain = await asyncio.gather(
            *[self._run_chain(c, all_frames, base_ctx, confirmed_task_id) for c in chains]
        )
        return [r for chain in per_chain for r in chain]

    def _build_chains(self, ready_frames, all_frames) -> list[list[TaskFrame]]:
        ready_ids = {f.task_id for f in ready_frames}
        chains, seen = [], set()
        for f in ready_frames:
            if f.task_id in seen:
                continue
            # Skip a dependent ONLY if its parent also runs this turn (parent pulls it in).
            # If the parent already ran on an earlier turn, this frame roots its own chain.
            if f.depends_on and f.depends_on in ready_ids:
                continue
            chain = [f]
            seen.add(f.task_id)
            deps = [
                x for x in all_frames.values()
                if x.depends_on == f.task_id and x.status == TaskStatus.READY
            ]
            chain.extend(deps)
            seen.update(d.task_id for d in deps)
            chains.append(chain)
        return chains

    async def _run_chain(self, chain, all_frames, base_ctx, confirmed_task_id) -> list[TaskResult]:
        results, prior = [], None
        for frame in chain:
            try:
                result = await self._execute_one(frame, all_frames, base_ctx, prior, confirmed_task_id)
                prior = result
                results.append(result)
                if result.status == TaskStatus.AWAITING_CONFIRMATION:
                    break  # stop before booking — wait for the user's yes
            except Exception as e:
                logger.error(f"Executor failed on {frame.intent.value}: {e}")
                frame.status = TaskStatus.FAILED
                results.append(TaskResult(
                    task_id=frame.task_id, intent=frame.intent,
                    status=TaskStatus.FAILED, error=str(e),
                ))
                break
        return results

    async def _execute_one(self, frame, all_frames, base_ctx, prior, confirmed_task_id) -> TaskResult:
        if frame.intent == TaskIntent.FIND_SCHEME:
            frame.status = TaskStatus.RUNNING
            r = await self.scheme_agent.run({**base_ctx, **self._scheme_ctx(frame)})
            frame.results = r.steps
            frame.status = TaskStatus.DONE
            return TaskResult(task_id=frame.task_id, intent=frame.intent, status=TaskStatus.DONE, steps=r.steps)

        if frame.intent == TaskIntent.FIND_FACILITY:
            frame.status = TaskStatus.RUNNING
            r = await self.facility_agent.run({**base_ctx, **self._facility_ctx(frame)})
            frame.results = r.steps
            frame.status = TaskStatus.DONE
            # Inject the chosen hospital into any SCHEDULE frame depending on this one —
            # now, regardless of whether that schedule is ready this turn or a later one.
            if r.steps:
                top = r.steps[0].action.replace("Visit ", "").replace(" (nearby)", "")
                for dep in all_frames.values():
                    if dep.intent == TaskIntent.SCHEDULE and dep.depends_on == frame.task_id:
                        dep.facts["hospital"] = Fact(value=top, user_specified=False)
                        dep.results = r.steps
            return TaskResult(task_id=frame.task_id, intent=frame.intent, status=TaskStatus.DONE, steps=r.steps)

        # SCHEDULE — hospital was injected when its facility completed (this turn or earlier).
        if frame.task_id != confirmed_task_id:
            # Not a confirmed booking → surface for confirmation, do NOT write to Calendar.
            frame.status = TaskStatus.AWAITING_CONFIRMATION
            return TaskResult(
                task_id=frame.task_id, intent=frame.intent,
                status=TaskStatus.AWAITING_CONFIRMATION, depends_on=frame.depends_on, steps=[],
            )

        # Confirmed → book it.
        frame.status = TaskStatus.RUNNING
        r = await self.action_agent.run({**base_ctx, **self._schedule_ctx(frame)})
        frame.results = r.steps
        frame.status = TaskStatus.DONE
        return TaskResult(task_id=frame.task_id, intent=frame.intent, status=TaskStatus.DONE, steps=r.steps)

    # ── ctx adapters — translate Facts into what each agent already expects ──────────
    @staticmethod
    def _fact(frame: TaskFrame, key: str, default: str = "") -> str:
        f = frame.facts.get(key)
        return f.value if (f and f.value) else default

    def _scheme_ctx(self, frame) -> dict:
        condition = self._fact(frame, "condition")
        location = self._fact(frame, "location")
        occupation = self._fact(frame, "occupation")
        income = self._fact(frame, "annual_income") or self._fact(frame, "income_level")
        social = self._fact(frame, "social_category")
        scope_pref = frame.preferences.get("coverage_scope")
        coverage_scope = scope_pref.value if (scope_pref and scope_pref.value) else "both"
        # scheme_agent extracts eligibility from user_message — synthesize a real sentence.
        parts = [p for p in [
            condition or "health coverage eligibility",
            f"in {location}" if location and "," not in location else "",
            f"occupation {occupation}" if occupation else "",
            f"income {income}" if income else "",
            f"category {social}" if social else "",
        ] if p]
        return {
            "condition": condition,
            "location": location,
            "occupation": occupation,
            "annual_income": income,
            "social_category": social,
            "coverage_scope": coverage_scope,
            "user_message": ", ".join(parts),
        }

    def _facility_ctx(self, frame) -> dict:
        pref = frame.preferences.get("facility_ranking")
        condition = self._fact(frame, "condition") or self._fact(frame, "procedure")
        location = self._fact(frame, "location")
        loc_txt = location if location and "," not in location else ""
        return {
            "condition": condition,
            "location": location,
            "specialty": self._fact(frame, "specialty"),
            "hospital": self._fact(frame, "hospital"),
            "facility_ranking": pref.value if pref else "nearest",
            "user_message": " ".join(p for p in [condition, f"in {loc_txt}" if loc_txt else ""] if p),
        }

    def _schedule_ctx(self, frame) -> dict:
        date = self._fact(frame, "date")
        t_start = self._fact(frame, "time_start")
        t_end = self._fact(frame, "time_end")
        start_iso = end_iso = ""
        if date and t_start and t_start != "flexible":
            start_iso = f"{date}T{t_start}:00"
            if t_end and t_end != "flexible":
                end_iso = f"{date}T{t_end}:00"
        steps_so_far = [s.model_dump() for s in frame.results]
        return {
            "extracted_procedure": self._fact(frame, "procedure"),
            "extracted_hospital": self._fact(frame, "hospital"),
            "extracted_start_datetime": start_iso,
            "extracted_end_datetime": end_iso,
            "for_member": self._fact(frame, "for_member", "self"),
            "care_plan_steps": steps_so_far,
            "care_plan_context": {
                "intent_summary": self._fact(frame, "procedure"),
                "ordered_steps": steps_so_far,
                "generated_at": datetime.utcnow().isoformat(),
                "disclaimer": "WithCare provides navigation assistance only. This is not medical advice.",
            },
            "user_message": self._fact(frame, "procedure"),
        }
