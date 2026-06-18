import { ref } from 'vue'

export const _notifications = ref([])

let _id = 0

export function add_notification(message, type = 'info', duration = 3000) {
  const id = ++_id
  const notification = { id, message, type, visible: true }
  _notifications.value.push(notification)

  if (duration > 0) {
    setTimeout(() => remove_notification(id), duration)
  }
  return id
}

export function remove_notification(id) {
  const idx = _notifications.value.findIndex(n => n.id === id)
  if (idx !== -1) {
    _notifications.value.splice(idx, 1)
  }
}

export function useNotification() {
  return {
    notifications: _notifications,
    success: (msg, duration) => add_notification(msg, 'success', duration),
    error: (msg, duration) => add_notification(msg, 'error', duration),
    warning: (msg, duration) => add_notification(msg, 'warning', duration),
    info: (msg, duration) => add_notification(msg, 'info', duration),
    remove: remove_notification,
  }
}
