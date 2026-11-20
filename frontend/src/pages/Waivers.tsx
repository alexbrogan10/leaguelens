import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api'
import { PosBadge } from '../components/PlayerBits'
import Sparkline from '../components/Sparkline'
import { ErrorState, Loading } from '../components/Status'
import { useApi } from '../useApi'

const POSITIONS = ['', 'RB', 'WR', 'TE', 'QB']

export default function Waivers() {
  const { leagueId = '' } = useParams()
  const [position, setPosition] = useState('')
  const { data, error, loading } = useApi(() => api.waivers(leagueId, position || undefined), [leagueId, position])

  return (
    <div className="stack">
      <section className="card">
        <div className="card-head">
          <div>
            <h2>Waiver radar</h2>
            <span className="sub">
              Players nobody in your league rosters, ranked by how fast their role is growing
              {data ? ` (weeks ${data.weeks[0]}–${data.weeks[data.weeks.length - 1]})` : ''}.
            </span>
          </div>
          <div className="segmented" role="group" aria-label="Position">
            {POSITIONS.map((p) => (
              <button key={p || 'all'} className={position === p ? 'active' : ''} aria-pressed={position === p} onClick={() => setPosition(p)}>
                {p || 'All'}
              </button>
            ))}
          </div>
        </div>
        {error ? (
          <ErrorState error={error} />
        ) : loading || !data ? (
          <Loading />
        ) : data.players.length === 0 ? (
          <p className="state">No available players with a rising role right now.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="num">#</th>
                  <th>Player</th>
                  <th title="Usage by week; the blue part is the last 3 weeks">Usage trend</th>
                  <th className="num" title="Change in usage per week over the last 3 weeks">
                    Slope
                  </th>
                  <th className="num hide-sm">Snaps</th>
                  <th className="num" title="Fantasy points per game in your scoring, last 3 weeks">
                    PPG
                  </th>
                  <th className="num" title="0.6 × z(slope) + 0.4 × z(latest usage), within position">
                    Score
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.players.map((p, i) => {
                  const last = p.history[p.history.length - 1]
                  return (
                    <tr key={p.player_id}>
                      <td className="num">{i + 1}</td>
                      <td>
                        <PosBadge position={p.position} />
                        <strong>{p.name}</strong>
                        <div className="muted">
                          {p.team}
                          {p.age ? ` · age ${p.age}` : ''}
                          {p.injury_status ? ` · ${p.injury_status}` : ''}
                        </div>
                      </td>
                      <td>
                        <Sparkline points={p.history} label={`${p.name} ${p.usage_label} by week`} />
                        <div className="muted">{p.usage_label}</div>
                      </td>
                      <td className={`num ${p.usage_slope > 0 ? 'pos' : 'neg'}`}>
                        {p.usage_slope > 0 ? '+' : ''}
                        {p.usage_slope.toFixed(p.position === 'QB' ? 1 : 3)}
                      </td>
                      <td className="num hide-sm">{last?.snap_pct != null ? `${Math.round(last.snap_pct * 100)}%` : '–'}</td>
                      <td className="num">{p.recent_ppg.toFixed(1)}</td>
                      <td className="num">
                        <strong>{p.score.toFixed(2)}</strong>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <p className="muted">
        Usage: WR/TE = weighted opportunity rating (1.5 × target share + 0.7 × air-yards share); RB = share of
        team carries + 2 × target share; QB = pass attempts + 2 × carries. Weeks without a stat line count as
        zero; bye weeks are skipped.
      </p>
    </div>
  )
}
