<script setup lang="ts">
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const form = reactive({ username: '', password: '', totpCode: '' })
const notice = computed(() => {
  if (route.query.password_changed === '1') return '管理员密码已更新，请使用新密码重新登录。'
  if (route.query.expired === '1') return '登录会话已过期，请重新验证身份。'
  return ''
})

async function submit(): Promise<void> {
  loading.value = true
  try {
    await auth.login(form.username, form.password, form.totpCode)
    const target = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    await router.replace(target)
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '登录失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-heading">
        <small>个人摄影服务</small>
        <h1>管理后台</h1>
        <p>使用管理员密码登录；启用动态验证码后，还需填写验证器中的六位代码。</p>
      </div>
      <el-alert v-if="notice" class="login-notice" type="success" :closable="false" :title="notice" show-icon />
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :prefix-icon="User" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            :prefix-icon="Lock"
            type="password"
            autocomplete="current-password"
            show-password
          />
        </el-form-item>
        <el-form-item label="六位动态验证码（启用后填写）">
          <el-input v-model="form.totpCode" inputmode="numeric" maxlength="6" autocomplete="one-time-code" />
        </el-form-item>
        <el-button native-type="submit" type="primary" :loading="loading" class="full-button">登录</el-button>
      </el-form>
    </section>
  </main>
</template>

<style scoped>
.login-notice {
  margin-bottom: 20px;
}
</style>
