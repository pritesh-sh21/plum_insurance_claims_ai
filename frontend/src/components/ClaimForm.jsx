import { useState, useRef } from 'react'
import { submitClaimUpload } from '../api/claims'
import styles from './ClaimForm.module.css'

const MEMBERS = [
  { id: 'EMP001', name: 'Rajesh Kumar' },
  { id: 'EMP002', name: 'Priya Singh' },
  { id: 'EMP003', name: 'Amit Patel' },
  { id: 'EMP004', name: 'Sneha Reddy' },
  { id: 'EMP005', name: 'Vikram Joshi' },
  { id: 'EMP006', name: 'Meera Nair' },
  { id: 'EMP007', name: 'Suresh Patil' },
  { id: 'EMP008', name: 'Kavitha Raman' },
  { id: 'EMP009', name: 'Anita Desai' },
  { id: 'EMP010', name: 'Deepak Shah' },
]

const CATEGORIES = [
  'CONSULTATION', 'DIAGNOSTIC', 'PHARMACY',
  'DENTAL', 'VISION', 'ALTERNATIVE_MEDICINE',
]

const DOC_TYPES = [
  'PRESCRIPTION', 'HOSPITAL_BILL', 'LAB_REPORT',
  'PHARMACY_BILL', 'DENTAL_REPORT', 'DISCHARGE_SUMMARY',
]

const HOSPITALS = [
  '', 'Apollo Hospitals', 'Fortis Hospital',
  'Manipal Hospital', 'Columbia Asia', 'City Clinic',
]

export default function ClaimForm({ onResult }) {
  const [form, setForm] = useState({
    member_id: 'EMP001',
    claim_category: 'CONSULTATION',
    treatment_date: new Date().toISOString().split('T')[0],
    claimed_amount: '',
    hospital_name: '',
    ytd_claims_amount: '0',
  })
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const fileRef = useRef()

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const guessDocType = (filename) => {
    const name = filename.toLowerCase()
    if (name.includes('prescription')) return 'PRESCRIPTION'
    if (name.includes('pharmacy')) return 'PHARMACY_BILL'
    if (name.includes('dental_report')) return 'DENTAL_REPORT'
    if (name.includes('discharge')) return 'DISCHARGE_SUMMARY'
    if (name.includes('bill') || name.includes('invoice')) return 'HOSPITAL_BILL'
    if (name.includes('lab') || name.includes('report') || name.includes('mri')) return 'LAB_REPORT'
    if (name.includes('dental')) return 'HOSPITAL_BILL'
    return 'PRESCRIPTION'
  }

  const handleFiles = (e) => {
    const picked = Array.from(e.target.files)
    setFiles(prev => [
      ...prev,
      ...picked.map(f => ({ file: f, docType: guessDocType(f.name) })),
    ])
  }

  const updateDocType = (i, t) => {
    setFiles(prev => prev.map((f, idx) => idx === i ? { ...f, docType: t } : f))
  }

  const removeFile = (i) => {
    setFiles(prev => prev.filter((_, idx) => idx !== i))
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const dropped = Array.from(e.dataTransfer.files)
    setFiles(prev => [
      ...prev,
      ...dropped.map(f => ({ file: f, docType: guessDocType(f.name) })),
    ])
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const fd = new FormData()
      fd.append('member_id', form.member_id)
      fd.append('policy_id', 'PLUM_GHI_2024')
      fd.append('claim_category', form.claim_category)
      fd.append('treatment_date', form.treatment_date)
      fd.append('claimed_amount', form.claimed_amount)
      fd.append('hospital_name', form.hospital_name || '')
      fd.append('ytd_claims_amount', form.ytd_claims_amount || '0')
      // Send as both JSON and comma-separated for maximum compatibility
      const docTypes = files.map(f => f.docType)
      fd.append('document_types', JSON.stringify(docTypes))
      files.forEach(({ file }) => fd.append('files', file))

      const result = await submitClaimUpload(fd)
      onResult(result)
    } catch (err) {
      if (err.detail?.stage === 'document_verification') {
        onResult({ status: 'document_verification_failed', ...err.detail })
      } else {
        setError(err.detail?.message || err.detail || 'Submission failed. Check the API is running.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.header}>
        <div className={styles.logo}>
          <span className={styles.logoMark}>P</span>
          <span>Plum Claims</span>
        </div>
        <p className={styles.subtitle}>AI-powered health insurance claim processing</p>
      </div>

      {/* Member + Category */}
      <div className={styles.row}>
        <div className={styles.field}>
          <label className={styles.label}>Member</label>
          <select className={styles.select} value={form.member_id}
            onChange={e => set('member_id', e.target.value)}>
            {MEMBERS.map(m => (
              <option key={m.id} value={m.id}>{m.name} — {m.id}</option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <label className={styles.label}>Claim Category</label>
          <select className={styles.select} value={form.claim_category}
            onChange={e => set('claim_category', e.target.value)}>
            {CATEGORIES.map(c => (
              <option key={c} value={c}>{c.replace('_', ' ')}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Date + Amount */}
      <div className={styles.row}>
        <div className={styles.field}>
          <label className={styles.label}>Treatment Date</label>
          <input className={styles.input} type="date"
            value={form.treatment_date}
            onChange={e => set('treatment_date', e.target.value)} />
        </div>
        <div className={styles.field}>
          <label className={styles.label}>Claimed Amount (₹)</label>
          <input className={styles.input} type="number" placeholder="e.g. 1500"
            value={form.claimed_amount}
            onChange={e => set('claimed_amount', e.target.value)}
            required min="1" />
        </div>
      </div>

      {/* Hospital + YTD */}
      <div className={styles.row}>
        <div className={styles.field}>
          <label className={styles.label}>Hospital / Clinic</label>
          <select className={styles.select} value={form.hospital_name}
            onChange={e => set('hospital_name', e.target.value)}>
            {HOSPITALS.map(h => (
              <option key={h} value={h}>{h || '— None / Other —'}</option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <label className={styles.label}>YTD Claims Amount (₹)</label>
          <input className={styles.input} type="number" placeholder="0"
            value={form.ytd_claims_amount}
            onChange={e => set('ytd_claims_amount', e.target.value)} />
        </div>
      </div>

      {/* File upload */}
      <div className={styles.field}>
        <label className={styles.label}>Documents</label>
        <div
          className={styles.dropzone}
          onDragOver={e => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileRef.current.click()}
        >
          <input ref={fileRef} type="file" multiple accept=".pdf,.jpg,.jpeg,.png"
            onChange={handleFiles} style={{ display: 'none' }} />
          <div className={styles.dropIcon}>⬆</div>
          <p className={styles.dropText}>Drop PDFs or images here, or <span>browse</span></p>
          <p className={styles.dropHint}>Prescription, hospital bill, lab report, pharmacy bill</p>
        </div>

        {files.length > 0 && (
          <div className={styles.fileList}>
            {files.map((f, i) => (
              <div key={i} className={styles.fileItem}>
                <div className={styles.fileIcon}>
                  {f.file.name.endsWith('.pdf') ? '📄' : '🖼'}
                </div>
                <div className={styles.fileInfo}>
                  <span className={styles.fileName}>{f.file.name}</span>
                  <span className={styles.fileSize}>
                    {(f.file.size / 1024).toFixed(1)} KB
                  </span>
                </div>
                <select
                  className={styles.typeSelect}
                  value={f.docType}
                  onChange={e => updateDocType(i, e.target.value)}
                >
                  {DOC_TYPES.map(t => (
                    <option key={t} value={t}>{t.replace('_', ' ')}</option>
                  ))}
                </select>
                <button type="button" className={styles.removeBtn}
                  onClick={() => removeFile(i)}>✕</button>
              </div>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className={styles.error}>
          <span>⚠</span> {error}
        </div>
      )}

      <button
        type="submit"
        className={styles.submit}
        disabled={loading || files.length === 0 || !form.claimed_amount}
      >
        {loading ? (
          <span className={styles.spinner} />
        ) : (
          <>Submit Claim <span className={styles.arrow}>→</span></>
        )}
      </button>
    </form>
  )
}