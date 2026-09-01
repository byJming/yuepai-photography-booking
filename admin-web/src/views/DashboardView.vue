<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, get } from '@/api/client'
import type { BookingSummary } from '@/types'

interface DashboardData {
  pending_count: number
  needs_info_count: number
  today_confirmed_count: number
  draft_portfolio_count: number
  upcoming: BookingSummary[]
  recent: BookingSummary[]
}

const router = useRouter()
const data = ref<DashboardData | null>(null)
const loading = ref(false)
const errorMessage = ref('')

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    data.value = await get<DashboardData>('/dashboard')
  } catch (error) {
    errorMessage.value = error instanceof ApiError ? error.message : '仪表盘加载失败，请稍后重试。'
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

async function openBookings(status = ''): Promise<void> {
  await router.push({ path: '/bookings', query: status ? { status } : {} })
}

onMounted(load)
</script>

<template>
  <section class="page">
    <div class="page-heading">
      <div>
        <h1>仪表盘</h1>
        <p>优先处理待确认预约和近期拍摄安排。</p>
      </div>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-alert
      v-if="errorMessage"
      type="error"
      :closable="false"
      :title="errorMessage"
      show-icon
      class="dashboard-alert"
    />

    <div v-loading="loading" class="metrics dashboard-metrics">
      <article class="metric-action" @click="openBookings('submitted')">
        <small>待确认预约</small><strong>{{ data?.pending_count ?? '—' }}</strong><span>查看待处理</span>
      </article>
      <article class="metric-action" @click="openBookings('needs_info')">
        <small>待补充信息</small><strong>{{ data?.needs_info_count ?? '—' }}</strong><span>查看跟进</span>
      </article>
      <article>
        <small>今日已确认拍摄</small><strong>{{ data?.today_confirmed_count ?? '—' }}</strong><span>按意向日期统计</span>
      </article>
      <article class="metric-action" @click="router.push('/portfolios')">
        <small>草稿作品</small><strong>{{ data?.draft_portfolio_count ?? '—' }}</strong><span>继续编辑</span>
      </article>
    </div>

    <section class="content-block">
      <div class="block-heading">
        <div><h2>未来七天安排</h2><p>仅展示已确认预约。</p></div>
        <el-button link type="primary" @click="openBookings('confirmed')">查看全部</el-button>
      </div>
      <el-empty v-if="!loading && !data?.upcoming.length" description="近期没有已确认拍摄" />
      <el-table v-else-if="data" :data="data.upcoming">
        <el-table-column prop="booking_no" label="预约编号" min-width="170" />
        <el-table-column prop="contact_name" label="联系人" min-width="110" />
        <el-table-column prop="requested_date" label="日期" min-width="120" />
        <el-table-column prop="shoot_type" label="类型" min-width="120" />
        <el-table-column prop="status_text" label="状态" min-width="110" />
      </el-table>
    </section>

    <section class="content-block">
      <div class="block-heading">
        <div><h2>最近预约</h2><p>按提交时间展示最近五条意向。</p></div>
        <el-button link type="primary" @click="openBookings()">预约管理</el-button>
      </div>
      <el-empty v-if="!loading && !data?.recent.length" description="暂无预约" />
      <el-table v-else-if="data" :data="data.recent">
        <el-table-column prop="booking_no" label="预约编号" min-width="170" />
        <el-table-column prop="status_text" label="状态" min-width="120" />
        <el-table-column prop="contact_name" label="联系人" min-width="110" />
        <el-table-column prop="requested_date" label="意向日期" min-width="120" />
        <el-table-column label="提交时间" min-width="140">
          <template #default="scope">{{ formatDateTime(scope.row.submitted_at) }}</template>
        </el-table-column>
      </el-table>
    </section>
  </section>
</template>

<style scoped>
.dashboard-metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metrics article span {
  margin-top: 10px;
  color: #8a8178;
  font-size: 13px;
}

.metric-action {
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease;
}

.metric-action:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 34px rgb(83 66 54 / 9%);
}

.dashboard-alert {
  margin-bottom: 20px;
}

@media (max-width: 1100px) {
  .dashboard-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .dashboard-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
