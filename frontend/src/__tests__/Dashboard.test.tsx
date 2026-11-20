import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Dashboard as DashboardData, StandingRow } from '../api'
import Dashboard from '../pages/Dashboard'
import { mockApi, renderAt } from './testUtils'

function row(id: number, name: string, extra: Partial<StandingRow>): StandingRow {
  return {
    roster_id: id, team_name: name, display_name: name, avatar_url: null,
    standing_rank: id, power_rank: id, wins: 1, losses: 1, ties: 0,
    points_for: 200, points_against: 200, points_per_game: 100,
    allplay_wins: 3, allplay_losses: 3, allplay_ties: 0, allplay_pct: 0.5,
    expected_wins: 1, luck: 0, power_score: 0.7, weekly_points: { 1: 100, 2: 100 },
    ...extra,
  }
}

const data: DashboardData = {
  league: {
    league_id: 'L1', name: 'Test', season: '2026', status: 'in_season', total_rosters: 2,
    roster_positions: [], scoring_type: 'PPR', playoff_week_start: 15, median_game: false,
    previous_league_id: null, completed_weeks: [1, 2], teams: [],
  },
  weeks: [1, 2],
  standings: [
    row(1, 'Lucky Ducks', { luck: 1.8, points_for: 250, points_per_game: 125 }),
    row(2, 'Sad Sacks', { luck: -1.8 }),
  ],
}

afterEach(() => vi.unstubAllGlobals())

describe('Dashboard', () => {
  it('shows power rankings and luck call-outs', async () => {
    mockApi({ '/leagues/L1/dashboard': data })
    renderAt('/league/L1', '/league/:leagueId', <Dashboard />)
    expect(await screen.findByText('Power rankings')).toBeInTheDocument()
    expect(screen.getByText('Luckiest').nextSibling).toHaveTextContent('Lucky Ducks')
    expect(screen.getByText('Unluckiest').nextSibling).toHaveTextContent('Sad Sacks')
    expect(screen.getByText('+1.8')).toHaveClass('pos')
  })

  it('shows the API error message', async () => {
    mockApi({})
    renderAt('/league/L9', '/league/:leagueId', <Dashboard />)
    expect(await screen.findByRole('alert')).toHaveTextContent('not found')
  })
})
