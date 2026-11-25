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

export async function api(path, { method = 'GET', body } = {}) {
  const response = await fetch(path, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(data?.error ?? `HTTP ${response.status}`)
  return data
}
