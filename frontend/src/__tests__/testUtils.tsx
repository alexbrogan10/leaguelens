import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

/** Stub fetch so each path prefix returns a canned JSON body. */
export function mockApi(routes: Record<string, unknown>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const url = String(input)
    const key = Object.keys(routes).find((k) => url.includes(k))
    if (!key) return new Response(JSON.stringify({ detail: 'not found' }), { status: 404 })
    return new Response(JSON.stringify(routes[key]), { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function renderAt(path: string, routePath: string, element: ReactElement) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={routePath} element={element} />
      </Routes>
    </MemoryRouter>,
  )
}
