import { Link, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Home from './pages/Home'
import Trade from './pages/Trade'
import Waivers from './pages/Waivers'
import LeagueLayout from './pages/LeagueLayout'
import UserLeagues from './pages/UserLeagues'

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
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/u/:username" element={<UserLeagues />} />
          <Route path="/league/:leagueId" element={<LeagueLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="trade" element={<Trade />} />
            <Route path="waivers" element={<Waivers />} />
          </Route>
          <Route path="*" element={<p className="state">Page not found.</p>} />
        </Routes>
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
