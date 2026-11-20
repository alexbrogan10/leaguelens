"""Rest-of-season player valuation and trade evaluation.

This module is pure: no I/O, no database, no clock. Every tunable number lives in
``ModelParams`` so the assumptions are visible and easy to change.

Pipeline
--------
1. **Recent PPG** - exponentially weighted mean of the last ``recent_games`` games
   (weight ``decay**k`` for the k-th most recent game), then shrunk toward the
   position's replacement level: ``(n*ppg + k*prior) / (n + k)``.
2. **Usage trend** - ``r = mean usage (last 3 games) / mean usage (3 games before)``,
   clamped to ``trend_clamp``. ``proj_ppg = ppg_adj * (1 + pass_through * (r - 1))``.
   Usage: WR/TE = WOPR; RB = carry share + 2 x target share; QB = attempts + 2 x carries.
3. **Replacement level** - league starters at a position = teams x slots (flex slots split
   by ``flex_split``). The next player after the last starter sets replacement PPG.
4. **ROS value** = ``max(0, proj - repl) x games remaining x availability``.
5. **Trade fit** - for each team, the optimal starting lineup before and after the trade.
   Gain = change in starting-lineup points over the rest of the season
   + ``bench_weight`` x change in bench ROS value. A player who would not start adds
   only depth; filling a weak slot adds a lot.

Known limitations (v1): no strength of schedule; kickers and defenses are valued at a flat
replacement level; no IDP; no draft picks; players without stats start at replacement.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from math import isclose

from leaguelens.valuation.scoring import StatLine

SKILL_POSITIONS = ("QB", "RB", "WR", "TE")

FLEX_ELIGIBILITY: dict[str, tuple[str, ...]] = {
    "FLEX": ("RB", "WR", "TE"),
    "WRRB_FLEX": ("RB", "WR"),
    "REC_FLEX": ("WR", "TE"),
    "SUPER_FLEX": ("QB", "RB", "WR", "TE"),
}
NON_STARTING_SLOTS = {"BN", "IR", "TAXI"}


@dataclass(frozen=True)
class ModelParams:
    recent_games: int = 6
    decay: float = 0.85
    shrink_games: float = 2.0
    trend_window: int = 3
    trend_clamp: tuple[float, float] = (0.75, 1.25)
    trend_pass_through: float = 0.5
    bench_weight: float = 0.15
    fair_threshold: float = 0.10
    fair_floor_points: float = 10.0
    flat_kdef_ppg: float = 8.0
    flex_split: Mapping[str, Mapping[str, float]] = field(
        default_factory=lambda: {
            "FLEX": {"RB": 0.45, "WR": 0.45, "TE": 0.10},
            "WRRB_FLEX": {"RB": 0.5, "WR": 0.5},
            "REC_FLEX": {"WR": 0.8, "TE": 0.2},
            "SUPER_FLEX": {"QB": 0.8, "RB": 0.1, "WR": 0.1},
        }
    )
    availability: Mapping[str, float] = field(
        default_factory=lambda: {
            "Questionable": 0.95,
            "Doubtful": 0.9,
            "Out": 0.85,  # likely misses about one week
            "Sus": 0.8,
            "PUP": 0.5,
            "IR": 0.5,
        }
    )


DEFAULT_PARAMS = ModelParams()


# --- inputs -----------------------------------------------------------------------------


@dataclass(frozen=True)
class GameLine:
    week: int
    points: float
    stats: StatLine


@dataclass(frozen=True)
class PlayerInput:
    player_id: str
    name: str
    position: str
    team: str | None
    games: Sequence[GameLine]  # any order; sorted internally
    games_remaining: int
    injury_status: str | None = None


# --- outputs ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Projection:
    player_id: str
    name: str
    position: str
    team: str | None
    games_played: int
    recent_ppg: float
    adjusted_ppg: float
    usage_recent: float | None
    usage_prior: float | None
    trend_ratio: float
    projected_ppg: float
    replacement_ppg: float
    vorp_ppg: float
    games_remaining: int
    availability: float
    ros_points: float
    ros_value: float
    injury_status: str | None


def usage(position: str, s: StatLine) -> float:
    if position in ("WR", "TE"):
        return s.wopr or (1.5 * s.target_share + 0.7 * s.air_yards_share)
    if position == "RB":
        carry_share = s.carries / s.team_carries if s.team_carries else 0.0
        return carry_share + 2 * s.target_share
    if position == "QB":
        return s.pass_att + 2 * s.carries
    return 0.0


def weighted_ppg(points_recent_first: Sequence[float], decay: float) -> float:
    if not points_recent_first:
        return 0.0
    weights = [decay**k for k in range(len(points_recent_first))]
    return sum(p * w for p, w in zip(points_recent_first, weights, strict=True)) / sum(weights)


def trend_ratio(
    usages_recent_first: Sequence[float], window: int, clamp: tuple[float, float]
) -> tuple[float, float | None, float | None]:
    """Return (clamped ratio, recent mean, prior mean). Ratio is 1.0 without enough data."""
    recent = usages_recent_first[:window]
    prior = usages_recent_first[window : 2 * window]
    if len(recent) < window or not prior:
        return 1.0, (sum(recent) / len(recent) if recent else None), None
    r_mean = sum(recent) / len(recent)
    p_mean = sum(prior) / len(prior)
    if p_mean <= 0:
        return 1.0, r_mean, p_mean
    ratio = min(max(r_mean / p_mean, clamp[0]), clamp[1])
    return ratio, r_mean, p_mean


def starters_per_position(
    roster_positions: Iterable[str], num_teams: int, params: ModelParams = DEFAULT_PARAMS
) -> dict[str, float]:
    per_team: dict[str, float] = {}
    for slot in roster_positions:
        if slot in NON_STARTING_SLOTS:
            continue
        split = params.flex_split.get(slot)
        if split:
            for pos, share in split.items():
                per_team[pos] = per_team.get(pos, 0.0) + share
        else:
            per_team[slot] = per_team.get(slot, 0.0) + 1
    return {pos: n * num_teams for pos, n in per_team.items()}


def replacement_level(ppgs: Iterable[float], starters: float) -> float:
    """PPG of the first player after the last league starter (0 if the pool is too small)."""
    ranked = sorted(ppgs, reverse=True)
    idx = round(starters)
    if not ranked:
        return 0.0
    return ranked[min(idx, len(ranked) - 1)]


def _base_ppg(p: PlayerInput, params: ModelParams) -> tuple[list[GameLine], float]:
    recent = sorted(p.games, key=lambda g: g.week, reverse=True)[: params.recent_games]
    return recent, weighted_ppg([g.points for g in recent], params.decay)


def project_players(
    players: Sequence[PlayerInput],
    roster_positions: Sequence[str],
    num_teams: int,
    params: ModelParams = DEFAULT_PARAMS,
) -> dict[str, Projection]:
    """Project every player. Replacement levels come from the whole pool passed in."""
    starters = starters_per_position(roster_positions, num_teams, params)

    # Pass 1: unshrunk PPG -> replacement level per position.
    base = {p.player_id: _base_ppg(p, params) for p in players}
    replacement: dict[str, float] = {}
    for pos in SKILL_POSITIONS:
        pool = [base[p.player_id][1] for p in players if p.position == pos and p.games]
        replacement[pos] = replacement_level(pool, starters.get(pos, 0))

    out: dict[str, Projection] = {}
    for p in players:
        recent, ppg = base[p.player_id]
        availability = params.availability.get(p.injury_status or "", 1.0)
        n = len(recent)
        if p.position not in SKILL_POSITIONS:
            proj = repl = adj = params.flat_kdef_ppg
            ratio, u_recent, u_prior = 1.0, None, None
        else:
            repl = replacement[p.position]
            adj = (n * ppg + params.shrink_games * repl) / (n + params.shrink_games)
            usages = [usage(p.position, g.stats) for g in recent]
            ratio, u_recent, u_prior = trend_ratio(usages, params.trend_window, params.trend_clamp)
            proj = adj * (1 + params.trend_pass_through * (ratio - 1))
        vorp = max(0.0, proj - repl)
        ros_points = proj * p.games_remaining * availability
        out[p.player_id] = Projection(
            player_id=p.player_id,
            name=p.name,
            position=p.position,
            team=p.team,
            games_played=n,
            recent_ppg=round(ppg, 2),
            adjusted_ppg=round(adj, 2),
            usage_recent=None if u_recent is None else round(u_recent, 3),
            usage_prior=None if u_prior is None else round(u_prior, 3),
            trend_ratio=round(ratio, 3),
            projected_ppg=round(proj, 2),
            replacement_ppg=round(repl, 2),
            vorp_ppg=round(vorp, 2),
            games_remaining=p.games_remaining,
            availability=availability,
            ros_points=round(ros_points, 1),
            ros_value=round(vorp * p.games_remaining * availability, 1),
            injury_status=p.injury_status,
        )
    return out


# --- lineups ----------------------------------------------------------------------------


@dataclass(frozen=True)
class LineupSlot:
    slot: str
    player_id: str | None


def optimal_lineup(
    roster: Sequence[Projection], roster_positions: Sequence[str]
) -> tuple[list[LineupSlot], list[Projection]]:
    """Fill starting slots by ROS points. Fixed slots first, then the most restrictive flex.

    Returns (slots, bench). Greedy is optimal here because flex eligibility sets are nested
    supersets of the fixed slots.
    """
    available = sorted(roster, key=lambda p: p.ros_points, reverse=True)
    starting = [s for s in roster_positions if s not in NON_STARTING_SLOTS]
    # Fixed slots first, then flex slots from most to least restrictive.
    order = sorted(
        range(len(starting)),
        key=lambda i: (starting[i] in FLEX_ELIGIBILITY, len(FLEX_ELIGIBILITY.get(starting[i], ()))),
    )
    chosen: dict[int, str | None] = {}
    for i in order:
        slot = starting[i]
        eligible = FLEX_ELIGIBILITY.get(slot, (slot,))
        pick = next((p for p in available if p.position in eligible), None)
        chosen[i] = pick.player_id if pick else None
        if pick:
            available.remove(pick)
    slots = [LineupSlot(slot=starting[i], player_id=chosen.get(i)) for i in range(len(starting))]
    return slots, available


def lineup_points(slots: Sequence[LineupSlot], players: Mapping[str, Projection]) -> float:
    return sum(players[s.player_id].ros_points for s in slots if s.player_id)


# --- trades -----------------------------------------------------------------------------


@dataclass(frozen=True)
class TeamTradeImpact:
    roster_id: int
    receives: list[str]
    gives: list[str]
    lineup_before: list[LineupSlot]
    lineup_after: list[LineupSlot]
    starters_before: float
    starters_after: float
    bench_before: float
    bench_after: float
    gain: float
    raw_value_in: float
    raw_value_out: float


@dataclass(frozen=True)
class TradeResult:
    team_a: TeamTradeImpact
    team_b: TeamTradeImpact
    verdict: str  # "fair" | "team_a" | "team_b"
    margin: float
    reasons: list[str]


def _impact(
    roster_id: int,
    roster: Sequence[str],
    gives: Sequence[str],
    receives: Sequence[str],
    players: Mapping[str, Projection],
    roster_positions: Sequence[str],
    params: ModelParams,
) -> TeamTradeImpact:
    before_ids = [pid for pid in roster if pid in players]
    after_ids = [pid for pid in before_ids if pid not in gives] + [
        pid for pid in receives if pid in players
    ]
    lb, bench_b = optimal_lineup([players[i] for i in before_ids], roster_positions)
    la, bench_a = optimal_lineup([players[i] for i in after_ids], roster_positions)
    sb, sa = lineup_points(lb, players), lineup_points(la, players)
    bb = sum(p.ros_value for p in bench_b)
    ba = sum(p.ros_value for p in bench_a)
    gain = (sa - sb) + params.bench_weight * (ba - bb)
    return TeamTradeImpact(
        roster_id=roster_id,
        receives=list(receives),
        gives=list(gives),
        lineup_before=lb,
        lineup_after=la,
        starters_before=round(sb, 1),
        starters_after=round(sa, 1),
        bench_before=round(bb, 1),
        bench_after=round(ba, 1),
        gain=round(gain, 1),
        raw_value_in=round(sum(players[i].ros_value for i in receives if i in players), 1),
        raw_value_out=round(sum(players[i].ros_value for i in gives if i in players), 1),
    )


def _lineup_changes(
    impact: TeamTradeImpact, players: Mapping[str, Projection], team_name: str
) -> list[str]:
    reasons: list[str] = []
    before = {s.player_id for s in impact.lineup_before if s.player_id}
    after = {s.player_id for s in impact.lineup_after if s.player_id}
    for pid in impact.receives:
        p = players.get(pid)
        if p is None:
            continue
        if pid in after:
            reasons.append(
                f"{p.name} would start for {team_name} ({p.projected_ppg:.1f} projected PPG)."
            )
        else:
            reasons.append(
                f"{p.name} would not crack {team_name}'s starting lineup, so only adds depth."
            )
    for pid in impact.gives:
        p = players.get(pid)
        if p is not None and pid in before:
            reasons.append(f"{team_name} loses a starter in {p.name}.")
    return reasons


def _player_notes(p: Projection, params: ModelParams) -> list[str]:
    notes: list[str] = []
    if p.trend_ratio >= 1.1:
        notes.append(f"{p.name}'s usage is up {round((p.trend_ratio - 1) * 100)}% recently.")
    elif p.trend_ratio <= 0.9:
        notes.append(f"{p.name}'s usage is down {round((1 - p.trend_ratio) * 100)}% recently.")
    if p.availability < 1:
        notes.append(f"{p.name} is listed {p.injury_status}: value cut to {p.availability:.0%}.")
    if p.games_played < params.trend_window and p.position in SKILL_POSITIONS:
        notes.append(
            f"Only {p.games_played} recent game(s) for {p.name}; "
            "projection leans on the replacement-level prior."
        )
    return notes


def evaluate_trade(
    roster_a: tuple[int, Sequence[str]],
    roster_b: tuple[int, Sequence[str]],
    a_gives: Sequence[str],
    b_gives: Sequence[str],
    players: Mapping[str, Projection],
    roster_positions: Sequence[str],
    team_names: Mapping[int, str] | None = None,
    params: ModelParams = DEFAULT_PARAMS,
) -> TradeResult:
    if not a_gives and not b_gives:
        raise ValueError("A trade needs at least one player")
    if set(a_gives) - set(roster_a[1]) or set(b_gives) - set(roster_b[1]):
        raise ValueError("Each side can only give players on its own roster")
    names = team_names or {}
    a_name = names.get(roster_a[0], "Team A")
    b_name = names.get(roster_b[0], "Team B")
    ia = _impact(roster_a[0], roster_a[1], a_gives, b_gives, players, roster_positions, params)
    ib = _impact(roster_b[0], roster_b[1], b_gives, a_gives, players, roster_positions, params)

    scale = max(abs(ia.gain), abs(ib.gain), params.fair_floor_points)
    margin = ia.gain - ib.gain
    if abs(margin) <= params.fair_threshold * scale or isclose(ia.gain, ib.gain):
        verdict = "fair"
    else:
        verdict = "team_a" if margin > 0 else "team_b"

    reasons: list[str] = []
    if ia.gain > 0 and ib.gain > 0:
        reasons.append("Both teams improve their projected lineups: a win-win on roster fit.")
    for impact, name in ((ia, a_name), (ib, b_name)):
        verb = "gains" if impact.gain >= 0 else "loses"
        reasons.append(
            f"{name} {verb} {abs(impact.gain):.1f} projected rest-of-season points "
            f"(starters {impact.starters_before:.0f} -> {impact.starters_after:.0f})."
        )
    reasons += _lineup_changes(ia, players, a_name)
    reasons += _lineup_changes(ib, players, b_name)
    for pid in [*a_gives, *b_gives]:
        if pid in players:
            reasons += _player_notes(players[pid], params)
    return TradeResult(
        team_a=ia, team_b=ib, verdict=verdict, margin=round(margin, 1), reasons=reasons
    )
