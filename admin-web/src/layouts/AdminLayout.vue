<script setup lang="ts">
import {
  Calendar,
  Camera,
  Clock,
  Delete,
  Document,
  House,
  Key,
  Menu,
  Setting,
  SwitchButton,
} from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const drawer = ref(false)
const items = [
  { path: '/dashboard', label: '仪表盘', icon: House },
  { path: '/bookings', label: '预约管理', icon: Clock },
  { path: '/availability', label: '档期管理', icon: Calendar },
  { path: '/portfolios', label: '作品管理', icon: Camera },
  { path: '/options', label: '预约配置', icon: Menu },
  { path: '/settings', label: '品牌设置', icon: Setting },
  { path: '/privacy', label: '数据删除', icon: Delete },
  { path: '/audit', label: '审计日志', icon: Document },
  { path: '/security', label: '账户安全', icon: Key },
]
const current = computed(() => route.path)

async function logout(): Promise<void> {
  await auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="admin-shell">
    <aside class="sidebar desktop-only">
      <div class="brand-lockup"><span>摄影预约</span><small>管理后台</small></div>
      <el-menu :default-active="current" router>
        <el-menu-item v-for="item in items" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
      <button class="logout-button" type="button" @click="logout">
        <el-icon><SwitchButton /></el-icon>退出登录
      </button>
    </aside>
    <main class="workspace">
      <header class="mobile-header mobile-only">
        <el-button :icon="Menu" circle aria-label="打开菜单" @click="drawer = true" />
        <strong>摄影预约管理后台</strong>
      </header>
      <router-view />
    </main>
    <el-drawer v-model="drawer" direction="ltr" size="280px" title="管理菜单">
      <el-menu :default-active="current" router @select="drawer = false">
        <el-menu-item v-for="item in items" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
      <el-button class="drawer-logout" :icon="SwitchButton" @click="logout">退出登录</el-button>
    </el-drawer>
  </div>
</template>
