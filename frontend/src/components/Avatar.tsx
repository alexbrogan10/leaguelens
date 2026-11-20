export default function Avatar({ src, size }: { src: string | null; size?: 'lg' }) {
  const cls = size === 'lg' ? 'avatar lg' : 'avatar'
  return src ? <img className={cls} src={src} alt="" loading="lazy" /> : <span className={cls} />
}
