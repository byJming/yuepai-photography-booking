import 'element-plus/dist/index.css'
import '@/styles.css'

import ElementPlus, { ElMessage } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import { ApiError } from '@/api/client'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.config.errorHandler = (error) => {
  if (error instanceof ApiError) {
    const requestHint = error.requestId ? `（Request ID：${error.requestId}）` : ''
    ElMessage.error(`${error.message}${requestHint}`)
    return
  }
  ElMessage.error('操作失败，请稍后重试。')
}
app.use(createPinia()).use(router).use(ElementPlus, { locale: zhCn }).mount('#app')
