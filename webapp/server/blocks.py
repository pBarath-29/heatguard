"""Block Radar logic: rank HDB blocks in a subzone by 1- and 2-room rental flats (pure functions, unit-tested).

Rental-flat counts are a proxy for where outreach may be needed — not counts of elderly residents, low-income households
or homes without air-conditioning. The flags below are descriptive building characteristics, not evidence a block is hotter.
"""
from __future__ import annotations

OLDER_BLOCK_YEAR = 1985     # completed in or before this year → "older block" (configurable)
TALL_BLOCK_FLOORS = 20      # highest floor at or above this → "tall block" (configurable)
TOP_N = 6


def rental_total(b: dict) -> int:
    return int(b.get("rental_1room") or 0) + int(b.get("rental_2room") or 0)


def flags(b: dict, older_year: int = OLDER_BLOCK_YEAR, tall_floors: int = TALL_BLOCK_FLOORS) -> list[str]:
    out = []
    if b.get("year_completed") and int(b["year_completed"]) <= older_year:
        out.append(f"Older block (completed {b['year_completed']})")
    if b.get("max_floor") and int(b["max_floor"]) >= tall_floors:
        out.append(f"Tall block ({b['max_floor']} floors)")
    return out


def filter_blocks(blocks: list[dict], min_rental: int = 0, year_from: int | None = None, year_to: int | None = None,
                  min_floor: int | None = None) -> list[dict]:
    out = []
    for b in blocks:
        if rental_total(b) < min_rental:
            continue
        y = b.get("year_completed")
        if year_from is not None and (y is None or int(y) < year_from):
            continue
        if year_to is not None and (y is None or int(y) > year_to):
            continue
        if min_floor is not None and (b.get("max_floor") is None or int(b["max_floor"]) < min_floor):
            continue
        out.append(b)
    return out


def rank_blocks(blocks: list[dict], top_n: int = TOP_N) -> dict:
    """Top blocks by combined 1- and 2-room rental flats, and their share of the subzone's rental flats.

    `blocks` must be ALL residential blocks of the subzone that were placed on the map (the share uses their total).
    Blocks with no rental flats are never ranked. If fewer than `top_n` qualify, all qualifying blocks are returned with a note."""
    total = sum(rental_total(b) for b in blocks)
    with_rental = sorted((b for b in blocks if rental_total(b) > 0),
                         key=lambda b: (-rental_total(b), str(b.get("blk_no")), str(b.get("street"))))
    top = [{**b, "rank": i + 1, "rental_total": rental_total(b), "flags": flags(b)} for i, b in enumerate(with_rental[:top_n])]
    top_sum = sum(b["rental_total"] for b in top)
    note = None
    if not with_rental:
        note = "No blocks with 1-room or 2-room rental flats were found in this subzone."
    elif len(with_rental) < top_n:
        note = f"Only {len(with_rental)} block{'s' if len(with_rental) != 1 else ''} in this subzone {'have' if len(with_rental) != 1 else 'has'} 1-room or 2-room rental flats."
    return {"top": top, "subzone_rental_total": total, "top_rental_total": top_sum,
            "top_share": round(top_sum / total, 4) if total else None, "blocks_with_rental": len(with_rental), "note": note}
