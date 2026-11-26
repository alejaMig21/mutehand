import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api.js'

// Load a list from the API. A response that arrives after the path changed (or after unmount) is ignored,
// so switching a filter quickly can never show the list of the previous one. `loading` and `loadError` keep
// "not here yet" and "could not be read" apart from "there is nothing". With `keep`, a list already shown stays when
// reading it again fails: for a screen that offers things, such as Stop, which must not vanish with one lost request.
export function useLoad(path, { keep = false } = {}) {
  const [state, setState] = useState({ path: null, data: [], loadError: '' })
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  const reload = useCallback(() => setVersion((v) => v + 1), [])

  useEffect(() => {
    let ignore = false
    api(path)
      .then((data) => { if (!ignore) setState({ path, data, loadError: '' }) })
      .catch((e) => {
        if (!ignore) setState((last) => (keep && last.path === path && !last.loadError ? last : { path, data: [], loadError: e.message }))
      })
    return () => { ignore = true }
  }, [path, version, keep])

  const loading = state.path !== path
  return { data: loading ? [] : state.data, loading, loadError: loading ? '' : state.loadError, error, reload, setError }
}

// Run a change on the server, then reload the list. One change at a time, so a double click sends one request;
// `said` tells the person what happened.
export function useAction(reload, setError) {
  const lock = useRef(false)
  const [busy, setBusy] = useState(false)
  const [said, setSaid] = useState('')
  const act = useCallback(async (request, done) => {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    setSaid('')
    setError('')
    try {
      await request()
      setSaid(done)
      reload()
    } catch (e) {
      setError(e.message)
    } finally {
      lock.current = false
      setBusy(false)
    }
  }, [reload, setError])
  return { act, busy, said }
}
