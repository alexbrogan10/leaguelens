"""Waiver radar: unrostered players ranked by rising usage."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from leaguelens.models import NflGame, Player, PlayerWeekStat
from leaguelens.schemas import UsageWeekOut, WaiverPlayerOut, WaiversOut
from leaguelens.services.league import LeagueService
from leaguelens.services.valuation import StatsUnavailableError, stat_line
from leaguelens.valuation.model import SKILL_POSITIONS, usage
from leaguelens.valuation.scoring import fantasy_points
from leaguelens.valuation.waivers import Candidate, UsagePoint, rank_candidates

WINDOW = 3
HISTORY = 6
USAGE_LABELS = {
    "WR": "WOPR",
    "TE": "WOPR",
    "RB": "carry share + 2 x target share",
    "QB": "pass attempts + 2 x carries",
}


class WaiverService:
    def __init__(self, session_factory: sessionmaker[Session], leagues: LeagueService) -> None:
        self._sf = session_factory
        self._leagues = leagues

    def radar(self, league_id: str, position: str | None = None, limit: int = 50) -> WaiversOut:
        ctx = self._leagues.context(league_id)
        season = int(ctx.season)
        rosters = self._leagues.sleeper.get_rosters(league_id, final=ctx.is_complete)
        rostered = {str(p) for r in rosters for p in (r.get("players") or [])}
        scoring = ctx.league.get("scoring_settings") or {}
        positions = [position] if position in SKILL_POSITIONS else list(SKILL_POSITIONS)

        with self._sf() as s:
            last = s.scalar(
                select(func.max(PlayerWeekStat.week)).where(
                    PlayerWeekStat.season == season,
                    PlayerWeekStat.week <= (max(ctx.completed_weeks, default=18)),
                )
            )
            if last is None:
                raise StatsUnavailableError(
                    f"Player stats for {season} haven't been loaded yet. "
                    "Run `python -m leaguelens.jobs all`."
                )
            first = max(1, last - HISTORY - 2)  # extra weeks so byes don't shrink the window
            players = [
                p
                for p in s.scalars(
                    select(Player).where(
                        Player.position.in_(positions),
                        Player.team.is_not(None),
                        Player.gsis_id.is_not(None),
                    )
                )
                if p.sleeper_id not in rostered
            ]
            by_gsis = {p.gsis_id: p for p in players}
            stats = s.scalars(
                select(PlayerWeekStat).where(
                    PlayerWeekStat.season == season,
                    PlayerWeekStat.week.between(first, last),
                    PlayerWeekStat.gsis_id.in_(list(by_gsis)),
                )
            ).all()
            games = s.scalars(
                select(NflGame).where(NflGame.season == season, NflGame.week.between(first, last))
            ).all()

        team_weeks: dict[str, set[int]] = defaultdict(set)
        for g in games:
            team_weeks[g.home_team].add(g.week)
            team_weeks[g.away_team].add(g.week)
        lines = {(r.gsis_id, r.week): r for r in stats}

        candidates: list[Candidate] = []
        histories: dict[str, list[UsagePoint]] = {}
        for p in players:
            pos = p.position or ""
            played_weeks = team_weeks.get(p.team or "", set())
            # Skip bye weeks (only when we have a schedule to know them).
            weeks = [w for w in range(first, last + 1) if not games or w in played_weeks]
            series = []
            for w in weeks:
                row = lines.get((p.gsis_id or "", w))
                if row is None:
                    series.append(UsagePoint(w, 0.0, None, 0.0))
                    continue
                line = stat_line(row)
                series.append(
                    UsagePoint(
                        w, usage(pos, line), row.snap_pct, fantasy_points(line, scoring, pos)
                    )
                )
            series = series[-HISTORY:]
            histories[p.sleeper_id] = series
            candidates.append(Candidate(p.sleeper_id, pos, series[-WINDOW:]))

        ranked = rank_candidates(candidates)[:limit]
        by_id = {p.sleeper_id: p for p in players}
        out = []
        for r in ranked:
            p = by_id[r.player_id]
            hist = histories[r.player_id]
            played = [h.points for h in hist[-WINDOW:] if h.usage > 0]
            out.append(
                WaiverPlayerOut(
                    player_id=p.sleeper_id,
                    name=p.full_name,
                    position=p.position or "",
                    team=p.team,
                    injury_status=p.injury_status,
                    age=p.age,
                    score=round(r.score, 3),
                    usage_slope=round(r.slope, 4),
                    latest_usage=round(r.latest, 4),
                    usage_label=USAGE_LABELS.get(p.position or "", "usage"),
                    recent_ppg=round(sum(played) / len(played), 2) if played else 0.0,
                    history=[
                        UsageWeekOut(
                            week=h.week,
                            usage=round(h.usage, 4),
                            snap_pct=h.snap_pct,
                            points=h.points,
                        )
                        for h in hist
                    ],
                )
            )
        return WaiversOut(
            season=ctx.season, weeks=list(range(max(1, last - WINDOW + 1), last + 1)), players=out
        )
