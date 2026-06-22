const BASE = '/api'

async function request(path, options = {}) {
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || data.message || `HTTP ${res.status}`)
  }

  return res.json()
}

export const api = {
  login: (username, password) => request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  register: (username, password) => request('/auth/register', { method: 'POST', body: JSON.stringify({ username, password }) }),
  getSettings: () => request('/settings'),
  updateSettings: (data) => request('/settings', { method: 'PUT', body: JSON.stringify(data) }),
  getProjects: () => request('/projects'),
  getProject: (id) => request(`/projects/${encodeURIComponent(id)}`),
  getProjectState: (id) => request(`/projects/${encodeURIComponent(id)}/state`),
  deleteProject: (id) => request(`/projects/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  getProjectFiles: (id) => request(`/projects/${encodeURIComponent(id)}/files`),
  downloadProject: (id) => {
    const token = localStorage.getItem('token')
    const url = `${BASE}/projects/${encodeURIComponent(id)}/download${token ? '?token=' + encodeURIComponent(token) : ''}`
    window.open(url, '_blank', 'noopener,noreferrer')
  },
  getProjectConversations: (id) => request(`/projects/${id}/conversations`),
  getProjectExecutions: (id) => request(`/projects/${id}/executions`),
  exportProject: (id) => {
    const token = localStorage.getItem('token')
    const url = `${BASE}/projects/${encodeURIComponent(id)}/export${token ? '?token=' + encodeURIComponent(token) : ''}`
    window.open(url, '_blank', 'noopener,noreferrer')
  },
  getQualityScore: (id) => request(`/projects/${encodeURIComponent(id)}/quality`),
  getSecurityReport: (id) => request(`/projects/${encodeURIComponent(id)}/security`),
  getDiff: (id, a, b) => request(`/projects/${encodeURIComponent(id)}/diff?a=${a}&b=${b}`),
  getSnapshots: (id) => request(`/projects/${encodeURIComponent(id)}/snapshots`),
  getTraces: (id, agent, iteration) => {
    const params = new URLSearchParams()
    if (agent) params.set('agent', agent)
    if (iteration != null) params.set('iteration', iteration)
    return request(`/projects/${encodeURIComponent(id)}/traces?${params}`)
  },
  // Presets
  getPresets: () => request('/settings/presets'),
  savePreset: (name) => request('/settings/presets', { method: 'POST', body: JSON.stringify({ name }) }),
  applyPreset: (name) => request(`/settings/presets/${name}/apply`, { method: 'POST' }),
  deletePreset: (name) => request(`/settings/presets/${name}`, { method: 'DELETE' }),
  // Webhooks
  getWebhooks: () => request('/settings/webhooks'),
  addWebhook: (data) => request('/settings/webhooks', { method: 'POST', body: JSON.stringify(data) }),
  deleteWebhook: (index) => request(`/settings/webhooks/${index}`, { method: 'DELETE' }),
}
