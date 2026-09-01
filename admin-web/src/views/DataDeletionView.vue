<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

import { get, post } from '@/api/client'
import type { DataDeletionRequest } from '@/types'

const rows = ref<DataDeletionRequest[]>([])
const loading = ref(false)
const processingId = ref<number | null>(null)
const status = ref('pending')
const page = ref(1)
const total = ref(0)
const pageSize = 20

async function load() {
  loading.value = true
  try {
    const query = status.value ? `&status=${status.value}` : ''
    const result = await get<{ items: DataDeletionRequest[]; total: number }>(
      `/data-deletion-requests?page=${page.value}&page_size=${pageSize}${query}`,
    )
    rows.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function runAction(row: DataDeletionRequest, action: 'complete' | 'reject') {
  const completing = action === 'complete'
  await ElMessageBox.confirm(
    completing
      ? '完成后会匿名化该用户符合条件的预约敏感数据，并使客户会话失效。确认继续？'
      : '拒绝申请只应用于存在未完成预约、争议或必要留存义务的情况。确认拒绝？',
    completing ? '完成删除申请' : '拒绝删除申请',
    { type: completing ? 'warning' : 'info', confirmButtonText: '确认执行' },
  )
  processingId.value = row.id
  try {
    await post(`/data-deletion-requests/${row.id}/actions`, { action })
    ElMessage.success(completing ? '删除申请已完成' : '删除申请已拒绝')
    await load()
  } finally {
    processingId.value = null
  }
}

function changeFilter() {
  page.value = 1
  load()
}

onMounted(load)
</script>

<template>
  <section class="page">
    <div class="page-heading">
      <div>
        <h1>个人数据删除</h1>
        <p>人工核对未完成预约和必要留存条件后处理客户申请。</p>
      </div>
    </div>

    <div class="filter-bar">
      <el-select v-model="status" style="width: 180px" @change="changeFilter">
        <el-option label="待处理" value="pending" />
        <el-option label="已完成" value="completed" />
        <el-option label="已拒绝" value="rejected" />
        <el-option label="全部" value="" />
      </el-select>
      <el-button @click="load">刷新</el-button>
    </div>

    <div class="content-block">
      <el-table v-loading="loading" :data="rows">
        <el-table-column prop="id" label="申请编号" width="100" />
        <el-table-column prop="user_id" label="用户编号" width="100" />
        <el-table-column label="申请时间" min-width="180">
          <template #default="scope">{{ new Date(scope.row.created_at).toLocaleString('zh-CN') }}</template>
        </el-table-column>
        <el-table-column label="未完成预约" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.active_booking_count ? 'warning' : 'success'">{{ scope.row.active_booking_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'pending' ? 'warning' : scope.row.status === 'completed' ? 'success' : 'info'">
              {{ scope.row.status === 'pending' ? '待处理' : scope.row.status === 'completed' ? '已完成' : '已拒绝' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="scope">
            <template v-if="scope.row.status === 'pending'">
              <el-button link type="primary" :loading="processingId === scope.row.id" @click="runAction(scope.row, 'complete')">完成</el-button>
              <el-button link type="danger" :disabled="processingId === scope.row.id" @click="runAction(scope.row, 'reject')">拒绝</el-button>
            </template>
            <span v-else>已处理</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" description="当前筛选下没有删除申请" />
      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="page"
        class="table-pagination"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="load"
      />
    </div>
  </section>
</template>
