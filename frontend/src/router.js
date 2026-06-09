import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth.js'

const routes = [
  { path: '/login', component: () => import('./pages/LoginPage.vue') },
  { path: '/', component: () => import('./pages/WorkbenchPage.vue'), meta: { requiresAuth: true } },
  { path: '/projects', component: () => import('./pages/ProjectsPage.vue'), meta: { requiresAuth: true } },
  { path: '/projects/:id', component: () => import('./pages/ProjectDetailPage.vue'), meta: { requiresAuth: true } },
  { path: '/settings', component: () => import('./pages/SettingsPage.vue'), meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isLoggedIn) return next('/login')
  if (to.path === '/login' && authStore.isLoggedIn) return next('/')
  next()
})

export default router
