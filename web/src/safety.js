// What the top bar says about the safety of the flow on the canvas. Pure, so node can test it.
// Only steps can be rejected or missing. No trust label is ever shown, and a doubt is the flow's, not the safety's.

export function safetySummary(nodes) {
  const steps = nodes.filter((n) => !n.data.node.kind || n.data.node.kind === 'step')
  return {
    rejected: steps.filter((n) => n.data.meta?.state === 'rejected').map((n) => ({ id: n.id, step: n.data.node.step })),
    missing: steps.filter((n) => n.data.meta?.missing).map((n) => ({ id: n.id, step: n.data.node.step, hole: n.data.meta.hole })),
    needsConsent: steps.filter((n) => n.data.meta?.consent === 'missing').length,
  }
}

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`

// [icon, words, tone]: each with an icon and words, never colour alone.
export function summaryMarks(summary) {
  const marks = []
  if (summary.rejected.length) marks.push(['xcircle', plural(summary.rejected.length, 'rejected step', 'rejected steps'), 'bad'])
  if (summary.missing.length) marks.push(['alert', plural(summary.missing.length, 'step not taught yet', 'steps not taught yet'), 'bad'])
  if (summary.needsConsent) marks.push(['lock', plural(summary.needsConsent, 'step needs consent', 'steps need consent'), 'warn'])
  return marks
}

// Why Run now is off, in words, or '' when the flow may start.
export function whyNotRunnable(summary, app = 'this app') {
  if (summary.missing.length) {
    const named = summary.missing.map((m) => (m.hole ? `the hole '${m.hole.hole}' of the recipe '${m.hole.recipe}'` : `'${m.step}'`)).join(', ')
    return `Will not start: ${named} has no step for ${app} yet. An agent teaches it in a chat.`
  }
  if (!summary.rejected.length) return ''
  const names = summary.rejected.map((r) => `'${r.step}'`).join(', ')
  const one = summary.rejected.length === 1
  return `Will not start: ${names} ${one ? 'is' : 'are'} rejected. Open Apps to see why and allow it again.`
}
