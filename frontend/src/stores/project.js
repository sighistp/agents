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
    },
    addMessage(msg) {
      this.messages.push({ ...msg, timestamp: Date.now() })
    },
    setAgentStatus(agent, status) {
      this.agentStatus = { ...this.agentStatus, [agent]: status }
    },
  },
})
