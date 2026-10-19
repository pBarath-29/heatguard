import pytest

from server import blocks as bk
from server import welfare as wf


def blk(no, r1, r2, year=1990, floors=12):
    return {"blk_no": no, "street": "TEST ST", "rental_1room": r1, "rental_2room": r2, "year_completed": year, "max_floor": floors,
            "latitude": 1.3, "longitude": 103.9}


# ---------------- Block Radar ----------------
def test_ranking_and_share_use_subzone_total():
    blocks = [blk("1", 100, 50), blk("2", 0, 0), blk("3", 30, 0), blk("4", 10, 10), blk("5", 5, 0), blk("6", 0, 40), blk("7", 2, 1), blk("8", 1, 0)]
    r = bk.rank_blocks(blocks)
    assert [b["blk_no"] for b in r["top"]] == ["1", "6", "3", "4", "5", "7"]
    assert r["subzone_rental_total"] == 249
    assert r["top_rental_total"] == 248
    assert r["top_share"] == round(248 / 249, 4)
    assert r["note"] is None


def test_fewer_than_six_blocks_explained():
    r = bk.rank_blocks([blk("1", 5, 0), blk("2", 0, 0)])
    assert len(r["top"]) == 1 and "Only 1 block" in r["note"]


def test_no_rental_blocks():
    r = bk.rank_blocks([blk("1", 0, 0)])
    assert r["top"] == [] and r["top_share"] is None and "No blocks" in r["note"]


def test_flags_are_descriptive_and_configurable():
    assert bk.flags(blk("1", 1, 0, year=1978, floors=25)) == ["Older block (completed 1978)", "Tall block (25 floors)"]
    assert bk.flags(blk("1", 1, 0, year=1978, floors=25), older_year=1970, tall_floors=30) == []


def test_filters():
    blocks = [blk("1", 100, 0, 1975, 12), blk("2", 5, 0, 1995, 25), blk("3", 0, 0, 1980, 30)]
    assert [b["blk_no"] for b in bk.filter_blocks(blocks, min_rental=10)] == ["1"]
    assert [b["blk_no"] for b in bk.filter_blocks(blocks, year_to=1985)] == ["1", "3"]
    assert [b["blk_no"] for b in bk.filter_blocks(blocks, min_floor=20)] == ["2", "3"]


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
