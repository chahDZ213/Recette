import { useEffect, useState } from 'react'
import Home from './screens/Home'
import Revision from './screens/Revision'
import Exam from './screens/Exam'
import { loadProgress, type Progress } from './lib/progress'
import './styles.css'

export type Screen = 'home' | 'revision' | 'exam'

export default function App() {
  const [screen, setScreen] = useState<Screen>('home')
  const [progress, setProgress] = useState<Progress>({})

  useEffect(() => {
    void loadProgress().then(setProgress)
  }, [])

  return (
    <>
      {screen === 'home' && <Home progress={progress} onNavigate={setScreen} />}
      {screen === 'revision' && (
        <Revision
          progress={progress}
          onProgress={setProgress}
          onHome={() => setScreen('home')}
        />
      )}
      {screen === 'exam' && (
        <Exam
          progress={progress}
          onProgress={setProgress}
          onHome={() => setScreen('home')}
        />
      )}
    </>
  )
}
