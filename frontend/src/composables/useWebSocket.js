import { useWsStore } from '../stores/websocket.js'
import { useAuthStore } from '../stores/auth.js'
import { useProjectStore } from '../stores/project.js'
import router from '../router.js'

let ws = null
let reconnectTimer = null
let activeProjectId = null  // 当前活跃项目 ID，忽略旧项目的消息
let reconnectDelay = 1000   // 指数退避：1s → 2s → 4s → 8s → 16s → 30s(max)
const MAX_RECONNECT_DELAY = 30000
const SEEN_MESSAGE_LIMIT = 1000
const seenMessageIds = new Set()  // 消息去重集合

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
        if (data.data.files) projectStore.files = data.data.files
        if (data.data.iteration !== undefined) projectStore.iteration = data.data.iteration
        // 初始化所有 Agent 为 waiting（后续 agent_start/agent_done 会更新）
        if (!data.data.agent_status) {
          const steps = ['pm', 'architect', 'developer', 'tester', 'reviewer']
          steps.forEach(name => projectStore.setAgentStatus(name, 'waiting'))
        } else {
          projectStore.agentStatus = data.data.agent_status
        }
      }
      break
    case 'agent_start':
      projectStore.isRunning = true
      projectStore.setAgentStatus(data.agent, 'running')
      break
    case 'agent_update':
      // 保存 Agent 结构化输出（供 AgentOutputCard 使用）
      if (data.agent && data.data) {
        projectStore.agentOutputs[data.agent] = data.data
      }
      if (data.data?.messages) {
        data.data.messages.forEach(m => {
          // 消息去重：用 content hash 作为去重 key
          const dedupeKey = m.name + ':' + (m.content || '').slice(0, 100)
          if (!seenMessageIds.has(dedupeKey)) {
            seenMessageIds.add(dedupeKey)
            if (seenMessageIds.size > SEEN_MESSAGE_LIMIT) {
              const iterator = seenMessageIds.values()
              const toRemove = seenMessageIds.size - SEEN_MESSAGE_LIMIT + 100
              for (let j = 0; j < toRemove; j++) {
                seenMessageIds.delete(iterator.next().value)
              }
            }
            projectStore.addMessage(m)
          }
        })
      }
      if (data.data?.files) projectStore.files = data.data.files
      if (data.data?.iteration !== undefined) projectStore.iteration = data.data.iteration
      break
    case 'agent_done':
      projectStore.setAgentStatus(data.agent, 'done')
      projectStore.clearToolProgress()
      break
    case 'tool_progress':
      projectStore.setToolProgress(data.data)
      break
    case 'cost_update':
      projectStore.setCostData(data.data)
      break
    case 'interrupt':
      projectStore.interrupt = data.data
      break
    case 'error':
      projectStore.isRunning = false
      projectStore.addMessage({ role: 'system', name: 'system', content: `错误: ${data.message}` })
      break
    case 'project_done':
      projectStore.isRunning = false
      if (data.data?.files) projectStore.files = data.data.files
      projectStore.addMessage({ role: 'system', name: 'system', content: '项目完成！' })
      break
    case 'paused':
      projectStore.isPaused = true
      break
    case 'resumed':
      projectStore.isPaused = false
      break
    case 'stopped':
      projectStore.isRunning = false
      projectStore.isPaused = false
      projectStore.addMessage({ role: 'system', name: 'system', content: '⏹ 任务已停止' })
      break
    case 'heartbeat':
      break
  }
}

/** 设置当前活跃项目 ID（开始新项目或清空聊天时调用） */
export function setActiveProject(projectId) {
  activeProjectId = projectId
  seenMessageIds.clear()  // 切换项目时清除去重集合
  if (projectId) localStorage.setItem('activeProjectId', projectId)
  else localStorage.removeItem('activeProjectId')
}

export function useWebSocket() {
  const wsStore = useWsStore()
  const authStore = useAuthStore()

  function isTokenExpired(token) {
    try {
      const parts = token.split('.')
      if (parts.length !== 3) return false  // 非 JWT 格式，不做过期检查
      const payload = JSON.parse(atob(parts[1]))
      return payload.exp * 1000 < Date.now()
    } catch { return false }
  }

  function connect() {
    const token = authStore.token
    if (!token) return
    // Token 过期 → 清除登录态 → 跳转登录页
    if (isTokenExpired(token)) {
      authStore.clearAuth()
      router.push('/login')
      return
    }
    if (ws && ws.readyState <= 1) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${protocol}//${location.host}/ws/project?token=${token}`)

    ws.onopen = () => {
      wsStore.setConnected(true)
      wsStore.setReconnecting(false)
      wsStore.setError(null)
      reconnectDelay = 1000
    }

    ws.onmessage = (e) => {
      try { handleMessage(JSON.parse(e.data)) } catch (err) { console.error('WS parse error:', err) }
    }

    ws.onclose = (e) => {
      wsStore.setConnected(false)
      if (e.code === 4001) {
        authStore.clearAuth()
        router.push('/login')
        return
      }
      // 连接失败（从未打开过）→ 检查 token 是否过期
      if (!wsStore.reconnecting && isTokenExpired(authStore.token)) {
        authStore.clearAuth()
        router.push('/login')
        return
      }
      wsStore.setReconnecting(true)
      // 指数退避：1s → 2s → 4s → 8s → 16s → 30s
      reconnectTimer = setTimeout(connect, reconnectDelay)
      reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY)
    }

    ws.onerror = () => { wsStore.setError('WebSocket connection error') }
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
