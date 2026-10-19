import pytest

from server import welfare as wf



# ---------------- Welfare checklist ----------------
def ev(action, at, outcome=None, remark=None):
    return {"action": action, "at": at, "outcome": outcome, "remark": remark, "by": "v@test"}


def test_opening_a_record_does_not_complete_it():
    assert wf.state([])["completed"] is False and wf.state([])["status"] == "pending"


def test_check_and_uncheck():
    s = wf.state([ev("complete", 1), ev("uncomplete", 2)])
    assert s["completed"] is False and s["version"] == 2
    assert s["outcome"] is None and s["status"] == "pending"          # undoing "done" doesn't leave a stale "reached"


def test_last_updater_recorded():
    s = wf.state([{**ev("complete", 1), "by_email": "volunteer@example.org"}])
    assert s["updated_by"] == "volunteer@example.org"


def test_failed_attempt_stays_incomplete_and_needs_follow_up():
    s = wf.state([ev("attempt", 1, outcome="no_response", remark="No answer at door")])
    assert s["completed"] is False and s["follow_up"] is True and s["status"] == "follow_up"


def test_follow_up_can_be_cleared_and_later_completed():
    s = wf.state([ev("attempt", 1, outcome="unreachable"), ev("follow_up_off", 2)])
    assert s["status"] == "unsuccessful"
    s = wf.state([ev("attempt", 1, outcome="unreachable"), ev("complete", 2)])
    assert s["status"] == "completed"


@pytest.mark.parametrize("event", [
    {"action": "attempt", "outcome": "reached"},          # a successful visit is recorded with "complete"
    {"action": "complete", "outcome": "no_response"},     # outcomes only with attempts
    {"action": "remark", "remark": "   "},                # empty remark
    {"action": "delete"},                                 # unknown action
    {"action": "remark", "remark": "x" * 1001},           # too long
])
def test_invalid_events_rejected(event):
    with pytest.raises(wf.WelfareError):
        wf.validate(event)


def test_remark_sanitised():
    assert wf.validate({"action": "remark", "remark": " Called twice\x07 "})["remark"] == "Called twice"


def test_conflicting_update_detected():
    wf.check_version(3, 3)
    with pytest.raises(wf.WelfareError):
        wf.check_version(4, 3)
