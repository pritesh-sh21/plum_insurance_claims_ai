import styles from './DecisionPanel.module.css'

const DECISION_META = {
  APPROVED: {
    label: 'Approved',
    icon: '✓',
    color: 'approved',
    message: 'Your claim has been approved.',
  },
  PARTIAL: {
    label: 'Partially Approved',
    icon: '◑',
    color: 'partial',
    message: 'Some items were approved, others excluded.',
  },
  REJECTED: {
    label: 'Rejected',
    icon: '✕',
    color: 'rejected',
    message: 'Your claim could not be approved.',
  },
  MANUAL_REVIEW: {
    label: 'Manual Review',
    icon: '⚑',
    color: 'manual',
    message: 'Claim flagged for human review.',
  },
}

const REJECTION_LABELS = {
  WAITING_PERIOD: 'Waiting Period Not Completed',
  PRE_AUTH_MISSING: 'Pre-Authorization Required',
  PER_CLAIM_EXCEEDED: 'Per-Claim Limit Exceeded',
  EXCLUDED_CONDITION: 'Excluded Condition',
  DOCUMENT_MISMATCH: 'Document Mismatch',
  FRAUD_SIGNAL: 'Fraud Signal Detected',
  SUB_LIMIT_EXCEEDED: 'Sub-Limit Exceeded',
}

export default function DecisionPanel({ result, onBack }) {
  // Handle document verification failure
  if (result.status === 'document_verification_failed') {
    return <DocVerificationError result={result} onBack={onBack} />
  }

  const meta = DECISION_META[result.decision] || DECISION_META.MANUAL_REVIEW
  const hasBreakdown = result.calculation_breakdown &&
    Object.keys(result.calculation_breakdown).length > 0

  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.topBar}>
        <button className={styles.back} onClick={onBack}>← New Claim</button>
        <span className={styles.claimId}>
          Claim #{result.claim_id}
        </span>
      </div>

      {/* Decision badge */}
      <div className={`${styles.badge} ${styles[meta.color]}`}>
        <div className={styles.badgeIcon}>{meta.icon}</div>
        <div className={styles.badgeContent}>
          <div className={styles.badgeLabel}>{meta.label}</div>
          <div className={styles.badgeMsg}>{meta.message}</div>
        </div>
      </div>

      {/* Amounts */}
      <div className={styles.amounts}>
        <div className={styles.amountCard}>
          <div className={styles.amountLabel}>Claimed</div>
          <div className={styles.amountValue}>
            ₹{result.claimed_amount?.toLocaleString('en-IN')}
          </div>
        </div>
        <div className={styles.amountArrow}>→</div>
        <div className={`${styles.amountCard} ${styles[meta.color + 'Card']}`}>
          <div className={styles.amountLabel}>Approved</div>
          <div className={`${styles.amountValue} ${styles[meta.color + 'Text']}`}>
            ₹{result.approved_amount?.toLocaleString('en-IN') || '0'}
          </div>
        </div>
      </div>

      {/* Confidence */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <span>Confidence Score</span>
          <span className={styles.confValue}>
            {Math.round((result.confidence_score || 0) * 100)}%
          </span>
        </div>
        <div className={styles.confBar}>
          <div
            className={`${styles.confFill} ${styles[meta.color + 'Fill']}`}
            style={{ width: `${(result.confidence_score || 0) * 100}%` }}
          />
        </div>
      </div>

      {/* Decision message */}
      <div className={styles.message}>
        <div className={styles.messageLabel}>Decision Reason</div>
        <p className={styles.messageText}>{result.message}</p>
      </div>

      {/* Rejection tags */}
      {result.rejection_reasons?.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Rejection Reasons</div>
          <div className={styles.tags}>
            {result.rejection_reasons.map(r => (
              <span key={r} className={styles.tag}>
                {REJECTION_LABELS[r] || r}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Line item breakdown (TC006) */}
      {result.line_item_decisions?.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Line Item Breakdown</div>
          <div className={styles.lineItems}>
            {result.line_item_decisions.map((li, i) => (
              <div
                key={i}
                className={`${styles.lineItem} ${li.approved_amount > 0 ? styles.liApproved : styles.liRejected}`}
              >
                <div className={styles.liLeft}>
                  <span className={styles.liDot}>
                    {li.approved_amount > 0 ? '✓' : '✕'}
                  </span>
                  <div>
                    <div className={styles.liDesc}>{li.description}</div>
                    <div className={styles.liReason}>{li.reason}</div>
                  </div>
                </div>
                <div className={styles.liAmounts}>
                  <div className={styles.liClaimed}>
                    ₹{li.claimed_amount?.toLocaleString('en-IN')}
                  </div>
                  <div className={`${styles.liApprovedAmt} ${li.approved_amount > 0 ? styles.approvedText : styles.rejectedText}`}>
                    ₹{li.approved_amount?.toLocaleString('en-IN')}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Calculation breakdown (TC010) */}
      {hasBreakdown && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Calculation Breakdown</div>
          <div className={styles.breakdown}>
            {Object.entries(result.calculation_breakdown)
              .filter(([k]) => !k.includes('annual'))
              .map(([key, val]) => (
                <div key={key} className={styles.breakdownRow}>
                  <span className={styles.breakdownKey}>
                    {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  </span>
                  <span className={styles.breakdownVal}>
                    {typeof val === 'number'
                      ? `₹${val.toLocaleString('en-IN')}`
                      : String(val)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Component failures (TC011) */}
      {result.component_failures?.length > 0 && (
        <div className={styles.warning}>
          <span className={styles.warningIcon}>⚠</span>
          <div>
            <div className={styles.warningTitle}>Component Failures Detected</div>
            <div className={styles.warningList}>
              {result.component_failures.map((f, i) => (
                <span key={i} className={styles.warningItem}>{f}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {result.manual_review_recommended && (
        <div className={styles.manualNote}>
          <span>⚑</span> This claim has been flagged for manual review by a claims adjuster.
        </div>
      )}
    </div>
  )
}

function DocVerificationError({ result, onBack }) {
  return (
    <div className={styles.panel}>
      <div className={styles.topBar}>
        <button className={styles.back} onClick={onBack}>← Fix Documents</button>
        <span className={styles.claimId}>Document Check Failed</span>
      </div>

      <div className={`${styles.badge} ${styles.rejected}`}>
        <div className={styles.badgeIcon}>⚠</div>
        <div className={styles.badgeContent}>
          <div className={styles.badgeLabel}>Document Verification Failed</div>
          <div className={styles.badgeMsg}>
            Fix the issues below and resubmit your claim.
          </div>
        </div>
      </div>

      <div className={styles.errorList}>
        {result.errors?.map((err, i) => (
          <div key={i} className={styles.errorCard}>
            <div className={styles.errorCode}>{err.error_code}</div>
            <p className={styles.errorMsg}>{err.message}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
