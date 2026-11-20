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


class PlayerValueOut(BaseModel):
    player_id: str
    name: str
    position: str
    team: str | None
    injury_status: str | None
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


class RosterOut(BaseModel):
    roster_id: int
    team_name: str
    display_name: str
    avatar_url: str | None
    players: list[PlayerValueOut]


class RostersOut(BaseModel):
    season: str
    weeks_remaining: int
    stats_through_week: int | None
    rosters: list[RosterOut]


class TradeRequest(BaseModel):
    team_a: int
    team_b: int
    a_gives: list[str]
    b_gives: list[str]


class LineupSlotOut(BaseModel):
    slot: str
    player_id: str | None
    name: str | None
    projected_ppg: float | None


class TeamImpactOut(BaseModel):
    roster_id: int
    team_name: str
    receives: list[PlayerValueOut]
    gives: list[PlayerValueOut]
    lineup_before: list[LineupSlotOut]
    lineup_after: list[LineupSlotOut]
    starters_before: float
    starters_after: float
    bench_before: float
    bench_after: float
    gain: float
    raw_value_in: float
    raw_value_out: float


class TradeOut(BaseModel):
    verdict: str
    headline: str
    margin: float
    team_a: TeamImpactOut
    team_b: TeamImpactOut
    reasons: list[str]
    weeks_remaining: int
