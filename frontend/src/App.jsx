import { useState, useEffect } from 'react'
import ClaimForm from './components/ClaimForm'
import DecisionPanel from './components/DecisionPanel'
import TraceViewer from './components/TraceViewer'
import { healthCheck } from './api/claims'
import './index.css'
import styles from './App.module.css'

export default function App() {
  const [screen, setScreen] = useState('form')   // 'form' | 'result'
  const [result, setResult]   = useState(null)
  const [apiOk, setApiOk]     = useState(null)   // null=checking, true=ok, false=down

  useEffect(() => {
    healthCheck()
      .then(() => setApiOk(true))
      .catch(() => setApiOk(false))
  }, [])

  const handleResult = (data) => {
    setResult(data)
    setScreen('result')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleBack = () => {
    setScreen('form')
    setResult(null)
  }

  return (
    <div className={styles.app}>
      {/* API status bar */}
      <div className={`${styles.statusBar} ${apiOk === false ? styles.statusDown : ''}`}>
        <div className={styles.statusInner}>
          <span className={`${styles.dot} ${apiOk === true ? styles.dotOk : apiOk === false ? styles.dotDown : styles.dotChecking}`} />
          <span className={styles.statusText}>
            {apiOk === null ? 'Connecting to API…' :
             apiOk ? 'API connected — localhost:8000' :
             'API offline — start uvicorn main:app --reload'}
          </span>
        </div>
      </div>

      {/* Main content */}
      <main className={styles.main}>
        {screen === 'form' && (
          <ClaimForm onResult={handleResult} />
        )}

        {screen === 'result' && result && (
          <>
            <DecisionPanel result={result} onBack={handleBack} />
            <TraceViewer
              trace={result.trace}
              componentFailures={result.component_failures}
            />
          </>
        )}
      </main>

      {/* Footer */}
      <footer className={styles.footer}>
        <span>Plum Health Insurance</span>
        <span className={styles.sep}>·</span>
        <span>AI Claims Processor v0.1</span>
        <span className={styles.sep}>·</span>
        <span>Powered by GPT-4o + LangGraph</span>
      </footer>
    </div>
  )
}
