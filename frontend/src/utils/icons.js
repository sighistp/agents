// Shared icon mappings — replace emoji with Lucide icons
// Usage: import { getAgentIcon, getAgentLabel } from '../utils/icons.js'

import {
  User, Building2, Code, FlaskConical, Search,
  Pause, Play, Square, Save, Trash2, Plus,
  RefreshCw, Edit, Download, Upload, Copy, X,
  Check, AlertTriangle, Info, FileText, Folder,
  BarChart3, Lock, Eye, Terminal,
} from '@lucide/vue'

// Agent icons (structural — identify each agent)
export const agentIcons = {
  pm: User,
  architect: Building2,
  developer: Code,
  tester: FlaskConical,
  reviewer: Search,
}

// Agent labels
export const agentLabels = {
  pm: 'PM', architect: '架构师', developer: '开发者',
  tester: '测试员', reviewer: '审查员',
  system: '系统', user: '用户',
  pm_proposer: 'PM·方案', pm_critic: 'PM·审查',
  arch_proposer: '架构师·方案', arch_critic: '架构师·审查',
  developer_critic: '开发·审查',
}

// Agent CSS classes (colors)
export const agentColorClasses = {
  pm: 'color-pm', architect: 'color-architect', developer: 'color-developer',
  tester: 'color-tester', reviewer: 'color-reviewer',
  system: 'color-system', user: 'color-user',
  pm_proposer: 'color-pm', pm_critic: 'color-reviewer',
  arch_proposer: 'color-architect', arch_critic: 'color-reviewer',
  developer_critic: 'color-reviewer',
}

// Toast icons
export const toastIcons = {
  success: Check,
  error: X,
  warning: AlertTriangle,
  info: Info,
}

// Button/action icons
export const actionIcons = {
  pause: Pause,
  play: Play,
  stop: Square,
  save: Save,
  delete: Trash2,
  plus: Plus,
  refresh: RefreshCw,
  edit: Edit,
  download: Download,
  upload: Upload,
  copy: Copy,
  close: X,
  export: Download,
}

// File type icons (fallback to FileText for unknown)
export const fileTypeIcons = {
  '.py': Terminal,
  '.html': FileText,
  '.css': FileText,
  '.js': Code,
  '.ts': Code,
  '.json': FileText,
  '.sh': Terminal,
  '.bat': Terminal,
}

export function getIcon(name) {
  return agentIcons[name] || FileText
}

export function getLabel(name) {
  return agentLabels[name] || name
}

export function getColorClass(name) {
  return agentColorClasses[name] || 'color-system'
}
