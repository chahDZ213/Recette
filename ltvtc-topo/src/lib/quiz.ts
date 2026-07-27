import { STREETS, type Street } from '../data/streets'
import { weight, type Progress } from './progress'

export type Question = {
  street: Street
  /** Les 6 propositions affichées, mélangées. */
  options: string[]
  begin: string
  end: string
}

/** Nombre de mauvaises réponses mêlées aux deux bonnes. */
const DISTRACTOR_COUNT = 4

export function shuffle<T>(arr: readonly T[]): T[] {
  const out = arr.slice()
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

export function buildQuestion(street: Street): Question {
  const wrong = shuffle(street.distractors).slice(0, DISTRACTOR_COUNT)
  return {
    street,
    options: shuffle([street.beginStreet, street.endStreet, ...wrong]),
    begin: street.beginStreet,
    end: street.endStreet,
  }
}

const normalise = (s: string) =>
  s
    .replace(/\s*\([^)]*\)/g, '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()

/**
 * Une réponse compte juste si les deux voies choisies correspondent au début et
 * à la fin, dans n'importe quel ordre. Les alternatives sont acceptées : à
 * certains carrefours plusieurs voies aboutissent au même bout de rue, et
 * l'examen peut retenir l'une ou l'autre.
 */
export function isCorrect(q: Question, picked: readonly string[]): boolean {
  if (picked.length !== 2) return false
  const begins = new Set(q.street.beginAlternatives.map(normalise))
  const ends = new Set(q.street.endAlternatives.map(normalise))
  const [a, b] = picked.map(normalise)
  return (begins.has(a) && ends.has(b)) || (begins.has(b) && ends.has(a))
}

/** Tirage pondéré sans remise : les rues les moins maîtrisées sortent plus. */
export function pickStreets(count: number, progress: Progress): Street[] {
  if (count <= 0 || count >= STREETS.length) return shuffle(STREETS)
  const pool = STREETS.map((s) => ({ s, w: weight(progress[s.rueOfficial]) }))
  const out: Street[] = []
  for (let n = 0; n < count && pool.length; n++) {
    const total = pool.reduce((sum, p) => sum + p.w, 0)
    let r = Math.random() * total
    let i = 0
    while (i < pool.length - 1 && (r -= pool[i].w) > 0) i++
    out.push(pool[i].s)
    pool.splice(i, 1)
  }
  return out
}

/** Ordre de révision : les boîtes les plus basses d'abord. */
export function revisionOrder(progress: Progress): Street[] {
  return shuffle(STREETS).sort(
    (a, b) =>
      (progress[a.rueOfficial]?.box ?? -1) - (progress[b.rueOfficial]?.box ?? -1),
  )
}

export const questionText = (q: Question) =>
  `Où débute et se termine ${q.street.rueDisplay} ? Propositions : ${q.options.join('. ')}.`

export const answerText = (q: Question) => `Début : ${q.begin}. Fin : ${q.end}.`
