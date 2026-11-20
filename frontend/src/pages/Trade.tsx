import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type PlayerValue, type Roster, type TeamImpact, type TradeResult } from '../api'
import { PosBadge } from '../components/PlayerBits'
import { ErrorState, Loading } from '../components/Status'
import { signed, trendClass, trendText } from '../format'
import { useApi } from '../useApi'

export default function Trade() {
  const { leagueId = '' } = useParams()
  const { data, error, loading } = useApi(() => api.rosters(leagueId), [leagueId])
  const [teamA, setTeamA] = useState<number | null>(null)
  const [teamB, setTeamB] = useState<number | null>(null)
  const [aGives, setAGives] = useState<string[]>([])
  const [bGives, setBGives] = useState<string[]>([])
  const [result, setResult] = useState<TradeResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [tradeError, setTradeError] = useState<string | null>(null)

  if (error) return <ErrorState error={error} />
  if (loading || !data) return <Loading />

  const rosterA = data.rosters.find((r) => r.roster_id === (teamA ?? data.rosters[0]?.roster_id))
  const rosterB = data.rosters.find(
    (r) => r.roster_id === (teamB ?? data.rosters.find((x) => x.roster_id !== rosterA?.roster_id)?.roster_id),
  )
  if (!rosterA || !rosterB) return <p className="state">This league needs at least two teams.</p>

  function toggle(list: string[], set: (v: string[]) => void, id: string) {
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id])
    setResult(null)
  }

  async function analyze() {
    if (!rosterA || !rosterB) return
    setBusy(true)
    setTradeError(null)
    try {
      setResult(
        await api.analyzeTrade(leagueId, {
          team_a: rosterA.roster_id,
          team_b: rosterB.roster_id,
          a_gives: aGives,
          b_gives: bGives,
        }),
      )
    } catch (e) {
      setTradeError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <p className="sub">
        Pick players from each side. Values are rest-of-season projections for the {data.weeks_remaining}{' '}
        remaining weeks, based on stats through week {data.stats_through_week ?? '–'}.
      </p>
      <div className="trade-grid">
        <Side
          label="Team A gives"
          rosters={data.rosters}
          roster={rosterA}
          exclude={rosterB.roster_id}
          selected={aGives}
          onTeam={(id) => {
            setTeamA(id)
            setAGives([])
            setResult(null)
          }}
          onToggle={(id) => toggle(aGives, setAGives, id)}
        />
        <Side
          label="Team B gives"
          rosters={data.rosters}
          roster={rosterB}
          exclude={rosterA.roster_id}
          selected={bGives}
          onTeam={(id) => {
            setTeamB(id)
            setBGives([])
            setResult(null)
          }}
          onToggle={(id) => toggle(bGives, setBGives, id)}
        />
      </div>
      <div className="trade-actions">
        <button className="primary" onClick={analyze} disabled={busy || (!aGives.length && !bGives.length)}>
          {busy ? 'Analyzing…' : 'Analyze trade'}
        </button>
        {(aGives.length > 0 || bGives.length > 0) && (
          <button
            onClick={() => {
              setAGives([])
              setBGives([])
              setResult(null)
            }}
          >
            Clear
          </button>
        )}
      </div>
      {tradeError && (
        <p className="error" role="alert">
          {tradeError}
        </p>
      )}
      {result && <TradeReport result={result} />}
    </div>
  )
}

function Side(props: {
  label: string
  rosters: Roster[]
  roster: Roster
  exclude: number
  selected: string[]
  onTeam: (id: number) => void
  onToggle: (id: string) => void
}) {
  const { label, rosters, roster, exclude, selected, onTeam, onToggle } = props
  const [query, setQuery] = useState('')
  const byId = useMemo(() => new Map(roster.players.map((p) => [p.player_id, p])), [roster])
  const shown = roster.players.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()))

  return (
    <section className="card">
      <div className="card-head">
        <h2>{label}</h2>
        <select
          aria-label={`${label} team`}
          value={roster.roster_id}
          onChange={(e) => onTeam(Number(e.target.value))}
        >
          {rosters
            .filter((r) => r.roster_id !== exclude)
            .map((r) => (
              <option key={r.roster_id} value={r.roster_id}>
                {r.team_name}
              </option>
            ))}
        </select>
      </div>
      <div className="chips" aria-live="polite">
        {selected.length === 0 && <span className="muted">No players selected</span>}
        {selected.map((id) => (
          <span className="chip" key={id}>
            {byId.get(id)?.name ?? id}
            <button aria-label={`Remove ${byId.get(id)?.name ?? id}`} onClick={() => onToggle(id)}>
              ×
            </button>
          </span>
        ))}
      </div>
      <input
        className="search-input"
        placeholder="Filter players"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label={`Filter ${roster.team_name} players`}
      />
      <div className="picker">
        {shown.map((p) => (
          <label key={p.player_id} className={selected.includes(p.player_id) ? 'selected' : ''}>
            <input
              type="checkbox"
              checked={selected.includes(p.player_id)}
              onChange={() => onToggle(p.player_id)}
            />
            <span>
              <PosBadge position={p.position} />
              {p.name}
              <br />
              <span className="meta">
                {p.team ?? 'FA'}
                {p.injury_status ? ` · ${p.injury_status}` : ''} · <span className={trendClass(p)}>{trendText(p)}</span>
              </span>
            </span>
            <span className="val">
              {p.projected_ppg.toFixed(1)} <span className="muted">PPG</span>
              <br />
              <span className="muted">{p.ros_value.toFixed(0)} VORP</span>
            </span>
          </label>
        ))}
      </div>
    </section>
  )
}

function TradeReport({ result }: { result: TradeResult }) {
  const players = [...result.team_a.gives, ...result.team_b.gives]
  return (
    <div className="stack" aria-live="polite">
      <div className={`verdict ${result.verdict}`}>
        <h2>{result.headline}</h2>
        <p className="sub" style={{ margin: '6px 0 0' }}>
          Measured by how each team's best possible starting lineup changes over the remaining{' '}
          {result.weeks_remaining} weeks, plus a small credit for bench depth.
        </p>
      </div>
      <div className="trade-grid">
        <ImpactCard impact={result.team_a} />
        <ImpactCard impact={result.team_b} />
      </div>
      <section className="card">
        <h2>Why</h2>
        <ul className="reasons">
          {result.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </section>
      <section className="card">
        <details open>
          <summary>Show the math for each player</summary>
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table>
              <thead>
                <tr>
                  <th>Player</th>
                  <th className="num" title="Games used (up to 6 most recent)">
                    G
                  </th>
                  <th className="num" title="Recency-weighted points per game">
                    Recent
                  </th>
                  <th className="num" title="Shrunk toward replacement level for small samples">
                    Adj.
                  </th>
                  <th className="num" title="Usage last 3 games vs the 3 before">
                    Usage
                  </th>
                  <th className="num">Proj.</th>
                  <th className="num" title="Replacement-level PPG at this position in your league">
                    Repl.
                  </th>
                  <th className="num" title="Value over replacement per game">
                    VORP/G
                  </th>
                  <th className="num" title="Games left before your league's final week">
                    Left
                  </th>
                  <th className="num" title="Injury discount">
                    Avail.
                  </th>
                  <th className="num">ROS value</th>
                </tr>
              </thead>
              <tbody>
                {players.map((p) => (
                  <PlayerMathRow key={p.player_id} p={p} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">
            ROS value = max(0, Proj − Repl) × games left × availability. See the README for every
            assumption.
          </p>
        </details>
      </section>
    </div>
  )
}

function PlayerMathRow({ p }: { p: PlayerValue }) {
  return (
    <tr>
      <td>
        <PosBadge position={p.position} />
        {p.name}
      </td>
      <td className="num">{p.games_played}</td>
      <td className="num">{p.recent_ppg.toFixed(1)}</td>
      <td className="num">{p.adjusted_ppg.toFixed(1)}</td>
      <td className={`num ${trendClass(p)}`}>{trendText(p)}</td>
      <td className="num">{p.projected_ppg.toFixed(1)}</td>
      <td className="num">{p.replacement_ppg.toFixed(1)}</td>
      <td className="num">{p.vorp_ppg.toFixed(1)}</td>
      <td className="num">{p.games_remaining}</td>
      <td className="num">{Math.round(p.availability * 100)}%</td>
      <td className="num">
        <strong>{p.ros_value.toFixed(1)}</strong>
      </td>
    </tr>
  )
}

function ImpactCard({ impact }: { impact: TeamImpact }) {
  const rows = impact.lineup_before.map((before, i) => ({ before, after: impact.lineup_after[i] }))
  return (
    <section className="card">
      <div className="card-head">
        <h2>{impact.team_name}</h2>
        <span className={`gain ${impact.gain > 0.05 ? 'pos' : impact.gain < -0.05 ? 'neg' : ''}`}>
          {signed(impact.gain)}
        </span>
      </div>
      <p className="sub">
        Receives {impact.receives.map((p) => p.name).join(', ') || 'nothing'} · gives{' '}
        {impact.gives.map((p) => p.name).join(', ') || 'nothing'}
      </p>
      <p className="muted">
        Starting lineup {impact.starters_before.toFixed(0)} → {impact.starters_after.toFixed(0)} projected
        points · bench VORP {impact.bench_before.toFixed(0)} → {impact.bench_after.toFixed(0)}
      </p>
      <div className="table-wrap">
        <table className="lineup">
          <thead>
            <tr>
              <th>Slot</th>
              <th>Before</th>
              <th>After</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ before, after }, i) => (
              <tr key={i}>
                <td className="muted">{before.slot}</td>
                <td>{before.name ?? '—'}</td>
                <td className={after?.player_id !== before.player_id ? 'changed' : ''}>{after?.name ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
