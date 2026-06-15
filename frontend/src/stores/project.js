import { defineStore } from 'pinia'

export const useProjectStore = defineStore('project', {
  state: () => ({
    messages: [],
    agentStatus: {},
    currentProject: null,
    iteration: 0,
    maxIterations: 3,
    files: {},
    interrupt: null,
    agentStartTime: {},
    agentOutputs: {},  // {agentName: {files, test_results, review_comments, ...}}
    isPaused: false,
    isRunning: false,
    saveDialogVisible: false,
    autoSaveName: '',
    pendingRequirement: null,
  }),
  getters: {
    agentList: (state) => {
      const order = ['pm', 'architect', 'developer', 'tester', 'reviewer']
      return order.map(name => ({
        name,
        status: state.agentStatus[name] || 'waiting',
      }))
    },
  },
  actions: {
    reset() {
      this.messages = []
      this.agentStatus = {}
      this.currentProject = null
      this.iteration = 0
      this.files = {}
      this.interrupt = null
      this.agentOutputs = {}
      this.isPaused = false
      this.isRunning = false
      this.pendingRequirement = null
    },
    addMessage(msg) {
      // 消息去重：检查最后一条消息是否相同（防止 WebSocket 重复推送）
      const last = this.messages[this.messages.length - 1]
      if (last && last.name === msg.name && last.content === msg.content && last.role === msg.role) {
        return  // 跳过重复消息
      }
      this.messages.push({ ...msg, timestamp: Date.now() })
    },
    async saveProject(name) {
      /** 保存当前项目到后端（upsert：已存在则更新） */
      if (!this.currentProject?.id) return false
      try {
        const token = localStorage.getItem('token')
        const res = await fetch('/api/projects', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            project_id: this.currentProject.id,
            requirement: this.currentProject.requirement || '',
            name: name || undefined,
          }),
        })
        return res.ok
      } catch (e) {
        console.error('Failed to save project:', e)
        return false
      }
    },
    setAgentStatus(agent, status) {
      this.agentStatus = { ...this.agentStatus, [agent]: status }
    },
    async restoreFromServer(projectId) {
      /** Restore project state from backend after page refresh. */
      try {
        const token = localStorage.getItem('token')
        const res = await fetch(`/api/projects/${projectId}/state`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        if (!res.ok) return false
        const data = await res.json()

        this.currentProject = { id: projectId, requirement: data.requirement }
        this.iteration = data.iteration || 0
        this.files = data.files || {}
        this.messages = (data.messages || []).map(m => ({
          ...m,
          timestamp: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
        }))
        // Restore agent status from current_step
        const steps = ['pm', 'architect', 'developer', 'tester', 'reviewer']
        const currentIdx = steps.indexOf(data.current_step)
        const isTerminal = ['completed', 'delivered', 'saved', 'failed', 'error'].includes(data.status)
        steps.forEach((name, i) => {
          if (isTerminal) {
            this.agentStatus[name] = 'done'
          } else if (i < currentIdx) {
            this.agentStatus[name] = 'done'
          } else if (i === currentIdx) {
            this.agentStatus[name] = 'running'
          } else {
            this.agentStatus[name] = 'waiting'
          }
        })
        return true
      } catch (e) {
        console.error('Failed to restore project state:', e)
        return false
      }
    },
  },
})
