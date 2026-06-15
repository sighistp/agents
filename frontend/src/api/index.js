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
  getProject: (id) => request(`/projects/${id}`),
  getProjectState: (id) => request(`/projects/${id}/state`),
  deleteProject: (id) => request(`/projects/${id}`, { method: 'DELETE' }),
  getProjectFiles: (id) => request(`/projects/${id}/files`),
  downloadProject: (id) => `/api/projects/${id}/download`,
  getProjectConversations: (id) => request(`/projects/${id}/conversations`),
  getProjectExecutions: (id) => request(`/projects/${id}/executions`),
  exportProject: (id) => `/api/projects/${id}/export`,
}
