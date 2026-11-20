function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join('')
}

export default function Avatar({ src, name = '', size }: { src: string | null; name?: string; size?: 'lg' }) {
  const cls = size === 'lg' ? 'avatar lg' : 'avatar'
  if (src) return <img className={cls} src={src} alt="" loading="lazy" />
  return (
    <span className={`${cls} initials`} aria-hidden="true">
      {initials(name)}
    </span>
  )
}
