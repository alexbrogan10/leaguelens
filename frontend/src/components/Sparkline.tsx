import type { UsageWeek } from '../api'

/** Tiny usage trend line. The last 3 points (the radar window) are emphasised. */
export default function Sparkline({ points, label }: { points: UsageWeek[]; label: string }) {
  const w = 120
  const h = 32
  const pad = 4
  if (points.length === 0) return null
  const max = Math.max(...points.map((p) => p.usage), 0.0001)
  const x = (i: number) => pad + (i * (w - 2 * pad)) / Math.max(points.length - 1, 1)
  const y = (v: number) => h - pad - (v / max) * (h - 2 * pad)
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.usage).toFixed(1)}`).join(' ')
  const start = Math.max(points.length - 3, 0)
  const recent = points
    .slice(start)
    .map((p, i) => `${i ? 'L' : 'M'}${x(start + i).toFixed(1)},${y(p.usage).toFixed(1)}`)
    .join(' ')
  return (
    <svg width={w} height={h} role="img" aria-label={label} className="sparkline">
      <path d={path} fill="none" stroke="var(--axis)" strokeWidth={2} strokeLinejoin="round" />
      <path d={recent} fill="none" stroke="var(--accent)" strokeWidth={2} strokeLinejoin="round" />
      {points.map((p, i) => (
        <circle key={p.week} cx={x(i)} cy={y(p.usage)} r={i >= start ? 3 : 2} fill={i >= start ? 'var(--accent)' : 'var(--axis)'}>
          <title>
            Week {p.week}: usage {p.usage.toFixed(2)}
            {p.snap_pct != null ? `, ${Math.round(p.snap_pct * 100)}% snaps` : ''}, {p.points.toFixed(1)} pts
          </title>
        </circle>
      ))}
    </svg>
  )
}
