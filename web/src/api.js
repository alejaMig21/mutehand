import { setAppNames } from './catalog.js'

// The server prints a URL like http://127.0.0.1:PORT/#token=XXXX. The token lives in the fragment, so
// it is never sent to the server in a request line or logged; it is kept for this tab only.
function readToken() {
  const fromHash = new URLSearchParams(location.hash.slice(1)).get('token')
  if (fromHash) {
    sessionStorage.setItem('wf-token', fromHash)
    history.replaceState(null, '', location.pathname)
  }
  return sessionStorage.getItem('wf-token')
}

const token = readToken()
// a new link pasted in the same tab only changes the fragment: load again so it is read
window.addEventListener('hashchange', () => { if (location.hash.includes('token=')) location.reload() })

export const LOCKED = 'wf-locked' // the event for "this token is no longer accepted"
export const UNREACHABLE = 'Cannot reach Workflow Factory. Is it still running?'

// An error with a `status` is the server's answer; one without it means no answer arrived.
export async function api(path, { method = 'GET', body } = {}) {
  let response
  try {
    response = await fetch(path, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new Error(UNREACHABLE)
  }
  const data = await response.json().catch(() => null)
  if (response.status === 401) window.dispatchEvent(new Event(LOCKED))
  if (!response.ok) throw Object.assign(new Error(data?.error ?? `HTTP ${response.status}`), { status: response.status })
  return data
}

// A name that cannot be read now leaves the screen with the file names it can work out itself.
export const loadAppNames = () => api('/api/app-names').then(setAppNames).catch(() => {})

export const encode = encodeURIComponent
