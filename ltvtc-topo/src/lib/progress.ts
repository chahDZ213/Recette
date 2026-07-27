import { openDB, type IDBPDatabase } from 'idb'

/** Fiche de progression Leitner pour une rue. */
export type Entry = {
  rue: string
  seen: number
  correct: number
  wrong: number
  /** Boîte Leitner, de 0 (jamais su) à 5 (acquis). */
  box: number
  lastSeen: number
}

export type Progress = Record<string, Entry>

const DB = 'ltvtc-topo'
const STORE = 'progress'

let dbp: Promise<IDBPDatabase> | null = null
const db = () =>
  (dbp ??= openDB(DB, 1, {
    upgrade(d) {
      if (!d.objectStoreNames.contains(STORE)) d.createObjectStore(STORE, { keyPath: 'rue' })
    },
  }))

export async function loadProgress(): Promise<Progress> {
  const all = (await (await db()).getAll(STORE)) as Entry[]
  return Object.fromEntries(all.map((e) => [e.rue, e]))
}

export async function recordAnswer(rue: string, correct: boolean): Promise<Progress> {
  const d = await db()
  const cur: Entry = (await d.get(STORE, rue)) ?? {
    rue,
    seen: 0,
    correct: 0,
    wrong: 0,
    box: 0,
    lastSeen: 0,
  }
  cur.seen += 1
  cur.lastSeen = Date.now()
  if (correct) {
    cur.correct += 1
    cur.box = Math.min(5, cur.box + 1)
  } else {
    cur.wrong += 1
    cur.box = 0
  }
  await d.put(STORE, cur)
  return loadProgress()
}

export async function resetProgress(): Promise<Progress> {
  await (await db()).clear(STORE)
  return {}
}

/**
 * Poids de tirage : une rue jamais vue, ou plus souvent ratée que réussie,
 * revient plus souvent.
 */
export const weight = (e?: Entry) =>
  !e || e.seen === 0 ? 8 : Math.max(1, 6 - e.box) + (e.wrong > e.correct ? 2 : 0)

// --- liste des rues révisées dans la session courante (localStorage) ---

const REVISED = 'ltvtc-revised'

export function revisedList(): string[] {
  try {
    const raw = localStorage.getItem(REVISED)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

export function markRevised(rue: string) {
  const list = revisedList()
  if (!list.includes(rue)) {
    list.push(rue)
    try {
      localStorage.setItem(REVISED, JSON.stringify(list))
    } catch {
      /* quota plein ou mode privé : la liste est optionnelle */
    }
  }
}

export function clearRevised() {
  try {
    localStorage.removeItem(REVISED)
  } catch {
    /* idem */
  }
}
