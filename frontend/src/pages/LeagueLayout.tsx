import { NavLink, Outlet, useParams } from 'react-router-dom'
import { api, type League } from '../api'
import { ErrorState, Loading } from '../components/Status'
import { useApi } from '../useApi'

export interface LeagueOutletContext {
  league: League
}

const TABS = [
  ['', 'Dashboard'],
  ['trade', 'Trade analyzer'],
  ['waivers', 'Waiver radar'],
  ['history', 'History'],
]

export default function LeagueLayout() {
  const { leagueId = '' } = useParams()
  const { data, error, loading } = useApi(() => api.league(leagueId), [leagueId])
  if (error) return <ErrorState error={error} />
  if (loading || !data) return <Loading />

  return (
    <>
      <div className="card-head">
        <div>
          <h1>{data.name}</h1>
          <span className="sub">
            {data.season} · {data.total_rosters} teams · {data.scoring_type}
            {data.median_game ? ' · median game' : ''}
          </span>
        </div>
      </div>
      <nav className="tabs" aria-label="League sections">
        {TABS.map(([path, label]) => (
          <NavLink key={path} to={path} end={path === ''}>
            {label}
          </NavLink>
        ))}
      </nav>
      <Outlet context={{ league: data } satisfies LeagueOutletContext} />
    </>
  )
}
