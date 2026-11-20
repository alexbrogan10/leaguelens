"""League-level data assembly on top of the Sleeper client."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from leaguelens.clients.sleeper import SleeperClient
from leaguelens.schemas import (
    DashboardOut,
    LeagueOut,
    LeagueSummaryOut,
    StandingRowOut,
    TeamOut,
    UserLeaguesOut,
    UserOut,
)
from leaguelens.services.standings import WeekScore, compute_records

AVATAR_URL = "https://sleepercdn.com/avatars/thumbs/{}"


class NotFoundError(Exception):
    pass


def avatar_url(avatar: str | None) -> str | None:
    if not avatar:
        return None
    if avatar.startswith("http"):
        return avatar
    return AVATAR_URL.format(avatar)


def scoring_type(scoring: dict[str, Any]) -> str:
    rec = float(scoring.get("rec", 0) or 0)
    if rec >= 1:
        return "PPR"
    if rec >= 0.5:
        return "Half PPR"
    return "Standard"


@dataclass
class LeagueContext:
    league: dict[str, Any]
    teams: list[TeamOut]
    completed_weeks: list[int]
    is_complete: bool
    current_week: int

    @property
    def settings(self) -> dict[str, Any]:
        s = self.league.get("settings") or {}
        return s if isinstance(s, dict) else {}

    @property
    def season(self) -> str:
        return str(self.league.get("season", ""))

    @property
    def playoff_week_start(self) -> int:
        return int(self.settings.get("playoff_week_start") or 15)

    @property
    def median_game(self) -> bool:
        return bool(self.settings.get("league_average_match"))

    @property
    def team_by_roster(self) -> dict[int, TeamOut]:
        return {t.roster_id: t for t in self.teams}


class LeagueService:
    def __init__(self, sleeper: SleeperClient) -> None:
        self.sleeper = sleeper

    # --- users ---------------------------------------------------------------------
    def user_leagues(self, username: str, season: str | None = None) -> UserLeaguesOut:
        user = self.sleeper.get_user(username.strip())
        if not user or not user.get("user_id"):
            raise NotFoundError(f"No Sleeper user named '{username}'")
        if season is None:
            state = self.sleeper.get_state()
            season = str(state.get("league_season") or state.get("season"))
        leagues = self.sleeper.get_user_leagues(str(user["user_id"]), season)
        return UserLeaguesOut(
            user=UserOut(
                user_id=str(user["user_id"]),
                username=user.get("username"),
                display_name=user.get("display_name") or user.get("username") or "Unknown",
                avatar_url=avatar_url(user.get("avatar")),
            ),
            season=season,
            leagues=[
                LeagueSummaryOut(
                    league_id=str(lg["league_id"]),
                    name=lg.get("name") or "Unnamed league",
                    season=str(lg.get("season", season)),
                    status=lg.get("status") or "unknown",
                    total_rosters=int(lg.get("total_rosters") or 0),
                    avatar_url=avatar_url(lg.get("avatar")),
                )
                for lg in leagues
                if lg.get("league_id")
            ],
        )

    # --- league context --------------------------------------------------------------
    def context(self, league_id: str) -> LeagueContext:
        league = self.sleeper.get_league(league_id)
        if not league:
            raise NotFoundError(f"League {league_id} not found")
        state = self.sleeper.get_state()
        is_complete, completed, current_week = completed_weeks(league, state)
        users = self.sleeper.get_league_users(league_id, final=is_complete)
        rosters = self.sleeper.get_rosters(league_id, final=is_complete)
        return LeagueContext(
            league=league,
            teams=build_teams(rosters, users),
            completed_weeks=completed,
            is_complete=is_complete,
            current_week=current_week,
        )

    def league_out(self, ctx: LeagueContext, completed: list[int] | None = None) -> LeagueOut:
        lg = ctx.league
        return LeagueOut(
            league_id=str(lg["league_id"]),
            name=lg.get("name") or "Unnamed league",
            season=ctx.season,
            status=lg.get("status") or "unknown",
            total_rosters=int(lg.get("total_rosters") or len(ctx.teams)),
            roster_positions=list(lg.get("roster_positions") or []),
            scoring_type=scoring_type(lg.get("scoring_settings") or {}),
            playoff_week_start=ctx.playoff_week_start,
            median_game=ctx.median_game,
            previous_league_id=_clean_id(lg.get("previous_league_id")),
            completed_weeks=ctx.completed_weeks if completed is None else completed,
            teams=ctx.teams,
        )

    def week_scores(self, ctx: LeagueContext, weeks: list[int]) -> list[WeekScore]:
        league_id = str(ctx.league["league_id"])
        last = max(ctx.completed_weeks, default=0)

        def fetch(week: int) -> list[WeekScore]:
            # The most recent week can still get stat corrections, so keep it short-lived.
            final = ctx.is_complete or week < last
            rows = self.sleeper.get_matchups(league_id, week, final=final)
            return [
                WeekScore(
                    week=week,
                    roster_id=int(r["roster_id"]),
                    matchup_id=r.get("matchup_id"),
                    points=float(r.get("points") or 0.0),
                )
                for r in rows
                if r.get("roster_id") is not None
            ]

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(fetch, weeks))
        scores: list[WeekScore] = []
        for week_rows in results:
            # Skip weeks nobody scored in (e.g. league started late, or bye weeks).
            if week_rows and any(r.points for r in week_rows):
                scores.extend(week_rows)
        return scores

    def dashboard(self, league_id: str) -> DashboardOut:
        ctx = self.context(league_id)
        scores = self.week_scores(ctx, ctx.completed_weeks)
        played = sorted({s.week for s in scores})
        records = compute_records(scores, [t.roster_id for t in ctx.teams], ctx.median_game)
        teams = ctx.team_by_roster
        return DashboardOut(
            league=self.league_out(ctx, played),
            weeks=played,
            standings=[
                StandingRowOut(
                    roster_id=r.roster_id,
                    team_name=teams[r.roster_id].team_name,
                    display_name=teams[r.roster_id].display_name,
                    avatar_url=teams[r.roster_id].avatar_url,
                    standing_rank=r.standing_rank,
                    power_rank=r.power_rank,
                    wins=r.wins,
                    losses=r.losses,
                    ties=r.ties,
                    points_for=round(r.points_for, 2),
                    points_against=round(r.points_against, 2),
                    points_per_game=round(r.points_per_game, 2),
                    allplay_wins=r.allplay_wins,
                    allplay_losses=r.allplay_losses,
                    allplay_ties=r.allplay_ties,
                    allplay_pct=round(r.allplay_pct, 4),
                    expected_wins=round(r.expected_wins, 2),
                    luck=round(r.luck, 2),
                    power_score=round(r.power_score, 4),
                    weekly_points={w: round(p, 2) for w, p in r.weekly_points.items()},
                )
                for r in records
            ],
        )


def _clean_id(value: Any) -> str | None:
    if value in (None, "", "0", 0):
        return None
    return str(value)


def build_teams(rosters: list[dict[str, Any]], users: list[dict[str, Any]]) -> list[TeamOut]:
    by_user = {str(u.get("user_id")): u for u in users}
    teams: list[TeamOut] = []
    for r in sorted(rosters, key=lambda r: int(r.get("roster_id") or 0)):
        rid = int(r["roster_id"])
        owner = r.get("owner_id")
        user = by_user.get(str(owner)) if owner else None
        display = (user or {}).get("display_name") or f"Team {rid}"
        metadata = (user or {}).get("metadata") or {}
        team_name = metadata.get("team_name") if isinstance(metadata, dict) else None
        teams.append(
            TeamOut(
                roster_id=rid,
                owner_id=str(owner) if owner else None,
                display_name=display,
                team_name=team_name or display,
                avatar_url=avatar_url((user or {}).get("avatar")),
            )
        )
    return teams


def completed_weeks(league: dict[str, Any], state: dict[str, Any]) -> tuple[bool, list[int], int]:
    """Return (league is complete, completed regular-season weeks, current NFL week)."""
    settings = league.get("settings") or {}
    start = int(settings.get("start_week") or 1)
    playoff_start = int(settings.get("playoff_week_start") or 0) or 18
    reg_end = playoff_start - 1
    status = league.get("status")
    league_season = int(league.get("season") or 0)
    state_season = int(state.get("season") or 0)
    week = int(state.get("week") or 0)

    if status in ("pre_draft", "drafting"):
        return False, [], week
    if status == "complete" or league_season < state_season:
        return True, list(range(start, reg_end + 1)), reg_end + 1
    if state.get("season_type") == "post":
        return False, list(range(start, reg_end + 1)), week
    last = min(reg_end, week - 1)
    return False, list(range(start, last + 1)), week
