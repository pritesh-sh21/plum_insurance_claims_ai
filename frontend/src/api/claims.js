const BASE = 'http://localhost:8000/api/v1'

export async function submitClaimUpload(formData) {
  const res = await fetch(`${BASE}/claims/upload`, {
    method: 'POST',
    body: formData,
  })
  const data = await res.json()
  if (!res.ok) {
    // FastAPI 422 returns detail object
    throw { status: res.status, detail: data.detail || data }
  }
  return data
}

export async function submitClaimJSON(payload) {
  const res = await fetch(`${BASE}/claims`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json()
  if (!res.ok) {
    throw { status: res.status, detail: data.detail || data }
  }
  return data
}

export async function healthCheck() {
  const res = await fetch('http://localhost:8000/health')
  return res.json()
}
