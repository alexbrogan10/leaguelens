"""Waiver radar scoring. Pure: takes usage series, returns ranked candidates.

For each available player we look at their usage (same per-position definition as the
valuation model) over the last ``window`` NFL weeks, skipping their bye. A week with no
stat line counts as zero usage.

    score = 0.6 * z(slope) + 0.4 * z(latest usage)

z-scores are computed within position across the available players being ranked, so the
radar highlights players whose role is growing relative to everything else on waivers.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import mean, pstdev

WEIGHT_SLOPE = 0.6
WEIGHT_LEVEL = 0.4


@dataclass(frozen=True)
class UsagePoint:
    week: int
    usage: float
    snap_pct: float | None
    points: float


@dataclass(frozen=True)
class Candidate:
    player_id: str
    position: str
    series: Sequence[UsagePoint]  # the window, oldest first, byes already removed


@dataclass(frozen=True)
class RadarScore:
    player_id: str
    slope: float
    latest: float
    score: float


def slope(values: Sequence[float]) -> float:
    """Least-squares slope per week of ``values`` (evenly spaced)."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = range(n)
    x_bar = (n - 1) / 2
    y_bar = mean(values)
    num = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, values, strict=True))
    den = sum((x - x_bar) ** 2 for x in xs)
    return num / den


def _z(values: Mapping[str, float]) -> dict[str, float]:
    if not values:
        return {}
    mu = mean(values.values())
    sd = pstdev(values.values())
    return {k: (v - mu) / sd if sd > 0 else 0.0 for k, v in values.items()}


def rank_candidates(candidates: Sequence[Candidate], min_games: int = 2) -> list[RadarScore]:
    """Score candidates with at least ``min_games`` non-zero weeks in the window."""
    eligible = [c for c in candidates if sum(1 for p in c.series if p.usage > 0) >= min_games]
    out: list[RadarScore] = []
    for pos in sorted({c.position for c in eligible}):
        group = [c for c in eligible if c.position == pos]
        slopes = {c.player_id: slope([p.usage for p in c.series]) for c in group}
        latest = {c.player_id: c.series[-1].usage if c.series else 0.0 for c in group}
        zs, zl = _z(slopes), _z(latest)
        for c in group:
            pid = c.player_id
            out.append(
                RadarScore(
                    player_id=pid,
                    slope=slopes[pid],
                    latest=latest[pid],
                    score=WEIGHT_SLOPE * zs[pid] + WEIGHT_LEVEL * zl[pid],
                )
            )
    return sorted(out, key=lambda r: r.score, reverse=True)
