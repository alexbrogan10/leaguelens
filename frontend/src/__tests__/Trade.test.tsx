import { fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PlayerValue, Rosters, TradeResult } from '../api'
import Trade from '../pages/Trade'
import { mockApi, renderAt } from './testUtils'

function pv(id: string, name: string, position: string): PlayerValue {
  return {
    player_id: id, name, position, team: 'AAA', injury_status: null, games_played: 6,
    recent_ppg: 15, adjusted_ppg: 14, usage_recent: 0.3, usage_prior: 0.25, trend_ratio: 1.2,
    projected_ppg: 15.4, replacement_ppg: 10, vorp_ppg: 5.4, games_remaining: 6,
    availability: 1, ros_points: 92, ros_value: 32.4,
  }
}

const rosters: Rosters = {
  season: '2026', weeks_remaining: 6, stats_through_week: 10,
  rosters: [
    { roster_id: 1, team_name: 'Alpha', display_name: 'A', avatar_url: null, players: [pv('1', 'Ann Runner', 'RB')] },
    { roster_id: 2, team_name: 'Beta', display_name: 'B', avatar_url: null, players: [pv('2', 'Bo Catcher', 'WR')] },
  ],
}

const impact = (rid: number, name: string, gain: number) => ({
  roster_id: rid, team_name: name, receives: [], gives: [], lineup_before: [], lineup_after: [],
  starters_before: 500, starters_after: 500 + gain, bench_before: 0, bench_after: 0, gain,
  raw_value_in: 0, raw_value_out: 0,
})

const result: TradeResult = {
  verdict: 'team_b', headline: 'Beta wins this trade by 12.0 projected points.', margin: -12,
  team_a: impact(1, 'Alpha', -4), team_b: impact(2, 'Beta', 8),
  reasons: ['Ann Runner would start for Beta.'], weeks_remaining: 6,
}

afterEach(() => vi.unstubAllGlobals())

describe('Trade analyzer', () => {
  it('sends the selected players and shows the verdict and reasons', async () => {
    const fetchMock = mockApi({ '/rosters': rosters, '/trade/analyze': result })
    renderAt('/league/L1/trade', '/league/:leagueId/trade', <Trade />)
    const analyze = await screen.findByRole('button', { name: 'Analyze trade' })
    expect(analyze).toBeDisabled()
    fireEvent.click(screen.getByLabelText(/Ann Runner/))
    fireEvent.click(analyze)
    expect(await screen.findByText(result.headline)).toBeInTheDocument()
    expect(screen.getByText('Ann Runner would start for Beta.')).toBeInTheDocument()
    expect(screen.getByText('+8.0')).toHaveClass('pos')
    const [, init] = fetchMock.mock.calls.at(-1)!
    expect(JSON.parse(String(init?.body))).toEqual({
      team_a: 1, team_b: 2, a_gives: ['1'], b_gives: [],
    })
  })
})
