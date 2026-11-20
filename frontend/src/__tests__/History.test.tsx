import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { History as HistoryData } from '../api'
import History from '../pages/History'
import { mockApi, renderAt } from './testUtils'

const ref = (id: string, name: string) => ({ owner_id: id, display_name: name, team_name: `${name} FC` })
const manager = (id: string, name: string, titles: number) => ({
  owner_id: id, display_name: name, avatar_url: null, seasons: 2, wins: 10, losses: 6, ties: 0,
  points_for: 2000, championships: titles, runner_ups: 0, best_finish: 1,
})

const data: HistoryData = {
  seasons: [
    { season: '2026', league_id: 'L1', name: 'L', status: 'in_season', champion: null, runner_up: null, standings: [] },
    {
      season: '2025', league_id: 'L0', name: 'L', status: 'complete',
      champion: ref('a', 'Ann'), runner_up: ref('b', 'Ben'), standings: [],
    },
  ],
  managers: [manager('a', 'Ann', 1), manager('b', 'Ben', 0)],
  head_to_head: [
    { owner_a: 'a', owner_b: 'b', wins: 3, losses: 1, ties: 0, points_for: 400, points_against: 350 },
    { owner_a: 'b', owner_b: 'a', wins: 1, losses: 3, ties: 0, points_for: 350, points_against: 400 },
  ],
}

afterEach(() => vi.unstubAllGlobals())

describe('History', () => {
  it('shows champions and head-to-head records', async () => {
    mockApi({ '/history': data })
    renderAt('/league/L1/history', '/league/:leagueId/history', <History />)
    expect(await screen.findByText(/Ann FC/)).toBeInTheDocument()
    expect(screen.getByText('In progress')).toBeInTheDocument()
    expect(screen.getByTitle(/Ann vs Ben: 3-1/)).toHaveTextContent('3-1')
    expect(screen.getByTitle(/Ben vs Ann: 1-3/)).toHaveTextContent('1-3')
  })
})
