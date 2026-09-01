<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { ApiError, get } from '@/api/client'

interface AuditLog {
  id: number
  action: string
  entity_type: string
  entity_id?: number
  request_id: string
  metadata: Record<string, unknown>
  created_at: string
}

interface AuditListResult {
  items: AuditLog[]
  page: number
  page_size: number
  total: number
}

const rows = ref<AuditLog[]>([])
const loading = ref(false)
const errorMessage = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const detailDialog = ref(false)
const selected = ref<AuditLog | null>(null)

const actionLabels: Record<string, string> = {
  'booking.view_sensitive': '查看预约敏感详情',
  'availability.batch_upsert': '批量更新档期',
  'portfolio.create': '创建作品系列',
  'portfolio.update': '更新作品系列',
  'portfolio.publish': '发布作品系列',
  'portfolio.archive': '归档作品系列',
  'settings.update': '更新系统设置',
  'data_deletion.complete': '完成数据删除',
  'data_deletion.reject': '拒绝数据删除',
  'option_group.update': '更新预约栏目规则',
  'option_item.create': '新增预约选项',
  'option_item.update': '更新预约选项',
  'media.upload': '上传作品图片',
  'media.delete': '删除作品图片',
}

const entityLabels: Record<string, string> = {
  booking: '预约',
  availability: '档期',
  portfolio_series: '作品系列',
  option_group: '预约栏目',
  option_item: '预约选项',
  app_setting: '系统设置',
  data_deletion_request: '数据删除申请',
  media_asset: '作品图片',
}

const metadataLabels: Record<string, string> = {
  booking_no: '预约编号',
  month: '月份',
  slot_count: '档期数量',
  key: '设置项目',
  kind: '图片用途',
  file_size: '文件大小',
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function actionText(action: string): string {
  return actionLabels[action] || '管理操作'
}

function metadataText(metadata: Record<string, unknown>): string {
  const entries = Object.entries(metadata)
  if (!entries.length) return '无补充信息'
  return entries
    .map(([key, value]) => `${metadataLabels[key] || '相关信息'}：${String(value)}`)
    .join('\n')
}

function entityText(entityType: string): string {
  return entityLabels[entityType] || '系统对象'
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await get<AuditListResult>(
      `/audit-logs?page=${page.value}&page_size=${pageSize.value}`,
    )
    rows.value = result.items
    total.value = result.total
  } catch (error) {
    errorMessage.value = error instanceof ApiError ? error.message : '审计日志加载失败，请稍后重试。'
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

function openDetail(row: AuditLog): void {
  selected.value = row
  detailDialog.value = true
}

async function changePage(nextPage: number): Promise<void> {
  page.value = nextPage
  await load()
}

async function changePageSize(nextPageSize: number): Promise<void> {
  pageSize.value = nextPageSize
  page.value = 1
  await load()
}

onMounted(load)
</script>

<template>
  <section class="page">
    <div class="page-heading">
      <div>
        <h1>审计日志</h1>
        <p>记录敏感查看和关键管理操作，不包含密码、Token 或客户明文备注。</p>
      </div>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-alert
      v-if="errorMessage"
      type="error"
      :closable="false"
      :title="errorMessage"
      show-icon
      class="audit-alert"
    />

    <div class="content-block">
      <el-table v-loading="loading" :data="rows">
        <el-table-column label="时间" min-width="190">
          <template #default="scope">{{ formatDateTime(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="动作" min-width="210">
          <template #default="scope">{{ actionText(scope.row.action) }}</template>
        </el-table-column>
        <el-table-column label="对象" min-width="140">
          <template #default="scope">{{ entityText(scope.row.entity_type) }}</template>
        </el-table-column>
        <el-table-column prop="entity_id" label="对象编号" width="100" />
        <el-table-column prop="request_id" label="请求编号" min-width="280" show-overflow-tooltip />
        <el-table-column label="详情" fixed="right" width="80">
          <template #default="scope">
            <el-button link type="primary" @click="openDetail(scope.row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" description="暂无审计记录" />
      <el-pagination
        v-if="total > 0"
        class="table-pagination"
        background
        layout="total, sizes, prev, pager, next"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[20, 50]"
        :total="total"
        @current-change="changePage"
        @size-change="changePageSize"
      />
    </div>

    <el-dialog v-model="detailDialog" title="审计详情" width="min(640px, 94vw)">
      <template v-if="selected">
        <el-descriptions border :column="1">
          <el-descriptions-item label="动作">{{ actionText(selected.action) }}</el-descriptions-item>
          <el-descriptions-item label="对象">{{ entityText(selected.entity_type) }} / {{ selected.entity_id ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="请求编号">{{ selected.request_id }}</el-descriptions-item>
          <el-descriptions-item label="时间">{{ formatDateTime(selected.created_at) }}</el-descriptions-item>
        </el-descriptions>
        <h3 class="metadata-heading">相关信息</h3>
        <pre class="metadata-view">{{ metadataText(selected.metadata) }}</pre>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.audit-alert {
  margin-bottom: 20px;
}

.metadata-heading {
  margin-top: 24px;
}

.metadata-view {
  max-height: 320px;
  padding: 14px;
  overflow: auto;
  border-radius: 10px;
  background: #292724;
  color: #f8f4ee;
  font-family: Consolas, "Courier New", monospace;
  font-size: 13px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
