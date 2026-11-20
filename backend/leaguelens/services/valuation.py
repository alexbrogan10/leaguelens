"""Builds model inputs from the database and Sleeper, and runs the pure valuation model."""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from leaguelens.models import NflGame, Player, PlayerWeekStat
from leaguelens.schemas import (
    LineupSlotOut,
    PlayerValueOut,
    RosterOut,
    RostersOut,
    TeamImpactOut,
    TradeOut,
    TradeRequest,
)
from leaguelens.services.league import LeagueContext, LeagueService
from leaguelens.valuation.model import (
    SKILL_POSITIONS,
    GameLine,
    LineupSlot,
    PlayerInput,
    Projection,
    TeamTradeImpact,
    evaluate_trade,
    project_players,
)
from leaguelens.valuation.scoring import StatLine, fantasy_points

CACHE_SECONDS = 600
STAT_FIELDS = [f for f in StatLine.__dataclass_fields__ if f != "snap_pct"]


class StatsUnavailableError(Exception):
    pass


class BadRequestError(Exception):
    pass


@dataclass
class LeagueValues:
    ctx: LeagueContext
    projections: dict[str, Projection]
    weeks_remaining: int
    stats_through_week: int | None
    rosters: dict[int, list[str]]


class ValuesMemo:
    """Short-lived in-process cache of computed league values (one per container)."""

    def __init__(self, seconds: float = CACHE_SECONDS) -> None:
        self._seconds = seconds
        self._data: dict[str, tuple[float, LeagueValues]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> LeagueValues | None:
        with self._lock:
            hit = self._data.get(key)
            if hit and time.monotonic() - hit[0] < self._seconds:
                return hit[1]
            return None

    def set(self, key: str, value: LeagueValues) -> None:
        with self._lock:
            self._data[key] = (time.monotonic(), value)


def stat_line(row: PlayerWeekStat) -> StatLine:
    values = {f: float(getattr(row, f) or 0) for f in STAT_FIELDS}
    return StatLine(**values, snap_pct=row.snap_pct)


def league_end_week(settings: dict[str, Any]) -> int:
    playoff_start = int(settings.get("playoff_week_start") or 15)
    teams = int(settings.get("playoff_teams") or 6)
    rounds = math.ceil(math.log2(teams)) if teams > 1 else 0
    return min(playoff_start + rounds - 1, 18)


class ValuationService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        leagues: LeagueService,
        memo: ValuesMemo | None = None,
    ) -> None:
        self._sf = session_factory
        self._leagues = leagues
        self._memo = memo or ValuesMemo()

    def values(self, league_id: str) -> LeagueValues:
        hit = self._memo.get(league_id)
        if hit is not None:
            return hit
        result = self._compute(league_id)
        self._memo.set(league_id, result)
        return result

    def _compute(self, league_id: str) -> LeagueValues:
        ctx = self._leagues.context(league_id)
        season = int(ctx.season)
        lg = ctx.league
        rosters_raw = self._leagues.sleeper.get_rosters(league_id, final=ctx.is_complete)
        rosters = {
            int(r["roster_id"]): [str(p) for p in (r.get("players") or [])] for r in rosters_raw
        }
        rostered = {pid for ids in rosters.values() for pid in ids}

        next_week = max(ctx.completed_weeks, default=0) + 1
        end_week = league_end_week(ctx.settings)
        weeks_remaining = 0 if ctx.is_complete else max(0, end_week - next_week + 1)

        with self._sf() as s:
            has_stats = s.scalar(
                select(func.count())
                .select_from(PlayerWeekStat)
                .where(PlayerWeekStat.season == season)
            )
            if not has_stats:
                raise StatsUnavailableError(
                    f"Player stats for {season} haven't been loaded yet. "
                    "Run `python -m leaguelens.jobs all`."
                )
            players = s.scalars(
                select(Player).where(
                    (Player.sleeper_id.in_(rostered))
                    | ((Player.position.in_(SKILL_POSITIONS)) & (Player.team.is_not(None)))
                )
            ).all()
            gsis_ids = [p.gsis_id for p in players if p.gsis_id]
            max_week = next_week - 1 if not ctx.is_complete else 18
            stats = s.scalars(
                select(PlayerWeekStat).where(
                    PlayerWeekStat.season == season,
                    PlayerWeekStat.week <= max_week,
                    PlayerWeekStat.gsis_id.in_(gsis_ids),
                )
            ).all()
            games = s.scalars(
                select(NflGame).where(
                    NflGame.season == season,
                    NflGame.week >= next_week,
                    NflGame.week <= end_week,
                )
            ).all()
            stats_through = s.scalar(
                select(func.max(PlayerWeekStat.week)).where(
                    PlayerWeekStat.season == season, PlayerWeekStat.week <= max_week
                )
            )

        team_games: dict[str, int] = defaultdict(int)
        for g in games:
            team_games[g.home_team] += 1
            team_games[g.away_team] += 1
        have_schedule = bool(games)

        scoring = lg.get("scoring_settings") or {}
        by_player: dict[str, list[GameLine]] = defaultdict(list)
        for row in stats:
            line = stat_line(row)
            pos = row.position or ""
            by_player[row.gsis_id].append(
                GameLine(week=row.week, points=fantasy_points(line, scoring, pos), stats=line)
            )

        inputs: list[PlayerInput] = []
        for p in players:
            if not p.position:
                continue
            if have_schedule and p.team:
                remaining = min(team_games.get(p.team, 0), weeks_remaining)
            else:
                remaining = weeks_remaining if p.team else 0
            inputs.append(
                PlayerInput(
                    player_id=p.sleeper_id,
                    name=p.full_name,
                    position=p.position,
                    team=p.team,
                    games=by_player.get(p.gsis_id or "", []),
                    games_remaining=remaining,
                    injury_status=p.injury_status,
                )
            )
        projections = project_players(
            inputs, list(lg.get("roster_positions") or []), len(ctx.teams) or 12
        )
        return LeagueValues(ctx, projections, weeks_remaining, stats_through, rosters)

    # --- API shapes ----------------------------------------------------------------------
    def rosters(self, league_id: str) -> RostersOut:
        v = self.values(league_id)
        out = []
        for team in v.ctx.teams:
            ids = v.rosters.get(team.roster_id, [])
            players = sorted(
                (player_out(v.projections[i]) for i in ids if i in v.projections),
                key=lambda p: (-p.ros_points, p.name),
            )
            out.append(
                RosterOut(
                    roster_id=team.roster_id,
                    team_name=team.team_name,
                    display_name=team.display_name,
                    avatar_url=team.avatar_url,
                    players=players,
                )
            )
        return RostersOut(
            season=v.ctx.season,
            weeks_remaining=v.weeks_remaining,
            stats_through_week=v.stats_through_week,
            rosters=out,
        )

    def analyze_trade(self, league_id: str, req: TradeRequest) -> TradeOut:
        v = self.values(league_id)
        if req.team_a == req.team_b:
            raise BadRequestError("Pick two different teams")
        for rid in (req.team_a, req.team_b):
            if rid not in v.rosters:
                raise BadRequestError(f"Unknown roster {rid}")
        names = {t.roster_id: t.team_name for t in v.ctx.teams}
        try:
            result = evaluate_trade(
                (req.team_a, v.rosters[req.team_a]),
                (req.team_b, v.rosters[req.team_b]),
                req.a_gives,
                req.b_gives,
                v.projections,
                list(v.ctx.league.get("roster_positions") or []),
                names,
            )
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        if result.verdict == "fair":
            headline = "Fair trade: both sides come out about even."
        else:
            winner = names[req.team_a] if result.verdict == "team_a" else names[req.team_b]
            headline = f"{winner} wins this trade by {abs(result.margin):.1f} projected points."
        if v.weeks_remaining == 0:
            headline = "The season is over, so there is no rest-of-season value left to trade."

        return TradeOut(
            verdict=result.verdict,
            headline=headline,
            margin=result.margin,
            team_a=self._impact_out(result.team_a, names, v.projections),
            team_b=self._impact_out(result.team_b, names, v.projections),
            reasons=result.reasons,
            weeks_remaining=v.weeks_remaining,
        )

    @staticmethod
    def _impact_out(
        impact: TeamTradeImpact, names: dict[int, str], projections: dict[str, Projection]
    ) -> TeamImpactOut:
        def slots(lineup: list[LineupSlot]) -> list[LineupSlotOut]:
            out = []
            for s in lineup:
                p = projections.get(s.player_id) if s.player_id else None
                out.append(
                    LineupSlotOut(
                        slot=s.slot,
                        player_id=s.player_id,
                        name=p.name if p else None,
                        projected_ppg=p.projected_ppg if p else None,
                    )
                )
            return out

        return TeamImpactOut(
            roster_id=impact.roster_id,
            team_name=names.get(impact.roster_id, f"Team {impact.roster_id}"),
            receives=[player_out(projections[i]) for i in impact.receives if i in projections],
            gives=[player_out(projections[i]) for i in impact.gives if i in projections],
            lineup_before=slots(impact.lineup_before),
            lineup_after=slots(impact.lineup_after),
            starters_before=impact.starters_before,
            starters_after=impact.starters_after,
            bench_before=impact.bench_before,
            bench_after=impact.bench_after,
            gain=impact.gain,
            raw_value_in=impact.raw_value_in,
            raw_value_out=impact.raw_value_out,
        )


def player_out(p: Projection) -> PlayerValueOut:
    return PlayerValueOut(**{k: getattr(p, k) for k in PlayerValueOut.model_fields})
