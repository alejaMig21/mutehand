// What a stopped flow says, the message to send for help, and how trying again went. Pure, so node can test it.
//
// An item is what the server lists as needing the person: {flow, title, app, private, node, step, reason, doubt, note, at,
// rejected_by_person}. It holds no screen content, and no node name for a private app: these words add none.

import { appLabel } from './catalog.js'
import { reasonWords, runNoteWords, sinceWords, whyWords } from './words.js'

const ON_SCREEN = ['control_not_found', 'unreadable', 'out_of_frame', 'wrong_window', 'template_no_match'] // the app was not as taught
const where = (item) => (item.step ? `“${item.step}”` : 'one of its steps')

export function stoppedWords(item, now = new Date()) {
  const app = appLabel(item.app || 'the app')
  const when = item.at ? ` ${sinceWords(item.at, now)}` : ''
  const hint = item.rejected_by_person?.length
    ? 'You blocked a step this flow uses, so trying again would not run it. Press “Allow again” first.'
    : ON_SCREEN.includes(item.reason)
      ? `Open ${app} the way you usually do, then try again. You will be told whether it worked.`
      : 'Try again, or ask for help. You will be told whether it worked.'
  return { title: `“${item.title}” stopped${when}`, detail: `At ${where(item)}: ${reasonWords(item.reason)}`, hint }
}

// The words the person sends in a chat. Only the person starts anything with them.
export function helpMessage(item, appName, note) {
  const mine = String(note ?? '').trim()
  return `In Mutehand my flow “${item.title}” (${appName}) stopped at ${where(item)}. ${reasonWords(item.reason)} `
    + `It is open question ${item.doubt} in Mutehand.${mine ? ` My note: “${mine}”.` : ''} Please help me get it running again.`
}

const finishedSteps = (run) => Object.values(run.nodes ?? {}).filter((state) => state === 'done' || state === 'continued').length

// How a try ended: {tone, title, detail}. `before` is the item when it was pressed, `after` the item now (null when the
// flow is no longer stopped), `run` the run that ended.
export function triedResult(before, run, after) {
  const name = `“${before.title}”`
  const app = appLabel(before.app || 'the app')
  if (run.status === 'finished') {
    const n = finishedSteps(run)
    return { tone: 'ok', title: `Fixed: ${name} ran to the end just now.`, detail: `${stepsWords(n)} finished.` }
  }
  if (run.status === 'stopped') {
    if (!after) return { tone: 'bad', title: `Stopped again: ${name}.`, detail: '' }
    const same = after.node === before.node && after.reason === before.reason
    return {
      tone: 'bad', detail: stoppedWords(after).detail,
      title: same ? `Still stopped: ${name} stopped at the same node for the same reason.` : `A new problem: ${name} stopped again.`,
    }
  }
  if (run.status === 'emergency') {
    return { tone: 'warn', title: `You stopped it. ${name} has not finished.`, detail: 'Try again to carry on from where it stopped.' }
  }
  return { tone: run.status === 'error' ? 'bad' : 'warn', title: `${name} did not run.`, detail: runNoteWords(run, app) }
}

const stepsWords = (n) => `${n} ${n === 1 ? 'step' : 'steps'}`

// How a run followed here ended, for the flow's row: {tone, words}, or null while there is nothing to say yet. It is the
// row's only line about the last run: it says when it worked, as the history line does, and how many steps it did.
export function ranResult(run, now = new Date()) {
  return run?.status === 'finished' && run.ended
    ? { tone: 'ok', words: `Worked ${sinceWords(run.ended, now)}. ${stepsWords(finishedSteps(run))} finished.` } : null
}

export const titles = (flows) => flows.map((flow) => `“${flow.title}”`).join(', ')

// The message to send in a chat when an app was updated: one text wherever it is offered. The steps are not named: the tutor
// finds which ones. `app` is the name on screen; `flows` are the flows that wait, when the place that offers it knows them.
export function relearnMessage(app, flows = []) {
  const waiting = flows.length ? ` so ${flows.length > 1 ? 'these flows' : 'this flow'} can run: ${titles(flows)}` : ''
  return `In Mutehand, ${app} was updated and its steps have to be learned again. Please find which ones and teach them again${waiting}.`
}

// An app update: what the card says, and the message to send in a chat.
export function relearnWords(item) {
  const app = appLabel(item.app)
  const many = item.flows.length > 1
  return {
    title: `${app} was updated`,
    detail: `Its steps have to be learned again. ${many ? 'These flows wait' : 'This flow waits'} for that: ${titles(item.flows)}.`,
    message: relearnMessage(app, item.flows),
  }
}

// A rejected step a flow needs. A private app's step is not named, nor what it did.
export function rejectedWords(item) {
  const app = appLabel(item.app)
  const why = item.why?.kind === 'person' ? whyWords(item.why)
    : item.private ? 'It did not do what it was taught to do the last time it ran.' : whyWords(item.why)
  return {
    title: item.private ? `A step in ${app} is blocked` : `“${item.step}” is blocked`,
    detail: `${why} ${item.flows.length > 1 ? 'These flows cannot run' : 'This flow cannot run'}: ${titles(item.flows)}.`,
  }
}
