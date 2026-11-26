// The history of one flow in words: pure, so node can test it. The server keeps what each box was (its step, or its kind
// and operation) when the run happened, so the names stay right after the flow is rebuilt. No data value is ever recorded.
import { systemEntryFor } from './catalog.js'
import { effectWords, lastRunWords, reasonWords } from './words.js'

const BOX = { done: ['done', 'ok'], blocked: ['stopped', 'bad'], skipped: ['skipped', 'muted'], continued: ['failed, carried on', 'warn'] }

function boxName({ step, kind, op }) {
  if (step) return step
  if (!kind) return 'A box' // recorded before boxes kept their kind
  if (kind === 'trigger') return 'Start'
  return systemEntryFor({ kind, op })?.title ?? kind
}

// `runs` as the server lists them (newest first) -> [{id, title, boxes: [{id, words, tone}]}]
export function historyWords(runs, now = new Date()) {
  return runs.map((run) => ({
    id: run.id,
    title: lastRunWords({ status: run.status, at: run.started_at }, now).words,
    boxes: run.nodes.map((node) => {
      const [said, tone] = BOX[node.status] ?? [node.status, 'muted']
      const words = `${boxName(node)}: ${said}${node.reason ? `. ${reasonWords(node.reason)}` : ''}${node.effect ? ` (${effectWords(node.effect)})` : ''}`
      return { id: node.node_id, words, tone }
    }),
  }))
}
