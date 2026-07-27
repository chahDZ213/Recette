/** Lecture vocale des questions et des réponses (mains libres). */

export const speechAvailable = () =>
  typeof window !== 'undefined' && 'speechSynthesis' in window

export function speak(text: string) {
  if (!speechAvailable()) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'fr-CH'
  u.rate = 0.95
  window.speechSynthesis.speak(u)
}

export function stopSpeaking() {
  if (speechAvailable()) window.speechSynthesis.cancel()
}

const AUTOREAD = 'ltvtc-autoread'

export function autoReadEnabled(): boolean {
  try {
    return localStorage.getItem(AUTOREAD) !== '0'
  } catch {
    return true
  }
}

export function setAutoRead(on: boolean) {
  try {
    localStorage.setItem(AUTOREAD, on ? '1' : '0')
  } catch {
    /* mode privé : le réglage reste en mémoire pour la session */
  }
}
