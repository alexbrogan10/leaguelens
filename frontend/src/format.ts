export function record(w: number, l: number, t: number): string {
  return t ? `${w}-${l}-${t}` : `${w}-${l}`
}

export function signed(n: number, digits = 1): string {
  const s = n.toFixed(digits)
  return n > 0 ? `+${s}` : s
}

export function pct(n: number, digits = 0): string {
  return `${(n * 100).toFixed(digits)}%`
}

export function luckLabel(luck: number): string {
  if (luck >= 1.5) return 'Very lucky'
  if (luck >= 0.5) return 'Lucky'
  if (luck <= -1.5) return 'Very unlucky'
  if (luck <= -0.5) return 'Unlucky'
  return 'Neutral'
}
