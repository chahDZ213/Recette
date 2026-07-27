import raw from './streets.json'

/**
 * Une rue du référentiel de topographie.
 *
 * Deux types de questions officielles sont couverts :
 *  - « Où se trouve : X ? »            → `referenceOfficial`
 *  - « Indiquez où débute et se termine » → `beginStreet` / `endStreet`
 */
export type Street = {
  /** Intitulé exact de la question officielle, ex. « LA RUE AGASSE ». */
  rueOfficial: string
  /** Nom lisible affiché à l'écran. */
  rueDisplay: string
  /** Repère officiel du PCTN, ex. « Près de la rue de l'Amandolier ». */
  referenceOfficial: string | null
  /** Voie de référence extraite du repère officiel. */
  correctAnswer?: string | null
  osmName?: string
  center: [number, number]
  geometry: [number, number][][]
  beginStreet: string
  endStreet: string
  /**
   * Réponses également acceptées pour ce bout de rue. La première entrée est
   * toujours `beginStreet` / `endStreet`. Utile là où plusieurs voies se
   * rejoignent à la même extrémité.
   */
  beginAlternatives: string[]
  endAlternatives: string[]
  beginPoint: [number, number]
  endPoint: [number, number]
  /** Mauvaises réponses proposées en mode examen. */
  distractors: string[]
  status: string
}

export const STREETS: Street[] = (raw as Street[]).filter(
  (s) => s.status === 'verified',
)

const byOfficial = new Map(STREETS.map((s) => [s.rueOfficial, s]))
export const getStreet = (rueOfficial: string) => byOfficial.get(rueOfficial)

/** Rues qui figurent au référentiel officiel des destinations du PCTN. */
export const OFFICIAL = STREETS.filter((s) => s.referenceOfficial)
