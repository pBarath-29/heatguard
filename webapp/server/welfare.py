"""Welfare-check rules (pure functions, unit-tested). Storage lives in main.py.

Every change is an append-only *event*, so the history of attempts and remarks is never overwritten (audit trail).
The current state of a resident is the fold of their events:

  completed   True only after an explicit "complete" event (opening a record never completes it);
              a failed contact attempt never sets it.
  outcome     last contact outcome: "reached" | "no_response" | "unavailable" | "unreachable" | "referred" | None
  follow_up   flagged for further action (set automatically by unsuccessful attempts and referrals; can be cleared)
"""
from __future__ import annotations

import re

ACTIONS = {"complete", "uncomplete", "attempt", "remark", "follow_up_on", "follow_up_off"}
FAILED_OUTCOMES = {"no_response", "unavailable", "unreachable"}
OUTCOMES = FAILED_OUTCOMES | {"reached", "referred"}
MAX_REMARK = 1000
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class WelfareError(ValueError):
    pass


def clean_remark(text: str | None) -> str | None:
    if text is None:
        return None
    t = _CTRL.sub("", text).strip()
    if len(t) > MAX_REMARK:
        raise WelfareError(f"Remarks can be at most {MAX_REMARK} characters.")
    return t or None


def validate(event: dict) -> dict:
    action = event.get("action")
    if action not in ACTIONS:
        raise WelfareError("Unknown action.")
    outcome = event.get("outcome")
    if action == "attempt":
        if outcome not in OUTCOMES - {"reached"}:
            raise WelfareError("Choose what happened on the unsuccessful attempt.")
    elif outcome is not None:
        raise WelfareError("An outcome can only be recorded with a contact attempt.")
    remark = clean_remark(event.get("remark"))
    if action == "remark" and not remark:
        raise WelfareError("Please write a remark before saving.")
    return {**event, "remark": remark}


def state(events: list[dict]) -> dict:
    s = {"completed": False, "outcome": None, "follow_up": False, "version": 0, "updated_at": None, "updated_by": None}
    for e in sorted(events, key=lambda e: (e["at"], e.get("seq", 0))):
        a = e["action"]
        if a == "complete":
            s.update(completed=True, outcome="reached")
        elif a == "uncomplete":
            s.update(completed=False, outcome=None if s["outcome"] == "reached" else s["outcome"])
        elif a == "attempt":
            s.update(outcome=e["outcome"], follow_up=True)        # a failed attempt never completes the check
        elif a == "follow_up_on":
            s["follow_up"] = True
        elif a == "follow_up_off":
            s["follow_up"] = False
        s.update(version=s["version"] + 1, updated_at=e["at"], updated_by=e.get("by_email", e.get("by")))
    s["status"] = "completed" if s["completed"] else "follow_up" if s["follow_up"] else ("unsuccessful" if s["outcome"] in FAILED_OUTCOMES else "pending")
    return s


def check_version(current_version: int, expected_version: int) -> None:
    if current_version != expected_version:
        raise WelfareError("Someone else updated this record a moment ago. Your changes are kept — review the latest update and save again.")
