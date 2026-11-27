// The history of one flow in words: pure, so node can test it. The server keeps what each node was (its step, or its kind
// and operation) when the run happened, so the names stay right after the flow is rebuilt. No data value is ever recorded.
import { systemEntryFor } from './catalog.js'
import { effectWords, lastRunWords, reasonWords } from './words.js'

const NODE = { done: ['done', 'ok'], blocked: ['stopped', 'bad'], skipped: ['skipped', 'muted'], continued: ['failed, carried on', 'warn'] }

function nodeName({ step, kind, op }) {
  if (step) return step
  if (!kind) return 'A node' // recorded before nodes kept their kind
  if (kind === 'trigger') return 'Start'
  return systemEntryFor({ kind, op })?.title ?? kind
}

// `runs` as the server lists them (newest first) -> [{id, title, nodes: [{id, words, tone}]}]
export function historyWords(runs, now = new Date()) {
  return runs.map((run) => ({
    id: run.id,
    title: lastRunWords({ status: run.status, at: run.started_at }, now).words,
    nodes: run.nodes.map((node) => {
      const [said, tone] = NODE[node.status] ?? [node.status, 'muted']
      const words = `${nodeName(node)}: ${said}${node.reason ? `. ${reasonWords(node.reason)}` : ''}${node.effect ? ` (${effectWords(node.effect)})` : ''}`
      return { id: node.node_id, words, tone }
    }),
  }))
}
