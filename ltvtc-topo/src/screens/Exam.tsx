import { useEffect, useRef, useState } from 'react'
import StreetMap from '../components/StreetMap'
import { STREETS, getStreet } from '../data/streets'
import {
  answerText,
  buildQuestion,
  isCorrect,
  pickStreets,
  questionText,
  shuffle,
  type Question,
} from '../lib/quiz'
import { recordAnswer, revisedList, type Progress } from '../lib/progress'
import {
  autoReadEnabled,
  setAutoRead,
  speak,
  speechAvailable,
  stopSpeaking,
} from '../lib/speech'

const LENGTHS = [10, 20, 40, 0]

export default function Exam({
  progress,
  onProgress,
  onHome,
}: {
  progress: Progress
  onProgress: (p: Progress) => void
  onHome: () => void
}) {
  const [phase, setPhase] = useState<'config' | 'running' | 'result'>('config')
  const [questions, setQuestions] = useState<Question[]>([])
  const [i, setI] = useState(0)
  /** Réponse validée pour chaque question, `null` tant qu'elle ne l'est pas. */
  const [answers, setAnswers] = useState<(string[] | null)[]>([])
  const [picked, setPicked] = useState<string[]>([])
  const [auto, setAuto] = useState(autoReadEnabled)
  const startedAt = useRef(0)
  const [elapsed, setElapsed] = useState(0)

  const revised = revisedList().map(getStreet).filter(Boolean) as typeof STREETS
  const q = questions[i]
  const locked = (answers[i] ?? null) !== null
  const isLast = i === questions.length - 1
  const score = questions.reduce(
    (n, question, idx) => n + (answers[idx] && isCorrect(question, answers[idx]!) ? 1 : 0),
    0,
  )
  const missed = questions
    .filter((question, idx) => answers[idx] && !isCorrect(question, answers[idx]!))
    .map((question) => question.street)

  useEffect(() => stopSpeaking, [])

  useEffect(() => {
    if (phase !== 'running' || !auto) return
    const current = questions[i]
    if (current) speak(questionText(current))
  }, [i, phase, auto, questions])

  useEffect(() => {
    setPicked(answers[i] ?? [])
  }, [i, answers])

  function start(list: Question[]) {
    setQuestions(list)
    setAnswers(new Array(list.length).fill(null))
    setI(0)
    setPicked([])
    startedAt.current = Date.now()
    setPhase('running')
  }

  const startRandom = (n: number) =>
    start(pickStreets(n, progress).map(buildQuestion))
  const startRevised = () => start(shuffle(revised).map(buildQuestion))
  const startMissed = () => start(missed.map(buildQuestion))

  function toggle(option: string) {
    if (locked) return
    setPicked((cur) =>
      cur.includes(option)
        ? cur.filter((o) => o !== option)
        : cur.length < 2
          ? [...cur, option]
          : [cur[1], option],
    )
  }

  function validate() {
    if (picked.length !== 2 || locked || !q) return
    const ok = isCorrect(q, picked)
    setAnswers((cur) => {
      const next = [...cur]
      next[i] = picked
      return next
    })
    void recordAnswer(q.street.rueOfficial, ok).then(onProgress)
    if (auto) speak(answerText(q))
  }

  function next() {
    stopSpeaking()
    if (isLast) {
      setElapsed(Date.now() - startedAt.current)
      setPhase('result')
    } else setI((n) => n + 1)
  }

  function toggleAuto() {
    const on = !auto
    setAuto(on)
    setAutoRead(on)
    if (!on) stopSpeaking()
  }

  if (phase === 'config') {
    return (
      <div className="screen center">
        <header className="topbar">
          <button className="icon-btn" onClick={onHome} aria-label="Accueil">
            ←
          </button>
          <span className="mode-tag">Examen</span>
          <span />
        </header>

        {revised.length > 0 && (
          <div className="config-section">
            <button className="big-btn revised-btn" onClick={startRevised}>
              <span className="big-btn-icon">📖</span>
              <span className="big-btn-label">Ce que je viens de réviser</span>
              <span className="big-btn-sub">
                {revised.length} rue{revised.length > 1 ? 's' : ''}
              </span>
            </button>
            <p className="or-sep">— ou au hasard —</p>
          </div>
        )}

        <h2 className="config-title">Combien de questions ?</h2>
        <div className="length-grid">
          {LENGTHS.map((n) => (
            <button key={n} className="big-btn small" onClick={() => startRandom(n)}>
              {n === 0 ? `Toutes (${STREETS.length})` : n}
            </button>
          ))}
        </div>
        <p className="muted">Les rues les moins maîtrisées reviennent plus souvent.</p>
      </div>
    )
  }

  if (phase === 'result') {
    const total = questions.length
    const pct = total ? Math.round((score / total) * 100) : 0
    const secs = Math.round(elapsed / 1000)
    const mm = String(Math.floor(secs / 60)).padStart(2, '0')
    const ss = String(secs % 60).padStart(2, '0')
    return (
      <div className="screen center">
        <h2 className="result-title">{pct >= 80 ? 'Bravo ! 🎉' : 'Résultat'}</h2>
        <div className={'score-ring ' + (pct >= 80 ? 'good' : pct >= 50 ? 'mid' : 'low')}>
          <span className="score-pct">{pct}%</span>
        </div>
        <p className="progress-text">
          {score} / {total} — {mm}:{ss}
        </p>
        {missed.length > 0 && (
          <button className="big-btn" onClick={startMissed}>
            <span className="big-btn-label">Refaire mes erreurs</span>
            <span className="big-btn-sub">
              {missed.length} rue{missed.length > 1 ? 's' : ''}
            </span>
          </button>
        )}
        <button className="big-btn" onClick={onHome}>
          <span className="big-btn-label">Retour à l'accueil</span>
        </button>
      </div>
    )
  }

  if (!q) return null

  const answered = answers[i]
  const good = answered ? isCorrect(q, answered) : false

  return (
    <div className="screen quiz">
      <header className="topbar">
        <button
          className="icon-btn"
          onClick={() => {
            stopSpeaking()
            onHome()
          }}
          aria-label="Accueil"
        >
          ←
        </button>
        <span className="counter">
          {i + 1} / {questions.length}
        </span>
        {speechAvailable() && (
          <button
            className={'icon-btn auto-toggle' + (auto ? ' on' : '')}
            onClick={toggleAuto}
            aria-label={auto ? 'Couper la lecture auto' : 'Activer la lecture auto'}
          >
            🔈
          </button>
        )}
      </header>

      <div className="question-block">
        <p className="q-label">Indiquez où débute et se termine</p>
        <h2 className="street-name">{q.street.rueDisplay}</h2>
        <p className="muted">Choisis deux propositions.</p>
      </div>

      <StreetMap
        geometry={q.street.geometry}
        streetCenter={q.street.center}
        beginPoint={q.street.beginPoint}
        endPoint={q.street.endPoint}
        showAnswer={locked}
      />

      <div className="options-grid">
        {q.options.map((option) => {
          const chosen = picked.includes(option)
          let cls = 'option'
          if (chosen) cls += ' picked'
          if (locked) {
            const valid =
              isCorrect(q, [option, q.end]) ||
              isCorrect(q, [q.begin, option]) ||
              isCorrect(q, [option, q.begin]) ||
              isCorrect(q, [q.end, option])
            if (valid) cls += ' correct'
            else if (chosen) cls += ' wrong'
          }
          return (
            <button key={option} className={cls} onClick={() => toggle(option)}>
              {option}
            </button>
          )
        })}
      </div>

      {locked ? (
        <>
          <p className={'verdict ' + (good ? 'good' : 'bad')}>
            {good ? 'Correct' : `Début : ${q.begin} — Fin : ${q.end}`}
          </p>
          <div className="nav-row">
            <button
              className="nav-prev"
              onClick={() => {
                stopSpeaking()
                setI((n) => Math.max(0, n - 1))
              }}
              disabled={i === 0}
              aria-label="Précédent"
            >
              ◀
            </button>
            <button className="judge-btn known" onClick={next}>
              {isLast ? 'Voir le résultat' : 'Suivant'}
            </button>
          </div>
        </>
      ) : (
        <button
          className="reveal-btn"
          onClick={validate}
          disabled={picked.length !== 2}
        >
          Valider
        </button>
      )}
    </div>
  )
}
