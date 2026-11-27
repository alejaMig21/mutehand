import { appKey, appLabel } from './catalog.js'

// Which app: chosen by the name shown on screen, sent by the name the server knows it by.
export default function AppSelect({ apps, value, onChange, ...props }) {
  const choices = value && !apps.some((app) => appKey(app) === appKey(value)) ? [...apps, value] : apps
  return (
    <select value={apps.find((app) => appKey(app) === appKey(value)) ?? value} onChange={(e) => onChange(e.target.value)} {...props}>
      {!value && <option value="">{choices.length ? 'Choose an app…' : 'No app learned yet'}</option>}
      {choices.map((app) => <option key={app} value={app}>{appLabel(app)}</option>)}
    </select>
  )
}
