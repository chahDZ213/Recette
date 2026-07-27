import { useEffect, useState } from 'react'
import StreetMap from '../components/StreetMap'
import { revisionOrder } from '../lib/quiz'
import {
  clearRevised,
  markRevised,
  recordAnswer,
  type Progress,
} from '../lib/progress'
import {
  autoReadEnabled,
  setAutoRead,
  speak,
  speechAvailable,
  stopSpeaking,
} from '../lib/speech'

export default function Revision({
  progress,
  onProgress,
  onHome,
}: {
  progress: Progress
  onProgress: (p: Progress) => void
  onHome: () => void
}) {
  const [deck] = useState(() => revisionOrder(progress))
  const [i, setI] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [auto, setAuto] = useState(autoReadEnabled)
  const card = deck[i]

  useEffect(() => {
    clearRevised()
    return stopSpeaking
  }, [])

  useEffect(() => {
    if (auto && card) speak(`Où débute et se termine ${card.rueDisplay} ?`)
  }, [i, auto, card])

  useEffect(() => {
    if (auto && revealed && card)
      speak(`Début : ${card.beginStreet}. Fin : ${card.endStreet}.`)
  }, [revealed, auto, card])

  if (!card) {
    return (
      <div className="screen center">
        <h2 className="result-title">Révision terminée 🎉</h2>
        <button className="big-btn" onClick={onHome}>
          <span className="big-btn-label">Retour à l'accueil</span>
        </button>
      </div>
    )
  }

  function judge(known: boolean) {
    stopSpeaking()
    markRevised(card.rueOfficial)
    void recordAnswer(card.rueOfficial, known).then(onProgress)
    setRevealed(false)
    setI((n) => n + 1)
  }

  function replay() {
    const q = `Où débute et se termine ${card.rueDisplay} ?`
    speak(revealed ? `${q} Début : ${card.beginStreet}. Fin : ${card.endStreet}.` : q)
  }

  function toggleAuto() {
    const next = !auto
    setAuto(next)
    setAutoRead(next)
    if (!next) stopSpeaking()
  }

  // Voies également acceptées, hors réponse principale.
  const alsoBegin = card.beginAlternatives.slice(1)
  const alsoEnd = card.endAlternatives.slice(1)

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
          {i + 1} / {deck.length}
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
        <p className="q-label">Où débute et se termine ?</p>
        <div className="street-row">
          <h2 className="street-name">{card.rueDisplay}</h2>
          {speechAvailable() && (
            <button className="speak-btn" onClick={replay} aria-label="Réécouter">
              🔊
            </button>
          )}
        </div>
      </div>

      <StreetMap
        geometry={card.geometry}
        streetCenter={card.center}
        beginPoint={card.beginPoint}
        endPoint={card.endPoint}
        showAnswer={revealed}
      />

      {revealed ? (
        <>
          <div className="answer-grid">
            <div className="answer-card begin">
              <span className="answer-tag">Début</span>
              <p className="answer-text">{card.beginStreet}</p>
              {alsoBegin.length > 0 && (
                <p className="answer-alt">aussi accepté : {alsoBegin.join(', ')}</p>
              )}
            </div>
            <div className="answer-card end">
              <span className="answer-tag">Fin</span>
              <p className="answer-text">{card.endStreet}</p>
              {alsoEnd.length > 0 && (
                <p className="answer-alt">aussi accepté : {alsoEnd.join(', ')}</p>
              )}
            </div>
          </div>

          {card.referenceOfficial && (
            <p className="official-ref">
              Question officielle « Où se trouve {card.rueOfficial} ? » →{' '}
              <strong>{card.referenceOfficial}</strong>
            </p>
          )}

          <div className="nav-row">
            <button
              className="nav-prev"
              onClick={() => {
                stopSpeaking()
                setRevealed(false)
                setI((n) => Math.max(0, n - 1))
              }}
              disabled={i === 0}
              aria-label="Précédent"
            >
              ◀
            </button>
            <button className="judge-btn again" onClick={() => judge(false)}>
              À revoir
            </button>
            <button className="judge-btn known" onClick={() => judge(true)}>
              Je la connais
            </button>
          </div>
        </>
      ) : (
        <button className="reveal-btn" onClick={() => setRevealed(true)}>
          Voir la réponse
        </button>
      )}
    </div>
  )
}
