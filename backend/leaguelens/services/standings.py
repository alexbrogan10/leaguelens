"""Pure standings math: actual record, all-play record, luck and power rankings.

Input is a list of ``WeekScore`` rows (one per team per completed week). No I/O here.

Definitions
-----------
* **All-play**: each week a team is matched against every other team. It earns a win
  for every team it outscored, a loss for every team that outscored it, a tie otherwise.
* **Expected wins** = all-play win% x games played (counting median games if the league
  plays them).
* **Luck** = actual wins - expected wins. Positive means the schedule helped.
* **Power score** = 0.6 x all-play win% + 0.4 x (points per game / best points per game).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import median

POWER_WEIGHT_ALLPLAY = 0.6
POWER_WEIGHT_POINTS = 0.4


@dataclass(frozen=True)
class WeekScore:
    week: int
    roster_id: int
    matchup_id: int | None
    points: float


@dataclass
class TeamRecord:
    roster_id: int
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = 0.0
    points_against: float = 0.0
    allplay_wins: int = 0
    allplay_losses: int = 0
    allplay_ties: int = 0
    games: int = 0
    weekly_points: dict[int, float] = field(default_factory=dict)
    expected_wins: float = 0.0
    luck: float = 0.0
    power_score: float = 0.0
    power_rank: int = 0
    standing_rank: int = 0

    @property
    def win_pct(self) -> float:
        total = self.wins + self.losses + self.ties
        return (self.wins + 0.5 * self.ties) / total if total else 0.0

    @property
    def allplay_pct(self) -> float:
        total = self.allplay_wins + self.allplay_losses + self.allplay_ties
        return (self.allplay_wins + 0.5 * self.allplay_ties) / total if total else 0.0

    @property
    def points_per_game(self) -> float:
        weeks = len(self.weekly_points)
        return self.points_for / weeks if weeks else 0.0


def compute_records(
    scores: list[WeekScore], roster_ids: list[int], median_game: bool = False
) -> list[TeamRecord]:
    """Return one ``TeamRecord`` per roster, sorted by standings (wins, then points for)."""
    records = {rid: TeamRecord(roster_id=rid) for rid in roster_ids}
    by_week: dict[int, list[WeekScore]] = defaultdict(list)
    for s in scores:
        if s.roster_id in records:
            by_week[s.week].append(s)

    for week, rows in sorted(by_week.items()):
        for r in rows:
            rec = records[r.roster_id]
            rec.points_for += r.points
            rec.weekly_points[week] = r.points
            for other in rows:
                if other.roster_id == r.roster_id:
                    continue
                if r.points > other.points:
                    rec.allplay_wins += 1
                elif r.points < other.points:
                    rec.allplay_losses += 1
                else:
                    rec.allplay_ties += 1

        by_matchup: dict[int, list[WeekScore]] = defaultdict(list)
        for r in rows:
            if r.matchup_id is not None:
                by_matchup[r.matchup_id].append(r)
        for pair in by_matchup.values():
            if len(pair) != 2:
                continue
            a, b = pair
            ra, rb = records[a.roster_id], records[b.roster_id]
            ra.points_against += b.points
            rb.points_against += a.points
            ra.games += 1
            rb.games += 1
            if a.points > b.points:
                ra.wins += 1
                rb.losses += 1
            elif a.points < b.points:
                rb.wins += 1
                ra.losses += 1
            else:
                ra.ties += 1
                rb.ties += 1

        if median_game and len(rows) > 1:
            mid = median(r.points for r in rows)
            for r in rows:
                rec = records[r.roster_id]
                rec.games += 1
                if r.points > mid:
                    rec.wins += 1
                elif r.points < mid:
                    rec.losses += 1
                else:
                    rec.ties += 1

    best_ppg = max((r.points_per_game for r in records.values()), default=0.0)
    for rec in records.values():
        rec.expected_wins = rec.allplay_pct * rec.games
        rec.luck = (rec.wins + 0.5 * rec.ties) - rec.expected_wins
        points_component = rec.points_per_game / best_ppg if best_ppg else 0.0
        rec.power_score = (
            POWER_WEIGHT_ALLPLAY * rec.allplay_pct + POWER_WEIGHT_POINTS * points_component
        )

    for i, rec in enumerate(
        sorted(records.values(), key=lambda r: (-r.power_score, -r.points_for)), start=1
    ):
        rec.power_rank = i
    ordered = sorted(records.values(), key=lambda r: (-r.win_pct, -r.points_for))
    for i, rec in enumerate(ordered, start=1):
        rec.standing_rank = i
    return ordered
