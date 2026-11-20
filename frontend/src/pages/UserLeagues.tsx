import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import Avatar from '../components/Avatar'
import { ErrorState, Loading } from '../components/Status'
import { useApi } from '../useApi'

const THIS_YEAR = new Date().getFullYear()
const SEASONS = Array.from({ length: 6 }, (_, i) => String(THIS_YEAR - i))

export default function UserLeagues() {
  const { username = '' } = useParams()
  const [season, setSeason] = useState<string | undefined>(undefined)
  const { data, error, loading } = useApi(() => api.userLeagues(username, season), [username, season])

  if (error) return <ErrorState error={error} />
  if (loading || !data) return <Loading />

  return (
    <div className="card">
      <div className="card-head">
        <div className="league-head">
          <Avatar src={data.user.avatar_url} name={data.user.display_name} size="lg" />
          <div>
            <h1>{data.user.display_name}</h1>
            <span className="sub">Pick a league</span>
          </div>
        </div>
        <label className="sub">
          Season{' '}
          <select value={season ?? data.season} onChange={(e) => setSeason(e.target.value)}>
            {[...new Set([data.season, ...SEASONS])].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
      </div>
      {data.leagues.length === 0 ? (
        <p className="state">No leagues for {data.season}.</p>
      ) : (
        <ul className="list">
          {data.leagues.map((lg) => (
            <li key={lg.league_id}>
              <Link to={`/league/${lg.league_id}`}>
                <Avatar src={lg.avatar_url} name={lg.name} />
                <span style={{ flex: 1 }}>
                  <strong>{lg.name}</strong>
                  <br />
                  <span className="muted">
                    {lg.total_rosters} teams · {lg.season}
                  </span>
                </span>
                <span className="pill">{lg.status.replace('_', ' ')}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
