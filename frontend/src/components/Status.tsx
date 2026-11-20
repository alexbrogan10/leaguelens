export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div aria-busy="true" aria-label={label}>
      <div className="skeleton" />
    </div>
  )
}

export function ErrorState({ error }: { error: Error }) {
  return (
    <div className="state error" role="alert">
      {error.message}
    </div>
  )
}
