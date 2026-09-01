import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory('/admin/'),
  routes: [
    { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    {
      path: '/',
      component: () => import('@/layouts/AdminLayout.vue'),
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', component: () => import('@/views/DashboardView.vue') },
        { path: 'bookings', component: () => import('@/views/BookingsView.vue') },
        { path: 'availability', component: () => import('@/views/AvailabilityView.vue') },
        { path: 'portfolios', component: () => import('@/views/PortfoliosView.vue') },
        { path: 'options', component: () => import('@/views/OptionsView.vue') },
        { path: 'settings', component: () => import('@/views/SettingsView.vue') },
        { path: 'privacy', component: () => import('@/views/DataDeletionView.vue') },
        { path: 'audit', component: () => import('@/views/AuditView.vue') },
        { path: 'security', component: () => import('@/views/SecurityView.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.restore()
  if (!to.meta.public && !auth.admin) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.path === '/login' && auth.admin) return '/dashboard'
})

export default router
