import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api.js'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
// a double click on Run must not land on Stop, which takes its place
const STOP_ARMS_AFTER_MS = 500

// The runs this editor follows, by flow name, so a run never shows on another flow. A lost request is asked again; only
// the server's own answer ends the following. After a reload the runs still in progress are picked up again.
export function useRuns(onSettled) {
  const [runs, setRuns] = useState({})
  const [offline, setOffline] = useState(false)
  const followed = useRef(new Set())
  const settled = useRef(onSettled)
  settled.current = onSettled

  const patch = useCallback((name, change) => {
    setRuns((all) => (all[name] ? { ...all, [name]: { ...all[name], ...change } } : all))
  }, [])

  const follow = useCallback(async (name, runId) => {
    if (followed.current.has(runId)) return
    followed.current.add(runId)
    setRuns((all) => ({ ...all, [name]: { runId, status: 'running', nodes: {}, log: [], armed: false } }))
    setTimeout(() => patch(name, { armed: true }), STOP_ARMS_AFTER_MS)
    for (;;) {
      try {
        const view = await api(`/api/runs/${runId}`)
        setOffline(false)
        patch(name, view)
        if (view.status !== 'running') break
        await sleep(250)
      } catch (e) {
        if (e.status) { // the server answered: it does not know this run any more
          patch(name, { status: 'error', error: e.message })
          break
        }
        setOffline(true)
        await sleep(1000)
      }
    }
    settled.current()
  }, [patch])

  const attach = useCallback(async () => {
    const going = await api('/api/runs').catch(() => [])
    for (const run of going) if (!run.flow_id.includes('#test:')) follow(run.flow_id, run.run_id)
  }, [follow])

  useEffect(() => { attach() }, [attach])

  const forget = useCallback((name) => {
    setRuns((all) => {
      if (!all[name] || all[name].status === 'running') return all
      const { [name]: _gone, ...rest } = all
      return rest
    })
  }, [])

  return { runs, offline, follow, attach, forget, patch }
}
