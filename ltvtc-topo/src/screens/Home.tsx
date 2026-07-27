import { STREETS } from '../data/streets'
import type { Progress } from '../lib/progress'
import type { Screen } from '../App'

export default function Home({
  progress,
  onNavigate,
}: {
  progress: Progress
  onNavigate: (s: Screen) => void
}) {
  const entries = Object.values(progress)
  const acquises = entries.filter((e) => e.box >= 4).length
  const vues = entries.filter((e) => e.seen > 0).length
  const pct = STREETS.length ? Math.round((acquises / STREETS.length) * 100) : 0

  return (
    <div className="screen center">
      <h1 className="app-title">LTVTC</h1>
      <p className="app-sub">Topographie Ville et Canton</p>

      <div className="progress-card">
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${pct}%` }} />
        </div>
        <p className="progress-text">
          {acquises} rue{acquises > 1 ? 's' : ''} acquise{acquises > 1 ? 's' : ''} sur{' '}
          {STREETS.length} — {vues} déjà vue{vues > 1 ? 's' : ''}
        </p>
      </div>

      <button className="big-btn" onClick={() => onNavigate('revision')}>
        <span className="big-btn-icon">📖</span>
        <span className="big-btn-label">Réviser</span>
        <span className="big-btn-sub">Carte et réponse, à ton rythme</span>
      </button>

      <button className="big-btn" onClick={() => onNavigate('exam')}>
        <span className="big-btn-icon">🎯</span>
        <span className="big-btn-label">Examen</span>
        <span className="big-btn-sub">6 propositions, comme le jour J</span>
      </button>
    </div>
  )
}
