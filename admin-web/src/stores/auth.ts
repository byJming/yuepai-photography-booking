import { defineStore } from 'pinia'

import { get, post, setCsrfToken } from '@/api/client'
import type { AdminSummary } from '@/types'

export const useAuthStore = defineStore('auth', {
  state: () => ({ admin: null as AdminSummary | null, ready: false }),
  actions: {
    clear() {
      setCsrfToken('')
      this.admin = null
    },
    async restore() {
      try {
        const { csrf_token, ...admin } = await get<AdminSummary & { csrf_token: string }>('/auth/me')
        setCsrfToken(csrf_token)
        this.admin = admin
      } catch {
        this.clear()
      } finally {
        this.ready = true
      }
    },
    async login(username: string, password: string, totpCode?: string) {
      const body: { username: string; password: string; totp_code?: string } = { username, password }
      if (totpCode) body.totp_code = totpCode
      const result = await post<{ admin: AdminSummary; csrf_token: string }>('/auth/login', body)
      setCsrfToken(result.csrf_token)
      this.admin = result.admin
    },
    setTotpEnabled(enabled: boolean, csrfToken: string) {
      setCsrfToken(csrfToken)
      if (this.admin) this.admin = { ...this.admin, totp_enabled: enabled }
    },
    async logout() {
      try {
        await post('/auth/logout')
      } finally {
        this.clear()
      }
    },
  },
})
