import { useWsStore } from '../stores/websocket.js'
import { useAuthStore } from '../stores/auth.js'
import { useProjectStore } from '../stores/project.js'
import router from '../router.js'

let ws = null
let reconnectTimer = null
let activeProjectId = null  // 当前活跃项目 ID，忽略旧项目的消息

function handleMessage(data) {
  const projectStore = useProjectStore()
  const wsStore = useWsStore()

  // 忽略不属于当前项目的消息（用户可能已开始新项目或清空聊天）
  if (data.project_id && activeProjectId && data.project_id !== activeProjectId) {
    return
  }

  switch (data.type) {
    case 'state_sync':
      if (data.project_id) activeProjectId = data.project_id
      if (data.data) {
        if (data.data.messages) projectStore.messages = data.data.messages
        if (data.data.agent_status) projectStore.agentStatus = data.data.agent_status
        if (data.data.files) projectStore.files = data.data.files
      }
      break
    case 'agent_start':
      projectStore.setAgentStatus(data.agent, 'running')
      break
    case 'agent_thinking':
      projectStore.addMessage({ role: 'assistant', name: data.agent, content: '思考中...' })
      break
    case 'agent_update':
      if (data.data?.messages) {
        data.data.messages.forEach(m => projectStore.addMessage(m))
      }
      if (data.data?.files) projectStore.files = data.data.files
      if (data.data?.iteration !== undefined) projectStore.iteration = data.data.iteration
      break
    case 'agent_done':
      projectStore.setAgentStatus(data.agent, 'done')
      break
    case 'interrupt':
      projectStore.interrupt = data.data
      break
    case 'error':
      projectStore.addMessage({ role: 'system', name: 'system', content: `错误: ${data.message}` })
      break
    case 'project_done':
      if (data.data?.files) projectStore.files = data.data.files
      projectStore.addMessage({ role: 'system', name: 'system', content: '项目完成！' })
      break
  }
}

/** 设置当前活跃项目 ID（开始新项目或清空聊天时调用） */
export function setActiveProject(projectId) {
  activeProjectId = projectId
}

export function useWebSocket() {
  const wsStore = useWsStore()
  const authStore = useAuthStore()

  function connect() {
    const token = authStore.token
    if (!token) return
    if (ws && ws.readyState <= 1) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${protocol}//${location.host}/ws/project?token=${token}`)

    ws.onopen = () => {
      wsStore.isConnected = true
      wsStore.reconnecting = false
      wsStore.lastError = null
    }

    ws.onmessage = (e) => {
      try { handleMessage(JSON.parse(e.data)) } catch (err) { console.error('WS parse error:', err) }
    }

    ws.onclose = (e) => {
      wsStore.isConnected = false
      if (e.code === 4001) {
        authStore.clearAuth()
        router.push('/login')
        return
      }
      wsStore.reconnecting = true
      reconnectTimer = setTimeout(connect, 2000)
    }

    ws.onerror = () => { wsStore.lastError = 'WebSocket connection error' }
  }

  function send(msg) {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(msg))
  }

  function disconnect() {
    clearTimeout(reconnectTimer)
    if (ws) { ws.close(); ws = null }
  }

  return { connect, send, disconnect }
}
