const BASE = '/api/v1/public'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // Stats
  getStats: () => request('/stats'),

  // Blacklist
  getBlacklistTop: (limit = 20, type = null) => {
    const params = new URLSearchParams({ limit })
    if (type) params.set('type', type)
    return request(`/blacklist/top?${params}`)
  },

  // Recent queries
  getRecentQueries: (limit = 50, type = null, risk_level = null) => {
    const params = new URLSearchParams({ limit })
    if (type) params.set('type', type)
    if (risk_level) params.set('risk_level', risk_level)
    return request(`/queries/recent?${params}`)
  },

  // Check endpoints
  checkPhone: (phone) => request('/check/phone', {
    method: 'POST', body: JSON.stringify({ phone }),
  }),
  checkUrl: (url) => request('/check/url', {
    method: 'POST', body: JSON.stringify({ url }),
  }),
  checkUsername: (username) => request('/check/username', {
    method: 'POST', body: JSON.stringify({ username }),
  }),
  checkContent: (content) => request('/check/content', {
    method: 'POST', body: JSON.stringify({ content }),
  }),
}
