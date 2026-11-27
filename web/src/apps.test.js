import assert from 'node:assert/strict'
import test from 'node:test'
import { noteWords, permissionWords, takeBackWords, teachMessage } from './apps.js'
import { relearnMessage } from './stopped.js'

const row = (extra) => ({ app: 'paint.exe', private: false, actions: 3, problems: 0, permissions: 0, ...extra })
const stops = (actions, flows) => ({ actions, flows: flows.map((title) => ({ id: title, title })) })

test('a row has a note only when something needs the person, a stopped chore first', () => {
  assert.equal(noteWords(row(), 0), null)
  assert.deepEqual(noteWords(row({ problems: 2 }), 0), { words: '2 to fix', tone: 'warn' })
  assert.deepEqual(noteWords(row({ problems: 2 }), 1), { words: '1 stopped', tone: 'bad' })
  assert.deepEqual(noteWords(row(), 3), { words: '3 stopped', tone: 'bad' })
})

test('a permission is said as what it lets the apprentice do, and a private app keeps its control to itself', () => {
  assert.equal(permissionWords({ control: 'Send', action: 'click' }, false), 'Press “Send”')
  assert.equal(permissionWords({ control: 'Subject', action: 'type_value' }, false), 'Type into “Subject”')
  assert.equal(permissionWords({ control: '*', action: 'click' }, false), 'Press anything')
  assert.equal(permissionWords({ control: 'Chat with Ana', action: 'click' }, true), 'Press a control')
  assert.equal(permissionWords({ control: 'x', action: 'something_new' }, false), 'something new “x”')
})

test('taking a permission back says which chores and actions stop working, by the data it was given', () => {
  const both = takeBackWords({ stops: stops(['Send', 'Send again'], ['Weekly report', 'Rent']) }, false)
  assert.match(both, /These chores will stop: “Weekly report”, “Rent”\./)
  assert.match(both, /These actions will not run without it: “Send”, “Send again”\./)
  assert.match(takeBackWords({ stops: stops(['Send'], []) }, false), /^The action “Send” will not run without it\./)
  assert.match(takeBackWords({ stops: stops([], []) }, false), /^No chore or action needs it now\./)
  const hidden = takeBackWords({ stops: stops(['Chat with Ana', 'Bank 4471'], ['Pay']) }, true)
  assert.match(hidden, /2 actions will not run without it\./)
  assert.doesNotMatch(hidden, /Ana|4471/)
})

test('the messages to send name the app and never start anything', () => {
  assert.match(teachMessage('Excel'), /^In Workflow Factory I want to teach another action in Excel\./)
  const update = relearnMessage('Excel')
  assert.match(update, /Excel was updated and its actions have to be learned again/)
  assert.doesNotMatch(update, /Claude Code|folder/) // plain words for a person who does not know the vocabulary
})
