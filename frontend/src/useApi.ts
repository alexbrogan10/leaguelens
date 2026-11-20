/* oxlint-disable react-hooks/exhaustive-deps -- callers pass their own dependency list */
import { useEffect, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  error: Error | null
  loading: boolean
}

/** Runs `load` whenever `deps` change; ignores results from stale calls. */
export function useApi<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: true })
  useEffect(() => {
    let active = true
    setState((s) => ({ ...s, loading: true, error: null }))
    load().then(
      (data) => active && setState({ data, error: null, loading: false }),
      (error: Error) => active && setState({ data: null, error, loading: false }),
    )
    return () => {
      active = false
    }
  }, deps)
  return state
}
