import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api, type StandingRow } from '../api'
import Avatar from '../components/Avatar'
import { ErrorState, Loading } from '../components/Status'
import { luckLabel, pct, record, signed } from '../format'
import { useApi } from '../useApi'

type SortKey = 'standing_rank' | 'power_rank' | 'points_for' | 'allplay_pct' | 'luck'

const COLUMNS: { key: SortKey; label: string; title: string }[] = [
  { key: 'power_rank', label: 'Power', title: '60% all-play win rate + 40% points per game vs the best team' },
  { key: 'standing_rank', label: 'Record', title: 'Actual head-to-head record' },
  { key: 'allplay_pct', label: 'All-play', title: 'Record if you played every team every week' },
  { key: 'points_for', label: 'PF', title: 'Points for' },
  { key: 'luck', label: 'Luck', title: 'Actual wins minus expected wins from all-play' },
]

export default function Dashboard() {
  const { leagueId = '' } = useParams()
  const { data, error, loading } = useApi(() => api.dashboard(leagueId), [leagueId])
  const [sort, setSort] = useState<SortKey>('power_rank')
  const [focus, setFocus] = useState<number | null>(null)

  const rows = useMemo(() => {
    if (!data) return []
    const asc = sort === 'standing_rank' || sort === 'power_rank'
    return [...data.standings].sort((a, b) => (asc ? a[sort] - b[sort] : b[sort] - a[sort]))
  }, [data, sort])

  if (error) return <ErrorState error={error} />
  if (loading || !data) return <Loading />
  if (data.weeks.length === 0)
    return <p className="state">No completed weeks yet. Check back after week 1.</p>

  const byPower = [...data.standings].sort((a, b) => a.power_rank - b.power_rank)
  const byLuck = [...data.standings].sort((a, b) => b.luck - a.luck)
  const topScorer = [...data.standings].sort((a, b) => b.points_for - a.points_for)[0]
  const focusTeam = data.standings.find((r) => r.roster_id === focus) ?? byPower[0]

  return (
    <div className="stack">
      <div className="stat-row">
        <Stat label="Power #1" team={byPower[0]} detail={`${pct(byPower[0].allplay_pct)} all-play`} />
        <Stat label="Most points" team={topScorer} detail={`${topScorer.points_per_game.toFixed(1)} per game`} />
        <Stat label="Luckiest" team={byLuck[0]} detail={`${signed(byLuck[0].luck)} wins vs expected`} />
        <Stat
          label="Unluckiest"
          team={byLuck[byLuck.length - 1]}
          detail={`${signed(byLuck[byLuck.length - 1].luck)} wins vs expected`}
        />
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Power rankings</h2>
          <span className="muted">Through week {Math.max(...data.weeks)} · click a column to sort</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Team</th>
                {COLUMNS.map((c) => (
                  <th key={c.key} className="num" title={c.title} aria-sort={sort === c.key ? 'descending' : 'none'}>
                    <button onClick={() => setSort(c.key)}>
                      {c.label}
                      {sort === c.key ? ' ▾' : ''}
                    </button>
                  </th>
                ))}
                <th className="num hide-sm" title="Points against">
                  PA
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.roster_id}>
                  <td className="num">{r.power_rank}</td>
                  <td>
                    <TeamCell row={r} />
                  </td>
                  <td className="num">{(r.power_score * 100).toFixed(1)}</td>
                  <td className="num">
                    {record(r.wins, r.losses, r.ties)} <span className="muted">({r.standing_rank})</span>
                  </td>
                  <td className="num">
                    {record(r.allplay_wins, r.allplay_losses, r.allplay_ties)}{' '}
                    <span className="muted">{pct(r.allplay_pct)}</span>
                  </td>
                  <td className="num">{r.points_for.toFixed(1)}</td>
                  <td className={`num ${r.luck >= 0.5 ? 'pos' : r.luck <= -0.5 ? 'neg' : ''}`}>
                    {signed(r.luck)}
                  </td>
                  <td className="num hide-sm">{r.points_against.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid-2">
        <section className="card">
          <div className="card-head">
            <h2>Luck</h2>
            <span className="muted">Actual wins − expected wins</span>
          </div>
          <LuckChart rows={byLuck} />
        </section>
        <section className="card">
          <div className="card-head">
            <h2>Weekly scoring</h2>
            <select
              aria-label="Team"
              value={focusTeam.roster_id}
              onChange={(e) => setFocus(Number(e.target.value))}
            >
              {byPower.map((r) => (
                <option key={r.roster_id} value={r.roster_id}>
                  {r.team_name}
                </option>
              ))}
            </select>
          </div>
          <WeeklyChart rows={data.standings} weeks={data.weeks} team={focusTeam} />
        </section>
      </div>
    </div>
  )
}

function Stat({ label, team, detail }: { label: string; team: StandingRow; detail: string }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="value">{team.team_name}</div>
      <div className="detail">{detail}</div>
    </div>
  )
}

function TeamCell({ row }: { row: StandingRow }) {
  return (
    <div className="team-cell">
      <Avatar src={row.avatar_url} />
      <div>
        <div className="name">{row.team_name}</div>
        {row.display_name !== row.team_name && <div className="owner">{row.display_name}</div>}
      </div>
    </div>
  )
}

function LuckChart({ rows }: { rows: StandingRow[] }) {
  const data = rows.map((r) => ({ name: r.team_name, luck: r.luck, row: r }))
  return (
    <ResponsiveContainer width="100%" height={Math.max(220, rows.length * 30)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }} barCategoryGap={4}>
        <CartesianGrid horizontal={false} stroke="var(--grid)" />
        <XAxis type="number" stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} />
        <YAxis
          type="category"
          dataKey="name"
          width={120}
          stroke="var(--ink-2)"
          fontSize={12}
          tickLine={false}
          axisLine={false}
        />
        <ReferenceLine x={0} stroke="var(--axis)" />
        <Tooltip
          cursor={{ fill: 'var(--surface-2)' }}
          content={({ active, payload }) => {
            const p = payload?.[0]?.payload as (typeof data)[number] | undefined
            if (!active || !p) return null
            return (
              <div className="chart-tooltip">
                <strong>{p.name}</strong>
                {record(p.row.wins, p.row.losses, p.row.ties)} actual, {p.row.expected_wins.toFixed(1)} expected
                wins
                <br />
                {luckLabel(p.luck)} ({signed(p.luck)})
              </div>
            )
          }}
        />
        <Bar dataKey="luck" radius={4} maxBarSize={18} isAnimationActive={false}>
          {data.map((d) => (
            <Cell key={d.name} fill={d.luck >= 0 ? 'var(--pos)' : 'var(--neg)'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function WeeklyChart({ rows, weeks, team }: { rows: StandingRow[]; weeks: number[]; team: StandingRow }) {
  const data = weeks.map((w) => {
    const scores = rows.map((r) => r.weekly_points[w] ?? 0).sort((a, b) => a - b)
    const mid = scores.length % 2 ? scores[(scores.length - 1) / 2] : (scores[scores.length / 2 - 1] + scores[scores.length / 2]) / 2
    return { week: w, team: team.weekly_points[w] ?? null, median: Math.round(mid * 10) / 10 }
  })
  return (
    <>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ left: -12, right: 16, top: 8 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="week" stroke="var(--muted)" fontSize={12} tickLine={false} tickFormatter={(w) => `W${w}`} />
          <YAxis stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} />
          <Tooltip
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <div className="chart-tooltip">
                  <strong>Week {label}</strong>
                  {team.team_name}: {String(payload.find((p) => p.dataKey === 'team')?.value ?? '–')}
                  <br />
                  League median: {String(payload.find((p) => p.dataKey === 'median')?.value ?? '–')}
                </div>
              ) : null
            }
          />
          <Line dataKey="median" stroke="var(--muted)" strokeDasharray="4 4" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line dataKey="team" stroke="var(--accent)" strokeWidth={2} dot={{ r: 4 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <div className="muted" style={{ display: 'flex', gap: 16 }}>
        <span>
          <span style={{ color: 'var(--accent)' }}>●</span> {team.team_name}
        </span>
        <span>
          <span style={{ color: 'var(--muted)' }}>- -</span> League median
        </span>
      </div>
    </>
  )
}
