// What a stopped chore says, the message to send for help, and how trying again went. Pure, so node can test it.
//
// An item is what the server lists as needing the person: {flow, title, app, private, node, box, reason, doubt, note, at,
// rejected_by_person}. It holds no screen content, and no box name for a private app: these words add none.

import { appLabel } from './catalog.js'
import { reasonWords, runNoteWords, sinceWords } from './words.js'

const ON_SCREEN = ['control_not_found', 'unreadable', 'out_of_frame', 'wrong_window', 'template_no_match'] // the app was not as taught
const where = (item) => (item.box ? `“${item.box}”` : 'one of its boxes')

export function stoppedWords(item, now = new Date()) {
  const app = appLabel(item.app || 'the app')
  const when = item.at ? ` ${sinceWords(item.at, now)}` : ''
  const hint = item.rejected_by_person?.length
    ? 'You rejected an action this chore uses, so trying again would not run it. Press “Allow again” first.'
    : ON_SCREEN.includes(item.reason)
      ? `Open ${app} the way you usually do, then try again. You will be told whether it worked.`
      : 'Try again, or ask for help. You will be told whether it worked.'
  return { title: `“${item.title}” stopped${when}`, detail: `At ${where(item)}: ${reasonWords(item.reason)}`, hint }
}

// The words the person sends in a chat. Only the person starts anything with them.
export function helpMessage(item, appName, note) {
  const mine = String(note ?? '').trim()
  return `In Workflow Factory my chore “${item.title}” (${appName}) stopped at ${where(item)}. ${reasonWords(item.reason)} `
    + `It is open question ${item.doubt} in Workflow Factory.${mine ? ` My note: “${mine}”.` : ''} Please help me get it running again.`
}

const finishedBoxes = (run) => Object.values(run.nodes ?? {}).filter((state) => state === 'done' || state === 'continued').length

// How a try ended: {tone, title, detail}. `before` is the item when it was pressed, `after` the item now (null when the
// chore is no longer stopped), `run` the run that ended.
export function triedResult(before, run, after) {
  const name = `“${before.title}”`
  const app = appLabel(before.app || 'the app')
  if (run.status === 'finished') {
    const n = finishedBoxes(run)
    return { tone: 'ok', title: `Fixed: ${name} ran to the end just now.`, detail: `${n} ${n === 1 ? 'box' : 'boxes'} finished.` }
  }
  if (run.status === 'stopped') {
    if (!after) return { tone: 'bad', title: `Stopped again: ${name}.`, detail: '' }
    const same = after.node === before.node && after.reason === before.reason
    return {
      tone: 'bad', detail: stoppedWords(after).detail,
      title: same ? `Still stopped: ${name} stopped at the same box for the same reason.` : `A new problem: ${name} stopped again.`,
    }
  }
  if (run.status === 'emergency') {
    return { tone: 'warn', title: `You stopped it. ${name} has not finished.`, detail: 'Try again to carry on from where it stopped.' }
  }
  return { tone: run.status === 'error' ? 'bad' : 'warn', title: `${name} did not run.`, detail: runNoteWords(run, app) }
}
