import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'

// Load a list from the API. A response that arrives after the path changed (or after unmount) is ignored,
// so switching a filter quickly can never show the list of the previous one.
export function useLoad(path) {
  const [data, setData] = useState([])
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  const reload = useCallback(() => setVersion((v) => v + 1), [])

  useEffect(() => {
    let ignore = false
    setError('')
    api(path)
      .then((value) => { if (!ignore) setData(value) })
      .catch((e) => { if (!ignore) setError(e.message) })
    return () => { ignore = true }
  }, [path, version])

  return { data, error, reload, setError }
}

// Run a change on the server, then reload the list; show the message if it fails.
export async function act(request, reload, setError) {
  try {
    await request()
    reload()
  } catch (e) {
    setError(e.message)
  }
}
