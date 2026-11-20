"""Fantasy points from a raw stat line, using a league's own Sleeper ``scoring_settings``.

Only offensive skill-player categories are covered (see ``SCORING_KEYS``); bonus and
kicker/defense categories are ignored, which is documented in the model assumptions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# Sleeper scoring key -> StatLine attribute
SCORING_KEYS: dict[str, str] = {
    "pass_yd": "pass_yd",
    "pass_td": "pass_td",
    "pass_int": "pass_int",
    "pass_2pt": "pass_2pt",
    "pass_cmp": "pass_cmp",
    "pass_att": "pass_att",
    "rush_yd": "rush_yd",
    "rush_td": "rush_td",
    "rush_2pt": "rush_2pt",
    "rush_att": "carries",
    "rec": "receptions",
    "rec_yd": "rec_yd",
    "rec_td": "rec_td",
    "rec_2pt": "rec_2pt",
    "fum_lost": "fum_lost",
}

# Sleeper's position-specific reception bonuses ("TE premium" etc.)
RECEPTION_BONUS = {"TE": "bonus_rec_te", "RB": "bonus_rec_rb", "WR": "bonus_rec_wr"}


@dataclass(frozen=True)
class StatLine:
    pass_att: float = 0
    pass_cmp: float = 0
    pass_yd: float = 0
    pass_td: float = 0
    pass_int: float = 0
    pass_2pt: float = 0
    carries: float = 0
    rush_yd: float = 0
    rush_td: float = 0
    rush_2pt: float = 0
    targets: float = 0
    receptions: float = 0
    rec_yd: float = 0
    rec_td: float = 0
    rec_2pt: float = 0
    fum_lost: float = 0
    air_yards: float = 0
    target_share: float = 0
    air_yards_share: float = 0
    wopr: float = 0
    team_carries: float = 0
    snap_pct: float | None = None


def fantasy_points(line: StatLine, scoring: Mapping[str, float], position: str = "") -> float:
    total = 0.0
    for key, attr in SCORING_KEYS.items():
        weight = scoring.get(key)
        if weight:
            total += float(weight) * float(getattr(line, attr))
    bonus_key = RECEPTION_BONUS.get(position)
    if bonus_key and scoring.get(bonus_key):
        total += float(scoring[bonus_key]) * line.receptions
    return round(total, 2)
