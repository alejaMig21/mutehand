import { api } from './api.js'
import { act, useLoad } from './useLoad.js'

export default function Library() {
  const { data: lessons, error, reload, setError } = useLoad('/api/library')
  const apps = [...new Set(lessons.map((lesson) => lesson.app))]

  return (
    <section>
      <h1>Lessons</h1>
      <p>Confidence is (successes + 1) / (successes + 3 x failures + 2). A lesson is trusted from 0.80 with two successes of its own and no failures.</p>
      {error && <div className="error" role="alert" data-testid="error">{error}</div>}
      {apps.map((app) => (
        <div key={app}>
          <h2>{app}</h2>
          <table>
            <thead>
              <tr><th>Lesson</th><th>Origin</th><th>State</th><th>Successes</th><th>Failures</th><th>Confidence</th><th>Action</th></tr>
            </thead>
            <tbody>
              {lessons.filter((lesson) => lesson.app === app).map((lesson) => (
                <tr key={lesson.name} data-testid={`lesson-row-${lesson.name}`}>
                  <td>{lesson.name}{lesson.sensitive ? ' (needs consent)' : ''}</td>
                  <td>{lesson.origin}</td>
                  <td data-testid={`state-${lesson.name}`}>{lesson.state}</td>
                  <td>{lesson.successes}</td>
                  <td>{lesson.failures}</td>
                  <td>{lesson.confidence}</td>
                  <td>
                    {lesson.state === 'rejected' ? (
                      <button data-testid={`restore-${lesson.name}`} aria-label={`Restore ${lesson.name}`} onClick={() =>
                        act(() => api(`/api/lessons/${lesson.app}/${lesson.name}/restore`, { method: 'POST', body: {} }), reload, setError)}>
                        Restore
                      </button>
                    ) : (
                      <button data-testid={`reject-${lesson.name}`} aria-label={`Reject ${lesson.name}`} onClick={() =>
                        act(() => api(`/api/lessons/${lesson.app}/${lesson.name}/reject`, { method: 'POST', body: {} }), reload, setError)}>
                        Reject
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </section>
  )
}
