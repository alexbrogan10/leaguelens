// Typed client for the LeagueLens API. Types mirror backend/leaguelens/schemas.py.

export interface User {
  user_id: string
  username: string | null
  display_name: string
  avatar_url: string | null
}

export interface LeagueSummary {
  league_id: string
  name: string
  season: string
  status: string
  total_rosters: number
  avatar_url: string | null
}

export interface UserLeagues {
  user: User
  season: string
  leagues: LeagueSummary[]
}

export interface Team {
  roster_id: number
  owner_id: string | null
  display_name: string
  team_name: string
  avatar_url: string | null
}

export interface League {
  league_id: string
  name: string
  season: string
  status: string
  total_rosters: number
  roster_positions: string[]
  scoring_type: string
  playoff_week_start: number
  median_game: boolean
  previous_league_id: string | null
  completed_weeks: number[]
  teams: Team[]
}

export interface StandingRow {
  roster_id: number
  team_name: string
  display_name: string
  avatar_url: string | null
  standing_rank: number
  power_rank: number
  wins: number
  losses: number
  ties: number
  points_for: number
  points_against: number
  points_per_game: number
  allplay_wins: number
  allplay_losses: number
  allplay_ties: number
  allplay_pct: number
  expected_wins: number
  luck: number
  power_score: number
  weekly_points: Record<string, number>
}

export interface Dashboard {
  league: League
  weeks: number[]
  standings: StandingRow[]
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? ''

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // keep the generic message
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

const enc = encodeURIComponent

export const api = {
  userLeagues: (username: string, season?: string) =>
    request<UserLeagues>(`/users/${enc(username)}/leagues${season ? `?season=${enc(season)}` : ''}`),
  league: (id: string) => request<League>(`/leagues/${enc(id)}`),
  dashboard: (id: string) => request<Dashboard>(`/leagues/${enc(id)}/dashboard`),
}
