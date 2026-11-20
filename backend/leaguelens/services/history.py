"""League history: follow ``previous_league_id`` back through past seasons.

Managers are keyed by Sleeper ``owner_id`` (user id), because roster IDs can be reshuffled
between seasons. Head-to-head records count regular-season matchups only.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from leaguelens.schemas import (
    HeadToHeadOut,
    HistoryOut,
    ManagerOut,
    SeasonOut,
    SeasonStandingOut,
    TeamOut,
    TeamRefOut,
)
from leaguelens.services.league import LeagueService, NotFoundError
from leaguelens.services.standings import WeekScore, compute_records

MAX_SEASONS = 20


@dataclass
class _Manager:
    owner_id: str
    display_name: str = ""
    avatar_url: str | None = None
    seasons: int = 0
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = 0.0
    championships: int = 0
    runner_ups: int = 0
    finishes: list[int] = field(default_factory=list)


@dataclass
class _H2H:
    wins: int = 0
    losses: int = 0
    ties: int = 0
    pf: float = 0.0
    pa: float = 0.0


def owner_key(owner_id: str | None, roster_id: int) -> str:
    return owner_id or f"roster:{roster_id}"


def head_to_head(scores: list[WeekScore], owners: dict[int, str]) -> dict[tuple[str, str], _H2H]:
    """Regular-season results between each ordered pair of owners."""
    out: dict[tuple[str, str], _H2H] = defaultdict(_H2H)
    by_matchup: dict[tuple[int, int], list[WeekScore]] = defaultdict(list)
    for s in scores:
        if s.matchup_id is not None:
            by_matchup[(s.week, s.matchup_id)].append(s)
    for pair in by_matchup.values():
        if len(pair) != 2:
            continue
        for me, them in (pair, pair[::-1]):
            rec = out[(owners[me.roster_id], owners[them.roster_id])]
            rec.pf += me.points
            rec.pa += them.points
            if me.points > them.points:
                rec.wins += 1
            elif me.points < them.points:
                rec.losses += 1
            else:
                rec.ties += 1
    return out


def _ref(key: str | None, teams: dict[str, TeamOut]) -> TeamRefOut | None:
    if key is None:
        return None
    t = teams[key]
    return TeamRefOut(owner_id=key, display_name=t.display_name, team_name=t.team_name)


class HistoryService:
    def __init__(self, leagues: LeagueService) -> None:
        self._leagues = leagues

    def history(self, league_id: str) -> HistoryOut:
        seasons: list[SeasonOut] = []
        managers: dict[str, _Manager] = {}
        h2h: dict[tuple[str, str], _H2H] = defaultdict(_H2H)
        seen: set[str] = set()
        current: str | None = league_id

        while current and current not in seen and len(seen) < MAX_SEASONS:
            seen.add(current)
            try:
                ctx = self._leagues.context(current)
            except NotFoundError:
                if current == league_id:
                    raise
                break
            owners = {t.roster_id: owner_key(t.owner_id, t.roster_id) for t in ctx.teams}
            teams = {owners[t.roster_id]: t for t in ctx.teams}
            scores = self._leagues.week_scores(ctx, ctx.completed_weeks)
            records = compute_records(scores, list(owners), ctx.median_game)

            champion = runner_up = None
            if ctx.is_complete:
                bracket = self._leagues.sleeper.get_winners_bracket(current, final=True)
                final = next((m for m in bracket if m.get("p") == 1), None)
                if final and final.get("w") in owners:
                    champion = owners[int(final["w"])]
                    if final.get("l") in owners:
                        runner_up = owners[int(final["l"])]

            standings = []
            for r in records:
                key = owners[r.roster_id]
                t = teams[key]
                standings.append(
                    SeasonStandingOut(
                        owner_id=key,
                        display_name=t.display_name,
                        team_name=t.team_name,
                        rank=r.standing_rank,
                        wins=r.wins,
                        losses=r.losses,
                        ties=r.ties,
                        points_for=round(r.points_for, 2),
                    )
                )
                m = managers.setdefault(key, _Manager(owner_id=key))
                if not m.display_name:  # newest season first: keep the latest name
                    m.display_name = t.display_name
                    m.avatar_url = t.avatar_url
                m.seasons += 1
                m.wins += r.wins
                m.losses += r.losses
                m.ties += r.ties
                m.points_for += r.points_for
                if ctx.is_complete:
                    m.finishes.append(r.standing_rank)
                m.championships += int(key == champion)
                m.runner_ups += int(key == runner_up)

            for pair, rec in head_to_head(scores, owners).items():
                agg = h2h[pair]
                agg.wins += rec.wins
                agg.losses += rec.losses
                agg.ties += rec.ties
                agg.pf += rec.pf
                agg.pa += rec.pa

            seasons.append(
                SeasonOut(
                    season=ctx.season,
                    league_id=current,
                    name=ctx.league.get("name") or "Unnamed league",
                    status=ctx.league.get("status") or "unknown",
                    champion=_ref(champion, teams),
                    runner_up=_ref(runner_up, teams),
                    standings=standings,
                )
            )
            prev = ctx.league.get("previous_league_id")
            current = str(prev) if prev not in (None, "", "0", 0) else None

        return HistoryOut(
            seasons=seasons,
            managers=sorted(
                (
                    ManagerOut(
                        owner_id=m.owner_id,
                        display_name=m.display_name,
                        avatar_url=m.avatar_url,
                        seasons=m.seasons,
                        wins=m.wins,
                        losses=m.losses,
                        ties=m.ties,
                        points_for=round(m.points_for, 2),
                        championships=m.championships,
                        runner_ups=m.runner_ups,
                        best_finish=min(m.finishes) if m.finishes else None,
                    )
                    for m in managers.values()
                ),
                key=lambda m: (-m.championships, -m.wins, -m.points_for),
            ),
            head_to_head=[
                HeadToHeadOut(
                    owner_a=a,
                    owner_b=b,
                    wins=r.wins,
                    losses=r.losses,
                    ties=r.ties,
                    points_for=round(r.pf, 2),
                    points_against=round(r.pa, 2),
                )
                for (a, b), r in sorted(h2h.items())
            ],
        )
