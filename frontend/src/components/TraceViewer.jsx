import { useState } from 'react'
import styles from './TraceViewer.module.css'

const AGENT_META = {
  document_verifier:   { label: 'Document Verifier',  color: 'blue',   icon: '🔍', step: 1 },
  document_parser:     { label: 'Document Parser',     color: 'amber',  icon: '📝', step: 2 },
  policy_evaluator:    { label: 'Policy Evaluator',    color: 'green',  icon: '⚖',  step: 3 },
  fraud_detector:      { label: 'Fraud Detector',      color: 'red',    icon: '🛡',  step: 4 },
  decision_synthesizer:{ label: 'Decision Synthesizer',color: 'purple', icon: '⚡', step: 5 },
}

export default function TraceViewer({ trace, componentFailures = [] }) {
  const [expanded, setExpanded] = useState({})

  if (!trace || trace.length === 0) return null

  const toggle = (i) => setExpanded(e => ({ ...e, [i]: !e[i] }))

  return (
    <div className={styles.viewer}>
      <div className={styles.header}>
        <span className={styles.title}>Audit Trail</span>
        <span className={styles.count}>{trace.length} steps</span>
      </div>

      {/* Timeline */}
      <div className={styles.timeline}>
        {trace.map((step, i) => {
          const meta = AGENT_META[step.agent] || {
            label: step.agent, color: 'blue', icon: '◆', step: i + 1,
          }
          const isFailed = step.status === 'AgentStatus.FAILED' ||
                           step.status === 'FAILED'
          const isExpanded = expanded[i]
          const hasData = step.data && Object.keys(step.data).length > 0

          return (
            <div key={i} className={`${styles.step} ${styles[meta.color]}`}>
              {/* Connector line */}
              {i < trace.length - 1 && <div className={styles.connector} />}

              <div className={styles.stepInner}>
                {/* Left: icon + step number */}
                <div className={`${styles.iconWrap} ${isFailed ? styles.iconFailed : ''}`}>
                  <span className={styles.stepIcon}>{meta.icon}</span>
                </div>

                {/* Right: content */}
                <div className={styles.stepContent}>
                  <div className={styles.stepHeader}>
                    <div className={styles.stepMeta}>
                      <span className={styles.stepNum}>Step {meta.step}</span>
                      <span className={`${styles.stepLabel} ${styles[meta.color + 'Text']}`}>
                        {meta.label}
                      </span>
                    </div>
                    <div className={styles.stepRight}>
                      {step.confidence_delta !== 0 && (
                        <span className={`${styles.delta} ${step.confidence_delta < 0 ? styles.deltaDown : styles.deltaUp}`}>
                          {step.confidence_delta > 0 ? '+' : ''}
                          {(step.confidence_delta * 100).toFixed(0)}%
                        </span>
                      )}
                      <span className={`${styles.status} ${isFailed ? styles.statusFailed : styles.statusOk}`}>
                        {isFailed ? 'FAILED' : 'OK'}
                      </span>
                      {hasData && (
                        <button
                          className={styles.expandBtn}
                          onClick={() => toggle(i)}
                        >
                          {isExpanded ? '▲' : '▼'}
                        </button>
                      )}
                    </div>
                  </div>

                  <p className={styles.detail}>{step.detail}</p>

                  {/* Expanded data */}
                  {isExpanded && hasData && (
                    <div className={styles.dataBlock}>
                      <pre className={styles.dataPre}>
                        {JSON.stringify(step.data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Component failures summary */}
      {componentFailures.length > 0 && (
        <div className={styles.failures}>
          <span className={styles.failuresLabel}>⚠ Component Failures</span>
          <div className={styles.failureList}>
            {componentFailures.map((f, i) => (
              <span key={i} className={styles.failureItem}>{f}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
