"""Pydantic response models shared by the services and the API."""

from __future__ import annotations

from pydantic import BaseModel


class UserOut(BaseModel):
    user_id: str
    username: str | None
    display_name: str
    avatar_url: str | None


class LeagueSummaryOut(BaseModel):
    league_id: str
    name: str
    season: str
    status: str
    total_rosters: int
    avatar_url: str | None


class UserLeaguesOut(BaseModel):
    user: UserOut
    season: str
    leagues: list[LeagueSummaryOut]


class StateOut(BaseModel):
    season: str
    week: int
    season_type: str


class TeamOut(BaseModel):
    roster_id: int
    owner_id: str | None
    display_name: str
    team_name: str
    avatar_url: str | None


class LeagueOut(BaseModel):
    league_id: str
    name: str
    season: str
    status: str
    total_rosters: int
    roster_positions: list[str]
    scoring_type: str
    playoff_week_start: int
    median_game: bool
    previous_league_id: str | None
    completed_weeks: list[int]
    teams: list[TeamOut]


class StandingRowOut(BaseModel):
    roster_id: int
    team_name: str
    display_name: str
    avatar_url: str | None
    standing_rank: int
    power_rank: int
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    points_per_game: float
    allplay_wins: int
    allplay_losses: int
    allplay_ties: int
    allplay_pct: float
    expected_wins: float
    luck: float
    power_score: float
    weekly_points: dict[int, float]


class DashboardOut(BaseModel):
    league: LeagueOut
    weeks: list[int]
    standings: list[StandingRowOut]
