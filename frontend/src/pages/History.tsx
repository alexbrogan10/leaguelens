import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type HeadToHead, type History as HistoryData } from '../api'
import Avatar from '../components/Avatar'
import { ErrorState, Loading } from '../components/Status'
import { pct, record } from '../format'
import { useApi } from '../useApi'

export default function History() {
  const { leagueId = '' } = useParams()
  const { data, error, loading } = useApi(() => api.history(leagueId), [leagueId])
  const [season, setSeason] = useState<string | null>(null)

  if (error) return <ErrorState error={error} />
  if (loading || !data) return <Loading label="Loading league history" />

  const shown = data.seasons.find((s) => s.season === season) ?? data.seasons[0]

  return (
    <div className="stack">
      <section className="card">
        <div className="card-head">
          <h2>Champions</h2>
          <span className="muted">
            {data.seasons.length} season{data.seasons.length === 1 ? '' : 's'} on record
          </span>
        </div>
        <div className="champions">
          {data.seasons.map((s) => (
            <div key={s.season} className="champion">
              <div className="label">{s.season}</div>
              {s.champion ? (
                <>
                  <div className="value">🏆 {s.champion.team_name}</div>
                  <div className="detail">
                    {s.champion.display_name}
                    {s.runner_up ? ` · beat ${s.runner_up.team_name}` : ''}
                  </div>
                </>
              ) : (
                <div className="detail">{s.status === 'complete' ? 'No bracket data' : 'In progress'}</div>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>All-time managers</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Manager</th>
                <th className="num">Titles</th>
                <th className="num">Record</th>
                <th className="num">Win %</th>
                <th className="num hide-sm">Seasons</th>
                <th className="num">Points for</th>
                <th className="num hide-sm" title="Best regular-season finish in a completed season">
                  Best finish
                </th>
              </tr>
            </thead>
            <tbody>
              {data.managers.map((m) => {
                const games = m.wins + m.losses + m.ties
                return (
                  <tr key={m.owner_id}>
                    <td>
                      <div className="team-cell">
                        <Avatar src={m.avatar_url} name={m.display_name} />
                        <span className="name">{m.display_name}</span>
                      </div>
                    </td>
                    <td className="num">{m.championships ? '🏆'.repeat(m.championships) : '–'}</td>
                    <td className="num">{record(m.wins, m.losses, m.ties)}</td>
                    <td className="num">{games ? pct((m.wins + m.ties / 2) / games) : '–'}</td>
                    <td className="num hide-sm">{m.seasons}</td>
                    <td className="num">{m.points_for.toFixed(1)}</td>
                    <td className="num hide-sm">{m.best_finish ?? '–'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      <HeadToHeadGrid data={data} />

      <section className="card">
        <div className="card-head">
          <h2>Season standings</h2>
          <select aria-label="Season" value={shown.season} onChange={(e) => setSeason(e.target.value)}>
            {data.seasons.map((s) => (
              <option key={s.season}>{s.season}</option>
            ))}
          </select>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Team</th>
                <th className="num">Record</th>
                <th className="num">Points for</th>
              </tr>
            </thead>
            <tbody>
              {shown.standings.map((r) => (
                <tr key={r.owner_id}>
                  <td className="num">{r.rank}</td>
                  <td>
                    <span className="name">{r.team_name}</span>{' '}
                    {shown.champion?.owner_id === r.owner_id && <span title="Champion">🏆</span>}
                    <div className="muted">{r.display_name}</div>
                  </td>
                  <td className="num">{record(r.wins, r.losses, r.ties)}</td>
                  <td className="num">{r.points_for.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

/** Diverging fill: blue when the row manager leads the series, red when trailing. */
function cellColor(h: HeadToHead): string {
  const games = h.wins + h.losses + h.ties
  if (!games) return 'transparent'
  const share = (h.wins + h.ties / 2) / games - 0.5 // -0.5..0.5
  const strength = Math.round(Math.abs(share) * 2 * 45)
  if (strength === 0) return 'var(--surface-2)'
  const hue = share > 0 ? 'var(--pos)' : 'var(--neg)'
  return `color-mix(in srgb, ${hue} ${strength}%, transparent)`
}

function HeadToHeadGrid({ data }: { data: HistoryData }) {
  const lookup = new Map(data.head_to_head.map((h) => [`${h.owner_a}|${h.owner_b}`, h]))
  const managers = data.managers
  return (
    <section className="card">
      <div className="card-head">
        <h2>Head-to-head</h2>
        <span className="muted">Row manager's regular-season record vs column manager</span>
      </div>
      <div className="table-wrap">
        <table className="h2h">
          <thead>
            <tr>
              <th />
              {managers.map((m) => (
                <th key={m.owner_id} className="num" title={m.display_name}>
                  {m.display_name.slice(0, 8)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {managers.map((row) => (
              <tr key={row.owner_id}>
                <th scope="row">{row.display_name}</th>
                {managers.map((col) => {
                  if (col.owner_id === row.owner_id) return <td key={col.owner_id} className="self" />
                  const h = lookup.get(`${row.owner_id}|${col.owner_id}`)
                  return (
                    <td
                      key={col.owner_id}
                      className="num"
                      style={{ background: h ? cellColor(h) : undefined }}
                      title={
                        h
                          ? `${row.display_name} vs ${col.display_name}: ${record(h.wins, h.losses, h.ties)}, ${h.points_for.toFixed(1)}–${h.points_against.toFixed(1)} points`
                          : 'Never played'
                      }
                    >
                      {h ? record(h.wins, h.losses, h.ties) : '·'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted" style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <span>
          <span className="swatch" style={{ background: 'color-mix(in srgb, var(--pos) 45%, transparent)' }} /> Leads
          the series
        </span>
        <span>
          <span className="swatch" style={{ background: 'color-mix(in srgb, var(--neg) 45%, transparent)' }} />{' '}
          Trails the series
        </span>
        <span>
          <span className="swatch" style={{ background: 'var(--surface-2)' }} /> Even
        </span>
      </p>
    </section>
  )
}
