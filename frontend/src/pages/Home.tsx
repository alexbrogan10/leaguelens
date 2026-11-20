import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

const FEATURES = [
  ['Power rankings & luck', 'All-play records show how good each team really is, and who the schedule helped.'],
  ['Trade analyzer', 'Rest-of-season value from recent scoring, usage trends and your roster needs, with the reasoning shown.'],
  ['Waiver radar', 'Available players whose usage has climbed over the last three weeks.'],
  ['League history', 'Champions, records and head-to-head results across every past season.'],
]

export default function Home() {
  const [username, setUsername] = useState('')
  const navigate = useNavigate()

  function submit(e: FormEvent) {
    e.preventDefault()
    const name = username.trim()
    if (name) navigate(`/u/${encodeURIComponent(name)}`)
  }

  return (
    <>
      <section className="hero">
        <h1>See your Sleeper league clearly</h1>
        <p>Enter your Sleeper username to get power rankings, trade analysis and waiver tips Sleeper doesn't show you.</p>
        <form className="search" onSubmit={submit}>
          <label htmlFor="username" className="sr-only" hidden>
            Sleeper username
          </label>
          <input
            id="username"
            placeholder="Sleeper username"
            value={username}
            autoComplete="off"
            onChange={(e) => setUsername(e.target.value)}
          />
          <button className="primary" type="submit" disabled={!username.trim()}>
            Find my leagues
          </button>
        </form>
        <p className="muted">
          No account handy? <Link to="/league/demo_2026">Try the demo league</Link>.
        </p>
      </section>
      <section className="features">
        {FEATURES.map(([title, body]) => (
          <div className="card" key={title}>
            <h3>{title}</h3>
            <p className="sub">{body}</p>
          </div>
        ))}
      </section>
    </>
  )
}
