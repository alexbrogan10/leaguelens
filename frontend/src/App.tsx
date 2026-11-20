import { lazy, Suspense } from 'react'
import { Link, Route, Routes } from 'react-router-dom'
import { Loading } from './components/Status'
import Home from './pages/Home'
import LeagueLayout from './pages/LeagueLayout'
import UserLeagues from './pages/UserLeagues'

// League tabs are split into their own chunks; Recharts only loads with the dashboard.
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Trade = lazy(() => import('./pages/Trade'))
const Waivers = lazy(() => import('./pages/Waivers'))
const History = lazy(() => import('./pages/History'))

export default function App() {
  return (
    <>
      <header className="site-header">
        <div className="container">
          <Link to="/" className="brand">
            <img src="/favicon.svg" alt="" />
            LeagueLens
          </Link>
          <Link to="/league/demo_2026" className="sub">
            Demo league
          </Link>
        </div>
      </header>
      <main className="container">
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/u/:username" element={<UserLeagues />} />
            <Route path="/league/:leagueId" element={<LeagueLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="trade" element={<Trade />} />
              <Route path="waivers" element={<Waivers />} />
              <Route path="history" element={<History />} />
            </Route>
            <Route path="*" element={<p className="state">Page not found.</p>} />
          </Routes>
        </Suspense>
      </main>
      <footer className="site-footer">
        <div className="container">
          LeagueLens is not affiliated with Sleeper. League data from the Sleeper API; player
          stats from nflverse.
        </div>
      </footer>
    </>
  )
}
